#!/usr/bin/env node

// ===== IMPORTS ===== //

/// ===== STDLIB ===== ///
const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const os = require('os');
const cp = require('child_process');
///-///

/// ===== 3RD-PARTY ===== ///
///-///

/// ===== LOCAL ===== ///
///-///

//-//

// ===== GLOBALS ===== //
// Global shared_state handle (set after files are installed)
let ss = null;

// Standard agents we ship and may import overrides for
const AGENT_BASELINE = [
  'code-review.md',
  'context-gathering.md',
  'context-refinement.md',
  'logging.md',
  'service-documentation.md',
];

const PADDING_TOP = 1;
const PADDING_LEFT = 2;
// Top padding inside the body pane for prompts/logs
const BODY_TOP_PAD = 0;

let _TUI_ACTIVE = false;
let _TUI = null;

const _ANSI_RE = /\x1B\[[0-?]*[ -/]*[@-~]/g;

//-//

/*
╔═════════════════════════════════════════════════════════════════════╗
║ ██████╗██╗  ██╗██████╗██████╗ █████╗ ██╗     ██╗     ██████╗█████╗  ║
║ ╚═██╔═╝███╗ ██║██╔═══╝╚═██╔═╝██╔══██╗██║     ██║     ██╔═══╝██╔═██╗ ║
║   ██║  ████╗██║██████╗  ██║  ███████║██║     ██║     █████╗ █████╔╝ ║
║   ██║  ██╔████║╚═══██║  ██║  ██╔══██║██║     ██║     ██╔══╝ ██╔═██╗ ║
║ ██████╗██║╚███║██████║  ██║  ██║  ██║███████╗███████╗██████╗██║ ██║ ║
║ ╚═════╝╚═╝ ╚══╝╚═════╝  ╚═╝  ╚═╝  ╚═╝╚══════╝╚══════╝╚═════╝╚═╝ ╚═╝ ║
╚═════════════════════════════════════════════════════════════════════╝
cc-sessions installer module for npm/npx installation.
This module is imported and executed when running `cc-sessions` command.
*/

// ===== DECLARATIONS ===== //

/// ===== ENUMS ===== ///
// Colors for terminal output
const Colors = {
  RESET: '\u001b[0m',
  RED: '\u001b[31m',
  GREEN: '\u001b[32m',
  YELLOW: '\u001b[33m',
  CYAN: '\u001b[36m',
  GRAY: '\u001b[38;5;240m',
  BOLD: '\u001b[1m',
};
///-///

//-//

// ===== CLASSES ===== //
class _TuiWriter {
  constructor(manager) {
    this.mgr = manager;
    this._buf = '';
  }
  write(s) {
    if (!s) return 0;
    this._buf += String(s);
    while (this._buf.includes('\n')) {
      const idx = this._buf.indexOf('\n');
      const line = this._buf.slice(0, idx);
      this._buf = this._buf.slice(idx + 1);
      this.mgr.logLine(line);
    }
    return s.length || 0;
  }
  flush() {
    if (this._buf) {
      this.mgr.logLine(this._buf);
      this._buf = '';
    }
  }
}

// Minimal ANSI-based TUI (header/body/footer) without external libraries.
class TuiManager {
  constructor() {
    this.headerLines = [];
    this.legend = '';
    this.log = [];
    this.inPrompt = false;
    this.infoLines = [];
    this._bindResize();
    this.redrawAll();
  }

  _bindResize() {
    if (process.stdout.isTTY) {
      process.stdout.on('resize', () => {
        this.redrawAll();
      });
    }
  }

  _termSize() {
    const h = process.stdout.rows || 24;
    const w = process.stdout.columns || 80;
    return { h, w };
  }

  _clear() {
    // Clear screen and move cursor to 1;1
    process.stdout.write('\u001b[2J\u001b[H');
  }

  setHeader(lines) {
    this.headerLines = (lines || []).map((x) => String(x));
    this.redrawHeader();
  }

  setLegend(txt) {
    this.legend = txt || '';
    this.redrawFooter();
  }

  setInfo(lines) {
    this.infoLines = (lines || []).map((x) => String(x));
    if (!this.inPrompt) this.redrawBody('log');
  }

  clearInfo() { this.setInfo([]); }

  logLine(line) {
    if (this.inPrompt) {
      this.log.push(line);
      return;
    }
    this.log.push(line);
    this.redrawBody('log');
  }

  redrawHeader() {
    const { h, w } = this._termSize();
    const maxLines = Math.max(0, Math.min(h - 2, this.headerLines.length));
    // Redraw full screen to avoid artifacts
    this._clear();
    for (let i = 0; i < maxLines; i++) {
      const y = 1 + i + PADDING_TOP;
      const text = this.headerLines[i] || '';
      process.stdout.write(`\u001b[${y};${PADDING_LEFT + 1}H`);
      process.stdout.write(text.slice(0, Math.max(0, w - PADDING_LEFT - 1)));
    }
  }

  redrawFooter() {
    const { h, w } = this._termSize();
    const y = h; // bottom line
    process.stdout.write(`\u001b[${y};1H`);
    process.stdout.write(' '.repeat(w));
    process.stdout.write(`\u001b[${y};${PADDING_LEFT + 1}H`);
    process.stdout.write(String(this.legend || '').slice(0, Math.max(0, w - PADDING_LEFT - 1)));
  }

  redrawBody(mode = 'log', listState = null) {
    const { h, w } = this._termSize();
    // Compute header height heuristic (headerLines + padding), footer=1
    const headerH = Math.min(Math.max(3, this.headerLines.length + PADDING_TOP), Math.max(3, h - 1 - 6));
    const bodyTop = headerH + 1; // 1-based
    const bodyH = Math.max(1, h - headerH - 1);

    // Clear body area
    for (let i = 0; i < bodyH; i++) {
      const y = bodyTop + i;
      process.stdout.write(`\u001b[${y};1H`);
      process.stdout.write(' '.repeat(w));
    }

    if (mode === 'log') {
      // Show info lines first, then logs
      let y = bodyTop + BODY_TOP_PAD;
      for (const il of this.infoLines) {
        process.stdout.write(`\u001b[${y};${PADDING_LEFT + 1}H`);
        process.stdout.write(String(il).slice(0, Math.max(0, w - PADDING_LEFT - 1)));
        y += 1;
        if (y >= bodyTop + bodyH) break;
      }
      const usable = Math.max(0, bodyTop + bodyH - y);
      const start = Math.max(0, this.log.length - usable);
      const visible = this.log.slice(start, start + usable);
      for (let i = 0; i < visible.length; i++) {
        const line = visible[i];
        const yy = y + i;
        process.stdout.write(`\u001b[${yy};${PADDING_LEFT + 1}H`);
        process.stdout.write(String(line).slice(0, Math.max(0, w - PADDING_LEFT - 1)));
      }
      this.redrawFooter();
      return;
    }

    if (mode === 'list' && listState) {
      const [title, options, idx, scroll] = listState;
      let y = bodyTop + BODY_TOP_PAD;
      for (const il of this.infoLines) {
        process.stdout.write(`\u001b[${y};${PADDING_LEFT + 1}H`);
        process.stdout.write(String(il).slice(0, Math.max(0, w - PADDING_LEFT - 1)));
        y += 1;
        if (y >= bodyTop + bodyH) break;
      }
      if (y < bodyTop + bodyH) {
        process.stdout.write(`\u001b[${y};${PADDING_LEFT + 1}H`);
        process.stdout.write(String(title).slice(0, Math.max(0, w - PADDING_LEFT - 1)));
        y += 1;
      }
      const maxVisible = Math.max(1, bodyTop + bodyH - (y + 1));
      let start = scroll;
      if (idx < start) start = idx; else if (idx >= start + maxVisible) start = idx - maxVisible + 1;
      for (let i = start; i < Math.min(options.length, start + maxVisible); i++) {
        const disp = String(options[i]);
        const prefix = (i === idx) ? '> ' : '  ';
        const text = `${prefix}${disp}`;
        process.stdout.write(`\u001b[${y + (1 + i - start)};${PADDING_LEFT + 1}H`);
        process.stdout.write(text.slice(0, Math.max(0, w - PADDING_LEFT - 1)));
      }
      this.redrawFooter();
      return;
    }

    if (mode === 'checkbox' && listState) {
      const [title, options, checkedSet, idx, scroll] = listState;
      let y = bodyTop + BODY_TOP_PAD;
      for (const il of this.infoLines) {
        process.stdout.write(`\u001b[${y};${PADDING_LEFT + 1}H`);
        process.stdout.write(String(il).slice(0, Math.max(0, w - PADDING_LEFT - 1)));
        y += 1;
        if (y >= bodyTop + bodyH) break;
      }
      if (y < bodyTop + bodyH) {
        process.stdout.write(`\u001b[${y};${PADDING_LEFT + 1}H`);
        process.stdout.write(String(title).slice(0, Math.max(0, w - PADDING_LEFT - 1)));
        y += 1;
      }
      const maxVisible = Math.max(1, bodyTop + bodyH - (y + 1));
      let start = scroll;
      if (idx < start) start = idx; else if (idx >= start + maxVisible) start = idx - maxVisible + 1;
      for (let i = start; i < Math.min(options.length, start + maxVisible); i++) {
        const disp = String(options[i]);
        const mark = checkedSet.has(options[i]) ? '[x]' : '[ ]';
        const prefix = (i === idx) ? '> ' : '  ';
        const text = `${prefix} ${mark} ${disp}`;
        process.stdout.write(`\u001b[${y + (1 + i - start)};${PADDING_LEFT + 1}H`);
        process.stdout.write(text.slice(0, Math.max(0, w - PADDING_LEFT - 1)));
      }
      this.redrawFooter();
    }
  }

  redrawAll() {
    this.redrawHeader();
    this.redrawBody('log');
    this.redrawFooter();
  }

  async listPrompt(message, choices, def = null) {
    this.inPrompt = true;
    this.setLegend('j/k or arrows • Enter select • Ctrl+C exit');
    let idx = 0;
    const opts = Array.pipfrom(choices || []);
    if (def != null) {
      const defIndex = opts.indexOf(def);
      if (defIndex >= 0) idx = defIndex;
    }
    let scroll = 0;
    const title = (typeof message === 'string') ? message : String(message);

    const readKey = () => new Promise((resolve) => {
      const onData = (b) => { resolve(b); };
      process.stdin.once('data', onData);
    });

    const rawModeWas = process.stdin.isRaw;
    if (process.stdin.isTTY) process.stdin.setRawMode(true);
    process.stdin.resume();
    try {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        this.redrawBody('list', [title, opts, idx, scroll]);
        const b = await readKey();
        const s = b.toString('utf8');
        const code = b[0];
        if (code === 3) { // Ctrl+C
          this.inPrompt = false; this.setLegend(''); this.redrawBody('log');
          throw new Error('KeyboardInterrupt');
        }
        if (s === '\u001b[A' || s === 'k') { // up
          idx = (idx - 1 + opts.length) % opts.length;
        } else if (s === '\u001b[B' || s === 'j') { // down
          idx = (idx + 1) % opts.length;
        } else if (s === '\r' || s === '\n') { // enter
          this.inPrompt = false; this.setLegend(''); this.redrawBody('log');
          return opts[idx];
        } else if (code === 27 && b.length === 1) { // single ESC only
          this.inPrompt = false; this.setLegend(''); this.redrawBody('log');
          throw new Error('KeyboardInterrupt');
        }
      }
    } finally {
      if (process.stdin.isTTY) process.stdin.setRawMode(!!rawModeWas);
    }
  }

  async checkboxPrompt(message, choices, def = null) {
    this.inPrompt = true;
    this.setLegend('j/k or arrows • Space toggle • Enter submit • Ctrl+C exit');
    const opts = Array.from(choices || []);
    const checkedSet = new Set(def || []);
    let idx = 0;
    let scroll = 0;
    const title = (typeof message === 'string') ? message : String(message);

    const readKey = () => new Promise((resolve) => {
      const onData = (b) => { resolve(b); };
      process.stdin.once('data', onData);
    });

    const rawModeWas = process.stdin.isRaw;
    if (process.stdin.isTTY) process.stdin.setRawMode(true);
    process.stdin.resume();
    try {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        this.redrawBody('checkbox', [title, opts, checkedSet, idx, scroll]);
        const b = await readKey();
        const s = b.toString('utf8');
        const code = b[0];
        if (code === 3) { // Ctrl+C
          this.inPrompt = false; this.setLegend(''); this.redrawBody('log');
          throw new Error('KeyboardInterrupt');
        }
        if (s === '\u001b[A' || s === 'k') { // up
          idx = (idx - 1 + opts.length) % opts.length;
        } else if (s === '\u001b[B' || s === 'j') { // down
          idx = (idx + 1) % opts.length;
        } else if (s === ' ') { // toggle
          const cur = opts[idx];
          if (checkedSet.has(cur)) checkedSet.delete(cur); else checkedSet.add(cur);
        } else if (s === '\r' || s === '\n') { // enter
          this.inPrompt = false; this.setLegend(''); this.redrawBody('log');
          return opts.filter((o) => checkedSet.has(o));
        } else if (code === 27 && b.length === 1) { // single ESC only
          this.inPrompt = false; this.setLegend(''); this.redrawBody('log');
          throw new Error('KeyboardInterrupt');
        }
      }
    } finally {
      if (process.stdin.isTTY) process.stdin.setRawMode(!!rawModeWas);
    }
  }

  async textInput(prompt) {
    this.inPrompt = true;
    this.setLegend('Type • Enter submit • Ctrl+C cancel');
    let buf = '';
    const title = (typeof prompt === 'string') ? prompt : String(prompt);
    const readKey = () => new Promise((resolve) => {
      const onData = (b) => { resolve(b); };
      process.stdin.once('data', onData);
    });

    const rawModeWas = process.stdin.isRaw;
    if (process.stdin.isTTY) process.stdin.setRawMode(true);
    process.stdin.resume();
    try {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        // Clear body and render info lines, then prompt title and input line
        const { h, w } = this._termSize();
        const headerH = Math.min(Math.max(3, this.headerLines.length + PADDING_TOP), Math.max(3, h - 1 - 6));
        const bodyTop = headerH + 1;
        const bodyH = Math.max(1, h - headerH - 1);

        // Clear body area
        for (let i = 0; i < bodyH; i++) {
          const cy = bodyTop + i;
          process.stdout.write(`\u001b[${cy};1H`);
          process.stdout.write(' '.repeat(w));
        }

        // Start at top of body with optional top padding
        let y = bodyTop + BODY_TOP_PAD;

        // Render info lines first
        for (const il of this.infoLines) {
          if (y >= bodyTop + bodyH) break;
          process.stdout.write(`\u001b[${y};${PADDING_LEFT + 1}H`);
          process.stdout.write(String(il).slice(0, Math.max(0, w - PADDING_LEFT - 1)));
          y += 1;
        }

        // Render prompt title
        if (y < bodyTop + bodyH) {
          process.stdout.write(`\u001b[${y};${PADDING_LEFT + 1}H`);
          process.stdout.write(String(title).slice(0, Math.max(0, w - PADDING_LEFT - 1)));
          y += 1;
        }

        // Render input buffer
        if (y < bodyTop + bodyH) {
          process.stdout.write(`\u001b[${y};${PADDING_LEFT + 1}H`);
          process.stdout.write(String(buf + '_').slice(0, Math.max(0, w - PADDING_LEFT - 1)));
        }

        const b = await readKey();
        const s = b.toString('utf8');
        const code = b[0];
        if (code === 3) { // Ctrl+C
          this.inPrompt = false; this.setLegend(''); this.redrawBody('log');
          throw new Error('KeyboardInterrupt');
        }
        if (s === '\r' || s === '\n') {
          this.inPrompt = false; this.setLegend(''); this.redrawBody('log');
          return buf;
        }
        if (code === 27 && b.length === 1) { // single ESC only
          this.inPrompt = false; this.setLegend(''); this.redrawBody('log');
          throw new Error('KeyboardInterrupt');
        }
        if (code === 127 || code === 8) { // backspace
          buf = buf.slice(0, -1);
        } else if (code >= 32 && code < 127) {
          buf += s;
        }
      }
    } finally {
      if (process.stdin.isTTY) process.stdin.setRawMode(!!rawModeWas);
    }
  }
}

