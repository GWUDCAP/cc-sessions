#!/usr/bin/env python3

# ===== IMPORTS ===== #

## ===== STDLIB ===== ##
import shutil, json, sys, os, subprocess, tempfile, contextlib, re
from pathlib import Path
from time import sleep
##-##

## ===== 3RD-PARTY ===== ##
from inquirer import themes
import platform
import inquirer
##-##

## ===== LOCAL ===== ##
##-##

# Global shared_state handle (set after files are installed)
ss = None

# Standard agents we ship and may import overrides for
AGENT_BASELINE = [
    'code-review.md',
    'context-gathering.md',
    'context-refinement.md',
    'logging.md',
    'service-documentation.md',
]

# ===== Inquirer wrappers (j/k navigation) ===== #
try:
    import curses
    _CURSES_AVAILABLE = True
except Exception:
    _CURSES_AVAILABLE = False

_ORIG_LIST_INPUT = getattr(inquirer, 'list_input', None)
_ORIG_CHECKBOX = getattr(inquirer, 'checkbox', None)

_ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
def _strip_ansi(s):
    try:
        return _ANSI_RE.sub('', s)
    except Exception:
        try: return str(s)
        except Exception: return ''

def _jk_list_input(message: str, choices, default=None):
    if not _CURSES_AVAILABLE or not sys.stdin.isatty() or _ORIG_LIST_INPUT is None:
        return _ORIG_LIST_INPUT(message=message, choices=choices, default=default)

    def _run(stdscr):
        curses.curs_set(0)
        stdscr.keypad(True)
        height, width = stdscr.getmaxyx()
        title = message if isinstance(message, str) else str(message)
        opts = list(choices)
        disp_opts = [_strip_ansi(str(x)) for x in opts]
        idx = 0
        if default is not None:
            try: idx = opts.index(default)
            except Exception: pass
        scroll = 0
        max_visible = max(3, height - 4)

        while True:
            stdscr.clear()
            stdscr.addstr(0, 0, title[:width-1])
            stdscr.addstr(1, 0, "Use j/k or arrows • Enter to select • Ctrl+C to exit")

            if idx < scroll: scroll = idx
            elif idx >= scroll + max_visible: scroll = idx - max_visible + 1

            for i in range(scroll, min(len(opts), scroll + max_visible)):
                disp = disp_opts[i]
                prefix = '> ' if i == idx else '  '
                text = f"{prefix}{disp}"
                if i == idx:
                    stdscr.addstr(2 + i - scroll, 0, text[:width-1], curses.A_REVERSE)
                else:
                    stdscr.addstr(2 + i - scroll, 0, text[:width-1])

            key = stdscr.getch()
            if key in (curses.KEY_UP, ord('k')):
                idx = (idx - 1) % len(opts)
            elif key in (curses.KEY_DOWN, ord('j')):
                idx = (idx + 1) % len(opts)
            elif key in (curses.KEY_ENTER, 10, 13):
                return opts[idx]
            elif key in (3, 27):
                raise KeyboardInterrupt

    return curses.wrapper(_run)

def _jk_checkbox(message: str, choices, default=None):
    if not _CURSES_AVAILABLE or not sys.stdin.isatty() or _ORIG_CHECKBOX is None:
        return _ORIG_CHECKBOX(message=message, choices=choices, default=default)

    def _run(stdscr):
        curses.curs_set(0)
        stdscr.keypad(True)
        height, width = stdscr.getmaxyx()
        title = message if isinstance(message, str) else str(message)
        opts = list(choices)
        disp_opts = [_strip_ansi(str(x)) for x in opts]
        checked = set(default or [])
        idx = 0
        scroll = 0
        max_visible = max(3, height - 5)
        legend = "j/k or arrows move • Space toggles • Enter submit • Ctrl+C exits"

        while True:
            stdscr.clear()
            stdscr.addstr(0, 0, title[:width-1])
            stdscr.addstr(1, 0, legend[:width-1])

            if idx < scroll: scroll = idx
            elif idx >= scroll + max_visible: scroll = idx - max_visible + 1

            for i in range(scroll, min(len(opts), scroll + max_visible)):
                line = opts[i]
                disp = disp_opts[i]
                mark = '[x]' if line in checked else '[ ]'
                pointer = '> ' if i == idx else '  '
                text = f"{pointer}{mark} {disp}"
                if i == idx:
                    stdscr.addstr(2 + i - scroll, 0, text[:width-1], curses.A_REVERSE)
                else:
                    stdscr.addstr(2 + i - scroll, 0, text[:width-1])

            key = stdscr.getch()
            if key in (curses.KEY_UP, ord('k')):
                idx = (idx - 1) % len(opts)
            elif key in (curses.KEY_DOWN, ord('j')):
                idx = (idx + 1) % len(opts)
            elif key in (ord(' '),):
                cur = opts[idx]
                if cur in checked: checked.remove(cur)
                else: checked.add(cur)
            elif key in (curses.KEY_ENTER, 10, 13):
                return [o for o in opts if o in checked]
            elif key in (3, 27):
                raise KeyboardInterrupt

    return curses.wrapper(_run)

try:
    if _ORIG_LIST_INPUT is not None:
        inquirer.list_input = _jk_list_input  # type: ignore
    if _ORIG_CHECKBOX is not None:
        inquirer.checkbox = _jk_checkbox  # type: ignore
except Exception:
    pass

#-#

"""
╔═════════════════════════════════════════════════════════════════════╗
║ ██████╗██╗  ██╗██████╗██████╗ █████╗ ██╗     ██╗     ██████╗█████╗  ║
║ ╚═██╔═╝███╗ ██║██╔═══╝╚═██╔═╝██╔══██╗██║     ██║     ██╔═══╝██╔═██╗ ║
║   ██║  ████╗██║██████╗  ██║  ███████║██║     ██║     █████╗ █████╔╝ ║
║   ██║  ██╔████║╚═══██║  ██║  ██╔══██║██║     ██║     ██╔══╝ ██╔═██╗ ║
║ ██████╗██║╚███║██████║  ██║  ██║  ██║███████╗███████╗██████╗██║ ██║ ║
║ ╚═════╝╚═╝ ╚══╝╚═════╝  ╚═╝  ╚═╝  ╚═╝╚══════╝╚══════╝╚═════╝╚═╝ ╚═╝ ║
╚═════════════════════════════════════════════════════════════════════╝
cc-sessions installer module for pip/pipx installation.
This module is imported and executed when running `cc-sessions` command.
"""

# ===== DECLARATIONS ===== #

## ===== ENUMS ===== ##
# Colors for terminal output
class Colors:
    RESET = '\033[0m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    CYAN = '\033[36m'
    BOLD = '\033[1m'
##-##

#-#

# ===== FUNCTIONS ===== #

## ===== UTILITIES ===== ##
def copy_file(src, dest):
    if src.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

        # Preserve executable permissions
        try:
            src_mode = src.stat().st_mode
            dest.chmod(src_mode)
        except Exception:
            # Ignore chmod errors
            pass

def copy_directory(src, dest):
    if not src.exists():
        return

    dest.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        src_path = src / item.name
        dest_path = dest / item.name

        if item.is_dir():
            copy_directory(src_path, dest_path)
        else:
            copy_file(src_path, dest_path)

def color(text, color_code) -> str:
    return f"{color_code}{text}{Colors.RESET}"

def fmt_msg(text: str) -> str:
    """Normalize prompt text and add cyan color.
    - Collapses duplicate trailing colons to a single colon
    - Applies cyan color for interactive prompts
    """
    if not isinstance(text, str):
        return text
    s = text.rstrip()
    # Collapse multiple trailing colons to one
    while s.endswith('::'):
        s = s[:-1]
    return color(s, Colors.CYAN)

def choices_filtered(choices):
    """Filter out falsy/None choices for inquirer inputs."""
    return [c for c in choices if c]

def get_package_root() -> Path:
    """Get the root directory of the installed cc_sessions package."""
    return Path(__file__).parent

def get_project_root() -> Path:
    """Get the root directory where cc-sessions should be installed."""
    return Path.cwd()
##-##

## ===== KEY TEXT ===== ##

#!> Main header
def print_installer_header() -> None:
    print(color('\n╔════════════════════════════════════════════════════════════╗', Colors.GREEN))
    print(color('║ ██████╗██████╗██████╗██████╗██████╗ █████╗ ██╗  ██╗██████╗ ║', Colors.GREEN))
    print(color('║ ██╔═══╝██╔═══╝██╔═══╝██╔═══╝╚═██╔═╝██╔══██╗███╗ ██║██╔═══╝ ║',Colors.GREEN))
    print(color('║ ██████╗█████╗ ██████╗██████╗  ██║  ██║  ██║████╗██║██████╗ ║',Colors.GREEN))
    print(color('║ ╚═══██║██╔══╝ ╚═══██║╚═══██║  ██║  ██║  ██║██╔████║╚═══██║ ║',Colors.GREEN))
    print(color('║ ██████║██████╗██████║██████║██████╗╚█████╔╝██║╚███║██████║ ║',Colors.GREEN))
    print(color('║ ╚═════╝╚═════╝╚═════╝╚═════╝╚═════╝ ╚════╝ ╚═╝ ╚══╝╚═════╝ ║',Colors.GREEN)) 
    print(color('╚════════╗  an opinionated approach to productive  ╔═════════╝',Colors.GREEN))
    print(color('         ╚═══   development with Claude Code   ════╝',Colors.GREEN))
    print()
    print()
#!<

#!> Configuration header (removed)
def print_config_header() -> None:
    return
#!<

#!> Git preferences header
def print_git_section() -> None:
    print(color('╔═════════════════════════════════════════════╗', Colors.GREEN))
    print(color('║ ██████╗ █████╗ ██╗ ██╗█████╗  █████╗██████╗ ║', Colors.GREEN))
    print(color('║ ██╔═══╝██╔══██╗██║ ██║██╔═██╗██╔═══╝██╔═══╝ ║', Colors.GREEN))
    print(color('║ ██████╗██║  ██║██║ ██║█████╔╝██║    █████╗  ║', Colors.GREEN))
    print(color('║ ╚═══██║██║  ██║██║ ██║██╔═██╗██║    ██╔══╝  ║', Colors.GREEN))
    print(color('║ ██████║╚█████╔╝╚████╔╝██║ ██║╚█████╗██████╗ ║', Colors.GREEN))
    print(color('║ ╚═════╝ ╚════╝  ╚═══╝ ╚═╝ ╚═╝ ╚════╝╚═════╝ ║', Colors.GREEN))
    print(color('╚═════════ configure git preferences ═════════╝', Colors.GREEN))
    print()
    print()
#!<

#!> Environment settings header
def print_env_section() -> None:
    print(color('╔══════════════════════════════════════════════════════╗', Colors.GREEN))
    print(color('║ ██████╗██╗  ██╗██╗ ██╗██████╗█████╗  █████╗ ██╗  ██╗ ║', Colors.GREEN))
    print(color('║ ██╔═══╝███╗ ██║██║ ██║╚═██╔═╝██╔═██╗██╔══██╗███╗ ██║ ║', Colors.GREEN))
    print(color('║ █████╗ ████╗██║██║ ██║  ██║  █████╔╝██║  ██║████╗██║ ║', Colors.GREEN))
    print(color('║ ██╔══╝ ██╔████║╚████╔╝  ██║  ██╔═██╗██║  ██║██╔████║ ║', Colors.GREEN))
    print(color('║ ██████╗██║╚███║ ╚██╔╝ ██████╗██║ ██║╚█████╔╝██║╚███║ ║', Colors.GREEN))
    print(color('║ ╚═════╝╚═╝ ╚══╝  ╚═╝  ╚═════╝╚═╝ ╚═╝ ╚════╝ ╚═╝ ╚══╝ ║', Colors.GREEN))
    print(color('╚════════════════ environment settings ════════════════╝', Colors.GREEN))
    print()
    print()
#!<

#!> Tool blocking
def print_blocking_header() -> None:
    print(color('╔══════════════════════════════════════════════════════════════╗', Colors.GREEN))
    print(color('║ █████╗ ██╗      █████╗  █████╗██╗  ██╗██████╗██╗  ██╗ █████╗ ║', Colors.GREEN))
    print(color('║ ██╔═██╗██║     ██╔══██╗██╔═══╝██║ ██╔╝╚═██╔═╝███╗ ██║██╔═══╝ ║', Colors.GREEN))
    print(color('║ █████╔╝██║     ██║  ██║██║    █████╔╝   ██║  ████╗██║██║     ║', Colors.GREEN))
    print(color('║ ██╔═██╗██║     ██║  ██║██║    ██╔═██╗   ██║  ██╔████║██║ ██╗ ║', Colors.GREEN))
    print(color('║ █████╔╝███████╗╚█████╔╝╚█████╗██║  ██╗██████╗██║╚███║╚█████║ ║', Colors.GREEN))
    print(color('║ ╚════╝ ╚══════╝ ╚════╝  ╚════╝╚═╝  ╚═╝╚═════╝╚═╝ ╚══╝ ╚════╝ ║', Colors.GREEN))
    print(color('╚══════════════ blocked tools and bash commands ═══════════════╝', Colors.GREEN))
    print()
    print()
#!<

#!> Read only commands section
def print_read_only_section() -> None:
    print(color('╔═══════════════════════════════════════════════════════════════════╗', Colors.GREEN))
    print(color('║ █████╗ ██████╗ █████╗ █████╗       ██╗     ██████╗██╗  ██╗██████╗ ║', Colors.GREEN))
    print(color('║ ██╔═██╗██╔═══╝██╔══██╗██╔═██╗      ██║     ╚═██╔═╝██║ ██╔╝██╔═══╝ ║', Colors.GREEN))
    print(color('║ █████╔╝█████╗ ███████║██║ ██║█████╗██║       ██║  █████╔╝ █████╗  ║', Colors.GREEN))
    print(color('║ ██╔═██╗██╔══╝ ██╔══██║██║ ██║╚════╝██║       ██║  ██╔═██╗ ██╔══╝  ║', Colors.GREEN))
    print(color('║ ██║ ██║██████╗██║  ██║█████╔╝      ███████╗██████╗██║  ██╗██████╗ ║', Colors.GREEN))
    print(color('║ ╚═╝ ╚═╝╚═════╝╚═╝  ╚═╝╚════╝       ╚══════╝╚═════╝╚═╝  ╚═╝╚═════╝ ║', Colors.GREEN))
    print(color('╚═══════════════ bash commands claude can use freely ═══════════════╝', Colors.GREEN))
    print()
    print()
#!<

#!> Write-like commands section
def print_write_like_section() -> None:
    print(color("╔════════════════════════════════════════════════════════════════════════════╗",Colors.GREEN))
    print(color("║ ██╗    ██╗█████╗ ██████╗██████╗██████╗      ██╗     ██████╗██╗  ██╗██████╗ ║",Colors.GREEN))
    print(color("║ ██║    ██║██╔═██╗╚═██╔═╝╚═██╔═╝██╔═══╝      ██║     ╚═██╔═╝██║ ██╔╝██╔═══╝ ║",Colors.GREEN))
    print(color("║ ██║ █╗ ██║█████╔╝  ██║    ██║  █████╗ █████╗██║       ██║  █████╔╝ █████╗  ║",Colors.GREEN))
    print(color("║ ██║███╗██║██╔═██╗  ██║    ██║  ██╔══╝ ╚════╝██║       ██║  ██╔═██╗ ██╔══╝  ║",Colors.GREEN))
    print(color("║ ╚███╔███╔╝██║ ██║██████╗  ██║  ██████╗      ███████╗██████╗██║  ██╗██████╗ ║",Colors.GREEN))
    print(color("║  ╚══╝╚══╝ ╚═╝ ╚═╝╚═════╝  ╚═╝  ╚═════╝      ╚══════╝╚═════╝╚═╝  ╚═╝╚═════╝ ║",Colors.GREEN))
    print(color("╚═══════════════ commands claude can't use in discussion mode ═══════════════╝",Colors.GREEN))
    print()
    print()
#!<

#!> Extrasafe section
def print_extrasafe_section() -> None:
    print(color("╔════════════════════════════════════════════════════════════════════╗",Colors.GREEN))
    print(color("║ ██████╗██╗  ██╗██████╗█████╗  █████╗ ██████╗ █████╗ ██████╗██████╗ ║",Colors.GREEN))
    print(color("║ ██╔═══╝╚██╗██╔╝╚═██╔═╝██╔═██╗██╔══██╗██╔═══╝██╔══██╗██╔═══╝██╔═══╝ ║",Colors.GREEN))
    print(color("║ █████╗  ╚███╔╝   ██║  █████╔╝███████║██████╗███████║█████╗ █████╗  ║",Colors.GREEN))
    print(color("║ ██╔══╝  ██╔██╗   ██║  ██╔═██╗██╔══██║╚═══██║██╔══██║██╔══╝ ██╔══╝  ║",Colors.GREEN))
    print(color("║ ██████╗██╔╝ ██╗  ██║  ██║ ██║██║  ██║██████║██║  ██║██║    ██████╗ ║",Colors.GREEN))
    print(color("║ ╚═════╝╚═╝  ╚═╝  ╚═╝  ╚═╝ ╚═╝╚═╝  ╚═╝╚═════╝╚═╝  ╚═╝╚═╝    ╚═════╝ ║",Colors.GREEN))
    print(color("╚════════════ toggle blocking for unrecognized commands ═════════════╝",Colors.GREEN))
    print()
    print()
#!<

#!> Trigger phrases
def print_triggers_header() -> None:
    print(color('╔══════════════════════════════════════════════════════════╗',Colors.GREEN))
    print(color('║ ██████╗█████╗ ██████╗ █████╗ █████╗██████╗█████╗ ██████╗ ║',Colors.GREEN))
    print(color('║ ╚═██╔═╝██╔═██╗╚═██╔═╝██╔═══╝██╔═══╝██╔═══╝██╔═██╗██╔═══╝ ║',Colors.GREEN))
    print(color('║   ██║  █████╔╝  ██║  ██║    ██║    █████╗ █████╔╝██████╗ ║',Colors.GREEN))
    print(color('║   ██║  ██╔═██╗  ██║  ██║ ██╗██║ ██╗██╔══╝ ██╔═██╗╚═══██║ ║',Colors.GREEN))
    print(color('║   ██║  ██║ ██║██████╗╚█████║╚█████║██████╗██║ ██║██████║ ║',Colors.GREEN))
    print(color('║   ╚═╝  ╚═╝ ╚═╝╚═════╝ ╚════╝ ╚════╝╚═════╝╚═╝ ╚═╝╚═════╝ ║',Colors.GREEN))
    print(color('╚════════ natural language controls for Claude Code ═══════╝',Colors.GREEN))
    print()
    print()
#!<

#!> Implementation mode triggers section
def print_go_triggers_section() -> None:
    print(color('╔══════════════════════════════════════════════════════════════════════════╗',Colors.GREEN))
    print(color('║ ██████╗███╗  ███╗██████╗ ██╗     ██████╗███╗  ███╗██████╗██╗  ██╗██████╗ ║',Colors.GREEN))
    print(color('║ ╚═██╔═╝████╗████║██╔══██╗██║     ██╔═══╝████╗████║██╔═══╝███╗ ██║╚═██╔═╝ ║',Colors.GREEN))
    print(color('║   ██║  ██╔███║██║██████╔╝██║     █████╗ ██╔███║██║█████╗ ████╗██║  ██║   ║',Colors.GREEN))
    print(color('║   ██║  ██║╚══╝██║██╔═══╝ ██║     ██╔══╝ ██║╚══╝██║██╔══╝ ██╔████║  ██║   ║',Colors.GREEN))
    print(color('║ ██████╗██║    ██║██║     ███████╗██████╗██║    ██║██████╗██║╚███║  ██║   ║',Colors.GREEN))
    print(color('║ ╚═════╝╚═╝    ╚═╝╚═╝     ╚══════╝╚═════╝╚═╝    ╚═╝╚═════╝╚═╝ ╚══╝  ╚═╝   ║',Colors.GREEN))
    print(color('╚════════════ activate implementation mode (claude can code) ══════════════╝',Colors.GREEN))
    print()
    print()
#!<

#!> Discussion mode triggers section
def print_no_triggers_section() -> None:
    print(color('╔═══════════════════════════════════════════════════╗',Colors.GREEN))
    print(color('║ █████╗ ██████╗██████╗ █████╗██╗ ██╗██████╗██████╗ ║',Colors.GREEN))
    print(color('║ ██╔═██╗╚═██╔═╝██╔═══╝██╔═══╝██║ ██║██╔═══╝██╔═══╝ ║',Colors.GREEN))
    print(color('║ ██║ ██║  ██║  ██████╗██║    ██║ ██║██████╗██████╗ ║',Colors.GREEN))
    print(color('║ ██║ ██║  ██║  ╚═══██║██║    ██║ ██║╚═══██║╚═══██║ ║',Colors.GREEN))
    print(color('║ █████╔╝██████╗██████║╚█████╗╚████╔╝██████║██████║ ║',Colors.GREEN))
    print(color('║ ╚════╝ ╚═════╝╚═════╝ ╚════╝ ╚═══╝ ╚═════╝╚═════╝ ║',Colors.GREEN))
    print(color('╚════════════ activate discussion mode ════════════╝',Colors.GREEN))
    print()
    print()
#!<

#!> Create triggers section
def print_create_section() -> None:
    print(color('╔═════════════════════════════════════════════╗',Colors.GREEN))
    print(color('║  █████╗█████╗ ██████╗ █████╗ ██████╗██████╗ ║',Colors.GREEN))
    print(color('║ ██╔═══╝██╔═██╗██╔═══╝██╔══██╗╚═██╔═╝██╔═══╝ ║',Colors.GREEN))
    print(color('║ ██║    █████╔╝█████╗ ███████║  ██║  █████╗  ║',Colors.GREEN))
    print(color('║ ██║    ██╔═██╗██╔══╝ ██╔══██║  ██║  ██╔══╝  ║',Colors.GREEN))
    print(color('║ ╚█████╗██║ ██║██████╗██║  ██║  ██║  ██████╗ ║',Colors.GREEN))
    print(color('║  ╚════╝╚═╝ ╚═╝╚═════╝╚═╝  ╚═╝  ╚═╝  ╚═════╝ ║',Colors.GREEN))
    print(color('╚══════ activate task creation protocol ══════╝',Colors.GREEN))
    print()
    print()
#!<

#!> Startup triggers section
def print_startup_section() -> None:
    print(color('╔═════════════════════════════════════════════════════╗',Colors.GREEN))
    print(color('║ ██████╗██████╗ █████╗ █████╗ ██████╗██╗ ██╗██████╗  ║',Colors.GREEN))
    print(color('║ ██╔═══╝╚═██╔═╝██╔══██╗██╔═██╗╚═██╔═╝██║ ██║██╔══██╗ ║',Colors.GREEN))
    print(color('║ ██████╗  ██║  ███████║█████╔╝  ██║  ██║ ██║██████╔╝ ║',Colors.GREEN))
    print(color('║ ╚═══██║  ██║  ██╔══██║██╔═██╗  ██║  ██║ ██║██╔═══╝  ║',Colors.GREEN))
    print(color('║ ██████║  ██║  ██║  ██║██║ ██║  ██║  ╚████╔╝██║      ║',Colors.GREEN))
    print(color('║ ╚═════╝  ╚═╝  ╚═╝  ╚═╝╚═╝ ╚═╝  ╚═╝   ╚═══╝ ╚═╝      ║',Colors.GREEN))
    print(color('╚══════════ activate task startup protocol ═══════════╝',Colors.GREEN))
    print()
    print()
#!<

#!> Completion triggers section
def print_complete_section() -> None:
    print(color('╔════════════════════════════════════════════════════════════════╗',Colors.GREEN))
    print(color('║  █████╗ █████╗ ███╗  ███╗██████╗ ██╗     ██████╗██████╗██████╗ ║',Colors.GREEN))
    print(color('║ ██╔═══╝██╔══██╗████╗████║██╔══██╗██║     ██╔═══╝╚═██╔═╝██╔═══╝ ║',Colors.GREEN))
    print(color('║ ██║    ██║  ██║██╔███║██║██████╔╝██║     █████╗   ██║  █████╗  ║',Colors.GREEN))
    print(color('║ ██║    ██║  ██║██║╚══╝██║██╔═══╝ ██║     ██╔══╝   ██║  ██╔══╝  ║',Colors.GREEN))
    print(color('║ ╚█████╗╚█████╔╝██║    ██║██║     ███████╗██████╗  ██║  ██████╗ ║',Colors.GREEN))
    print(color('║  ╚════╝ ╚════╝ ╚═╝    ╚═╝╚═╝     ╚══════╝╚═════╝  ╚═╝  ╚═════╝ ║',Colors.GREEN))
    print(color('╚══════════════ activate task completion protocol ═══════════════╝',Colors.GREEN))
    print()
    print()
#!<

#!> Compaction triggers section
def print_compact_section() -> None:
    print(color('╔═════════════════════════════════════════════════════════╗',Colors.GREEN))
    print(color('║  █████╗ █████╗ ███╗  ███╗██████╗  █████╗  █████╗██████╗ ║',Colors.GREEN))
    print(color('║ ██╔═══╝██╔══██╗████╗████║██╔══██╗██╔══██╗██╔═══╝╚═██╔═╝ ║',Colors.GREEN))
    print(color('║ ██║    ██║  ██║██╔███║██║██████╔╝███████║██║      ██║   ║',Colors.GREEN))
    print(color('║ ██║    ██║  ██║██║╚══╝██║██╔═══╝ ██╔══██║██║      ██║   ║',Colors.GREEN))
    print(color('║ ╚█████╗╚█████╔╝██║    ██║██║     ██║  ██║╚█████╗  ██║   ║',Colors.GREEN))
    print(color('║  ╚════╝ ╚════╝ ╚═╝    ╚═╝╚═╝     ╚═╝  ╚═╝ ╚════╝  ╚═╝   ║',Colors.GREEN))
    print(color('╚═════════ activate context compaction protocol ══════════╝',Colors.GREEN))
    print()
    print()
#!<

#!> Feature toggles header
def print_features_header() -> None:
    print(color('╔═══════════════════════════════════════════════════════════╗',Colors.GREEN))
    print(color('║ ██████╗██████╗ █████╗ ██████╗██╗ ██╗█████╗ ██████╗██████╗ ║',Colors.GREEN))
    print(color('║ ██╔═══╝██╔═══╝██╔══██╗╚═██╔═╝██║ ██║██╔═██╗██╔═══╝██╔═══╝ ║',Colors.GREEN))
    print(color('║ █████╗ █████╗ ███████║  ██║  ██║ ██║█████╔╝█████╗ ██████╗ ║',Colors.GREEN))
    print(color('║ ██╔══╝ ██╔══╝ ██╔══██║  ██║  ██║ ██║██╔═██╗██╔══╝ ╚═══██║ ║',Colors.GREEN))
    print(color('║ ██║    ██████╗██║  ██║  ██║  ╚████╔╝██║ ██║██████╗██████║ ║',Colors.GREEN))
    print(color('║ ╚═╝    ╚═════╝╚═╝  ╚═╝  ╚═╝   ╚═══╝ ╚═╝ ╚═╝╚═════╝╚═════╝ ║',Colors.GREEN))
    print(color('╚════════════ turn on/off cc-sessions features ═════════════╝',Colors.GREEN))
    print()
    print()
#!<

#!> Statusline header
def print_statusline_header() -> None:
    print(color('╔═══════════════════════════════════════════════════════════════════════════╗',Colors.GREEN))
    print(color('║ ██████╗██████╗ █████╗ ██████╗██╗ ██╗██████╗██╗     ██████╗██╗  ██╗██████╗ ║',Colors.GREEN))
    print(color('║ ██╔═══╝╚═██╔═╝██╔══██╗╚═██╔═╝██║ ██║██╔═══╝██║     ╚═██╔═╝███╗ ██║██╔═══╝ ║',Colors.GREEN))
    print(color('║ ██████╗  ██║  ███████║  ██║  ██║ ██║██████╗██║       ██║  ████╗██║█████╗  ║',Colors.GREEN))
    print(color('║ ╚═══██║  ██║  ██╔══██║  ██║  ██║ ██║╚═══██║██║       ██║  ██╔████║██╔══╝  ║',Colors.GREEN))
    print(color('║ ██████║  ██║  ██║  ██║  ██║  ╚████╔╝██████║███████╗██████╗██║╚███║██████╗ ║',Colors.GREEN))
    print(color('║ ╚═════╝  ╚═╝  ╚═╝  ╚═╝  ╚═╝   ╚═══╝ ╚═════╝╚══════╝╚═════╝╚═╝ ╚══╝╚═════╝ ║',Colors.GREEN))
    print(color('╚═════════════ cc-sessions custom statusline w/ modes + tasks ══════════════╝',Colors.GREEN))
    print()
    print()
#!<

#!> Kickstart header
def print_kickstart_header() -> None:
    print(color('╔════════════════════════════════════════════════════════════════════╗',Colors.GREEN))
    print(color('║ ██╗  ██╗██████╗ █████╗██╗  ██╗██████╗██████╗ █████╗ █████╗ ██████╗ ║',Colors.GREEN))
    print(color('║ ██║ ██╔╝╚═██╔═╝██╔═══╝██║ ██╔╝██╔═══╝╚═██╔═╝██╔══██╗██╔═██╗╚═██╔═╝ ║',Colors.GREEN))
    print(color('║ █████╔╝   ██║  ██║    █████╔╝ ██████╗  ██║  ███████║█████╔╝  ██║   ║',Colors.GREEN))
    print(color('║ ██╔═██╗   ██║  ██║    ██╔═██╗ ╚═══██║  ██║  ██╔══██║██╔═██╗  ██║   ║',Colors.GREEN))
    print(color('║ ██║  ██╗██████╗╚█████╗██║  ██╗██████║  ██║  ██║  ██║██║ ██║  ██║   ║',Colors.GREEN))
    print(color('║ ╚═╝  ╚═╝╚═════╝ ╚════╝╚═╝  ╚═╝╚═════╝  ╚═╝  ╚═╝  ╚═╝╚═╝ ╚═╝  ╚═╝   ║',Colors.GREEN))
    print(color('╚════════════════════════════════════════════════════════════════════╝',Colors.GREEN))
    print()
    print()


#!<

##-##

## ===== FILESYSTEM ===== ##

#!> Previous install - create backup
def create_backup(project_root):
    """Create timestamped backup of tasks and agents before reinstall."""
    from datetime import datetime

    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_dir = project_root / '.claude' / f'.backup-{timestamp}'

    print(color(f'\n💾 Creating backup at {backup_dir.relative_to(project_root)}/...', Colors.CYAN))

    backup_dir.mkdir(parents=True, exist_ok=True)

    # Backup all task files (includes done/, indexes/, and all task files)
    tasks_src = project_root / 'sessions' / 'tasks'
    task_count = 0
    if tasks_src.exists():
        tasks_dest = backup_dir / 'tasks'
        copy_directory(tasks_src, tasks_dest)

        # Count task files for user feedback and verification
        task_count = sum(1 for f in tasks_src.rglob('*.md'))
        backed_up_count = sum(1 for f in tasks_dest.rglob('*.md'))

        if task_count != backed_up_count:
            print(color(f'   ✗ Backup verification failed: {backed_up_count}/{task_count} files backed up', Colors.RED))
            raise Exception('Backup verification failed - aborting to prevent data loss')

        print(color(f'   ✓ Backed up {task_count} task files', Colors.GREEN))

    # Backup all agents
    agents_src = project_root / '.claude' / 'agents'
    agent_count = 0
    if agents_src.exists():
        agents_dest = backup_dir / 'agents'
        copy_directory(agents_src, agents_dest)

        agent_count = len(list(agents_src.glob('*.md')))
        backed_up_agents = len(list(agents_dest.glob('*.md')))

        if agent_count != backed_up_agents:
            print(color(f'   ✗ Backup verification failed: {backed_up_agents}/{agent_count} agents backed up', Colors.RED))
            raise Exception('Backup verification failed - aborting to prevent data loss')

        print(color(f'   ✓ Backed up {agent_count} agent files', Colors.GREEN))

    return backup_dir
#!<

#!> Create directory structure
def create_directory_structure(project_root):
    print(color('Creating directory structure...', Colors.CYAN))

    dirs = [
        '.claude',
        '.claude/agents',
        '.claude/commands',
        'sessions',
        'sessions/tasks',
        'sessions/tasks/done',
        'sessions/tasks/indexes',
        'sessions/hooks',
        'sessions/api',
        'sessions/protocols',
        'sessions/knowledge'
    ]

    for dir_name in dirs:
        full_path = project_root / dir_name
        full_path.mkdir(parents=True, exist_ok=True)
#!<

#!> Copy files
def copy_files(script_dir, project_root):
    print(color('Installing files...', Colors.CYAN))

    # Copy agents
    agents_source = script_dir / 'agents'
    agents_dest = project_root / '.claude' / 'agents'
    if agents_source.exists():
        copy_directory(agents_source, agents_dest)

    # Copy knowledge base
    knowledge_source = script_dir / 'knowledge'
    knowledge_dest = project_root / 'sessions' / 'knowledge'
    if knowledge_source.exists():
        copy_directory(knowledge_source, knowledge_dest)

    print(color('Installing Python-specific files...', Colors.CYAN))

    py_root = script_dir / 'python'

    # Copy statusline
    copy_file(py_root / 'statusline.py', project_root / 'sessions' / 'statusline.py')

    # Copy API
    copy_directory(py_root / 'api', project_root / 'sessions' / 'api')

    # Copy hooks
    copy_directory(py_root / 'hooks', project_root / 'sessions' / 'hooks')

    # Copy protocols from shared directory
    copy_directory(script_dir / 'protocols', project_root / 'sessions' / 'protocols')

    # Copy commands from shared directory
    copy_directory(script_dir / 'commands', project_root / '.claude' / 'commands')

    # Copy templates from shared directory to their respective destinations
    templates_dir = script_dir / 'templates'

    copy_file(templates_dir / 'CLAUDE.sessions.md', project_root / 'sessions' / 'CLAUDE.sessions.md')

    copy_file(templates_dir / 'TEMPLATE.md', project_root / 'sessions' / 'tasks' / 'TEMPLATE.md')

    copy_file(templates_dir / 'h-kickstart-setup.md', project_root / 'sessions' / 'tasks' / 'h-kickstart-setup.md')

    copy_file(templates_dir / 'INDEX_TEMPLATE.md', project_root / 'sessions' / 'tasks' / 'indexes' / 'INDEX_TEMPLATE.md')
#!<

#!> Configure settings.json
def configure_settings(project_root):
    print(color('Configuring Claude Code hooks...', Colors.CYAN))

    settings_path = project_root / '.claude' / 'settings.json'
    settings = {}

    # Load existing settings if they exist
    if settings_path.exists():
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            print(color('⚠️  Could not parse existing settings.json, will create new one', Colors.YELLOW))

    # Define sessions hooks
    is_windows = sys.platform == 'win32'
    sessions_hooks = {
        'UserPromptSubmit': [
            {
                'hooks': [
                    {
                        'type': 'command',
                        'command': 'python "%CLAUDE_PROJECT_DIR%\\sessions\\hooks\\user_messages.py"' if is_windows
                                 else 'python $CLAUDE_PROJECT_DIR/sessions/hooks/user_messages.py'
                    }
                ]
            }
        ],
        'PreToolUse': [
            {
                'matcher': 'Write|Edit|MultiEdit|Task|Bash',
                'hooks': [
                    {
                        'type': 'command',
                        'command': 'python "%CLAUDE_PROJECT_DIR%\\sessions\\hooks\\sessions_enforce.py"' if is_windows
                                 else 'python $CLAUDE_PROJECT_DIR/sessions/hooks/sessions_enforce.py'
                    }
                ]
            },
            {
                'matcher': 'Task',
                'hooks': [
                    {
                        'type': 'command',
                        'command': 'python "%CLAUDE_PROJECT_DIR%\\sessions\\hooks\\subagent_hooks.py"' if is_windows
                                 else 'python $CLAUDE_PROJECT_DIR/sessions/hooks/subagent_hooks.py'
                    }
                ]
            }
        ],
        'PostToolUse': [
            {
                'hooks': [
                    {
                        'type': 'command',
                        'command': 'python "%CLAUDE_PROJECT_DIR%\\sessions\\hooks\\post_tool_use.py"' if is_windows
                                 else 'python $CLAUDE_PROJECT_DIR/sessions/hooks/post_tool_use.py'
                    }
                ]
            }
        ],
        'SessionStart': [
            {
                'matcher': 'startup|clear',
                'hooks': [
                    {
                        'type': 'command',
                        'command': 'python "%CLAUDE_PROJECT_DIR%\\sessions\\hooks\\session_start.py"' if is_windows
                                 else 'python $CLAUDE_PROJECT_DIR/sessions/hooks/session_start.py'
                    }
                ]
            }
        ]
    }

    # Initialize hooks object if it doesn't exist
    if 'hooks' not in settings:
        settings['hooks'] = {}

    # Merge each hook type (sessions hooks take precedence)
    for hook_type, hook_config in sessions_hooks.items():
        if hook_type not in settings['hooks']:
            settings['hooks'][hook_type] = []

        # Add sessions hooks (prepend so they run first)
        settings['hooks'][hook_type] = hook_config + settings['hooks'][hook_type]

    # Write updated settings
    with open(settings_path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
#!<

#!> Configure CLAUDE.md
def configure_claude_md(project_root):
    print(color('Configuring CLAUDE.md...', Colors.CYAN))

    claude_path = project_root / 'CLAUDE.md'
    reference = '@sessions/CLAUDE.sessions.md'

    if claude_path.exists():
        content = claude_path.read_text(encoding='utf-8')

        # Only add if not already present
        if reference not in content:
            # Add at the beginning after any frontmatter
            lines = content.split('\n')
            insert_index = 0

            # Skip frontmatter if it exists
            if lines[0] == '---':
                for i in range(1, len(lines)):
                    if lines[i] == '---':
                        insert_index = i + 1
                        break

            lines.insert(insert_index, '')
            lines.insert(insert_index + 1, reference)
            lines.insert(insert_index + 2, '')
            content = '\n'.join(lines)
            claude_path.write_text(content, encoding='utf-8')
    else:
        # Create minimal CLAUDE.md with reference
        minimal_claude = f"""# CLAUDE.md

{reference}

This file provides instructions for Claude Code when working with this codebase.
"""
        claude_path.write_text(minimal_claude, encoding='utf-8')
#!<

#!> Configure .gitignore
def configure_gitignore(project_root):
    print(color('Configuring .gitignore...', Colors.CYAN))

    gitignore_path = project_root / '.gitignore'
    gitignore_entries = [
        '',
        '# cc-sessions runtime files',
        'sessions/sessions-state.json',
        'sessions/transcripts/',
        ''
    ]

    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding='utf-8')

        # Only add if not already present
        if 'sessions/sessions-state.json' not in content:
            # Append to end of file
            content += '\n'.join(gitignore_entries)
            gitignore_path.write_text(content, encoding='utf-8')
    else:
        # Create new .gitignore with our entries
        gitignore_path.write_text('\n'.join(gitignore_entries), encoding='utf-8')
#!<

#!> Setup shared state and initialize config/state
def setup_shared_state_and_initialize(project_root):
    print(color('Initializing state and configuration...', Colors.CYAN))

    # Ensure shared_state can resolve the project root
    os.environ['CLAUDE_PROJECT_DIR'] = str(project_root)
    hooks_path = project_root / 'sessions' / 'hooks'
    if str(hooks_path) not in sys.path:
        sys.path.insert(0, str(hooks_path))

    global ss
    try:
        import shared_state as ss  # type: ignore
    except Exception as e:
        print(color('⚠️  Could not import shared_state module after file installation.', Colors.YELLOW))
        print(color(f'Error: {e}', Colors.YELLOW))
        raise

    # Ensure files exist and set a sensible default OS
    try:
        _ = ss.load_config()
    except Exception as e:
        # Attempt to sanitize legacy/bad config keys and retry
        try:
            cfg_path = ss.CONFIG_FILE
            if cfg_path.exists():
                data = json.loads(cfg_path.read_text(encoding='utf-8'))
                ba = data.get('blocked_actions', {})
                if isinstance(ba, dict):
                    allowed = {'implementation_only_tools', 'bash_read_patterns', 'bash_write_patterns', 'extrasafe'}
                    bad_keys = [k for k in list(ba.keys()) if k not in allowed]
                    if bad_keys:
                        for k in bad_keys: ba.pop(k, None)
                        data['blocked_actions'] = ba
                        cfg_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
        except Exception:
            pass
        # Retry; if still fails, back up and reset to defaults
        try:
            _ = ss.load_config()
        except Exception:
            try:
                cfg_path = ss.CONFIG_FILE
                if cfg_path.exists():
                    bad = cfg_path.with_suffix('.bad.json')
                    with contextlib.suppress(Exception): cfg_path.replace(bad)
                _ = ss.load_config()
            except Exception as e2:
                raise e2

    _ = ss.load_state()

    os_name = platform.system()
    os_map = {'Windows': ss.UserOS.WINDOWS, 'Linux': ss.UserOS.LINUX, 'Darwin': ss.UserOS.MACOS}
    detected_os = os_map.get(os_name, ss.UserOS.LINUX)

    with ss.edit_config() as config:
        # Coerce/initialize OS field
        current = getattr(config.environment, 'os', None)
        if isinstance(current, str):
            try:
                config.environment.os = ss.UserOS(current)
            except Exception:
                config.environment.os = detected_os
        elif current is None:
            config.environment.os = detected_os

    # Verify files were created
    state_file = project_root / 'sessions' / 'sessions-state.json'
    config_file = project_root / 'sessions' / 'sessions-config.json'
    if not state_file.exists() or not config_file.exists():
        print(color('⚠️  State files were not created properly', Colors.YELLOW))
        print(color('You may need to initialize them manually on first run', Colors.YELLOW))
#!<

#!> Kickstart cleanup
def kickstart_cleanup(project_root):
    """
    Delete kickstart files when user skips onboarding.
    Returns manual cleanup instructions for router/settings that require careful editing.
    """
    print(color('\n🧹 Removing kickstart files...', Colors.CYAN))

    sessions_dir = project_root / 'sessions'

    # 1. Delete kickstart hook (check both language variants)
    py_hook = sessions_dir / 'hooks' / 'kickstart_session_start.py'
    js_hook = sessions_dir / 'hooks' / 'kickstart_session_start.js'

    if py_hook.exists():
        py_hook.unlink()
        is_python = True
        print(color('   ✓ Deleted kickstart_session_start.py', Colors.GREEN))
    elif js_hook.exists():
        js_hook.unlink()
        is_python = False
        print(color('   ✓ Deleted kickstart_session_start.js', Colors.GREEN))
    else:
        is_python = True  # default fallback

    # 2. Delete kickstart protocols directory
    protocols_dir = sessions_dir / 'protocols' / 'kickstart'
    if protocols_dir.exists():
        shutil.rmtree(protocols_dir)
        print(color('   ✓ Deleted protocols/kickstart/', Colors.GREEN))

    # 3. Delete kickstart setup task
    task_file = sessions_dir / 'tasks' / 'h-kickstart-setup.md'
    if task_file.exists():
        task_file.unlink()
        print(color('   ✓ Deleted h-kickstart-setup.md', Colors.GREEN))

    # Generate language-specific cleanup instructions
    if is_python:
        instructions = """
Manual cleanup required (edit these files carefully):

1. sessions/api/router.py
   - Remove: from .kickstart_commands import handle_kickstart_command
   - Remove: 'kickstart': handle_kickstart_command from COMMAND_HANDLERS

2. .claude/settings.json
   - Remove the kickstart SessionStart hook entry

3. sessions/api/kickstart_commands.py
   - Delete this entire file
"""
    else:  # JavaScript
        instructions = """
Manual cleanup required (edit these files carefully):

1. sessions/api/router.js
   - Remove: const { handleKickstartCommand } = require('./kickstart_commands');
   - Remove: 'kickstart': handleKickstartCommand from COMMAND_HANDLERS

2. .claude/settings.json
   - Remove the kickstart SessionStart hook entry

3. sessions/api/kickstart_commands.js
   - Delete this entire file
"""

    print(color(instructions, Colors.YELLOW))
    return instructions
#!<

#!> Restore tasks
def restore_tasks(project_root, backup_dir):
    """Restore tasks from backup after installation."""
    print(color('\n♻️  Restoring tasks...', Colors.CYAN))

    try:
        tasks_backup = backup_dir / 'tasks'
        if tasks_backup.exists():
            tasks_dest = project_root / 'sessions' / 'tasks'
            copy_directory(tasks_backup, tasks_dest)

            task_count = sum(1 for f in tasks_backup.rglob('*.md'))
            print(color(f'   ✓ Restored {task_count} task files', Colors.GREEN))
    except Exception as e:
        print(color(f'   ✗ Restore failed: {e}', Colors.RED))
        print(color(f'   Your backup is safe at: {backup_dir.relative_to(project_root)}/', Colors.YELLOW))
        print(color('   Manually copy files from backup/tasks/ to sessions/tasks/', Colors.YELLOW))
        # Don't raise - let user recover manually

#!<

##-##

## ===== CONFIG QUESTIONS ===== ##

#!> Git preferences
def _ask_default_branch():
    print(color("cc-sessions uses git branches to section off task work and\nmerge back to your main work branch when the task is done.", Colors.CYAN))
    print()
    val = input("""When completing a task and merging the changes, Claude should
merge to (ex. 'main', 'next', 'master', etc.): """) or 'main'
    with ss.edit_config() as conf: conf.git_preferences.default_branch = val
    print()
    sleep(0.3)

def _ask_has_submodules():
    val = inquirer.list_input(message="The repo you're installing into is a", choices=['Monorepo (no submodules)', 'Super-repo (has submodules)'])
    with ss.edit_config() as conf: conf.git_preferences.has_submodules = ('Super-repo' in val)
    print()
    sleep(0.3)

def _ask_git_add_pattern():
    val = inquirer.list_input(message='When choosing what changes to stage and commit from completed tasks, Claude should', choices=['Ask me each time', 'Stage all modified files automatically'])
    with ss.edit_config() as conf: conf.git_preferences.add_pattern = ss.GitAddPattern.ASK if 'Ask' in val else ss.GitAddPattern.ALL
    print()
    sleep(0.3)

def _ask_commit_style():
    val = inquirer.list_input(message="You want Claude's commit messages to be", choices=['Detailed (multi-line with description)', 'Conventional (type: subject format)', 'Simple (single line)'])
    print()
    sleep(0.3)
    with ss.edit_config() as conf:
        if 'Detailed' in val: conf.git_preferences.commit_style = ss.GitCommitStyle.OP
        elif 'Conventional' in val: conf.git_preferences.commit_style = ss.GitCommitStyle.REG
        else: conf.git_preferences.commit_style = ss.GitCommitStyle.SIMP

def _ask_auto_merge():
    print_git_section()
    default_branch = ss.load_config().git_preferences.default_branch
    val = inquirer.list_input(message='During task completion, after comitting changes, Claude should', choices=[f'Auto-merge to {default_branch}', f'Ask me if I want to merge to {default_branch}'])
    with ss.edit_config() as conf: conf.git_preferences.auto_merge = ('Auto-merge' in val)
    print()
    sleep(0.3)

def _ask_auto_push():
    print_git_section()
    val = inquirer.list_input(message='After committing/merging, Claude should', choices=['Auto-push to remote', 'Ask me if I want to push'])
    with ss.edit_config() as conf: conf.git_preferences.auto_push = ('Auto-push' in val)
    print()
    sleep(0.3)
#!<

#!> Environment settings
def _ask_developer_name():
    name = input(color("Claude should call you: ", Colors.CYAN)) or 'developer'
    with ss.edit_config() as conf: conf.environment.developer_name = name
    print()
    sleep(0.3)

def _ask_os():
    os_name = platform.system()
    detected = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'macos'}.get(os_name, 'linux')
    val = inquirer.list_input(
        message=f"Detected OS [{detected.capitalize()}]",
        choices=choices_filtered([
            f'{detected.capitalize()} is correct',
            'Switch to Windows' if detected != 'windows' else None,
            'Switch to macOS' if detected != 'macos' else None,
            'Switch to Linux' if detected != 'linux' else None
        ]),
        default=f'{detected.capitalize()} is correct')
    with ss.edit_config() as conf:
        if 'Windows' in val: conf.environment.os = ss.UserOS.WINDOWS
        elif 'macOS' in val: conf.environment.os = ss.UserOS.MACOS
        elif 'Linux' in val: conf.environment.os = ss.UserOS.LINUX
        else: conf.environment.os = ss.UserOS(detected)
    print()
    sleep(0.3)