class _TuiSession {
  constructor() {
    this._origLog = console.log;
    this._origError = console.error;
  }
  async enter() {
    if (!process.stdin.isTTY) { _TUI_ACTIVE = false; return this; }
    _TUI_ACTIVE = true;
    _TUI = new TuiManager();
    const writer = new _TuiWriter(_TUI);
    console.log = (...args) => { writer.write(args.map(String).join(' ') + '\n'); };
    console.error = (...args) => { writer.write(args.map(String).join(' ') + '\n'); };
    // Hide terminal cursor during TUI
    try { if (process.stdout.isTTY) process.stdout.write('\x1b[?25l'); } catch {}
    return this;
  }
  async exit() {
    console.log = this._origLog;
    console.error = this._origError;
    // Restore terminal cursor on exit
    try { if (process.stdout.isTTY) process.stdout.write('\x1b[?25h'); } catch {}
    _TUI_ACTIVE = false;
    _TUI = null;
  }
}

//-//

// ===== FUNCTIONS ===== //

/// ===== UTILITIES ===== ///

function _strip_ansi(s) {
  try { return String(s).replace(_ANSI_RE, ''); }
  catch { try { return String(s); } catch { return ''; } }
}

function tui_session() { return new _TuiSession(); }

// Inquirer-like helpers with j/k navigation bridged to our TUI
const inquirer = {
  async list_input({ message, choices, default: def } = {}) {
    if (_TUI_ACTIVE && _TUI) return _TUI.listPrompt(message, choices, def);
    return await _basicListPrompt(message, choices, def);
  },
  async checkbox({ message, choices, default: def } = {}) {
    if (_TUI_ACTIVE && _TUI) return _TUI.checkboxPrompt(message, choices, def);
    return await _basicCheckboxPrompt(message, choices, def);
  },
};

async function _basicListPrompt(message, choices, def) {
  // Fallback using stdin raw mode similar to TUI, but without header footer
  const mgr = _TUI || new TuiManager();
  return await mgr.listPrompt(message, choices, def);
}

async function _basicCheckboxPrompt(message, choices, def) {
  const mgr = _TUI || new TuiManager();
  return await mgr.checkboxPrompt(message, choices, def);
}


function copy_file(src, dest) {
  if (fs.existsSync(src)) {
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(src, dest);
    try {
      const mode = fs.statSync(src).mode;
      fs.chmodSync(dest, mode);
    } catch { /* ignore */ }
  }
}

function copy_directory(src, dest) {
  if (!fs.existsSync(src)) return;
  fs.mkdirSync(dest, { recursive: true });
  for (const name of fs.readdirSync(src)) {
    const sp = path.join(src, name);
    const dp = path.join(dest, name);
    if (fs.statSync(sp).isDirectory()) copy_directory(sp, dp);
    else copy_file(sp, dp);
  }
}

function color(text, colorCode) { return `${colorCode}${text}${Colors.RESET}`; }

function fmt_msg(text) {
  if (typeof text !== 'string') return text;
  let s = text.replace(/\s+$/, '');
  while (s.endsWith('::')) s = s.slice(0, -1);
  return color(s, Colors.CYAN);
}

function choices_filtered(choices) { return (choices || []).filter(Boolean); }

function capture_header(printer_fn) {
  let buf = '';
  const orig = console.log;
  try {
    console.log = (...args) => { buf += args.join(' ') + '\n'; };
    printer_fn();
  } finally {
    console.log = orig;
  }
  // Preserve empty lines so header padding matches Python version
  const lines = buf.split(/\r?\n/);
  // Keep trailing empty if present; TUI sizing accounts for it
  return lines;
}

function show_header(printer_fn) {
  if (_TUI_ACTIVE && _TUI) {
    try { _TUI.setHeader(capture_header(printer_fn)); }
    catch { printer_fn(); }
  } else {
    printer_fn();
  }
}

function set_info(lines) {
  if (_TUI_ACTIVE && _TUI) _TUI.setInfo(lines);
  else (lines || []).forEach((ln) => console.log(ln));
}

function clear_info() { if (_TUI_ACTIVE && _TUI) _TUI.clearInfo(); }

function get_package_root() { return __dirname; }
function get_project_root() { return process.cwd(); }

///-///

/// ===== ASCII BANNERS ===== ///

// For brevity, we port the headers shown during configuration.
function print_installer_header() {
  console.log()
  console.log(color('╔════════════════════════════════════════════════════════════╗', Colors.GREEN))
  console.log(color('║ ██████╗██████╗██████╗██████╗██████╗ █████╗ ██╗  ██╗██████╗ ║', Colors.GREEN))
  console.log(color('║ ██╔═══╝██╔═══╝██╔═══╝██╔═══╝╚═██╔═╝██╔══██╗███╗ ██║██╔═══╝ ║',Colors.GREEN))
  console.log(color('║ ██████╗█████╗ ██████╗██████╗  ██║  ██║  ██║████╗██║██████╗ ║',Colors.GREEN))
  console.log(color('║ ╚═══██║██╔══╝ ╚═══██║╚═══██║  ██║  ██║  ██║██╔████║╚═══██║ ║',Colors.GREEN))
  console.log(color('║ ██████║██████╗██████║██████║██████╗╚█████╔╝██║╚███║██████║ ║',Colors.GREEN))
  console.log(color('║ ╚═════╝╚═════╝╚═════╝╚═════╝╚═════╝ ╚════╝ ╚═╝ ╚══╝╚═════╝ ║',Colors.GREEN)) 
  console.log(color('╚════════╗  an opinionated approach to productive  ╔═════════╝',Colors.GREEN))
  console.log(color('         ╚═══   development with Claude Code   ════╝',Colors.GREEN))
  console.log()
  console.log()
}

function print_config_header() {
  console.log();
  console.log(color('╔══════════════════════════════════════════════╗', Colors.GREEN));
  console.log(color('║  █████╗ █████╗ ██╗  ██╗██████╗██████╗ █████╗ ║', Colors.GREEN));
  console.log(color('║ ██╔═══╝██╔══██╗███╗ ██║██╔═══╝╚═██╔═╝██╔═══╝ ║', Colors.GREEN));
  console.log(color('║ ██║    ██║  ██║████╗██║█████╗   ██║  ██║     ║', Colors.GREEN));
  console.log(color('║ ██║    ██║  ██║██╔████║██╔══╝   ██║  ██║ ██╗ ║', Colors.GREEN));
  console.log(color('║ ╚█████╗╚█████╔╝██║╚███║██║    ██████╗╚█████║ ║', Colors.GREEN));
  console.log(color('║  ╚════╝ ╚════╝ ╚═╝ ╚══╝╚═╝    ╚═════╝ ╚════╝ ║', Colors.GREEN));
  console.log(color('╚════════════ quick config editor ═════════════╝', Colors.GREEN));
  console.log();
  console.log();
}

function print_git_section() {
  console.log();
  console.log(color('╔═════════════════════════════════════════════╗', Colors.GREEN));
  console.log(color('║ ██████╗ █████╗ ██╗ ██╗█████╗  █████╗██████╗ ║', Colors.GREEN));
  console.log(color('║ ██╔═══╝██╔══██╗██║ ██║██╔═██╗██╔═══╝██╔═══╝ ║', Colors.GREEN));
  console.log(color('║ ██████╗██║  ██║██║ ██║█████╔╝██║    █████╗  ║', Colors.GREEN));
  console.log(color('║ ╚═══██║██║  ██║██║ ██║██╔═██╗██║    ██╔══╝  ║', Colors.GREEN));
  console.log(color('║ ██████║╚█████╔╝╚████╔╝██║ ██║╚█████╗██████╗ ║', Colors.GREEN));
  console.log(color('║ ╚═════╝ ╚════╝  ╚═══╝ ╚═╝ ╚═╝ ╚════╝╚═════╝ ║', Colors.GREEN));
  console.log(color('╚═════════ configure git preferences ═════════╝', Colors.GREEN));
  console.log();
  console.log();
}

function print_env_section() {
  console.log();
  console.log(color('╔══════════════════════════════════════════════════════╗', Colors.GREEN));
  console.log(color('║ ██████╗██╗  ██╗██╗ ██╗██████╗█████╗  █████╗ ██╗  ██╗ ║', Colors.GREEN));
  console.log(color('║ ██╔═══╝███╗ ██║██║ ██║╚═██╔═╝██╔═██╗██╔══██╗███╗ ██║ ║', Colors.GREEN));
  console.log(color('║ █████╗ ████╗██║██║ ██║  ██║  █████╔╝██║  ██║████╗██║ ║', Colors.GREEN));
  console.log(color('║ ██╔══╝ ██╔████║╚████╔╝  ██║  ██╔═██╗██║  ██║██╔████║ ║', Colors.GREEN));
  console.log(color('║ ██████╗██║╚███║ ╚██╔╝ ██████╗██║ ██║╚█████╔╝██║╚███║ ║', Colors.GREEN));
  console.log(color('║ ╚═════╝╚═╝  ╚═╝  ╚═╝  ╚═════╝╚═╝  ╚═╝ ╚════╝╚═╝  ╚═╝ ║', Colors.GREEN));
  console.log(color('╚════════════ configure your environment ══════════════╝', Colors.GREEN));
  console.log();
  console.log();
}

function print_blocking_header() {
  console.log();
  console.log(color('╔══════════════════════════════════════════════════════════════╗', Colors.GREEN));
  console.log(color('║ █████╗ ██╗      █████╗  █████╗██╗  ██╗██████╗██╗  ██╗ █████╗ ║', Colors.GREEN));
  console.log(color('║ ██╔═██╗██║     ██╔══██╗██╔═══╝██║ ██╔╝╚═██╔═╝███╗ ██║██╔═══╝ ║', Colors.GREEN));
  console.log(color('║ █████╔╝██║     ██║  ██║██║    █████╔╝   ██║  ████╗██║██║     ║', Colors.GREEN));
  console.log(color('║ ██╔═██╗██║     ██║  ██║██║    ██╔═██╗   ██║  ██╔████║██║ ██╗ ║', Colors.GREEN));
  console.log(color('║ █████╔╝███████╗╚█████╔╝╚█████╗██║  ██╗██████╗██║╚███║╚█████║ ║', Colors.GREEN));
  console.log(color('║ ╚════╝ ╚══════╝ ╚════╝  ╚════╝╚═╝  ╚═╝╚═════╝╚═╝ ╚══╝ ╚════╝ ║', Colors.GREEN));
  console.log(color('╚══════════════ blocked tools and bash commands ═══════════════╝', Colors.GREEN));
  console.log();
  console.log();
}