def _ask_shell():
    detected_shell = os.environ.get('SHELL', 'bash').split('/')[-1]
    val = inquirer.list_input(
        message=f"Detected shell [{detected_shell}]",
        choices=choices_filtered([
            f'{detected_shell} is correct',
            'Switch to bash' if detected_shell != 'bash' else None,
            'Switch to zsh' if detected_shell != 'zsh' else None,
            'Switch to fish' if detected_shell != 'fish' else None,
            'Switch to powershell' if detected_shell != 'powershell' else None,
            'Switch to cmd' if detected_shell != 'cmd' else None
        ]),
        default=f'{detected_shell} is correct')
    with ss.edit_config() as conf:
        if 'bash' in val: conf.environment.shell = ss.UserShell.BASH
        elif 'zsh' in val: conf.environment.shell = ss.UserShell.ZSH
        elif 'fish' in val: conf.environment.shell = ss.UserShell.FISH
        elif 'powershell' in val: conf.environment.shell = ss.UserShell.POWERSHELL
        elif 'cmd' in val: conf.environment.shell = ss.UserShell.CMD
        else:
            try: conf.environment.shell = ss.UserShell(detected_shell)
            except Exception: conf.environment.shell = ss.UserShell.BASH
    print()
    sleep(0.3)
#!<