function print_read_only_section() {
  console.log();
  console.log(color('╔═══════════════════════════════════════════════════════════════════╗', Colors.GREEN));
  console.log(color('║ █████╗ ██████╗ █████╗ █████╗       ██╗     ██████╗██╗  ██╗██████╗ ║', Colors.GREEN));
  console.log(color('║ ██╔═██╗██╔═══╝██╔══██╗██╔═██╗      ██║     ╚═██╔═╝██║ ██╔╝██╔═══╝ ║', Colors.GREEN));
  console.log(color('║ █████╔╝█████╗ ███████║██║ ██║█████╗██║       ██║  █████╔╝ █████╗  ║', Colors.GREEN));
  console.log(color('║ ██╔═██╗██╔══╝ ██╔══██║██║ ██║╚════╝██║       ██║  ██╔═██╗ ██╔══╝  ║', Colors.GREEN));
  console.log(color('║ ██║ ██║██████╗██║  ██║█████╔╝      ███████╗██████╗██║  ██╗██████╗ ║', Colors.GREEN));
  console.log(color('║ ╚═╝ ╚═╝╚═════╝╚═╝  ╚═╝╚════╝       ╚══════╝╚═════╝╚═╝  ╚═╝╚═════╝ ║', Colors.GREEN));
  console.log(color('╚═══════════════ bash commands claude can use freely ═══════════════╝', Colors.GREEN));
  console.log();
  console.log();
}

function print_write_like_section() {
  console.log();
  console.log(color("╔════════════════════════════════════════════════════════════════════════════╗",Colors.GREEN));
  console.log(color("║ ██╗    ██╗█████╗ ██████╗██████╗██████╗      ██╗     ██████╗██╗  ██╗██████╗ ║",Colors.GREEN));
  console.log(color("║ ██║    ██║██╔═██╗╚═██╔═╝╚═██╔═╝██╔═══╝      ██║     ╚═██╔═╝██║ ██╔╝██╔═══╝ ║",Colors.GREEN));
  console.log(color("║ ██║ █╗ ██║█████╔╝  ██║    ██║  █████╗ █████╗██║       ██║  █████╔╝ █████╗  ║",Colors.GREEN));
  console.log(color("║ ██║███╗██║██╔═██╗  ██║    ██║  ██╔══╝ ╚════╝██║       ██║  ██╔═██╗ ██╔══╝  ║",Colors.GREEN));
  console.log(color("║ ╚███╔███╔╝██║ ██║██████╗  ██║  ██████╗      ███████╗██████╗██║  ██╗██████╗ ║",Colors.GREEN));
  console.log(color("║  ╚══╝╚══╝ ╚═╝ ╚═╝╚═════╝  ╚═╝  ╚═════╝      ╚══════╝╚═════╝╚═╝  ╚═╝╚═════╝ ║",Colors.GREEN));
  console.log(color("╚═══════════════ commands claude can't use in discussion mode ═══════════════╝",Colors.GREEN));
  console.log();
  console.log();
}

function print_extrasafe_section() {
  console.log();
  console.log(color("╔════════════════════════════════════════════════════════════════════╗",Colors.GREEN));
  console.log(color("║ ██████╗██╗  ██╗██████╗█████╗  █████╗ ██████╗ █████╗ ██████╗██████╗ ║",Colors.GREEN));
  console.log(color("║ ██╔═══╝╚██╗██╔╝╚═██╔═╝██╔═██╗██╔══██╗██╔═══╝██╔══██╗██╔═══╝██╔═══╝ ║",Colors.GREEN));
  console.log(color("║ █████╗  ╚███╔╝   ██║  █████╔╝███████║██████╗███████║█████╗ █████╗  ║",Colors.GREEN));
  console.log(color("║ ██╔══╝  ██╔██╗   ██║  ██╔═██╗██╔══██║╚═══██║██╔══██║██╔══╝ ██╔══╝  ║",Colors.GREEN));
  console.log(color("║ ██████╗██╔╝ ██╗  ██║  ██║ ██║██║  ██║██████║██║  ██║██║    ██████╗ ║",Colors.GREEN));
  console.log(color("║ ╚═════╝╚═╝  ╚═╝  ╚═╝  ╚═╝ ╚═╝╚═╝  ╚═╝╚═════╝╚═╝  ╚═╝╚═╝    ╚═════╝ ║",Colors.GREEN));
  console.log(color("╚════════════ toggle blocking for unrecognized commands ═════════════╝",Colors.GREEN));
  console.log();
  console.log();
}

function print_triggers_header() {
  console.log();
  console.log(color('╔══════════════════════════════════════════════════════════╗',Colors.GREEN));
  console.log(color('║ ██████╗█████╗ ██████╗ █████╗ █████╗██████╗█████╗ ██████╗ ║',Colors.GREEN));
  console.log(color('║ ╚═██╔═╝██╔═██╗╚═██╔═╝██╔═══╝██╔═══╝██╔═══╝██╔═██╗██╔═══╝ ║',Colors.GREEN));
  console.log(color('║   ██║  █████╔╝  ██║  ██║    ██║    █████╗ █████╔╝██████╗ ║',Colors.GREEN));
  console.log(color('║   ██║  ██╔═██╗  ██║  ██║ ██╗██║ ██╗██╔══╝ ██╔═██╗╚═══██║ ║',Colors.GREEN));
  console.log(color('║   ██║  ██║ ██║██████╗╚█████║╚█████║██████╗██║ ██║██████║ ║',Colors.GREEN));
  console.log(color('║   ╚═╝  ╚═╝ ╚═╝╚═════╝ ╚════╝ ╚════╝╚═════╝╚═╝ ╚═╝╚═════╝ ║',Colors.GREEN));
  console.log(color('╚════════ natural language controls for Claude Code ═══════╝',Colors.GREEN));
  console.log();
  console.log();
}

function print_go_triggers_section() {
  console.log();
  console.log(color('╔══════════════════════════════════════════════════════════════════════════╗',Colors.GREEN));
  console.log(color('║ ██████╗███╗  ███╗██████╗ ██╗     ██████╗███╗  ███╗██████╗██╗  ██╗██████╗ ║',Colors.GREEN));
  console.log(color('║ ╚═██╔═╝████╗████║██╔══██╗██║     ██╔═══╝████╗████║██╔═══╝███╗ ██║╚═██╔═╝ ║',Colors.GREEN));
  console.log(color('║   ██║  ██╔███║██║██████╔╝██║     █████╗ ██╔███║██║█████╗ ████╗██║  ██║   ║',Colors.GREEN));
  console.log(color('║   ██║  ██║╚══╝██║██╔═══╝ ██║     ██╔══╝ ██║╚══╝██║██╔══╝ ██╔████║  ██║   ║',Colors.GREEN));
  console.log(color('║ ██████╗██║    ██║██║     ███████╗██████╗██║    ██║██████╗██║╚███║  ██║   ║',Colors.GREEN));
  console.log(color('║ ╚═════╝╚═╝    ╚═╝╚═╝     ╚══════╝╚═════╝╚═╝    ╚═╝╚═════╝╚═╝ ╚══╝  ╚═╝   ║',Colors.GREEN));
  console.log(color('╚════════════ activate implementation mode (claude can code) ══════════════╝',Colors.GREEN));
  console.log();
  console.log();
}

function print_no_triggers_section() {
  console.log();
  console.log(color('╔═══════════════════════════════════════════════════╗',Colors.GREEN));
  console.log(color('║ █████╗ ██████╗██████╗ █████╗██╗ ██╗██████╗██████╗ ║',Colors.GREEN));
  console.log(color('║ ██╔═██╗╚═██╔═╝██╔═══╝██╔═══╝██║ ██║██╔═══╝██╔═══╝ ║',Colors.GREEN));
  console.log(color('║ ██║ ██║  ██║  ██████╗██║    ██║ ██║██████╗██████╗ ║',Colors.GREEN));
  console.log(color('║ ██║ ██║  ██║  ╚═══██║██║    ██║ ██║╚═══██║╚═══██║ ║',Colors.GREEN));
  console.log(color('║ █████╔╝██████╗██████║╚█████╗╚████╔╝██████║██████║ ║',Colors.GREEN));
  console.log(color('║ ╚════╝ ╚═════╝╚═════╝ ╚════╝ ╚═══╝ ╚═════╝╚═════╝ ║',Colors.GREEN));
  console.log(color('╚════════════ activate discussion mode ════════════╝',Colors.GREEN));
  console.log();
  console.log();
}

function print_create_section() {
  console.log();
  console.log(color('╔═════════════════════════════════════════════╗',Colors.GREEN));
  console.log(color('║  █████╗█████╗ ██████╗ █████╗ ██████╗██████╗ ║',Colors.GREEN));
  console.log(color('║ ██╔═══╝██╔═██╗██╔═══╝██╔══██╗╚═██╔═╝██╔═══╝ ║',Colors.GREEN));
  console.log(color('║ ██║    █████╔╝█████╗ ███████║  ██║  █████╗  ║',Colors.GREEN));
  console.log(color('║ ██║    ██╔═██╗██╔══╝ ██╔══██║  ██║  ██╔══╝  ║',Colors.GREEN));
  console.log(color('║ ╚█████╗██║ ██║██████╗██║  ██║  ██║  ██████╗ ║',Colors.GREEN));
  console.log(color('║  ╚════╝╚═╝ ╚═╝╚═════╝╚═╝  ╚═╝  ╚═╝  ╚═════╝ ║',Colors.GREEN));
  console.log(color('╚══════ activate task creation protocol ══════╝',Colors.GREEN));
  console.log();
  console.log();
}

function print_startup_section() {
  console.log();
  console.log(color('╔═════════════════════════════════════════════════════╗',Colors.GREEN));
  console.log(color('║ ██████╗██████╗ █████╗ █████╗ ██████╗██╗ ██╗██████╗  ║',Colors.GREEN));
  console.log(color('║ ██╔═══╝╚═██╔═╝██╔══██╗██╔═██╗╚═██╔═╝██║ ██║██╔══██╗ ║',Colors.GREEN));
  console.log(color('║ ██████╗  ██║  ███████║█████╔╝  ██║  ██║ ██║██████╔╝ ║',Colors.GREEN));
  console.log(color('║ ╚═══██║  ██║  ██╔══██║██╔═██╗  ██║  ██║ ██║██╔═══╝  ║',Colors.GREEN));
  console.log(color('║ ██████║  ██║  ██║  ██║██║ ██║  ██║  ╚████╔╝██║      ║',Colors.GREEN));
  console.log(color('║ ╚═════╝  ╚═╝  ╚═╝  ╚═╝╚═╝ ╚═╝  ╚═╝   ╚═══╝ ╚═╝      ║',Colors.GREEN));
  console.log(color('╚══════════ activate task startup protocol ═══════════╝',Colors.GREEN));
  console.log();
  console.log();
}

function print_complete_section() {
  console.log();
  console.log(color('╔════════════════════════════════════════════════════════════════╗',Colors.GREEN));
  console.log(color('║  █████╗ █████╗ ███╗  ███╗██████╗ ██╗     ██████╗██████╗██████╗ ║',Colors.GREEN));
  console.log(color('║ ██╔═══╝██╔══██╗████╗████║██╔══██╗██║     ██╔═══╝╚═██╔═╝██╔═══╝ ║',Colors.GREEN));
  console.log(color('║ ██║    ██║  ██║██╔███║██║██████╔╝██║     █████╗   ██║  █████╗  ║',Colors.GREEN));
  console.log(color('║ ██║    ██║  ██║██║╚══╝██║██╔═══╝ ██║     ██╔══╝   ██║  ██╔══╝  ║',Colors.GREEN));
  console.log(color('║ ╚█████╗╚█████╔╝██║    ██║██║     ███████╗██████╗  ██║  ██████╗ ║',Colors.GREEN));
  console.log(color('║  ╚════╝ ╚════╝ ╚═╝    ╚═╝╚═╝     ╚══════╝╚═════╝  ╚═╝  ╚═════╝ ║',Colors.GREEN));
  console.log(color('╚══════════════ activate task completion protocol ═══════════════╝',Colors.GREEN));
  console.log();
  console.log();
}

function print_compact_section() {
  console.log();
  console.log(color('╔═════════════════════════════════════════════════════════╗',Colors.GREEN));
  console.log(color('║  █████╗ █████╗ ███╗  ███╗██████╗  █████╗  █████╗██████╗ ║',Colors.GREEN));
  console.log(color('║ ██╔═══╝██╔══██╗████╗████║██╔══██╗██╔══██╗██╔═══╝╚═██╔═╝ ║',Colors.GREEN));
  console.log(color('║ ██║    ██║  ██║██╔███║██║██████╔╝███████║██║      ██║   ║',Colors.GREEN));
  console.log(color('║ ██║    ██║  ██║██║╚══╝██║██╔═══╝ ██╔══██║██║      ██║   ║',Colors.GREEN));
  console.log(color('║ ╚█████╗╚█████╔╝██║    ██║██║     ██║  ██║╚█████╗  ██║   ║',Colors.GREEN));
  console.log(color('║  ╚════╝ ╚════╝ ╚═╝    ╚═╝╚═╝     ╚═╝  ╚═╝ ╚════╝  ╚═╝   ║',Colors.GREEN));
  console.log(color('╚═════════ activate context compaction protocol ══════════╝',Colors.GREEN));
  console.log();
  console.log();
}