#!> Blocked actions
def _edit_bash_read_patterns():

    print(color("In Discussion mode, Claude can only use read-like tools (including commands in",Colors.CYAN))
    print(color("the Bash tool).\n", Colors.CYAN))
    print(color("To do this, we parse Claude's Bash tool input in Discussion mode to check for", Colors.CYAN))
    print(color("write-like and read-only bash commands from a known list.\n",Colors.CYAN))
    print("You might have some CLI commands that you want to mark as \"safe\" to use in")
    print("Discussion mode. For reference, here are the commands we already auto-approve")
    print("in Discussion mode:\n")
    print(color(', '.join(['cat', 'ls', 'pwd', 'cd', 'echo', 'grep', 'find', 'git status', 'git log',]),Colors.YELLOW))
    print(color(', '.join(['git diff', 'docker ps', 'kubectl get', 'npm list', 'pip show', 'head', 'tail',]),Colors.YELLOW))
    print(color(', '.join(['less', 'more', 'file', 'stat', 'du', 'df', 'ps', 'top', 'htop', 'who', 'w',]),Colors.YELLOW))
    print(color('...(70+ commands total)', Colors.YELLOW))
    print()
    print("Type any additional command you would like to auto-allow in Discussion mode and")
    print("hit \"enter\" to add it. You may add as many as you like. When you're done, hit")
    print("enter again to move to the next configuration option:\n")

    custom_read = []
    while True:
        cmd = input(color("> ", Colors.CYAN)).strip()
        if not cmd: break
        custom_read.append(cmd)
        print(color(f"✓ Added '{cmd}' to read-only commands", Colors.GREEN))

    with ss.edit_config() as conf: conf.blocked_actions.bash_read_patterns = custom_read
    print()
    sleep(0.3)