function print_features_header() {
  console.log();
  console.log(color('╔═══════════════════════════════════════════════════════════╗',Colors.GREEN));
  console.log(color('║ ██████╗██████╗ █████╗ ██████╗██╗ ██╗█████╗ ██████╗██████╗ ║',Colors.GREEN));
  console.log(color('║ ██╔═══╝██╔═══╝██╔══██╗╚═██╔═╝██║ ██║██╔═██╗██╔═══╝██╔═══╝ ║',Colors.GREEN));
  console.log(color('║ █████╗ █████╗ ███████║  ██║  ██║ ██║█████╔╝█████╗ ██████╗ ║',Colors.GREEN));
  console.log(color('║ ██╔══╝ ██╔══╝ ██╔══██║  ██║  ██║ ██║██╔═██╗██╔══╝ ╚═══██║ ║',Colors.GREEN));
  console.log(color('║ ██║    ██████╗██║  ██║  ██║  ╚████╔╝██║ ██║██████╗██████║ ║',Colors.GREEN));
  console.log(color('║ ╚═╝    ╚═════╝╚═╝  ╚═╝  ╚═╝   ╚═══╝ ╚═╝ ╚═╝╚═════╝╚═════╝ ║',Colors.GREEN));
  console.log(color('╚════════════ turn on/off cc-sessions features ═════════════╝',Colors.GREEN));
  console.log();
  console.log();
}

function print_statusline_header() {
  console.log();
  console.log(color('╔═══════════════════════════════════════════════════════════════════════════╗',Colors.GREEN));
  console.log(color('║ ██████╗██████╗ █████╗ ██████╗██╗ ██╗██████╗██╗     ██████╗██╗  ██╗██████╗ ║',Colors.GREEN));
  console.log(color('║ ██╔═══╝╚═██╔═╝██╔══██╗╚═██╔═╝██║ ██║██╔═══╝██║     ╚═██╔═╝███╗ ██║██╔═══╝ ║',Colors.GREEN));
  console.log(color('║ ██████╗  ██║  ███████║  ██║  ██║ ██║██████╗██║       ██║  ████╗██║█████╗  ║',Colors.GREEN));
  console.log(color('║ ╚═══██║  ██║  ██╔══██║  ██║  ██║ ██║╚═══██║██║       ██║  ██╔████║██╔══╝  ║',Colors.GREEN));
  console.log(color('║ ██████║  ██║  ██║  ██║  ██║  ╚████╔╝██████║███████╗██████╗██║╚███║██████╗ ║',Colors.GREEN));
  console.log(color('║ ╚═════╝  ╚═╝  ╚═╝  ╚═╝  ╚═╝   ╚═══╝ ╚═════╝╚══════╝╚═════╝╚═╝ ╚══╝╚═════╝ ║',Colors.GREEN));
  console.log(color('╚═════════════ cc-sessions custom statusline w/ modes + tasks ══════════════╝',Colors.GREEN));
  console.log();
  console.log();
}

function print_kickstart_header() {
  console.log();
  console.log(color('╔════════════════════════════════════════════════════════════════════╗',Colors.GREEN));
  console.log(color('║ ██╗  ██╗██████╗ █████╗██╗  ██╗██████╗██████╗ █████╗ █████╗ ██████╗ ║',Colors.GREEN));
  console.log(color('║ ██║ ██╔╝╚═██╔═╝██╔═══╝██║ ██╔╝██╔═══╝╚═██╔═╝██╔══██╗██╔═██╗╚═██╔═╝ ║',Colors.GREEN));
  console.log(color('║ █████╔╝   ██║  ██║    █████╔╝ ██████╗  ██║  ███████║█████╔╝  ██║   ║',Colors.GREEN));
  console.log(color('║ ██╔═██╗   ██║  ██║    ██╔═██╗ ╚═══██║  ██║  ██╔══██║██╔═██╗  ██║   ║',Colors.GREEN));
  console.log(color('║ ██║  ██╗██████╗╚█████╗██║  ██╗██████║  ██║  ██║  ██║██║ ██║  ██║   ║',Colors.GREEN));
  console.log(color('║ ╚═╝  ╚═╝╚═════╝ ╚════╝╚═╝  ╚═╝╚═════╝  ╚═╝  ╚═╝  ╚═╝╚═╝ ╚═╝  ╚═╝   ║',Colors.GREEN));
  console.log(color('╚════════════════════════════════════════════════════════════════════╝',Colors.GREEN));
  console.log();
  console.log();
}

///-///

/// ===== FILESYSTEM ===== ///

function _countFiles(dir, ext) {
  let count = 0;
  const walk = (d) => {
    for (const name of fs.readdirSync(d)) {
      const p = path.join(d, name);
      const st = fs.statSync(p);
      if (st.isDirectory()) walk(p);
      else if (!ext || p.endsWith(ext)) count += 1;
    }
  };
  if (fs.existsSync(dir)) walk(dir);
  return count;
}

// Previous install - create backup
function create_backup(project_root) {
  const timestamp = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 15);
  const backup_dir = path.join(project_root, '.claude', `.backup-${timestamp}`);
  console.log(color(`\n💾 Creating backup at ${path.relative(project_root, backup_dir)}/...`, Colors.CYAN));
  fs.mkdirSync(backup_dir, { recursive: true });

  const tasks_src = path.join(project_root, 'sessions', 'tasks');
  let taskCount = 0;
  if (fs.existsSync(tasks_src)) {
    const tasks_dest = path.join(backup_dir, 'tasks');
    copy_directory(tasks_src, tasks_dest);
    taskCount = _countFiles(tasks_src, '.md');
    const backed = _countFiles(tasks_dest, '.md');
    if (taskCount !== backed) {
      console.log(color(`   ✗ Backup verification failed: ${backed}/${taskCount} files backed up`, Colors.RED));
      throw new Error('Backup verification failed - aborting to prevent data loss');
    }
    console.log(color(`   ✓ Backed up ${taskCount} task files`, Colors.GREEN));
  }

  // Backup agents
  const agents_src = path.join(project_root, '.claude', 'agents');
  if (fs.existsSync(agents_src)) {
    const agents_dest = path.join(backup_dir, 'agents');
    copy_directory(agents_src, agents_dest);
    const agentCount = _countFiles(agents_src);
    const backedAgents = _countFiles(agents_dest);
    if (agentCount !== backedAgents) {
      console.log(color(`   ✗ Backup verification failed: ${backedAgents}/${agentCount} agents backed up`, Colors.RED));
      throw new Error('Backup verification failed - aborting to prevent data loss');
    }
    console.log(color(`   ✓ Backed up ${agentCount} agent files`, Colors.GREEN));
  }

  return backup_dir;
}

function create_directory_structure(project_root) {
  console.log(color('Creating directory structure...', Colors.CYAN));
  const dirs = [
    '.claude', '.claude/agents', '.claude/commands',
    'sessions', 'sessions/tasks', 'sessions/tasks/done', 'sessions/tasks/indexes',
    'sessions/hooks', 'sessions/api', 'sessions/protocols', 'sessions/knowledge',
  ];
  for (const d of dirs) fs.mkdirSync(path.join(project_root, d), { recursive: true });
}

function copy_files(script_dir, project_root) {
  console.log(color('Installing files...', Colors.CYAN));
  const agents_src = path.join(script_dir, 'agents');
  const agents_dest = path.join(project_root, '.claude', 'agents');
  if (fs.existsSync(agents_src)) copy_directory(agents_src, agents_dest);

  const knowledge_src = path.join(script_dir, 'knowledge');
  const knowledge_dest = path.join(project_root, 'sessions', 'knowledge');
  if (fs.existsSync(knowledge_src)) copy_directory(knowledge_src, knowledge_dest);

  console.log(color('Installing JavaScript-specific files...', Colors.CYAN));
  const js_root = path.join(script_dir, 'javascript');
  copy_file(path.join(js_root, 'statusline.js'), path.join(project_root, 'sessions', 'statusline.js'));
  copy_directory(path.join(js_root, 'api'), path.join(project_root, 'sessions', 'api'));
  copy_directory(path.join(js_root, 'hooks'), path.join(project_root, 'sessions', 'hooks'));
  copy_directory(path.join(script_dir, 'protocols'), path.join(project_root, 'sessions', 'protocols'));
  copy_directory(path.join(script_dir, 'commands'), path.join(project_root, '.claude', 'commands'));

  const tdir = path.join(script_dir, 'templates');
  copy_file(path.join(tdir, 'CLAUDE.sessions.md'), path.join(project_root, 'sessions', 'CLAUDE.sessions.md'));
  copy_file(path.join(tdir, 'TEMPLATE.md'), path.join(project_root, 'sessions', 'tasks', 'TEMPLATE.md'));
  copy_file(path.join(tdir, 'h-kickstart-setup.md'), path.join(project_root, 'sessions', 'tasks', 'h-kickstart-setup.md'));
  copy_file(path.join(tdir, 'INDEX_TEMPLATE.md'), path.join(project_root, 'sessions', 'tasks', 'indexes', 'INDEX_TEMPLATE.md'));
}

function configure_settings(project_root) {
  console.log(color('Configuring Claude Code hooks...', Colors.CYAN));
  const settings_path = path.join(project_root, '.claude', 'settings.json');
  let settings = {};
  if (fs.existsSync(settings_path)) {
    try { settings = JSON.parse(fs.readFileSync(settings_path, 'utf8')); }
    catch { console.log(color('⚠️  Could not parse existing settings.json, will create new one', Colors.YELLOW)); }
  }
  const is_windows = process.platform === 'win32';
  const sessions_hooks = {
    'UserPromptSubmit': [ { hooks: [ { type: 'command', command: is_windows ? 'node "%CLAUDE_PROJECT_DIR%\\sessions\\hooks\\user_messages.js"' : 'node $CLAUDE_PROJECT_DIR/sessions/hooks/user_messages.js' } ] } ],
    'PreToolUse': [
      { matcher: 'Write|Edit|MultiEdit|Task|Bash', hooks: [ { type: 'command', command: is_windows ? 'node "%CLAUDE_PROJECT_DIR%\\sessions\\hooks\\sessions_enforce.js"' : 'node $CLAUDE_PROJECT_DIR/sessions/hooks/sessions_enforce.js' } ] },
      { matcher: 'Task', hooks: [ { type: 'command', command: is_windows ? 'node "%CLAUDE_PROJECT_DIR%\\sessions\\hooks\\subagent_hooks.js"' : 'node $CLAUDE_PROJECT_DIR/sessions/hooks/subagent_hooks.js' } ] },
    ],
    'PostToolUse': [ { hooks: [ { type: 'command', command: is_windows ? 'node "%CLAUDE_PROJECT_DIR%\\sessions\\hooks\\post_tool_use.js"' : 'node $CLAUDE_PROJECT_DIR/sessions/hooks/post_tool_use.js' } ] } ],
    'SessionStart': [ { matcher: 'startup|clear', hooks: [ { type: 'command', command: is_windows ? 'node "%CLAUDE_PROJECT_DIR%\\sessions\\hooks\\session_start.js"' : 'node $CLAUDE_PROJECT_DIR/sessions/hooks/session_start.js' } ] } ],
  };
  if (!settings.hooks) settings.hooks = {};
  for (const [hookType, hookConfig] of Object.entries(sessions_hooks)) {
    if (!settings.hooks[hookType]) settings.hooks[hookType] = [];
    settings.hooks[hookType] = [...hookConfig, ...settings.hooks[hookType]];
  }
  fs.writeFileSync(settings_path, JSON.stringify(settings, null, 2));
}

function configure_claude_md(project_root) {
  console.log(color('Configuring CLAUDE.md...', Colors.CYAN));
  const claude_path = path.join(project_root, 'CLAUDE.md');
  const reference = '@sessions/CLAUDE.sessions.md';
  if (fs.existsSync(claude_path)) {
    let content = fs.readFileSync(claude_path, 'utf8');
    if (!content.includes(reference)) {
      const lines = content.split('\n');
      let insertIndex = 0;
      if (lines[0] === '---') {
        for (let i = 1; i < lines.length; i++) { if (lines[i] === '---') { insertIndex = i + 1; break; } }
      }
      lines.splice(insertIndex, 0, '', reference, '');
      content = lines.join('\n');
      fs.writeFileSync(claude_path, content, 'utf8');
    }
  } else {
    const minimal = `# CLAUDE.md\n\n${reference}\n\nThis file provides instructions for Claude Code when working with this codebase.\n`;
    fs.writeFileSync(claude_path, minimal, 'utf8');
  }
}