def _edit_bash_write_patterns():

    print(color("Similar to the read-only bash commands, we also check for write-like bash",Colors.CYAN))
    print(color("commands during Discussion mode and block them.\n",Colors.CYAN))
    print("You might have some CLI commands that you want to mark as \"blocked\" in")
    print("Discussion mode. For reference, here are the commands we already block in")
    print("Discussion mode:\n")
    print(color(', '.join(['rm', 'mv', 'cp', 'chmod', 'chown', 'mkdir', 'rmdir', 'systemctl', 'service']),Colors.YELLOW))
    print(color(', '.join(['apt', 'yum', 'npm install', 'pip install', 'make', 'cmake', 'sudo', 'kill']),Colors.YELLOW))
    print(color('...(and more)',Colors.YELLOW))
    print()
    print("Type any additional command you would like blocked in Discussion mode and hit")
    print("\"enter\" to add it. You may add as many as you like. When you're done, hit")
    print("\"enter\" again to move to the next configuration option:\n")

    custom_write = []
    while True:
        cmd = input(color("> ", Colors.CYAN)).strip()
        if not cmd: break
        custom_write.append(cmd)
        print(color(f"✓ Added '{cmd}' to write-like commands", Colors.GREEN))

    with ss.edit_config() as conf: conf.blocked_actions.bash_write_patterns = custom_write
    print()
    sleep(0.3)

def _ask_extrasafe_mode():
    val = inquirer.list_input(message="What if Claude uses a bash command in discussion mode that's not in our\nread-only *or* our write-like list", choices=['Extrasafe OFF (allows unrecognized commands)', 'Extrasafe ON (blocks unrecognized commands)'])
    with ss.edit_config() as conf: conf.blocked_actions.extrasafe = ('ON' in val)
    print()
    sleep(0.3)

def _edit_blocked_tools():

    print("Which Claude Code tools should be blocked in discussion mode?")
    print(color("*Use Space to toggle, Enter to submit*\n", Colors.YELLOW))
    print()
    print(color("NOTE: Write-like Bash commands are already blocked",Colors.YELLOW))

    # Default blocked tools
    default_blocked = ['Edit', 'Write', 'MultiEdit', 'NotebookEdit']
    all_tools = ['Edit', 'Write', 'MultiEdit', 'NotebookEdit', 'Bash', 'Read', 'Glob', 'Grep', 'Task', 'TodoWrite']

    blocked_tools = inquirer.checkbox(
        message="Select tools to BLOCK in discussion mode",
        choices=all_tools,
        default=default_blocked
    )
    with ss.edit_config() as conf:
        conf.blocked_actions.implementation_only_tools = []
        for t in blocked_tools:
            try: conf.blocked_actions.implementation_only_tools.append(ss.CCTools(t))
            except Exception: pass
    print()
    sleep(0.3)
#!<

#!> Trigger phrases
def _customize_triggers() -> bool:
    print("While you can drive cc-sessions using our slash command API, the preferred way")
    print("is with (somewhat) natural language. To achieve this, we use unique trigger")
    print("phrases that automatically activate the 4 protocols and 2 driving modes in")
    print("cc-sessions:\n")
    print(color("╔══════════════════════════════════════════════════════╗", Colors.YELLOW))
    print(f"{color('║',Colors.YELLOW)}  • Switch to implementation mode {colors('(default: \"yert\")',Colors.GREEN)}   {color('║',Colors.YELLOW)}")
    print(f"{color('║',Colors.YELLOW)}  • Switch to discussion mode {colors('(default: \"SILENCE\")',Colors.GREEN)}    {color('║',Colors.YELLOW)}")
    print(f"{color('║',Colors.YELLOW)}  • Create a new task/task file {colors('(default: \"mek:\")',Colors.GREEN)}     {color('║',Colors.YELLOW)}")
    print(f"{color('║',Colors.YELLOW)}  • Start a task/task file {colors('(default: \"start^:\")',Colors.GREEN)}       {color('║',Colors.YELLOW)}")
    print(f"{color('║',Colors.YELLOW)}  • Close/complete current task {colors('(default: \"finito\")',Colors.GREEN)}   {color('║',Colors.YELLOW)}")
    print(f"{color('║',Colors.YELLOW)}  • Compact context mid-task {colors('(default: \"squish\")',Colors.GREEN)}      {color('║',Colors.YELLOW)}")
    print(color("╚══════════════════════════════════════════════════════╝",Colors.YELLOW))

    customize_triggers = inquirer.list_input(
        message="Would you like to add any of your own custom trigger phrases?",
        choices=['Use defaults', 'Customize']
    )

    # Ensure sensible defaults exist in config
    with ss.edit_config() as conf:
        tp = conf.trigger_phrases
        # Only set defaults if lists are empty
        if not getattr(tp, 'implementation_mode', None): tp.implementation_mode = ['yert']
        if not getattr(tp, 'discussion_mode', None): tp.discussion_mode = ['SILENCE']
        if not getattr(tp, 'task_creation', None): tp.task_creation = ['mek:']
        if not getattr(tp, 'task_startup', None): tp.task_startup = ['start^:']
        if not getattr(tp, 'task_completion', None): tp.task_completion = ['finito']
        if not getattr(tp, 'context_compaction', None): tp.context_compaction = ['squish']

    print()
    sleep(0.3)
    return (customize_triggers == 'Customize')


def _edit_triggers_implementation():
    print(color("The implementation mode trigger is used when Claude proposes todos for",Colors.CYAN))
    print(color("implementation that you agree with. Once used, the user_messages hook will",Colors.CYAN))
    print(color("automatically switch the mode to Implementation, notify Claude, and lock in the",Colors.CYAN))
    print(color("proposed todo list to ensure Claude doesn't go rogue.\n",Colors.CYAN))
    print()
    print(color(   "╔════════════════════════════════════════════════════╗", Colors.YELLOW))
    print(f"{color('║', Colors.YELLOW)}  To add your own custom trigger phrase, think of   {color('║', Colors.YELLOW)}")
    print(f"{color('║', Colors.YELLOW)}  something that is:                                {color('║',Colors.YELLOW)}")
    print(f"{color('║                                                    ║',Colors.YELLOW)}")
    print(f"{color('║',Colors.YELLOW)}     • Easy to remember and type                    {color('║',Colors.YELLOW)}")
    print(f"{color('║',Colors.YELLOW)}     • Won't ever come up in regular operation      {color('║',Colors.YELLOW)}")
    print(color("╚════════════════════════════════════════════════════╝",Colors.YELLOW))
    print()
    print(color("We recommend using symbols or uppercase for trigger phrases that may otherwise",Colors.CYAN))
    print(color("be used naturally in conversation (ex. instead of \"stop\", you might use \"STOP\"",Colors.CYAN))
    print(color("or \"st0p\" or \"--stop\").\n",Colors.CYAN))
    print(f"Current phrase: \"yert\"\n")
    print("Type a trigger phrase to add and press \"enter\". When you're done, press \"enter\"")
    print("again to move on to the next step:\n")

    while True:
        phrase = input(color("> ", Colors.CYAN)).strip()
        if not phrase: break
        with ss.edit_config() as conf:
            conf.trigger_phrases.implementation_mode.append(phrase)
        print(color(f"✓ Added '{phrase}'", Colors.GREEN))
    print()
    sleep(0.3)

def _edit_triggers_discussion():
    print(color("The discussion mode trigger is an emergency stop that immediately switches",Colors.CYAN))
    print(color("Claude back to discussion mode. Once used, the user_messages hook will set the",Colors.CYAN))
    print(color("mode to discussion and inform Claude that they need to re-align.\n",Colors.CYAN))
    print(f"Current phrase: \"SILENCE\"\n")
    print('Add discussion mode trigger phrases ("stop phrases"). Press Enter on empty line to finish.\n')
    while True:
        phrase = input(color('> ', Colors.CYAN)).strip()
        if not phrase: break
        with ss.edit_config() as conf: conf.trigger_phrases.discussion_mode.append(phrase)
        print(color(f"✓ Added '{phrase}'", Colors.GREEN))

def _edit_triggers_task_creation():
    print(color("The task creation trigger activates the task creation protocol. Once used, the",Colors.CYAN))
    print(color("user_messages hook will load the task creation protocol which guides Claude",Colors.CYAN))
    print(color("through creating a properly structured task file with priority, success",Colors.CYAN))
    print(color("criteria, and context manifest.\n",Colors.CYAN))
    print(f"Current phrase: \"mek:\"\n")
    print('Add task creation trigger phrases. Press Enter on empty line to finish.\n')
    while True:
        phrase = input(color('> ', Colors.CYAN)).strip()
        if not phrase: break
        with ss.edit_config() as conf: conf.trigger_phrases.task_creation.append(phrase)
        print(color(f"✓ Added '{phrase}'", Colors.GREEN))
    print()
    sleep(0.3)

def _edit_triggers_task_startup():
    print(color("The task startup trigger activates the task startup protocol. Once used, the",Colors.CYAN))
    print(color("user_messages hook will load the task startup protocol which guides Claude",Colors.CYAN))
    print(color("through checking git status, creating branches, gathering context, and",Colors.CYAN))
    print(color("proposing implementation todos.\n",Colors.CYAN))
    print(f"Current phrase: \"start^:\"\n")
    print('Add task startup trigger phrases. Press Enter on empty line to finish.\n')
    while True:
        phrase = input(color('> ', Colors.CYAN)).strip()
        if not phrase: break
        with ss.edit_config() as conf: conf.trigger_phrases.task_startup.append(phrase)
        print(color(f"✓ Added '{phrase}'", Colors.GREEN))

def _edit_triggers_task_completion():
    print(color("The task completion trigger activates the task completion protocol. Once used,",Colors.CYAN))
    print(color("the user_messages hook will load the task completion protocol which guides",Colors.CYAN))
    print(color("Claude through running pre-completion checks, committing changes, merging to",Colors.CYAN))
    print(color("main, and archiving the completed task.\n",Colors.CYAN))
    print(f"Current phrase: \"finito\"\n")
    print('Add task completion trigger phrases. Press Enter on empty line to finish.\n')
    while True:
        phrase = input(color('> ', Colors.CYAN)).strip()
        if not phrase: break
        with ss.edit_config() as conf: conf.trigger_phrases.task_completion.append(phrase)
        print(color(f"✓ Added '{phrase}'", Colors.GREEN))
    print()
    sleep(0.3)

def _edit_triggers_compaction():
    print(color("The context compaction trigger activates the context compaction protocol. Once",Colors.CYAN))
    print(color("used, the user_messages hook will load the context compaction protocol which",Colors.CYAN))
    print(color("guides Claude through running logging and context-refinement agents to preserve",Colors.CYAN))
    print(color("task state before the context window fills up.\n",Colors.CYAN))
    print(f"Current phrase: \"squish\"\n")
    print(color('Add context compaction trigger phrases. Press Enter on empty line to finish.\n', Colors.CYAN))
    while True:
        phrase = input(color('> ', Colors.CYAN)).strip()
        if not phrase: break
        with ss.edit_config() as conf: conf.trigger_phrases.context_compaction.append(phrase)
        print(color(f"✓ Added '{phrase}'", Colors.GREEN))
    print()
    sleep(0.3)
#!<

#!> Feature toggles
def _ask_branch_enforcement():
    print(color("When working on a task, branch enforcement blocks edits to files unless they",Colors.CYAN))
    print(color("are in a repo that is on the task branch. If in a submodule, the submodule",Colors.CYAN))
    print(color("also has to be listed in the task file under the \"submodules\" field.\n",Colors.CYAN))
    print("This prevents Claude from doing silly things with files outside the scope of")
    print("what you're working on, which can happen frighteningly often. But, it may not")
    print("be as flexible as you want. *It also doesn't work well with non-Git VCS*.\n")

    val = inquirer.list_input(message='I want branch enforcement', choices=['Enabled (recommended for git workflows)', 'Disabled (for alternative VCS like Jujutsu)'])
    with ss.edit_config() as conf: conf.features.branch_enforcement = ('Enabled' in val)
    print()
    sleep(0.3)

def _ask_auto_ultrathink():
    print(color("\nAuto-ultrathink adds \"[[ ultrathink ]]\" to *every message* you submit to",Colors.CYAN))
    print(color("Claude Code. This is the most robust way to force maximum thinking for every",Colors.CYAN))
    print(color("message.\n",Colors.CYAN))
    print("If you are not a Claude Max x20 subscriber and/or you are budget-conscious,")
    print("it's recommended that you disable auto-ultrathink and manually trigger thinking")
    print("as needed.\n")
    val = inquirer.list_input(message='Auto-ultrathink', choices=['Enabled', 'Disabled (recommended for budget-conscious users)'])
    with ss.edit_config() as conf: conf.features.auto_ultrathink = (val == 'Enabled')
    print()
    sleep(0.3)

def _ask_nerd_fonts():
    val = inquirer.list_input(message='I want Nerd Fonts icons in statusline', choices=['Enabled (Nerd Fonts installed)', 'Disabled (ASCII fallback)'])
    with ss.edit_config() as conf: conf.features.use_nerd_fonts = (val == 'Enabled')
    print()
    sleep(0.3)

def _ask_context_warnings():
    val = inquirer.list_input(message='I want Claude to be warned to suggest compacting context at', choices=['85% and 90%', '90%', 'Never'])
    with ss.edit_config() as conf:
        if 'and' in val:
            conf.features.context_warnings.warn_85 = True
            conf.features.context_warnings.warn_90 = True
        elif '90' in val:
            conf.features.context_warnings.warn_85 = False
            conf.features.context_warnings.warn_90 = True
        else:
            conf.features.context_warnings.warn_85 = False
            conf.features.context_warnings.warn_90 = False