function configure_gitignore(project_root) {
  console.log(color('Configuring .gitignore...', Colors.CYAN));
  const gitignore_path = path.join(project_root, '.gitignore');
  const entries = ['','# cc-sessions runtime files','sessions/sessions-state.json','sessions/transcripts/',''];
  if (fs.existsSync(gitignore_path)) {
    let content = fs.readFileSync(gitignore_path, 'utf8');
    if (!content.includes('sessions/sessions-state.json')) {
      content += entries.join('\n');
      fs.writeFileSync(gitignore_path, content, 'utf8');
    }
  } else {
    fs.writeFileSync(gitignore_path, entries.join('\n'), 'utf8');
  }
}

async function setup_shared_state_and_initialize(project_root) {
  console.log(color('Initializing state and configuration...', Colors.CYAN));
  process.env.CLAUDE_PROJECT_DIR = project_root;
  // Load project shared_state (JavaScript implementation)
  const hooks_path = path.join(project_root, 'sessions', 'hooks');
  const shared_state_path = path.join(hooks_path, 'shared_state.js');
  // eslint-disable-next-line global-require, import/no-dynamic-require
  ss = require(shared_state_path);
  try { ss.loadConfig(); }
  catch (e) {
    // Attempt to sanitize legacy/bad config keys and retry
    try {
      const cfgPath = ss.CONFIG_FILE;
      if (fs.existsSync(cfgPath)) {
        const data = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
        const ba = data.blocked_actions || {};
        const allowed = new Set(['implementation_only_tools', 'bash_read_patterns', 'bash_write_patterns', 'extrasafe']);
        for (const k of Object.keys(ba)) { if (!allowed.has(k)) delete ba[k]; }
        data.blocked_actions = ba;
        fs.writeFileSync(cfgPath, JSON.stringify(data, null, 2));
      }
    } catch {}
    // Retry
    ss.loadConfig();
  }

  ss.loadState();

  // Coerce/initialize OS field
  const osName = os.platform() === 'win32' ? 'Windows' : (os.platform() === 'darwin' ? 'Darwin' : 'Linux');
  const osMap = { Windows: ss.UserOS ? ss.UserOS.WINDOWS : 'windows', Linux: ss.UserOS ? ss.UserOS.LINUX : 'linux', Darwin: ss.UserOS ? ss.UserOS.MACOS : 'macos' };
  const detected = osMap[osName] || 'linux';
  await ss.editConfig((config) => {
    const cur = (config.environment || {}).os;
    if (typeof cur === 'string') config.environment.os = cur;
    else if (cur == null) config.environment.os = detected;
  });

  const state_file = path.join(project_root, 'sessions', 'sessions-state.json');
  const config_file = path.join(project_root, 'sessions', 'sessions-config.json');
  if (!fs.existsSync(state_file) || !fs.existsSync(config_file)) {
    console.log(color('⚠️  State files were not created properly', Colors.YELLOW));
    console.log(color('You may need to initialize them manually on first run', Colors.YELLOW));
  }
}

function kickstart_cleanup(project_root) {
  console.log(color('\n🧹 Removing kickstart files...', Colors.CYAN));
  const sessions_dir = path.join(project_root, 'sessions');
  const py_hook = path.join(sessions_dir, 'hooks', 'kickstart_session_start.py');
  const js_hook = path.join(sessions_dir, 'hooks', 'kickstart_session_start.js');
  let is_python = true;
  if (fs.existsSync(py_hook)) { fs.unlinkSync(py_hook); is_python = true; console.log(color('   ✓ Deleted kickstart_session_start.py', Colors.GREEN)); }
  else if (fs.existsSync(js_hook)) { fs.unlinkSync(js_hook); is_python = false; console.log(color('   ✓ Deleted kickstart_session_start.js', Colors.GREEN)); }
  const protocols_dir = path.join(sessions_dir, 'protocols', 'kickstart');
  if (fs.existsSync(protocols_dir)) { fs.rmSync(protocols_dir, { recursive: true, force: true }); console.log(color('   ✓ Deleted protocols/kickstart/', Colors.GREEN)); }
  const task_file = path.join(sessions_dir, 'tasks', 'h-kickstart-setup.md');
  if (fs.existsSync(task_file)) { fs.unlinkSync(task_file); console.log(color('   ✓ Deleted h-kickstart-setup.md', Colors.GREEN)); }
  let instructions;
  if (is_python) {
    instructions = `\nManual cleanup required (edit these files carefully):\n\n1. sessions/api/router.py\n   - Remove: from .kickstart_commands import handle_kickstart_command\n   - Remove: 'kickstart': handle_kickstart_command from COMMAND_HANDLERS\n\n2. .claude/settings.json\n   - Remove the kickstart SessionStart hook entry\n\n3. sessions/api/kickstart_commands.py\n   - Delete this entire file\n`;
  } else {
    instructions = `\nManual cleanup required (edit these files carefully):\n\n1. sessions/api/router.js\n   - Remove: const { handleKickstartCommand } = require('./kickstart_commands');\n   - Remove: 'kickstart': handleKickstartCommand from COMMAND_HANDLERS\n\n2. .claude/settings.json\n   - Remove the kickstart SessionStart hook entry\n\n3. sessions/api/kickstart_commands.js\n   - Delete this entire file\n`;
  }
  console.log(color(instructions, Colors.YELLOW));
  return instructions;
}

function restore_tasks(project_root, backup_dir) {
  console.log(color('\n♻️  Restoring tasks...', Colors.CYAN));
  try {
    const tasks_backup = path.join(backup_dir, 'tasks');
    if (fs.existsSync(tasks_backup)) {
      const tasks_dest = path.join(project_root, 'sessions', 'tasks');
      copy_directory(tasks_backup, tasks_dest);
      const cnt = _countFiles(tasks_backup, '.md');
      console.log(color(`   ✓ Restored ${cnt} task files`, Colors.GREEN));
    }
  } catch (e) {
    console.log(color(`   ✗ Restore failed: ${String(e)}`, Colors.RED));
    console.log(color(`   Your backup is safe at: ${path.relative(project_root, backup_dir)}/`, Colors.YELLOW));
    console.log(color('   Manually copy files from backup/tasks/ to sessions/tasks/', Colors.YELLOW));
  }
}

///-///

/// ===== CONFIG QUESTIONS ===== ///

async function _ask_default_branch() {
  set_info([
    color('cc-sessions uses git branches to section off task work and', Colors.CYAN),
    color("merge back to your default work branch when the task is done.", Colors.CYAN),
    '', 'Set your default branch...', ''
  ]);
  const val = (await _input("Claude should merge task branches to (ex. 'main', 'next', 'master', etc.): ")) || 'main';
  await ss.editConfig((conf) => { conf.git_preferences.default_branch = val; });
  clear_info();
}

async function _ask_has_submodules() {
  const val = await inquirer.list_input({ message: "The repo you're installing into is a:", choices: ['Monorepo (no submodules)', 'Super-repo (has submodules)'] });
  await ss.editConfig((conf) => { conf.git_preferences.has_submodules = (val.includes('Super-repo')); });
}

async function _ask_git_add_pattern() {
  const val = await inquirer.list_input({ message: 'When choosing what changes to stage and commit from completed tasks, Claude should:', choices: ['Ask me each time', 'Stage all modified files automatically'] });
  await ss.editConfig((conf) => { conf.git_preferences.add_pattern = val.includes('Ask') ? ss.GitAddPattern.ASK : ss.GitAddPattern.ALL; });
}

async function _ask_commit_style() {
  const val = await inquirer.list_input({ message: "You want Claude's commit messages to be:", choices: ['Detailed (multi-line with description)', 'Conventional (type: subject format)', 'Simple (single line)'] });
  await ss.editConfig((conf) => {
    if (val.includes('Detailed')) conf.git_preferences.commit_style = ss.GitCommitStyle.OP;
    else if (val.includes('Conventional')) conf.git_preferences.commit_style = ss.GitCommitStyle.REG;
    else conf.git_preferences.commit_style = ss.GitCommitStyle.SIMP;
  });
}

async function _ask_auto_merge() {
  show_header(print_git_section);
  const default_branch = ss.loadConfig().git_preferences.default_branch;
  const val = await inquirer.list_input({ message: 'During task completion, after comitting changes, Claude should:', choices: [`Auto-merge to ${default_branch}`, `Ask me if I want to merge to ${default_branch}`] });
  await ss.editConfig((conf) => { conf.git_preferences.auto_merge = val.includes('Auto-merge'); });
}

async function _ask_auto_push() {
  show_header(print_git_section);
  const val = await inquirer.list_input({ message: 'After committing/merging, Claude should:', choices: ['Auto-push to remote', 'Ask me if I want to push'] });
  await ss.editConfig((conf) => { conf.git_preferences.auto_push = val.includes('Auto-push'); });
}

async function _ask_developer_name() {
  const name = (await _input('Claude should call you: ')) || 'developer';
  await ss.editConfig((conf) => { conf.environment.developer_name = name; });
}

async function _ask_os() {
  const osName = { win32: 'windows', linux: 'linux', darwin: 'macos' }[process.platform] || 'linux';
  const val = await inquirer.list_input({
    message: `Detected OS [${color(osName.charAt(0).toUpperCase() + osName.slice(1), Colors.YELLOW)}]`,
    choices: choices_filtered([
      `${osName.charAt(0).toUpperCase() + osName.slice(1)} is correct`,
      osName !== 'windows' ? 'Switch to Windows' : null,
      osName !== 'macos' ? 'Switch to macOS' : null,
      osName !== 'linux' ? 'Switch to Linux' : null,
    ]),
    default: `${osName.charAt(0).toUpperCase() + osName.slice(1)} is correct`,
  });
  await ss.editConfig((conf) => {
    if (val.includes('Windows')) conf.environment.os = ss.UserOS.WINDOWS;
    else if (val.includes('macOS')) conf.environment.os = ss.UserOS.MACOS;
    else if (val.includes('Linux')) conf.environment.os = ss.UserOS.LINUX;
    else conf.environment.os = osName;
  });
}

async function _ask_shell() {
  const detected_shell = (process.env.SHELL || 'bash').split('/').slice(-1)[0];
  const val = await inquirer.list_input({
    message: `Detected shell [${color(detected_shell, Colors.YELLOW)}]`,
    choices: choices_filtered([
      `${detected_shell} is correct`,
      detected_shell !== 'bash' ? 'Switch to bash' : null,
      detected_shell !== 'zsh' ? 'Switch to zsh' : null,
      detected_shell !== 'fish' ? 'Switch to fish' : null,
      detected_shell !== 'powershell' ? 'Switch to powershell' : null,
      detected_shell !== 'cmd' ? 'Switch to cmd' : null,
    ]),
    default: `${detected_shell} is correct`,
  });
  await ss.editConfig((conf) => {
    if (val.includes('bash')) conf.environment.shell = ss.UserShell.BASH;
    else if (val.includes('zsh')) conf.environment.shell = ss.UserShell.ZSH;
    else if (val.includes('fish')) conf.environment.shell = ss.UserShell.FISH;
    else if (val.includes('powershell')) conf.environment.shell = ss.UserShell.POWERSHELL;
    else if (val.includes('cmd')) conf.environment.shell = ss.UserShell.CMD;
    else conf.environment.shell = detected_shell;
  });
}

async function _edit_bash_read_patterns() {
  const info = [
    color('In Discussion mode, Claude can only use read-like tools (including commands in', Colors.CYAN),
    color('the Bash tool).', Colors.CYAN),
    color("To do this, we parse Claude's Bash tool input in Discussion mode to check for", Colors.CYAN),
    color('write-like and read-only bash commands from a known list.', Colors.CYAN),
    '',
    'You might have some CLI commands that you want to mark as "safe" to use in Discussion mode.',
    'For reference, here are the commands we already auto-approve in Discussion mode:',
    color('cat, ls, pwd, cd, echo, grep, find, git status, git log', Colors.YELLOW),
    color('git diff, docker ps, kubectl get, npm list, pip show, head, tail', Colors.YELLOW),
    color('less, more, file, stat, du, df, ps, top, htop, who, w', Colors.YELLOW),
    color('...(70+ commands total)', Colors.YELLOW), '',
    'Type any additional command you would like to auto-allow and press Enter.',
    'Press Enter on an empty line to finish.', ''
  ];
  set_info(info);
  const collected = [];
  while (true) {
    const cmd = (await _input('')).trim();
    if (!cmd) break;
    collected.push(cmd);
    const added = [color(`✓ Added ${collected.slice(-5).join(', ')}${collected.length > 5 ? `... (${collected.length} total)` : ''}`, Colors.GREEN), ''];
    set_info(info.concat(added));
  }
  await ss.editConfig((conf) => { conf.blocked_actions.bash_read_patterns = collected; });
  clear_info();
}

async function _edit_bash_write_patterns() {
  const info = [
    color('Similar to the read-only bash commands, we also check for write-like bash', Colors.CYAN),
    color('commands during Discussion mode and block them.', Colors.CYAN), '',
    'You might have some CLI commands that you want to mark as blocked in Discussion mode.',
    'For reference, here are the commands we already block in Discussion mode:',
    color('rm, mv, cp, chmod, chown, mkdir, rmdir, systemctl, service', Colors.YELLOW),
    color('apt, yum, npm install, pip install, make, cmake, sudo, kill', Colors.YELLOW),
    color('...(and more)', Colors.YELLOW), '',
    'Type any additional command you would like blocked and press Enter.',
    'Press Enter on an empty line to finish.', ''
  ];
  set_info(info);
  const collected = [];
  while (true) {
    const cmd = (await _input('')).trim();
    if (!cmd) break;
    collected.push(cmd);
    const added = [color(`✓ Added ${collected.slice(-5).join(', ')}${collected.length > 5 ? `... (${collected.length} total)` : ''}`, Colors.GREEN), ''];
    set_info(info.concat(added));
  }
  await ss.editConfig((conf) => { conf.blocked_actions.bash_write_patterns = collected; });
  clear_info();
}