def _ask_statusline():
    val = inquirer.list_input(message="cc-sessions includes a statusline that shows context usage, current task, mode, and git branch. Would you like to use it?", choices=['Yes, use cc-sessions statusline', 'No, I have my own statusline'])
    if 'Yes' in val:
        settings_file = ss.PROJECT_ROOT / '.claude' / 'settings.json'
        if settings_file.exists(): 
            with open(settings_file, 'r') as f: settings = json.load(f)
        else: settings = {}
        settings['statusLine'] = {'type': 'command', 'command': 'python $CLAUDE_PROJECT_DIR/sessions/statusline.py'}
        with open(settings_file, 'w') as f: json.dump(settings, f, indent=2)
        print(color('✓ Statusline configured in .claude/settings.json', Colors.GREEN))
    else: 
        print(color('\nYou can add the cc-sessions statusline later by adding this to .claude/settings.json:', Colors.YELLOW))
        print(color('{\n  "statusLine": {\n    "type": "command",\n    "command": "python $CLAUDE_PROJECT_DIR/sessions/statusline.py"\n  }\n}', Colors.YELLOW))
    print()
    sleep(0.3)
    return True if 'Yes' in val else False
#!<

##-##

## ===== CONFIG PHASES ===== ##

def run_full_configuration():
    print_config_header()
    cfg = {'git_preferences': {}, 'environment': {}, 'blocked_actions': {}, 'trigger_phrases': {}, 'features': {}}

    #!> Gather git preferences
    print_git_section()
    _ask_default_branch()
    _ask_has_submodules()
    _ask_git_add_pattern()
    _ask_commit_style()
    _ask_auto_merge()
    _ask_auto_push()
    #!<

    #!> Gather environment settings
    print_env_section()
    _ask_developer_name()
    _ask_os()
    _ask_shell()
    #!<

    #!> Gather blocked actions
    print_read_only_section()
    _edit_bash_read_patterns()

    print_write_like_section()
    _edit_bash_write_patterns()

    print_extrasafe_section()
    _ask_extrasafe_mode()

    print_blocking_header()
    _edit_blocked_tools()
    #!<

    #!> Gather trigger phrases
    print_triggers_header()
    wants_customization = _customize_triggers()
    if wants_customization:
        print_go_triggers_section()
        _edit_triggers_implementation()

        print_no_triggers_section()
        _edit_triggers_discussion()

        print_create_section()
        _edit_triggers_task_creation()

        print_startup_section()
        _edit_triggers_task_startup()

        print_complete_section()
        _edit_triggers_task_completion()

        print_compact_section()
        _edit_triggers_compaction()
    #!<

    #!> Ask about statusline
    print_statusline_header()
    statusline_installed = _ask_statusline()
    #!<

    #!> Gather feature toggles
    print_features_header()

    _ask_branch_enforcement()
    _ask_auto_ultrathink()
    if statusline_installed: _ask_nerd_fonts()
    _ask_context_warnings()
    #!<

    print(color('\n✓ Configuration complete!\n', Colors.GREEN))


def run_config_editor(project_root):
    """Interactive config editor"""
    print_config_header()
    print(color('How to use:', Colors.BOLD))
    print('- Use j/k or arrows to navigate, Enter to select')
    print('- Choose Back to return, Done to finish')
    print('- You can also press Ctrl+C to exit anytime')
    print()

    settings_path = project_root / '.claude' / 'settings.json'

    def _statusline_installed() -> bool:
        try:
            data = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
            cmd = (data.get('statusLine') or {}).get('command')
            return bool(cmd and 'sessions/statusline.py' in cmd)
        except Exception: return False

    def _fmt_bool(v: bool) -> str: return 'Enabled' if v else 'Disabled'

    def _fmt_enum(v) -> str:
        try: return getattr(v, 'value', str(v))
        except Exception: return str(v)

    def _fmt_list(xs) -> str:
        try: return ', '.join([x for x in xs if x]) if xs else 'None'
        except Exception: return 'None'

    def _fmt_tools(xs) -> str:
        try: return ', '.join([getattr(x, 'value', str(x)) for x in xs]) if xs else 'None'
        except Exception: return 'None'

    def _reload():
        cfg: ss.SessionsConfig = ss.load_config()
        return cfg, _statusline_installed()

    def _git_menu():
        cfg, _ = _reload()
        g = cfg.git_preferences
        actions = [
            (f"Default branch | {_fmt_enum(g.default_branch)}", _ask_default_branch),
            (f"Has submodules | {_fmt_enum(g.has_submodules)}", _ask_has_submodules),
            (f"Staging pattern | {_fmt_enum(g.add_pattern)}", _ask_git_add_pattern),
            (f"Commit style | {_fmt_enum(g.commit_style)}", _ask_commit_style),
            (f"Auto-merge | {_fmt_enum(g.auto_merge)}", _ask_auto_merge),
            (f"Auto-push | {_fmt_enum(g.auto_push)}", _ask_auto_push),
            (color("Back",Colors.YELLOW), None),
        ]
        labels = [lbl for (lbl, _) in actions]
        while True:
            choice = inquirer.list_input(message='Git Settings', choices=labels)
            if 'Back' in choice: break
            fn = dict(actions).get(choice)
            if fn: fn()
            cfg, _ = _reload()
            g = cfg.git_preferences
            actions[0] = (f"Default branch | {_fmt_enum(g.default_branch)}", _ask_default_branch)
            actions[1] = (f"Has submodules | {_fmt_enum(g.has_submodules)}", _ask_has_submodules)
            actions[2] = (f"Staging pattern | {_fmt_enum(g.add_pattern)}", _ask_git_add_pattern)
            actions[3] = (f"Commit style | {_fmt_enum(g.commit_style)}", _ask_commit_style)
            actions[4] = (f"Auto-merge | {_fmt_enum(g.auto_merge)}", _ask_auto_merge)
            actions[5] = (f"Auto-push | {_fmt_enum(g.auto_push)}", _ask_auto_push)
            labels[:] = [lbl for (lbl, _) in actions]

    def _env_menu():
        cfg, _ = _reload()
        e = cfg.environment
        actions = [
            (f"Developer name | {_fmt_enum(e.developer_name)}", _ask_developer_name),
            (f"Operating system | {_fmt_enum(e.os)}", _ask_os),
            (f"Shell | {_fmt_enum(e.shell)}", _ask_shell),
            (color("Back",Colors.YELLOW), None),
        ]
        labels = [lbl for (lbl, _) in actions]
        while True:
            choice = inquirer.list_input(message='Environment', choices=labels)
            if 'Back' in choice: break
            fn = dict(actions).get(choice)
            if fn: fn()
            cfg, _ = _reload(); e = cfg.environment
            actions[0] = (f"Developer name | {_fmt_enum(e.developer_name)}", _ask_developer_name)
            actions[1] = (f"Operating system | {_fmt_enum(e.os)}", _ask_os)
            actions[2] = (f"Shell | {_fmt_enum(e.shell)}", _ask_shell)
            labels[:] = [lbl for (lbl, _) in actions]

    def _blocked_menu():
        cfg, _ = _reload()
        b = cfg.blocked_actions
        actions = [
            (f"Tools list | {_fmt_tools(b.implementation_only_tools)}", _edit_blocked_tools),
            (f"Bash read-only | {_fmt_list(b.bash_read_patterns)}", _edit_bash_read_patterns),
            (f"Bash write-like | {_fmt_list(b.bash_write_patterns)}", _edit_bash_write_patterns),
            (f"Extrasafe mode | {_fmt_bool(b.extrasafe)}", _ask_extrasafe_mode),
            (color("Back",Colors.YELLOW), None),
        ]
        labels = [lbl for (lbl, _) in actions]
        while True:
            choice = inquirer.list_input(message='Blocked Actions', choices=labels)
            if 'Back' in choice: break
            fn = dict(actions).get(choice)
            if fn: fn()
            cfg, _ = _reload(); b = cfg.blocked_actions
            actions[0] = (f"Tools list | {_fmt_tools(b.implementation_only_tools)}", _edit_blocked_tools)
            actions[1] = (f"Bash read-only | {_fmt_list(b.bash_read_patterns)}", _edit_bash_read_patterns)
            actions[2] = (f"Bash write-like | {_fmt_list(b.bash_write_patterns)}", _edit_bash_write_patterns)
            actions[3] = (f"Extrasafe mode | {_fmt_bool(b.extrasafe)}", _ask_extrasafe_mode)
            labels[:] = [lbl for (lbl, _) in actions]

    def _triggers_menu():
        cfg, _ = _reload(); t = cfg.trigger_phrases
        actions = [
            (f"Implementation mode | {_fmt_list(t.implementation_mode)}", _edit_triggers_implementation),
            (f"Discussion mode | {_fmt_list(t.discussion_mode)}", _edit_triggers_discussion),
            (f"Task creation | {_fmt_list(t.task_creation)}", _edit_triggers_task_creation),
            (f"Task startup | {_fmt_list(t.task_startup)}", _edit_triggers_task_startup),
            (f"Task completion | {_fmt_list(t.task_completion)}", _edit_triggers_task_completion),
            (f"Context compaction | {_fmt_list(t.context_compaction)}", _edit_triggers_compaction),
            (color("Back",Colors.YELLOW), None),
        ]
        labels = [lbl for (lbl, _) in actions]
        while True:
            choice = inquirer.list_input(message='Trigger Phrases', choices=labels)
            if 'Back' in choice: break
            fn = dict(actions).get(choice)
            if fn: fn()
            cfg, _ = _reload(); t = cfg.trigger_phrases
            actions[0] = (f"Implementation mode | {_fmt_list(t.implementation_mode)}", _edit_triggers_implementation)
            actions[1] = (f"Discussion mode | {_fmt_list(t.discussion_mode)}", _edit_triggers_discussion)
            actions[2] = (f"Task creation | {_fmt_list(t.task_creation)}", _edit_triggers_task_creation)
            actions[3] = (f"Task startup | {_fmt_list(t.task_startup)}", _edit_triggers_task_startup)
            actions[4] = (f"Task completion | {_fmt_list(t.task_completion)}", _edit_triggers_task_completion)
            actions[5] = (f"Context compaction | {_fmt_list(t.context_compaction)}", _edit_triggers_compaction)
            labels[:] = [lbl for (lbl, _) in actions]

    def _features_menu():
        cfg, installed = _reload(); f = cfg.features
        cw = []
        if getattr(f.context_warnings, 'warn_85', False): cw.append('85%')
        if getattr(f.context_warnings, 'warn_90', False): cw.append('90%')
        cw_str = ', '.join(cw) if cw else 'Never'

        actions = [
            (f"Statusline integration | {'Installed' if installed else 'Not installed'}", _ask_statusline),
            (f"Branch enforcement | {_fmt_bool(f.branch_enforcement)}", _ask_branch_enforcement),
            (f"Auto-ultrathink | {_fmt_bool(f.auto_ultrathink)}", _ask_auto_ultrathink),
            (f"Nerd Fonts | {_fmt_bool(f.use_nerd_fonts)}", _ask_nerd_fonts) if installed else None,
            (f"Context warnings | {cw_str}", _ask_context_warnings),
            (color("Back",Colors.YELLOW), None),
        ]
        actions = [a for a in actions if a]
        labels = [lbl for (lbl, _) in actions]
        while True:
            choice = inquirer.list_input(message='Features', choices=labels)
            if 'Back' in choice: break
            fn = dict(actions).get(choice)
            if fn: fn()
            cfg, installed = _reload(); f = cfg.features
            cw = []
            if getattr(f.context_warnings, 'warn_85', False): cw.append('85%')
            if getattr(f.context_warnings, 'warn_90', False): cw.append('90%')
            cw_str = ', '.join(cw) if cw else 'Never'
            actions = [
                (f"Statusline integration | {'Installed' if installed else 'Not installed'}", _ask_statusline),
                (f"Branch enforcement | {_fmt_bool(f.branch_enforcement)}", _ask_branch_enforcement),
                (f"Auto-ultrathink | {_fmt_bool(f.auto_ultrathink)}", _ask_auto_ultrathink),
                (f"Nerd Fonts | {_fmt_bool(f.use_nerd_fonts)}", _ask_nerd_fonts) if installed else None,
                (f"Context warnings | {cw_str}", _ask_context_warnings),
                (color("Back",Colors.YELLOW), None),
            ]
            actions = [a for a in actions if a]
            labels[:] = [lbl for (lbl, _) in actions]

    # (statusline menu removed; statusline now part of Features)

    # Main menu: grouped categories to avoid long scrolling
    while True:
        try:
            choice = inquirer.list_input(
                message='Config Editor — choose a category',
                choices=['Git', 'Environment', 'Blocked Actions', 'Trigger Phrases', 'Features', color('Done',Colors.RED)])
        except KeyboardInterrupt: break

        if 'Done' in choice: break
        elif choice == 'Git': _git_menu()
        elif choice == 'Environment': _env_menu()
        elif choice == 'Blocked Actions': _blocked_menu()
        elif choice == 'Trigger Phrases': _triggers_menu()
        elif choice == 'Features': _features_menu()
        else: continue # Shouldn't happen, but continue gracefully