async function _ask_extrasafe_mode() {
  const val = await inquirer.list_input({ message: 'Extrasafe mode:', choices: ['ON (block everything in discussion except explicitly allowed)', 'OFF'] });
  await ss.editConfig((conf) => { conf.blocked_actions.extrasafe = val.includes('ON'); });
}

async function _edit_blocked_tools() {
  set_info([
    'Which Claude Code tools should be blocked in discussion mode?',
    color('NOTE: Write-like Bash commands are already blocked', Colors.YELLOW), ''
  ]);
  const default_blocked = ['Edit', 'Write', 'MultiEdit', 'NotebookEdit'];
  const blocked_tools = await inquirer.checkbox({ message: 'Block these tools in Discussion Mode:', choices: ['Read','Write','Edit','MultiEdit','NotebookEdit','Grep','Glob','LS','Bash','BashOutput','KillBash','WebSearch'], default: default_blocked });
  await ss.editConfig((conf) => {
    conf.blocked_actions.implementation_only_tools = [];
    for (const t of blocked_tools) conf.blocked_actions.implementation_only_tools.push(t);
  });
  clear_info();
}

async function _customize_triggers() {
  const customize_triggers = await inquirer.list_input({ message: 'Would you like to add any of your own custom trigger phrases?', choices: ['Use defaults', 'Customize'] });
  return customize_triggers === 'Customize';
}

async function _edit_triggers_implementation() {
  const info = [
    color('The implementation mode trigger activates Implementation Mode. Once used, the', Colors.CYAN),
    color('user_messages hook will set Implementation Mode and remind Claude: You are now in', Colors.CYAN),
    color('Implementation Mode - use tools to execute agreed actions, and return to Discussion', Colors.CYAN),
    color('Mode immediately when done.', Colors.CYAN), '',
    color('We recommend your trigger phrase be:', Colors.YELLOW),
    color('╔════════════════════════════════════════════════════╗', Colors.YELLOW),
    `${color('║', Colors.YELLOW)}     • Short                                           ${color('║', Colors.YELLOW)}`,
    `${color('║', Colors.YELLOW)}     • Easy to remember and type                    ${color('║', Colors.YELLOW)}`,
    `${color('║', Colors.YELLOW)}     • Won't ever come up in regular operation      ${color('║', Colors.YELLOW)}`,
    color('╚════════════════════════════════════════════════════╝', Colors.YELLOW), '',
    color('We recommend using symbols or uppercase for trigger phrases that may otherwise', Colors.CYAN),
    color("be used naturally in conversation (ex. instead of \"stop\", you might use \"STOP\"", Colors.CYAN),
    color('or \"st0p\" or \"--stop\".', Colors.CYAN), '\n', 'Current phrase: "yert"', '',
    'Type a trigger phrase to add and press "enter". When you\'re done, press "enter"',
    'again to move on to the next step:', ''
  ];
  set_info(info);
  const phrases = [];
  while (true) {
    const phrase = (await _input('')).trim();
    if (!phrase) break;
    phrases.push(phrase);
    await ss.editConfig((conf) => { conf.trigger_phrases.implementation_mode.push(phrase); });
    const added = [color(`✓ Added ${phrases.slice(-5).join(', ')}${phrases.length > 5 ? `... (${phrases.length} total)` : ''}`, Colors.GREEN), ''];
    set_info(info.concat(added));
  }
  clear_info();
}

async function _edit_triggers_discussion() {
  const info = [
    color('The discussion mode trigger is an emergency stop that immediately switches', Colors.CYAN),
    color('Claude back to discussion mode. Once used, the user_messages hook will set the', Colors.CYAN),
    color('mode to discussion and inform Claude that they need to re-align.', Colors.CYAN), '',
    'Current phrase: "SILENCE"', 'Add discussion mode trigger phrases ("stop phrases"). Press Enter on empty line to finish.'
  ];
  set_info(info);
  const phrases = [];
  while (true) {
    const phrase = (await _input('')).trim();
    if (!phrase) break;
    phrases.push(phrase);
    await ss.editConfig((conf) => { conf.trigger_phrases.discussion_mode.push(phrase); });
    const added = [color(`✓ Added ${phrases.slice(-5).join(', ')}${phrases.length > 5 ? `... (${phrases.length} total)` : ''}`, Colors.GREEN), ''];
    set_info(info.concat(added));
  }
  clear_info();
}

async function _edit_triggers_task_creation() {
  const info = [
    color('The task creation trigger activates the task creation protocol. Once used, the', Colors.CYAN),
    color('user_messages hook will load the task creation protocol which guides Claude', Colors.CYAN),
    color('through creating a properly structured task file with priority, success', Colors.CYAN),
    color('criteria, and context manifest.', Colors.CYAN), '',
    'Current phrase: "mek:"', 'Add task creation trigger phrases. Press Enter on empty line to finish.', ''
  ];
  set_info(info);
  const phrases = [];
  while (true) {
    const phrase = (await _input('')).trim();
    if (!phrase) break;
    phrases.push(phrase);
    await ss.editConfig((conf) => { conf.trigger_phrases.task_creation.push(phrase); });
    const added = [color(`✓ Added ${phrases.slice(-5).join(', ')}${phrases.length > 5 ? `... (${phrases.length} total)` : ''}`, Colors.GREEN), ''];
    set_info(info.concat(added));
  }
  clear_info();
}

async function _edit_triggers_task_startup() {
  const info = [
    color('The task startup trigger activates the task startup protocol. Once used, the', Colors.CYAN),
    color('user_messages hook will load the task startup protocol which guides Claude', Colors.CYAN),
    color('through checking git status, creating branches, gathering context, and', Colors.CYAN),
    color('proposing implementation todos.', Colors.CYAN), '',
    'Current phrase: "start^:"', 'Add task startup trigger phrases. Press Enter on empty line to finish.'
  ];
  set_info(info);
  const phrases = [];
  while (true) {
    const phrase = (await _input('')).trim();
    if (!phrase) break;
    phrases.push(phrase);
    await ss.editConfig((conf) => { conf.trigger_phrases.task_startup.push(phrase); });
    const added = [color(`✓ Added ${phrases.slice(-5).join(', ')}${phrases.length > 5 ? `... (${phrases.length} total)` : ''}`, Colors.GREEN), ''];
    set_info(info.concat(added));
  }
}

async function _edit_triggers_task_completion() {
  const info = [
    color('The task completion trigger activates the task completion protocol. Once used,', Colors.CYAN),
    color('the user_messages hook will load the task completion protocol which guides', Colors.CYAN),
    color('Claude through running pre-completion checks, committing changes, merging to', Colors.CYAN),
    color('main, and archiving the completed task.', Colors.CYAN), '',
    'Current phrase: "finito"', 'Add task completion trigger phrases. Press Enter on empty line to finish.', ''
  ];
  set_info(info);
  const phrases = [];
  while (true) {
    const phrase = (await _input('')).trim();
    if (!phrase) break;
    phrases.push(phrase);
    await ss.editConfig((conf) => { conf.trigger_phrases.task_completion.push(phrase); });
    const added = [color(`✓ Added ${phrases.slice(-5).join(', ')}${phrases.length > 5 ? `... (${phrases.length} total)` : ''}`, Colors.GREEN), ''];
    set_info(info.concat(added));
  }
  clear_info();
}

async function _edit_triggers_compaction() {
  const info = [
    color('The context compaction trigger activates the context compaction protocol. Once', Colors.CYAN),
    color('used, the user_messages hook will load the context compaction protocol which', Colors.CYAN),
    color('guides Claude through running logging and context-refinement agents to preserve', Colors.CYAN),
    color('task state before the context window fills up.', Colors.CYAN), '',
    'Current phrase: "squish"', 'Add context compaction trigger phrases. Press Enter on empty line to finish.', ''
  ];
  set_info(info);
  const phrases = [];
  while (true) {
    const phrase = (await _input('')).trim();
    if (!phrase) break;
    phrases.push(phrase);
    await ss.editConfig((conf) => { conf.trigger_phrases.context_compaction.push(phrase); });
    const added = [color(`✓ Added ${phrases.slice(-5).join(', ')}${phrases.length > 5 ? `... (${phrases.length} total)` : ''}`, Colors.GREEN), ''];
    set_info(info.concat(added));
  }
  clear_info();
}

async function _ask_branch_enforcement() {
  set_info([
    color('When working on a task, branch enforcement blocks edits to files unless they', Colors.CYAN),
    color('are in a repo that is on the task branch. If in a submodule, the submodule', Colors.CYAN),
    color('also has to be listed in the task file under the "submodules" field.', Colors.CYAN), '',
    'This prevents Claude from doing silly things with files outside the scope of',
    "what you're working on, which can happen frighteningly often. But, it may not",
    "be as flexible as you want. *It also doesn't work well with non-Git VCS*.",
  ]);
  const val = await inquirer.list_input({ message: 'I want branch enforcement:', choices: ['Enabled (recommended for git workflows)', 'Disabled (for alternative VCS like Jujutsu)'] });
  await ss.editConfig((conf) => { conf.features.branch_enforcement = val.includes('Enabled'); });
  clear_info();
}

async function _ask_auto_ultrathink() {
  set_info([
    color('Auto-ultrathink adds "[[ ultrathink ]]" to *every message* you submit to', Colors.CYAN),
    color('Claude Code. This is the most robust way to force maximum thinking for every', Colors.CYAN),
    color('message.', Colors.CYAN), '',
    "If you are not a Claude Max x20 subscriber and/or you are budget-conscious,",
    "it's recommended that you disable auto-ultrathink and manually trigger thinking",
    'as needed.',
  ]);
  const val = await inquirer.list_input({ message: 'I want auto-ultrathink:', choices: ['Enabled', 'Disabled (recommended for budget-conscious users)'] });
  await ss.editConfig((conf) => { conf.features.auto_ultrathink = (val === 'Enabled'); });
  clear_info();
}

async function _ask_nerd_fonts() {
  const val = await inquirer.list_input({ message: 'I want Nerd Fonts icons in statusline:', choices: ['Enabled (Nerd Fonts installed)', 'Disabled (ASCII fallback)'] });
  await ss.editConfig((conf) => { conf.features.use_nerd_fonts = (val === 'Enabled'); });
}

async function _ask_context_warnings() {
  const val = await inquirer.list_input({ message: 'I want Claude to be warned to suggest compacting context at:', choices: ['85% and 90%', '90%', 'Never'] });
  await ss.editConfig((conf) => {
    if (val.includes('and')) { conf.features.context_warnings.warn_85 = true; conf.features.context_warnings.warn_90 = true; }
    else if (val.includes('90')) { conf.features.context_warnings.warn_85 = false; conf.features.context_warnings.warn_90 = true; }
    else { conf.features.context_warnings.warn_85 = false; conf.features.context_warnings.warn_90 = false; }
  });
}

async function _ask_statusline() {
  set_info([
    color('cc-sessions includes a statusline that shows context usage, mode', Colors.CYAN),
    color('current task, git branch, open tasks, and uncommitted files.', Colors.CYAN), ''
  ]);
  const val = await inquirer.list_input({ message: 'Would you like to use it?', choices: ['Yes, use cc-sessions statusline', 'No, I have my own statusline'] });
  if (val.includes('Yes')) {
    const settings_file = path.join(ss.PROJECT_ROOT, '.claude', 'settings.json');
    let settings = {};
    if (fs.existsSync(settings_file)) settings = JSON.parse(fs.readFileSync(settings_file, 'utf8'));
    settings.statusLine = { type: 'command', command: 'node $CLAUDE_PROJECT_DIR/sessions/statusline.js' };
    fs.writeFileSync(settings_file, JSON.stringify(settings, null, 2));
    set_info([color('✓ Statusline configured in .claude/settings.json', Colors.GREEN)]);
    await sleep(500);
  } else {
    set_info([
      color('You can add the cc-sessions statusline later by adding this to .claude/settings.json:', Colors.YELLOW),
      color('{', Colors.YELLOW), color('  "statusLine": {', Colors.YELLOW), color('    "type": "command",', Colors.YELLOW),
      color('    "command": "node $CLAUDE_PROJECT_DIR/sessions/statusline.js"', Colors.YELLOW), color('  }', Colors.YELLOW), color('}', Colors.YELLOW), ''
    ]);
    await _input('Press enter to continue...');
  }
  return val.includes('Yes');
}

///-///

/// ===== CONFIG PHASES ===== ///

async function run_full_configuration() {
  show_header(print_config_header);
  // Gather git preferences
  show_header(print_git_section);
  await _ask_default_branch();
  await _ask_has_submodules();
  await _ask_git_add_pattern();
  await _ask_commit_style();
  await _ask_auto_merge();
  await _ask_auto_push();
  // Env
  show_header(print_env_section);
  await _ask_developer_name();
  await _ask_os();
  await _ask_shell();
  // Blocked
  show_header(print_read_only_section);
  await _edit_bash_read_patterns();
  show_header(print_write_like_section);
  await _edit_bash_write_patterns();
  show_header(print_extrasafe_section);
  await _ask_extrasafe_mode();
  show_header(print_blocking_header);
  await _edit_blocked_tools();
  // Triggers
  show_header(print_triggers_header);
  const wants = await _customize_triggers();
  if (wants) {
    show_header(print_go_triggers_section); await _edit_triggers_implementation();
    show_header(print_no_triggers_section); await _edit_triggers_discussion();
    show_header(print_create_section); await _edit_triggers_task_creation();
    show_header(print_startup_section); await _edit_triggers_task_startup();
    show_header(print_complete_section); await _edit_triggers_task_completion();
    show_header(print_compact_section); await _edit_triggers_compaction();
  }
  // Statusline
  show_header(print_statusline_header);
  const statusline_installed = await _ask_statusline();
  // Feature toggles
  show_header(print_features_header);
  await _ask_branch_enforcement();
  await _ask_auto_ultrathink();
  if (statusline_installed) await _ask_nerd_fonts();
  await _ask_context_warnings();
  console.log(color('\n✓ Configuration complete!\n', Colors.GREEN));
}

async function run_config_editor(project_root) {
  show_header(print_config_header);
  set_info([
    color('How to use:', Colors.CYAN),
    color('- Use j/k or arrows to navigate, Enter to select', Colors.CYAN),
    color('- Choose Back to return, Done to finish', Colors.CYAN),
    color('- You can also press Ctrl+C to exit anytime', Colors.CYAN), ''
  ]);

  const settings_path = path.join(project_root, '.claude', 'settings.json');
  const _statusline_installed = () => {
    try {
      const data = fs.existsSync(settings_path) ? JSON.parse(fs.readFileSync(settings_path, 'utf8')) : {};
      const cmd = (data.statusLine || {}).command;
      return !!(cmd && cmd.includes('sessions/statusline.js'));
    } catch { return false; }
  };

  const _fmt_bool = (v) => (v ? 'Enabled' : 'Disabled');
  const _fmt_enum = (v) => (v && typeof v === 'object' && 'value' in v ? v.value : String(v));
  const _fmt_list = (xs) => { try { return xs && xs.length ? xs.filter(Boolean).join(', ') : 'None'; } catch { return 'None'; } };
  const _fmt_tools = (xs) => { try { return xs && xs.length ? xs.map((x) => (x && x.value) || String(x)).join(', ') : 'None'; } catch { return 'None'; } };
  const _reload = () => { const cfg = ss.loadConfig(); return [cfg, _statusline_installed()]; };

  async function _git_menu() {
    show_header(print_git_section);
    let [cfg] = _reload();
    let g = cfg.git_preferences;
    let actions = [
      [`${color('Default branch', Colors.RESET)} | ${color(g.default_branch, Colors.YELLOW)}`, _ask_default_branch],
      [`${color('Has submodules', Colors.RESET)} | ${color(String(g.has_submodules), Colors.YELLOW)}`, _ask_has_submodules],
      [`${color('Staging pattern', Colors.RESET)} | ${color(String(g.add_pattern), Colors.YELLOW)}`, _ask_git_add_pattern],
      [`${color('Commit style', Colors.RESET)} | ${color(String(g.commit_style), Colors.YELLOW)}`, _ask_commit_style],
      [`${color('Auto-merge', Colors.RESET)} | ${color(String(g.auto_merge), Colors.YELLOW)}`, _ask_auto_merge],
      [`${color('Auto-push', Colors.RESET)} | ${color(String(g.auto_push), Colors.YELLOW)}`, _ask_auto_push],
      [color('Back', Colors.YELLOW), null],
    ];
    let labels = actions.map(([lbl]) => lbl);
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const choice = await inquirer.list_input({ message: `${color('[Setting]', Colors.RESET)} | ${color('[Current Value]', Colors.YELLOW)}\n`, choices: labels });
      if (choice.includes('Back')) break;
      const fn = new Map(actions).get(choice);
      if (fn) await fn();
      [cfg] = _reload(); g = cfg.git_preferences;
      actions[0] = [`${color('Default branch', Colors.RESET)} | ${color(String(g.default_branch), Colors.YELLOW)}`, _ask_default_branch];
      actions[1] = [`${color('Has submodules', Colors.RESET)} | ${color(String(g.has_submodules), Colors.YELLOW)}`, _ask_has_submodules];
      actions[2] = [`${color('Staging pattern', Colors.RESET)} | ${color(String(g.add_pattern), Colors.YELLOW)}`, _ask_git_add_pattern];
      actions[3] = [`${color('Commit style', Colors.RESET)} | ${color(String(g.commit_style), Colors.YELLOW)}`, _ask_commit_style];
      actions[4] = [`${color('Auto-merge', Colors.RESET)} | ${color(String(g.auto_merge), Colors.YELLOW)}`, _ask_auto_merge];
      actions[5] = [`${color('Auto-push', Colors.RESET)} | ${color(String(g.auto_push), Colors.YELLOW)}`, _ask_auto_push];
      labels = actions.map(([lbl]) => lbl);
    }
  }

  async function _env_menu() {
    show_header(print_env_section);
    let [cfg] = _reload();
    let e = cfg.environment;
    let actions = [
      [`Developer name | ${color(String(e.developer_name), Colors.YELLOW)}`, _ask_developer_name],
      [`Operating system | ${color(String(e.os), Colors.YELLOW)}`, _ask_os],
      [`Shell | ${color(String(e.shell), Colors.YELLOW)}`, _ask_shell],
      [color('Back', Colors.YELLOW), null],
    ];
    let labels = actions.map(([lbl]) => lbl);
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const choice = await inquirer.list_input({ message: `${color('[Setting]', Colors.RESET)} | ${color('[Current Value]', Colors.YELLOW)}\n`, choices: labels });
      if (choice.includes('Back')) break;
      const fn = new Map(actions).get(choice);
      if (fn) await fn();
      [cfg] = _reload(); e = cfg.environment;
      actions[0] = [`Developer name | ${color(String(e.developer_name), Colors.YELLOW)}`, _ask_developer_name];
      actions[1] = [`Operating system | ${color(String(e.os), Colors.YELLOW)}`, _ask_os];
      actions[2] = [`Shell | ${color(String(e.shell), Colors.YELLOW)}`, _ask_shell];
      labels = actions.map(([lbl]) => lbl);
    }
  }

  async function _blocked_menu() {
    show_header(print_blocking_header);
    let [cfg] = _reload();
    let b = cfg.blocked_actions;
    let actions = [
      [`Tools list | ${color(_fmt_tools(b.implementation_only_tools), Colors.YELLOW)}`, _edit_blocked_tools],
      [`Bash read-only | ${color(_fmt_list(b.bash_read_patterns), Colors.YELLOW)}`, _edit_bash_read_patterns],
      [`Bash write-like | ${color(_fmt_list(b.bash_write_patterns), Colors.YELLOW)}`, _edit_bash_write_patterns],
      [`Extrasafe mode | ${color(_fmt_bool(b.extrasafe), Colors.YELLOW)}`, _ask_extrasafe_mode],
      [color('Back', Colors.YELLOW), null],
    ];
    let labels = actions.map(([lbl]) => lbl);
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const choice = await inquirer.list_input({ message: `${color('[Setting]', Colors.RESET)} | ${color('[Current Value]', Colors.YELLOW)}\n`, choices: labels });
      if (choice.includes('Back')) break;
      const fn = new Map(actions).get(choice);
      if (fn) {
        if (choice.includes('Bash read-only')) show_header(print_read_only_section);
        else if (choice.includes('Bash write-like')) show_header(print_write_like_section);
        else if (choice.includes('Extrasafe')) show_header(print_extrasafe_section);
        await fn();
        show_header(print_blocking_header);
      }
      [cfg] = _reload(); b = cfg.blocked_actions;
      actions[0] = [`Tools list | ${color(_fmt_tools(b.implementation_only_tools), Colors.YELLOW)}`, _edit_blocked_tools];
      actions[1] = [`Bash read-only | ${color(_fmt_list(b.bash_read_patterns), Colors.YELLOW)}`, _edit_bash_read_patterns];
      actions[2] = [`Bash write-like | ${color(_fmt_list(b.bash_write_patterns), Colors.YELLOW)}`, _edit_bash_write_patterns];
      actions[3] = [`Extrasafe mode | ${color(_fmt_bool(b.extrasafe), Colors.YELLOW)}`, _ask_extrasafe_mode];
      labels = actions.map(([lbl]) => lbl);
    }
  }

  async function _triggers_menu() {
    show_header(print_triggers_header);
    let [cfg] = _reload();
    let t = cfg.trigger_phrases;
    let actions = [
      [`Implementation mode | ${color(_fmt_list(t.implementation_mode), Colors.YELLOW)}`, _edit_triggers_implementation],
      [`Discussion mode | ${color(_fmt_list(t.discussion_mode), Colors.YELLOW)}`, _edit_triggers_discussion],
      [`Task creation | ${color(_fmt_list(t.task_creation), Colors.YELLOW)}`, _edit_triggers_task_creation],
      [`Task startup | ${color(_fmt_list(t.task_startup), Colors.YELLOW)}`, _edit_triggers_task_startup],
      [`Task completion | ${color(_fmt_list(t.task_completion), Colors.YELLOW)}`, _edit_triggers_task_completion],
      [`Context compaction | ${color(_fmt_list(t.context_compaction), Colors.YELLOW)}`, _edit_triggers_compaction],
      [color('Back', Colors.YELLOW), null],
    ];
    let labels = actions.map(([lbl]) => lbl);
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const choice = await inquirer.list_input({ message: `${color('[Setting]', Colors.RESET)} | ${color('[Current Value]', Colors.YELLOW)}\n`, choices: labels });
      if (choice.includes('Back')) break;
      const fn = new Map(actions).get(choice);
      if (fn) {
        if (choice.includes('Implementation mode')) show_header(print_go_triggers_section);
        else if (choice.includes('Discussion mode')) show_header(print_no_triggers_section);
        else if (choice.includes('Task creation')) show_header(print_create_section);
        else if (choice.includes('Task startup')) show_header(print_startup_section);
        else if (choice.includes('Task completion')) show_header(print_complete_section);
        else if (choice.includes('Context compaction')) show_header(print_compact_section);
        await fn();
        show_header(print_triggers_header);
      }
      [cfg] = _reload(); t = cfg.trigger_phrases;
      actions[0] = [`Implementation mode | ${_fmt_list(t.implementation_mode)}`, _edit_triggers_implementation];
      actions[1] = [`Discussion mode | ${color(_fmt_list(t.discussion_mode), Colors.YELLOW)}`, _edit_triggers_discussion];
      actions[2] = [`Task creation | ${color(_fmt_list(t.task_creation), Colors.YELLOW)}`, _edit_triggers_task_creation];
      actions[3] = [`Task startup | ${color(_fmt_list(t.task_startup), Colors.YELLOW)}`, _edit_triggers_task_startup];
      actions[4] = [`Task completion | ${color(_fmt_list(t.task_completion), Colors.YELLOW)}`, _edit_triggers_task_completion];
      actions[5] = [`Context compaction | ${color(_fmt_list(t.context_compaction), Colors.YELLOW)}`, _edit_triggers_compaction];
      labels = actions.map(([lbl]) => lbl);
    }
  }

  // Main menu: grouped categories
  // eslint-disable-next-line no-constant-condition
  while (true) {
    try {
      show_header(print_config_header);
      const choice = await inquirer.list_input({
        message: 'Config Editor — choose a category',
        choices: [
          `${color('Git Preferences', Colors.CYAN)} ${color('(default branch, submodules, staging pattern, commit style, auto-merge, auto-push)', Colors.GRAY)}`,
          `${color('Environment', Colors.CYAN)} ${color('(developer name, operating system, shell)', Colors.GRAY)}`,
          `${color('Blocked Actions', Colors.CYAN)} ${color('(tools, read-only commands, write-like commands, extrasafe)', Colors.GRAY)}`,
          `${color('Trigger Phrases', Colors.CYAN)} ${color('(implementation, discussion, task create/start/complete, compaction)', Colors.GRAY)}`,
          `${color('Features', Colors.CYAN)} ${color('(statusline, branch enforcement, ultrathink, context warnings, Nerd Fonts)', Colors.GRAY)}`,
          color('Done', Colors.RED),
        ],
      });
      const norm = _strip_ansi(choice);
      if (choice.includes('Done')) { clear_info(); break; }
      else if (norm.startsWith('Git Preferences')) await _git_menu();
      else if (norm.startsWith('Environment')) await _env_menu();
      else if (norm.startsWith('Blocked Actions')) await _blocked_menu();
      else if (norm.startsWith('Trigger Phrases')) await _triggers_menu();
      else if (norm.startsWith('Features')) await _features_menu();
    } catch (e) { break; }
  }

  async function _features_menu() {
    show_header(print_features_header);
    let [cfg, installed] = _reload();
    let f = cfg.features;
    const cw = [];
    if (f.context_warnings && f.context_warnings.warn_85) cw.push('85%');
    if (f.context_warnings && f.context_warnings.warn_90) cw.push('90%');
    let cw_str = cw.length ? cw.join(', ') : 'Never';
    let actions = [
      [`Statusline integration | ${color(installed ? 'Installed' : 'Not installed', Colors.YELLOW)}`, _ask_statusline],
      [`Branch enforcement | ${color(_fmt_bool(f.branch_enforcement), Colors.YELLOW)}`, _ask_branch_enforcement],
      [`Auto-ultrathink | ${color(_fmt_bool(f.auto_ultrathink), Colors.YELLOW)}`, _ask_auto_ultrathink],
      installed ? [`Nerd Fonts | ${color(_fmt_bool(f.use_nerd_fonts), Colors.YELLOW)}`, _ask_nerd_fonts] : null,
      [`Context warnings | ${color(cw_str, Colors.YELLOW)}`, _ask_context_warnings],
      [color('Back', Colors.YELLOW), null],
    ].filter(Boolean);
    let labels = actions.map(([lbl]) => lbl);
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const choice = await inquirer.list_input({ message: `${color('[Setting]', Colors.RESET)} | ${color('[Current Value]', Colors.YELLOW)}\n`, choices: labels });
      if (choice.includes('Back')) break;
      const fn = new Map(actions).get(choice);
      if (fn) {
        if (choice.includes('Statusline integration')) show_header(print_statusline_header);
        await fn();
        show_header(print_features_header);
      }
      [cfg, installed] = _reload(); f = cfg.features; cw.length = 0;
      if (f.context_warnings && f.context_warnings.warn_85) cw.push('85%');
      if (f.context_warnings && f.context_warnings.warn_90) cw.push('90%');
      cw_str = cw.length ? cw.join(', ') : 'Never';
      actions = [
        [`Statusline integration | ${color(installed ? 'Installed' : 'Not installed', Colors.YELLOW)}`, _ask_statusline],
        [`Branch enforcement | ${color(_fmt_bool(f.branch_enforcement), Colors.YELLOW)}`, _ask_branch_enforcement],
        [`Auto-ultrathink | ${color(_fmt_bool(f.auto_ultrathink), Colors.YELLOW)}`, _ask_auto_ultrathink],
        installed ? [`Nerd Fonts | ${color(_fmt_bool(f.use_nerd_fonts), Colors.YELLOW)}`, _ask_nerd_fonts] : null,
        [`Context warnings | ${color(cw_str, Colors.YELLOW)}`, _ask_context_warnings],
        [color('Back', Colors.YELLOW), null],
      ].filter(Boolean);
      labels = actions.map(([lbl]) => lbl);
    }
  }
}