##-##

## ===== IMPORT CONFIG ===== ##
def import_config(project_root: Path, source: str, source_type: str) -> bool:
    """Import configuration and selected agents from a local dir, Git URL, or GitHub stub.
    Returns True on success (config or any agent imported).
    """
    tmp_to_remove: Path | None = None
    imported_any = False
    try:
        # Resolve source to a local directory path
        if source_type == 'GitHub stub (owner/repo)':
            owner_repo = source.strip().strip('/')
            url = f"https://github.com/{owner_repo}.git"
            tmp_to_remove = Path(tempfile.mkdtemp(prefix='ccs-import-'))
            try: subprocess.run(['git', 'clone', '--depth', '1', url, str(tmp_to_remove)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except Exception as e:
                print(color(f'Git clone failed for {url}: {e}', Colors.RED))
                return False
            src_path = tmp_to_remove
        elif source_type == 'Git repository URL':
            url = source.strip()
            tmp_to_remove = Path(tempfile.mkdtemp(prefix='ccs-import-'))
            try: subprocess.run(['git', 'clone', '--depth', '1', url, str(tmp_to_remove)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except Exception as e:
                print(color(f'Git clone failed for {url}: {e}', Colors.RED))
                return False
            src_path = tmp_to_remove
        else:
            # Local directory
            src_path = Path(source).expanduser().resolve()
            if not src_path.exists() or not src_path.is_dir():
                print(color('Provided path does not exist or is not a directory.', Colors.RED))
                return False

        # sessions-config.json from repo_root/sessions/
        src_cfg = (src_path / 'sessions' / 'sessions-config.json')
        dst_cfg = (project_root / 'sessions' / 'sessions-config.json')
        if src_cfg.exists():
            dst_cfg.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_cfg, dst_cfg)
            print(color('✓ Imported sessions-config.json', Colors.GREEN))
            imported_any = True
        else: print(color('No sessions-config.json found to import at sessions/sessions-config.json', Colors.YELLOW))

        # Agents: present baseline agent files for choice
        src_agents = src_path / '.claude' / 'agents'
        dst_agents = project_root / '.claude' / 'agents'
        if src_agents.exists():
            for agent_name in AGENT_BASELINE:
                src_file = src_agents / agent_name
                dst_file = dst_agents / agent_name
                if src_file.exists():
                    choice = inquirer.list_input(
                        message=f"Agent '{agent_name}' found in import. Which version to keep?",
                        choices=['Use imported version', 'Keep default']
                    )
                    if choice == 'Use imported version':
                        dst_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_file, dst_file)
                        print(color(f"✓ Imported agent: {agent_name}", Colors.GREEN))
                        imported_any = True
        else: print(color('No .claude/agents directory found to import agents from', Colors.YELLOW))

        # Reload config/state
        setup_shared_state_and_initialize(project_root)
        return imported_any
    except Exception as e:
        print(color(f'Import failed: {e}', Colors.RED))
        return False
    finally:
        if tmp_to_remove is not None:
            with contextlib.suppress(Exception): shutil.rmtree(tmp_to_remove)

def kickstart_decision(project_root: Path) -> str:
    """Prompt user for kickstart onboarding preference and set state/cleanup accordingly.
    Returns one of: 'full', 'subagents', 'skip'.
    """
    print_kickstart_header()

    print("cc-sessions is an opinionated interactive workflow. You can learn how to use")
    print("it with Claude Code via a custom \"session\" called kickstart.\n")
    print("Kickstart will:")
    print("  • Teach you the features of cc-sessions")
    print("  • Help you set up your first task")
    print("  • Show the 4 core protocols you can run")
    print("  • Help customize subagents for your codebase\n")
    print("Time: 15–30 minutes\n")

    choice = inquirer.list_input(
        message="Would you like to run kickstart on your first session?",
        choices=[
            'Yes (auto-start full kickstart tutorial)',
            'Just subagents (customize subagents but skip tutorial)',
            'No (skip tutorial, remove kickstart files)'
        ]
    )

    if 'Yes' in choice:
        with ss.edit_state() as s: s.metadata['kickstart'] = {'mode': 'full'}
        print(color('\n✓ Kickstart will auto-start on your first session', Colors.GREEN))
        return 'full'

    if 'Just subagents' in choice:
        with ss.edit_state() as s: s.metadata['kickstart'] = {'mode': 'subagents'}
        print(color('\n✓ Kickstart will guide you through subagent customization only', Colors.GREEN))
        return 'subagents'

    # Skip
    print(color('\n⏭️  Skipping kickstart onboarding...', Colors.CYAN))
    kickstart_cleanup(project_root)
    print(color('\n✓ Kickstart files removed', Colors.GREEN))
    return 'skip'
##-##

#-#

# ===== ENTRYPOINT ===== #
def main():
    global ss
    SCRIPT_DIR = get_package_root()
    PROJECT_ROOT = get_project_root()

    #!> Check if already installed and backup if needed
    sessions_dir = PROJECT_ROOT / 'sessions'
    backup_dir = None

    if sessions_dir.exists():
        # Check if there's actual content to preserve
        tasks_dir = sessions_dir / 'tasks'
        has_content = tasks_dir.exists() and any(tasks_dir.rglob('*.md'))

        if not has_content: print(color('🆕 Detected empty sessions directory, treating as fresh install', Colors.CYAN))
        else: print(color('🔍 Detected existing cc-sessions installation', Colors.CYAN)); backup_dir = create_backup(PROJECT_ROOT)
    #!<

    print(color(f'\n⚙️  Installing cc-sessions to: {PROJECT_ROOT}', Colors.CYAN))
    print()

    try:
        # Phase: install files
        create_directory_structure(PROJECT_ROOT)
        copy_files(SCRIPT_DIR, PROJECT_ROOT)
        configure_settings(PROJECT_ROOT)
        configure_claude_md(PROJECT_ROOT)
        configure_gitignore(PROJECT_ROOT)

        # Phase: load shared state and initialize defaults
        setup_shared_state_and_initialize(PROJECT_ROOT)

        # Phase: decision point (import vs full config)
        did_import = installer_decision_flow(PROJECT_ROOT)

        # Phase: configuration
        if did_import: run_config_editor(PROJECT_ROOT) # Present config editor so user can tweak imported settings
        else: run_full_configuration()

        # Phase: kickstart decision
        kickstart_mode = kickstart_decision(PROJECT_ROOT)
        
        # Restore tasks if this was an update
        if backup_dir:
            restore_tasks(PROJECT_ROOT, backup_dir)
            print(color(f'\n📁 Backup saved at: {backup_dir.relative_to(PROJECT_ROOT)}/', Colors.CYAN))
            print(color('   (Agents backed up for manual restoration if needed)', Colors.CYAN))

        # Output final message
        print(color('\n✅ cc-sessions installed successfully!\n', Colors.GREEN))
        print(color('Next steps:', Colors.BOLD))
        print('  1. Restart your Claude Code session (or run /clear)')

        if kickstart_mode == 'full':
            print('  2. The kickstart onboarding will guide you through setup\n')
        elif kickstart_mode == 'subagents':
            print('  2. Kickstart will guide you through subagent customization\n')
        else:  # skip
            print('  2. You can start using cc-sessions right away!')
            print('     - Try "mek: my first task" to create a task')
            print('     - Type "help" to see available commands\n')

        if backup_dir: print(color('Note: Check backup/ for any custom agents you want to restore\n', Colors.CYAN))


    except Exception as error:
        print(color(f'\n❌ Installation failed: {error}', Colors.RED), file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def installer_decision_flow(project_root):
    """
    Decision point: detect returning users and optionally import config/agents.
    Returns True if a config import occurred and succeeded.
    """
    print_installer_header()

    did_import = False
    first_time = inquirer.list_input(message="Is this your first time using cc-sessions?", choices=['Yes', 'No'])

    if first_time == 'No':
        version_check = inquirer.list_input(
            message="Have you used cc-sessions v0.3.0 or later (released October 2025)?",
            choices=['Yes', 'No']
        )
        if version_check == 'Yes':
            import_choice = inquirer.list_input(
                message="Would you like to import your configuration and agents?",
                choices=['Yes', 'No']
            )
            if import_choice == 'Yes':
                import_source = inquirer.list_input(
                    message="Where is your cc-sessions configuration?",
                    choices=['Local directory', 'Git repository URL', 'GitHub stub (owner/repo)', 'Skip import']
                )
                if import_source != 'Skip import':
                    source_path = input(color("Path or URL: ", Colors.CYAN)).strip()
                    did_import = import_config(project_root, source_path, import_source)
                    if not did_import:
                        print(color('\nImport failed or not implemented. Continuing with configuration...', Colors.YELLOW))
                else:
                    print(color('\nSkipping import. Continuing with configuration...', Colors.CYAN))
            else:
                print(color('\nContinuing with configuration...', Colors.CYAN))
        else:
            print(color('\nContinuing with configuration...', Colors.CYAN))

    return did_import

#-#

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(color(f'\n❌ Fatal error: {error}', Colors.RED), file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
#-#

# Enter and set global, SCRIPT_DIR, and PROJECT_ROOT
# Check for previous installation, throw to backup if needed