///-///

/// ===== IMPORT CONFIG ===== ///
async function import_config(project_root, source, source_type, info) {
  let tmp_to_remove = null;
  let imported_any = false;
  try {
    let src_path = null;
    if (source_type === 'GitHub stub (owner/repo)') {
      const owner_repo = String(source).trim().replace(/^\/+|\/+$/g, '');
      const url = `https://github.com/${owner_repo}.git`;
      tmp_to_remove = await fsp.mkdtemp(path.join(os.tmpdir(), 'ccs-import-'));
      try {
        cp.execFileSync('git', ['clone', '--depth', '1', url, tmp_to_remove], { stdio: 'ignore' });
      } catch (e) { set_info(info.concat([color(`Git clone failed for ${url}: ${e}`, Colors.RED)])); return false; }
      src_path = tmp_to_remove;
    } else if (source_type === 'Git repository URL') {
      const url = String(source).trim();
      tmp_to_remove = await fsp.mkdtemp(path.join(os.tmpdir(), 'ccs-import-'));
      try {
        cp.execFileSync('git', ['clone', '--depth', '1', url, tmp_to_remove], { stdio: 'ignore' });
      } catch (e) { set_info(info.concat([color(`Git clone failed for ${url}: ${e}`, Colors.RED)])); return false; }
      src_path = tmp_to_remove;
    } else {
      src_path = path.resolve(String(source));
      if (!fs.existsSync(src_path) || !fs.statSync(src_path).isDirectory()) {
        set_info(info.concat([color('Provided path does not exist or is not a directory.', Colors.RED)]));
        return false;
      }
    }

    const src_cfg = path.join(src_path, 'sessions', 'sessions-config.json');
    const dst_cfg = path.join(project_root, 'sessions', 'sessions-config.json');
    if (fs.existsSync(src_cfg)) {
      fs.mkdirSync(path.dirname(dst_cfg), { recursive: true });
      fs.copyFileSync(src_cfg, dst_cfg);
      set_info(info.concat([color('✓ Imported sessions-config.json', Colors.GREEN)]));
      imported_any = true;
    } else { set_info(info.concat([color('No sessions-config.json found to import at sessions/sessions-config.json', Colors.YELLOW)])); }

    const src_agents = path.join(src_path, '.claude', 'agents');
    const dst_agents = path.join(project_root, '.claude', 'agents');
    if (fs.existsSync(src_agents)) {
      for (const agent_name of AGENT_BASELINE) {
        const src_file = path.join(src_agents, agent_name);
        const dst_file = path.join(dst_agents, agent_name);
        if (fs.existsSync(src_file)) {
          const choice = await inquirer.list_input({ message: `Agent '${agent_name}' found in import. Which version to keep?`, choices: ['Use imported version', 'Keep default'] });
          if (choice === 'Use imported version') {
            fs.mkdirSync(path.dirname(dst_file), { recursive: true });
            fs.copyFileSync(src_file, dst_file);
            set_info(info.concat([color(`✓ Imported agent: ${agent_name}`, Colors.GREEN)]));
            imported_any = true;
          }
        }
      }
    } else { set_info(info.concat([color('No .claude/agents directory found to import agents from', Colors.YELLOW)])); }

    await setup_shared_state_and_initialize(project_root);
    return imported_any;
  } catch (e) {
    set_info(info.concat([color(`Import failed: ${e}`, Colors.RED)]));
    return false;
  } finally {
    if (tmp_to_remove) { try { await fsp.rm(tmp_to_remove, { recursive: true, force: true }); } catch {} }
  }
}

async function kickstart_decision(project_root) {
  show_header(print_kickstart_header);
  set_info([
    'cc-sessions is an opinionated interactive workflow. You can learn how to use',
    'it with Claude Code via a custom "session" called kickstart.',
    '',
    'Kickstart will:',
    '  • Teach you the features of cc-sessions',
    '  • Help you set up your first task',
    '  • Show the 4 core protocols you can run',
    '  • Help customize subagents for your codebase',
    '',
    'Time: 15–30 minutes',
  ]);
  const choice = await inquirer.list_input({ message: 'Would you like to run kickstart on your first session?', choices: ['Yes (auto-start full kickstart tutorial)', 'Just subagents (customize subagents but skip tutorial)', 'No (skip tutorial, remove kickstart files)'] });
  clear_info();
  if (choice.includes('Yes')) {
    await ss.editState((s) => { if (!s.metadata) s.metadata = {}; s.metadata.kickstart = { mode: 'full' }; });
    console.log(color('\n✓ Kickstart will auto-start on your first session', Colors.GREEN));
    return 'full';
  }
  if (choice.includes('Just subagents')) {
    await ss.editState((s) => { if (!s.metadata) s.metadata = {}; s.metadata.kickstart = { mode: 'subagents' }; });
    console.log(color('\n✓ Kickstart will guide you through subagent customization only', Colors.GREEN));
    return 'subagents';
  }
  console.log(color('\n⏭️  Skipping kickstart onboarding...', Colors.CYAN));
  kickstart_cleanup(project_root);
  console.log(color('\n✓ Kickstart files removed', Colors.GREEN));
  return 'skip';
}

///-///

//-//

// ===== ENTRYPOINT ===== //

async function main() {
  const SCRIPT_DIR = get_package_root();
  const PROJECT_ROOT = get_project_root();

  // Check if already installed and backup if needed
  const sessions_dir = path.join(PROJECT_ROOT, 'sessions');
  let backup_dir = null;
  if (fs.existsSync(sessions_dir)) {
    const tasks_dir = path.join(sessions_dir, 'tasks');
    const has_content = fs.existsSync(tasks_dir) && _countFiles(tasks_dir, '.md') > 0;
    if (!has_content) console.log(color('🆕 Detected empty sessions directory, treating as fresh install', Colors.CYAN));
    else { console.log(color('🔍 Detected existing cc-sessions installation', Colors.CYAN)); backup_dir = create_backup(PROJECT_ROOT); }
  }

  console.log(color(`\n⚙️  Installing cc-sessions to: ${PROJECT_ROOT}`, Colors.CYAN));
  console.log();

  try {
    // Phase: install files
    create_directory_structure(PROJECT_ROOT);
    copy_files(SCRIPT_DIR, PROJECT_ROOT);
    configure_settings(PROJECT_ROOT);
    configure_claude_md(PROJECT_ROOT);
    configure_gitignore(PROJECT_ROOT);

    // Phase: load shared state and initialize defaults
    await setup_shared_state_and_initialize(PROJECT_ROOT);

    // Phase: interactive portions under TUI
    const session = tui_session();
    await session.enter();
    try {
      const did_import = await installer_decision_flow(PROJECT_ROOT);
      if (did_import) await run_config_editor(PROJECT_ROOT);
      else await run_full_configuration();
      const kickstart_mode = await kickstart_decision(PROJECT_ROOT);
      // Restore tasks if this was an update
      if (backup_dir) {
        restore_tasks(PROJECT_ROOT, backup_dir);
        console.log(color(`\n📁 Backup saved at: ${path.relative(PROJECT_ROOT, backup_dir)}/`, Colors.CYAN));
        console.log(color('   (Agents backed up for manual restoration if needed)', Colors.CYAN));
      }
      console.log(color('\n✅ cc-sessions installed successfully!\n', Colors.GREEN));
      console.log(color('Next steps:', Colors.BOLD));
      console.log('  1. Restart your Claude Code session (or run /clear)');
      if (kickstart_mode === 'full') console.log('  2. The kickstart onboarding will guide you through setup\n');
      else if (kickstart_mode === 'subagents') console.log('  2. Kickstart will guide you through subagent customization\n');
      else { console.log('  2. You can start using cc-sessions right away!'); console.log('     - Try "mek: my first task" to create a task'); console.log('     - Type "help" to see available commands\n'); }
      if (backup_dir) console.log(color('Note: Check backup/ for any custom agents you want to restore\n', Colors.CYAN));
    } finally {
      await session.exit();
    }
  } catch (error) {
    console.error(color(`\n❌ Installation failed: ${error}`, Colors.RED));
    console.error(error && error.stack ? error.stack : String(error));
    process.exitCode = 1;
  }
}

async function installer_decision_flow(project_root) {
  show_header(print_installer_header);
  let did_import = false;
  const first_time = await inquirer.list_input({ message: 'Is this your first time using cc-sessions?', choices: ['Yes', 'No'] });
  if (first_time === 'No') {
    const version_check = await inquirer.list_input({ message: 'Have you used cc-sessions v0.3.0 or later (released October 2025)?', choices: ['Yes', 'No'] });
    if (version_check === 'Yes') {
      const import_choice = await inquirer.list_input({ message: 'Would you like to import your configuration and agents?', choices: ['Yes', 'No'] });
      if (import_choice === 'Yes') {
        const info = [ color('We can import your config and, optionally, agents from Github (URL or stub) or', Colors.CYAN), color('a project folder on your local machine.', Colors.CYAN), '' ];
        set_info(info);
        const import_source = await inquirer.list_input({ message: 'Where is your cc-sessions configuration?', choices: ['Local directory', 'Git repository URL', 'GitHub stub (owner/repo)', 'Skip import'] });
        if (import_source !== 'Skip import') {
          let source_path;
          if (import_source.includes('Local')) source_path = (await _input('Path to project: ')).trim();
          else if (import_source.includes('URL')) source_path = await _input('Github URL: ');
          else if (import_source.includes('stub')) source_path = await _input('Github stub (i.e. author/repo_name): ');
          set_info(info.concat([color(`Steady lads - importing from ${source_path}...`, Colors.YELLOW)]));
          did_import = await import_config(project_root, source_path, import_source, info);
          if (!did_import) console.log(color('\nImport failed or not implemented. Continuing with configuration...', Colors.YELLOW));
        } else {
          console.log(color('\nSkipping import. Continuing with configuration...', Colors.CYAN));
        }
      } else {
        console.log(color('\nContinuing with configuration...', Colors.CYAN));
      }
    } else {
      console.log(color('\nContinuing with configuration...', Colors.CYAN));
    }
  }
  return did_import;
}

async function _input(prompt = '') {
  if (_TUI_ACTIVE && _TUI) return await _TUI.textInput(prompt);
  // Fallback simple prompt (no dependency)
  return await new Promise((resolve) => {
    process.stdout.write(prompt);
    const chunks = [];
    const onData = (b) => {
      if (b[0] === 3) { // Ctrl+C
        process.stdout.write('\n');
        process.stdin.off('data', onData);
        resolve('');
        return;
      }
      if (b[0] === 13 || b[0] === 10) {
        process.stdout.write('\n');
        process.stdin.off('data', onData);
        resolve(Buffer.concat(chunks).toString('utf8'));
        return;
      }
      chunks.push(b);
    };
    process.stdin.on('data', onData);
  });
}

if (require.main === module) {
  main();
}
