#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');
const inquirer = require('inquirer');

// Colors for terminal output
const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  cyan: '\x1b[36m',
  bold: '\x1b[1m'
};

function color(text, colorCode) {
  return `${colorCode}${text}${colors.reset}`;
}

// Determine package and project root
const SCRIPT_DIR = __dirname;
const PROJECT_ROOT = process.cwd();

async function main() {
  console.log(color('\n╔════════════════════════════════════════════════════════════════╗', colors.cyan));
  console.log(color('║         CC-SESSIONS INSTALLER (JavaScript Edition)            ║', colors.cyan));
  console.log(color('╚════════════════════════════════════════════════════════════════╝\n', colors.cyan));

  // Check if already installed and backup if needed
  const sessionsDir = path.join(PROJECT_ROOT, 'sessions');
  let backupDir = null;

  if (fs.existsSync(sessionsDir)) {
    // Check if there's actual content to preserve
    const tasksDir = path.join(sessionsDir, 'tasks');
    let hasContent = false;
    if (fs.existsSync(tasksDir)) {
      const checkContent = (dir) => {
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        for (const entry of entries) {
          if (entry.isDirectory()) {
            if (checkContent(path.join(dir, entry.name))) return true;
          } else if (entry.name.endsWith('.md')) {
            return true;
          }
        }
        return false;
      };
      hasContent = checkContent(tasksDir);
    }

    if (!hasContent) {
      console.log(color('🆕 Detected empty sessions directory, treating as fresh install', colors.cyan));
    } else {
      console.log(color('🔍 Detected existing cc-sessions installation', colors.cyan));
      backupDir = createBackup(PROJECT_ROOT);
    }
  }

  console.log(color('\n⚙️  Installing cc-sessions to: ' + PROJECT_ROOT, colors.cyan));
  console.log();

  try {
    // Create directory structure
    createDirectoryStructure();

    // Copy shared files
    copySharedFiles();

    // Copy JavaScript-specific files
    copyJavaScriptFiles();

    // Configure .claude/settings.json
    await configureSettings();

    // Add reference to CLAUDE.md
    configureCLAUDEmd();

    // Configure .gitignore
    configureGitignore();

    // Initialize state and config files
    initializeStateFiles();

    // Run installer decision flow (first-time detection, config, kickstart)
    const kickstartMode = await installerDecisionFlow();

    // Restore tasks if this was an update
    if (backupDir) {
      restoreTasks(PROJECT_ROOT, backupDir);
      const relPath = path.relative(PROJECT_ROOT, backupDir);
      console.log(color(`\n📁 Backup saved at: ${relPath}/`, colors.cyan));
      console.log(color('   (Agents backed up for manual restoration if needed)', colors.cyan));
    }

    console.log(color('\n✅ cc-sessions installed successfully!\n', colors.green));
    console.log(color('Next steps:', colors.bold));
    console.log('  1. Restart your Claude Code session (or run /clear)');

    if (kickstartMode === 'full') {
      console.log('  2. The kickstart onboarding will guide you through setup\n');
    } else if (kickstartMode === 'subagents') {
      console.log('  2. Kickstart will guide you through subagent customization\n');
    } else {  // skip
      console.log('  2. You can start using cc-sessions right away!');
      console.log('     - Try "mek: my first task" to create a task');
      console.log('     - Type "help" to see available commands\n');
    }

    if (backupDir) {
      console.log(color('Note: Check backup/ for any custom agents you want to restore\n', colors.cyan));
    }

  } catch (error) {
    console.error(color('\n❌ Installation failed:', colors.red), error.message);
    console.error(error.stack);
    process.exit(1);
  }
}

function createDirectoryStructure() {
  console.log(color('Creating directory structure...', colors.cyan));

  const dirs = [
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
  ];

  for (const dir of dirs) {
    const fullPath = path.join(PROJECT_ROOT, dir);
    if (!fs.existsSync(fullPath)) {
      fs.mkdirSync(fullPath, { recursive: true });
    }
  }
}

function copySharedFiles() {
  console.log(color('Installing shared files...', colors.cyan));

  // Copy agents
  const agentsSource = path.join(SCRIPT_DIR, 'cc_sessions', 'agents');
  const agentsDest = path.join(PROJECT_ROOT, '.claude', 'agents');
  if (fs.existsSync(agentsSource)) {
    copyDirectory(agentsSource, agentsDest);
  }

  // Copy knowledge base
  const knowledgeSource = path.join(SCRIPT_DIR, 'cc_sessions', 'knowledge');
  const knowledgeDest = path.join(PROJECT_ROOT, 'sessions', 'knowledge');
  if (fs.existsSync(knowledgeSource)) {
    copyDirectory(knowledgeSource, knowledgeDest);
  }
}

function copyJavaScriptFiles() {
  console.log(color('Installing JavaScript-specific files...', colors.cyan));

  const jsRoot = path.join(SCRIPT_DIR, 'cc_sessions', 'javascript');

  // Copy statusline
  copyFile(
    path.join(jsRoot, 'statusline.js'),
    path.join(PROJECT_ROOT, 'sessions', 'statusline.js')
  );

  // Copy API
  copyDirectory(
    path.join(jsRoot, 'api'),
    path.join(PROJECT_ROOT, 'sessions', 'api')
  );

  // Copy hooks
  copyDirectory(
    path.join(jsRoot, 'hooks'),
    path.join(PROJECT_ROOT, 'sessions', 'hooks')
  );

  // Copy protocols from shared directory
  copyDirectory(
    path.join(SCRIPT_DIR, 'cc_sessions', 'protocols'),
    path.join(PROJECT_ROOT, 'sessions', 'protocols')
  );

  // Copy commands from shared directory
  copyDirectory(
    path.join(SCRIPT_DIR, 'cc_sessions', 'commands'),
    path.join(PROJECT_ROOT, '.claude', 'commands')
  );

  // Copy templates from shared directory to their respective destinations
  const templatesDir = path.join(SCRIPT_DIR, 'cc_sessions', 'templates');

  copyFile(
    path.join(templatesDir, 'CLAUDE.sessions.md'),
    path.join(PROJECT_ROOT, 'sessions', 'CLAUDE.sessions.md')
  );

  copyFile(
    path.join(templatesDir, 'TEMPLATE.md'),
    path.join(PROJECT_ROOT, 'sessions', 'tasks', 'TEMPLATE.md')
  );

  copyFile(
    path.join(templatesDir, 'h-kickstart-setup.md'),
    path.join(PROJECT_ROOT, 'sessions', 'tasks', 'h-kickstart-setup.md')
  );

  copyFile(
    path.join(templatesDir, 'INDEX_TEMPLATE.md'),
    path.join(PROJECT_ROOT, 'sessions', 'tasks', 'indexes', 'INDEX_TEMPLATE.md')
  );
}

async function configureSettings() {
  console.log(color('Configuring Claude Code hooks...', colors.cyan));

  const settingsPath = path.join(PROJECT_ROOT, '.claude', 'settings.json');
  let settings = {};

  // Load existing settings if they exist
  if (fs.existsSync(settingsPath)) {
    try {
      settings = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'));
    } catch (error) {
      console.log(color('⚠️  Could not parse existing settings.json, will create new one', colors.yellow));
    }
  }

  // Define sessions hooks
  const sessionsHooks = {
    UserPromptSubmit: [
      {
        hooks: [
          {
            type: "command",
            command: process.platform === 'win32'
              ? "node \"%CLAUDE_PROJECT_DIR%\\sessions\\hooks\\user_messages.js\""
              : "node $CLAUDE_PROJECT_DIR/sessions/hooks/user_messages.js"
          }
        ]
      }
    ],
    PreToolUse: [
      {
        matcher: "Write|Edit|MultiEdit|Task|Bash",
        hooks: [
          {
            type: "command",
            command: process.platform === 'win32'
              ? "node \"%CLAUDE_PROJECT_DIR%\\sessions\\hooks\\sessions_enforce.js\""
              : "node $CLAUDE_PROJECT_DIR/sessions/hooks/sessions_enforce.js"
          }
        ]
      },
      {
        matcher: "Task",
        hooks: [
          {
            type: "command",
            command: process.platform === 'win32'
              ? "node \"%CLAUDE_PROJECT_DIR%\\sessions\\hooks\\subagent_hooks.js\""
              : "node $CLAUDE_PROJECT_DIR/sessions/hooks/subagent_hooks.js"
          }
        ]
      }
    ],
    PostToolUse: [
      {
        hooks: [
          {
            type: "command",
            command: process.platform === 'win32'
              ? "node \"%CLAUDE_PROJECT_DIR%\\sessions\\hooks\\post_tool_use.js\""
              : "node $CLAUDE_PROJECT_DIR/sessions/hooks/post_tool_use.js"
          }
        ]
      }
    ],
    SessionStart: [
      {
        matcher: "startup|clear",
        hooks: [
          {
            type: "command",
            command: process.platform === 'win32'
              ? "node \"%CLAUDE_PROJECT_DIR%\\sessions\\hooks\\session_start.js\""
              : "node $CLAUDE_PROJECT_DIR/sessions/hooks/session_start.js"
          }
        ]
      }
    ]
  };

  // Initialize hooks object if it doesn't exist
  if (!settings.hooks) {
    settings.hooks = {};
  }

  // Merge each hook type (sessions hooks take precedence)
  for (const [hookType, hookConfig] of Object.entries(sessionsHooks)) {
    if (!settings.hooks[hookType]) {
      settings.hooks[hookType] = [];
    }

    // Add sessions hooks (prepend so they run first)
    settings.hooks[hookType] = [...hookConfig, ...settings.hooks[hookType]];
  }

  // Write updated settings
  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
}

function configureCLAUDEmd() {
  console.log(color('Configuring CLAUDE.md...', colors.cyan));

  const claudePath = path.join(PROJECT_ROOT, 'CLAUDE.md');
  const reference = '@sessions/CLAUDE.sessions.md';

  if (fs.existsSync(claudePath)) {
    let content = fs.readFileSync(claudePath, 'utf-8');

    // Only add if not already present
    if (!content.includes(reference)) {
      // Add at the beginning after any frontmatter
      const lines = content.split('\n');
      let insertIndex = 0;

      // Skip frontmatter if it exists
      if (lines[0] === '---') {
        for (let i = 1; i < lines.length; i++) {
          if (lines[i] === '---') {
            insertIndex = i + 1;
            break;
          }
        }
      }

      lines.splice(insertIndex, 0, '', reference, '');
      content = lines.join('\n');
      fs.writeFileSync(claudePath, content);
    }
  } else {
    // Create minimal CLAUDE.md with reference
    const minimalCLAUDE = `# CLAUDE.md

${reference}

This file provides instructions for Claude Code when working with this codebase.
`;
    fs.writeFileSync(claudePath, minimalCLAUDE);
  }
}

function configureGitignore() {
  console.log(color('Configuring .gitignore...', colors.cyan));

  const gitignorePath = path.join(PROJECT_ROOT, '.gitignore');
  const gitignoreEntries = [
    '',
    '# cc-sessions runtime files',
    'sessions/sessions-state.json',
    'sessions/transcripts/',
    ''
  ];

  if (fs.existsSync(gitignorePath)) {
    let content = fs.readFileSync(gitignorePath, 'utf-8');

    // Only add if not already present
    if (!content.includes('sessions/sessions-state.json')) {
      // Append to end of file
      content += gitignoreEntries.join('\n');
      fs.writeFileSync(gitignorePath, content);
    }
  } else {
    // Create new .gitignore with our entries
    fs.writeFileSync(gitignorePath, gitignoreEntries.join('\n'));
  }
}

function initializeStateFiles() {
  console.log(color('Initializing state files...', colors.cyan));

  // Set environment variable so shared_state can find project root
  process.env.CLAUDE_PROJECT_DIR = PROJECT_ROOT;

  // Import and call loadState/loadConfig from shared_state
  const sharedStatePath = path.join(PROJECT_ROOT, 'sessions', 'hooks', 'shared_state.js');

  if (!fs.existsSync(sharedStatePath)) {
    console.log(color('⚠️  Could not find shared_state.js after installation', colors.yellow));
    process.exit(1);
  }

  const { loadState, loadConfig, editConfig } = require(sharedStatePath);

  // These functions create the files if they don't exist
  loadState();
  loadConfig();

  // Detect and set OS in configuration using editConfig callback
  const osType = os.platform();  // Returns 'win32', 'linux', or 'darwin'
  const osMap = {
    'win32': 'windows',
    'linux': 'linux',
    'darwin': 'macos'
  };
  const detectedOs = osMap[osType] || 'linux';  // Default to linux if unknown

  // Update config with detected OS using editConfig callback
  editConfig((config) => {
    config.environment.os = detectedOs;
  });

  // Verify files were created
  const stateFile = path.join(PROJECT_ROOT, 'sessions', 'sessions-state.json');
  const configFile = path.join(PROJECT_ROOT, 'sessions', 'sessions-config.json');

  if (!fs.existsSync(stateFile) || !fs.existsSync(configFile)) {
    console.log(color('⚠️  State files were not created properly', colors.yellow));
    console.log(color('You may need to initialize them manually on first run', colors.yellow));
  }
}

function kickstartCleanup() {
  console.log(color('\n🧹 Removing kickstart files...', colors.cyan));

  const sessionsDir = path.join(PROJECT_ROOT, 'sessions');

  // 1. Delete kickstart hook (check both language variants)
  const pyHook = path.join(sessionsDir, 'hooks', 'kickstart_session_start.py');
  const jsHook = path.join(sessionsDir, 'hooks', 'kickstart_session_start.js');

  let isPython;
  if (fs.existsSync(pyHook)) {
    fs.unlinkSync(pyHook);
    isPython = true;
    console.log(color('   ✓ Deleted kickstart_session_start.py', colors.green));
  } else if (fs.existsSync(jsHook)) {
    fs.unlinkSync(jsHook);
    isPython = false;
    console.log(color('   ✓ Deleted kickstart_session_start.js', colors.green));
  } else {
    isPython = true; // default fallback
  }

  // 2. Delete kickstart protocols directory
  const protocolsDir = path.join(sessionsDir, 'protocols', 'kickstart');
  if (fs.existsSync(protocolsDir)) {
    fs.rmSync(protocolsDir, { recursive: true, force: true });
    console.log(color('   ✓ Deleted protocols/kickstart/', colors.green));
  }

  // 3. Delete kickstart setup task
  const taskFile = path.join(sessionsDir, 'tasks', 'h-kickstart-setup.md');
  if (fs.existsSync(taskFile)) {
    fs.unlinkSync(taskFile);
    console.log(color('   ✓ Deleted h-kickstart-setup.md', colors.green));
  }

  // Generate language-specific cleanup instructions
  let instructions;
  if (isPython) {
    instructions = `
Manual cleanup required (edit these files carefully):

1. sessions/api/router.py
   - Remove: from .kickstart_commands import handle_kickstart_command
   - Remove: 'kickstart': handle_kickstart_command from COMMAND_HANDLERS

2. .claude/settings.json
   - Remove the kickstart SessionStart hook entry

3. sessions/api/kickstart_commands.py
   - Delete this entire file
`;
  } else {
    instructions = `
Manual cleanup required (edit these files carefully):

1. sessions/api/router.js
   - Remove: const { handleKickstartCommand } = require('./kickstart_commands');
   - Remove: 'kickstart': handleKickstartCommand from COMMAND_HANDLERS

2. .claude/settings.json
   - Remove the kickstart SessionStart hook entry

3. sessions/api/kickstart_commands.js
   - Delete this entire file
`;
  }

  console.log(color(instructions, colors.yellow));
  return instructions;
}

function getReadonlyCommandsList() {
  return [
    'cat', 'ls', 'pwd', 'cd', 'echo', 'grep', 'find', 'git status', 'git log',
    'git diff', 'docker ps', 'kubectl get', 'npm list', 'pip show', 'head', 'tail',
    'less', 'more', 'file', 'stat', 'du', 'df', 'ps', 'top', 'htop', 'who', 'w',
    '...(70+ commands total)'
  ];
}

function getWriteCommandsList() {
  return [
    'rm', 'mv', 'cp', 'chmod', 'chown', 'mkdir', 'rmdir', 'systemctl', 'service',
    'apt', 'yum', 'npm install', 'pip install', 'make', 'cmake', 'sudo', 'kill',
    '...(and more)'
  ];
}

async function interactiveConfiguration() {
  console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
  console.log(color('  Configuration Setup', colors.bold));
  console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));

  const config = {
    git_preferences: {},
    environment: {},
    blocked_actions: {
      implementation_only_tools: [],
      bash_read_patterns: [],
      bash_write_patterns: []
    },
    trigger_phrases: {},
    features: {}
  };

  // Git Preferences Section
  console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
  console.log(color('  Git Preferences', colors.bold));
  console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));

  console.log("Default branch name (e.g. 'main', 'master', 'develop', etc.):");
  console.log(color("*This is the branch you will merge to when completing tasks*", colors.yellow));
  const defaultBranchAnswer = await inquirer.prompt([{
    type: 'input',
    name: 'value',
    message: color('[main] ', colors.cyan),
    default: 'main'
  }]);
  config.git_preferences.default_branch = defaultBranchAnswer.value || 'main';

  const hasSubmodules = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: 'Does this repository use git submodules?',
    choices: ['Yes', 'No'],
    default: 'Yes'
  }]);
  config.git_preferences.has_submodules = (hasSubmodules.value === 'Yes');

  const addPattern = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: 'When committing, how should files be staged?',
    choices: [
      'Ask me each time',
      'Stage all modified files automatically'
    ]
  }]);
  config.git_preferences.add_pattern = addPattern.value.includes('Ask') ? 'ask' : 'all';

  const commitStyle = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: 'Commit message style:',
    choices: [
      'Detailed (multi-line with description)',
      'Conventional (type: subject format)',
      'Simple (single line)'
    ]
  }]);
  if (commitStyle.value.includes('Detailed')) {
    config.git_preferences.commit_style = 'detailed';
  } else if (commitStyle.value.includes('Conventional')) {
    config.git_preferences.commit_style = 'conventional';
  } else {
    config.git_preferences.commit_style = 'simple';
  }

  const autoMerge = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: 'After task completion:',
    choices: [
      'Ask me first',
      `Auto-merge to ${config.git_preferences.default_branch}`
    ]
  }]);
  config.git_preferences.auto_merge = autoMerge.value.includes('Auto-merge');

  const autoPush = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: 'After committing/merging:',
    choices: [
      'Ask me first',
      'Auto-push to remote'
    ]
  }]);
  config.git_preferences.auto_push = autoPush.value.includes('Auto-push');

  // Environment Section
  console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
  console.log(color('  Environment Settings', colors.bold));
  console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));

  const developerName = await inquirer.prompt([{
    type: 'input',
    name: 'value',
    message: color('What should Claude call you? [developer] ', colors.cyan),
    default: 'developer'
  }]);
  config.environment.developer_name = developerName.value || 'developer';

  // Detect OS
  const osType = os.platform();
  const osMap = { 'win32': 'windows', 'linux': 'linux', 'darwin': 'macos' };
  const detectedOs = osMap[osType] || 'linux';

  const osChoices = [
    `${detectedOs.charAt(0).toUpperCase() + detectedOs.slice(1)} is correct`
  ];
  if (detectedOs !== 'windows') osChoices.push('Switch to Windows');
  if (detectedOs !== 'macos') osChoices.push('Switch to macOS');
  if (detectedOs !== 'linux') osChoices.push('Switch to Linux');

  const osChoice = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: `Detected OS: ${detectedOs.charAt(0).toUpperCase() + detectedOs.slice(1)}`,
    choices: osChoices,
    default: osChoices[0]
  }]);

  if (osChoice.value.includes('Windows')) {
    config.environment.os = 'windows';
  } else if (osChoice.value.includes('macOS')) {
    config.environment.os = 'macos';
  } else if (osChoice.value.includes('Linux')) {
    config.environment.os = 'linux';
  } else {
    config.environment.os = detectedOs;
  }

  // Detect shell
  const detectedShell = (process.env.SHELL || 'bash').split('/').pop();

  const shellChoices = [
    `${detectedShell} is correct`
  ];
  const shells = ['bash', 'zsh', 'fish', 'powershell', 'cmd'];
  shells.forEach(shell => {
    if (shell !== detectedShell) {
      shellChoices.push(`Switch to ${shell}`);
    }
  });

  const shellChoice = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: `Detected shell: ${detectedShell}`,
    choices: shellChoices,
    default: shellChoices[0]
  }]);

  for (const shell of shells) {
    if (shellChoice.value.toLowerCase().includes(shell)) {
      config.environment.shell = shell;
      break;
    }
  }
  if (!config.environment.shell) {
    config.environment.shell = detectedShell;
  }

  // Blocked Actions Section
  console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
  console.log(color('  Tool Blocking Configuration', colors.bold));
  console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));

  console.log('Which tools should be blocked in discussion mode?');
  console.log(color('*Use Space to toggle, Enter to submit*\n', colors.yellow));

  const defaultBlocked = ['Edit', 'Write', 'MultiEdit', 'NotebookEdit'];
  const allTools = ['Edit', 'Write', 'MultiEdit', 'NotebookEdit', 'Bash', 'Read', 'Glob', 'Grep', 'Task', 'TodoWrite'];

  const blockedTools = await inquirer.prompt([{
    type: 'checkbox',
    name: 'value',
    message: 'Select tools to BLOCK in discussion mode',
    choices: allTools,
    default: defaultBlocked
  }]);
  config.blocked_actions.implementation_only_tools = blockedTools.value;

  // Bash patterns - Read-only
  console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
  console.log(color('  Read-Only Bash Commands', colors.bold));
  console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));

  console.log('In Discussion mode, Claude can only use read-like tools (including commands in');
  console.log('the Bash tool).\n');
  console.log('To do this, we parse Claude\'s Bash tool input in Discussion mode to check for');
  console.log('write-like and read-only bash commands from a known list.\n');
  console.log('You might have some CLI commands that you want to mark as "safe" to use in');
  console.log('Discussion mode. For reference, here are the commands we already auto-approve');
  console.log('in Discussion mode:\n');
  console.log(color(`  ${getReadonlyCommandsList().join(', ')}\n`, colors.yellow));
  console.log('Type any additional command you would like to auto-allow in Discussion mode and');
  console.log('hit "enter" to add it. You may add as many as you like. When you\'re done, hit');
  console.log('enter again to move to the next configuration option:\n');

  const customRead = [];
  while (true) {
    const answer = await inquirer.prompt([{
      type: 'input',
      name: 'value',
      message: color('> ', colors.cyan)
    }]);
    const cmd = answer.value.trim();
    if (!cmd) break;
    customRead.push(cmd);
    console.log(color(`✓ Added '${cmd}' to read-only commands`, colors.green));
  }
  config.blocked_actions.bash_read_patterns = customRead;

  // Bash patterns - Write-like
  console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
  console.log(color('  Write-Like Bash Commands', colors.bold));
  console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));

  console.log('Similar to the read-only bash commands, we also check for write-like bash');
  console.log('commands during Discussion mode and block them.\n');
  console.log('You might have some CLI commands that you want to mark as "blocked" in');
  console.log('Discussion mode. For reference, here are the commands we already block in');
  console.log('Discussion mode:\n');
  console.log(color(`  ${getWriteCommandsList().join(', ')}\n`, colors.yellow));
  console.log('Type any additional command you would like blocked in Discussion mode and hit');
  console.log('"enter" to add it. You may add as many as you like. When you\'re done, hit');
  console.log('"enter" again to move to the next configuration option:\n');

  const customWrite = [];
  while (true) {
    const answer = await inquirer.prompt([{
      type: 'input',
      name: 'value',
      message: color('> ', colors.cyan)
    }]);
    const cmd = answer.value.trim();
    if (!cmd) break;
    customWrite.push(cmd);
    console.log(color(`✓ Added '${cmd}' to write-like commands`, colors.green));
  }
  config.blocked_actions.bash_write_patterns = customWrite;

  // Extrasafe mode
  console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
  console.log(color('  Extrasafe Mode', colors.bold));
  console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));

  const extrasafe = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: 'What if Claude uses a bash command in discussion mode that\'s not in our\nread-only *or* our write-like list?',
    choices: [
      'Extrasafe OFF (allows unrecognized commands)',
      'Extrasafe ON (blocks unrecognized commands)'
    ]
  }]);
  config.blocked_actions.extrasafe = extrasafe.value.includes('ON');

  // Trigger Phrases Section
  console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
  console.log(color('  Trigger Phrases', colors.bold));
  console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));

  console.log('While you can drive cc-sessions using our slash command API, the preferred way');
  console.log('is with (somewhat) natural language. To achieve this, we use unique trigger');
  console.log('phrases that automatically activate the 4 protocols and 2 driving modes in');
  console.log('cc-sessions:\n');
  console.log('  • Switch to implementation mode (default: "yert")');
  console.log('  • Switch to discussion mode (default: "SILENCE")');
  console.log('  • Create a new task/task file (default: "mek:")');
  console.log('  • Start a task/task file (default: "start^:")');
  console.log('  • Complete/archive the current task (default: "finito")');
  console.log('  • Compact context with active task (default: "squish")\n');

  const customizeTriggers = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: 'Would you like to add any of your own custom trigger phrases?',
    choices: ['Use defaults', 'Customize']
  }]);

  // Set defaults first
  config.trigger_phrases = {
    implementation_mode: ['yert'],
    discussion_mode: ['SILENCE'],
    task_creation: ['mek:'],
    task_startup: ['start^:'],
    task_completion: ['finito'],
    context_compaction: ['squish']
  };

  if (customizeTriggers.value === 'Customize') {
    // Implementation mode
    console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
    console.log(color('  Implementation Mode Trigger', colors.bold));
    console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));
    console.log('The implementation mode trigger is used when Claude proposes todos for');
    console.log('implementation that you agree with. Once used, the user_messages hook will');
    console.log('automatically switch the mode to Implementation, notify Claude, and lock in the');
    console.log('proposed todo list to ensure Claude doesn\'t go rogue.\n');
    console.log('To add your own custom trigger phrase, think of something that is:');
    console.log('  • Easy to remember and type');
    console.log('  • Won\'t ever come up in regular operation\n');
    console.log('We recommend using symbols or uppercase for trigger phrases that may otherwise');
    console.log('be used naturally in conversation (ex. instead of "stop", you might use "STOP"');
    console.log('or "st0p" or "--stop").\n');
    console.log('Current phrase: "yert"\n');
    console.log('Type a trigger phrase to add and press "enter". When you\'re done, press "enter"');
    console.log('again to move on to the next step:\n');

    while (true) {
      const answer = await inquirer.prompt([{
        type: 'input',
        name: 'value',
        message: color('> ', colors.cyan)
      }]);
      const phrase = answer.value.trim();
      if (!phrase) break;
      config.trigger_phrases.implementation_mode.push(phrase);
      console.log(color(`✓ Added '${phrase}'`, colors.green));
    }

    // Discussion mode
    console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
    console.log(color('  Discussion Mode Trigger', colors.bold));
    console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));
    console.log('The discussion mode trigger is an emergency stop that immediately switches');
    console.log('Claude back to discussion mode. Once used, the user_messages hook will set the');
    console.log('mode to discussion and inform Claude that they need to re-align.\n');
    console.log('Current phrase: "SILENCE"\n');

    while (true) {
      const answer = await inquirer.prompt([{
        type: 'input',
        name: 'value',
        message: color('> ', colors.cyan)
      }]);
      const phrase = answer.value.trim();
      if (!phrase) break;
      config.trigger_phrases.discussion_mode.push(phrase);
      console.log(color(`✓ Added '${phrase}'`, colors.green));
    }

    // Task creation
    console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
    console.log(color('  Task Creation Trigger', colors.bold));
    console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));
    console.log('The task creation trigger activates the task creation protocol. Once used, the');
    console.log('user_messages hook will load the task creation protocol which guides Claude');
    console.log('through creating a properly structured task file with priority, success');
    console.log('criteria, and context manifest.\n');
    console.log('Current phrase: "mek:"\n');

    while (true) {
      const answer = await inquirer.prompt([{
        type: 'input',
        name: 'value',
        message: color('> ', colors.cyan)
      }]);
      const phrase = answer.value.trim();
      if (!phrase) break;
      config.trigger_phrases.task_creation.push(phrase);
      console.log(color(`✓ Added '${phrase}'`, colors.green));
    }

    // Task startup
    console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
    console.log(color('  Task Startup Trigger', colors.bold));
    console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));
    console.log('The task startup trigger activates the task startup protocol. Once used, the');
    console.log('user_messages hook will load the task startup protocol which guides Claude');
    console.log('through checking git status, creating branches, gathering context, and');
    console.log('proposing implementation todos.\n');
    console.log('Current phrase: "start^:"\n');

    while (true) {
      const answer = await inquirer.prompt([{
        type: 'input',
        name: 'value',
        message: color('> ', colors.cyan)
      }]);
      const phrase = answer.value.trim();
      if (!phrase) break;
      config.trigger_phrases.task_startup.push(phrase);
      console.log(color(`✓ Added '${phrase}'`, colors.green));
    }

    // Task completion
    console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
    console.log(color('  Task Completion Trigger', colors.bold));
    console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));
    console.log('The task completion trigger activates the task completion protocol. Once used,');
    console.log('the user_messages hook will load the task completion protocol which guides');
    console.log('Claude through running pre-completion checks, committing changes, merging to');
    console.log('main, and archiving the completed task.\n');
    console.log('Current phrase: "finito"\n');

    while (true) {
      const answer = await inquirer.prompt([{
        type: 'input',
        name: 'value',
        message: color('> ', colors.cyan)
      }]);
      const phrase = answer.value.trim();
      if (!phrase) break;
      config.trigger_phrases.task_completion.push(phrase);
      console.log(color(`✓ Added '${phrase}'`, colors.green));
    }

    // Context compaction
    console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
    console.log(color('  Context Compaction Trigger', colors.bold));
    console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));
    console.log('The context compaction trigger activates the context compaction protocol. Once');
    console.log('used, the user_messages hook will load the context compaction protocol which');
    console.log('guides Claude through running logging and context-refinement agents to preserve');
    console.log('task state before the context window fills up.\n');
    console.log('Current phrase: "squish"\n');

    while (true) {
      const answer = await inquirer.prompt([{
        type: 'input',
        name: 'value',
        message: color('> ', colors.cyan)
      }]);
      const phrase = answer.value.trim();
      if (!phrase) break;
      config.trigger_phrases.context_compaction.push(phrase);
      console.log(color(`✓ Added '${phrase}'`, colors.green));
    }
  }

  // Feature Toggles Section
  console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
  console.log(color('  Feature Toggles', colors.bold));
  console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));

  console.log('Configure optional features and behaviors:\n');

  // Branch enforcement
  console.log('When working on a task, branch enforcement blocks edits to files unless they');
  console.log('are in a repo that is on the task branch. If in a submodule, the submodule');
  console.log('also has to be listed in the task file under the "submodules" field.\n');
  console.log('This prevents Claude from doing silly things with files outside the scope of');
  console.log('what you\'re working on, which can happen frighteningly often. But, it may not');
  console.log('be as flexible as you want. *It also doesn\'t work well with non-Git VCS*.\n');

  const branchEnforcement = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: 'Branch enforcement:',
    choices: [
      'Enabled (recommended for git workflows)',
      'Disabled (for alternative VCS like Jujutsu)'
    ]
  }]);
  config.features.branch_enforcement = branchEnforcement.value.includes('Enabled');

  // Auto-ultrathink
  console.log('\nAuto-ultrathink adds "[[ ultrathink ]]" to *every message* you submit to');
  console.log('Claude Code. This is the most robust way to force maximum thinking for every');
  console.log('message.\n');
  console.log('If you are not a Claude Max x20 subscriber and/or you are budget-conscious,');
  console.log('it\'s recommended that you disable auto-ultrathink and manually trigger thinking');
  console.log('as needed.\n');

  const autoUltrathink = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: 'Auto-ultrathink:',
    choices: [
      'Enabled',
      'Disabled (recommended for budget-conscious users)'
    ]
  }]);
  config.features.auto_ultrathink = (autoUltrathink.value === 'Enabled');

  // Nerd Fonts
  const nerdFonts = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: 'Nerd Fonts display icons in the statusline for a visual interface:',
    choices: [
      'Enabled',
      'Disabled (ASCII fallback)'
    ]
  }]);
  config.features.use_nerd_fonts = (nerdFonts.value === 'Enabled');

  // Context warnings
  const contextWarnings = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: 'Context warnings notify you when approaching token limits (85% and 90%):',
    choices: [
      'Both warnings enabled',
      'Only 90% warning',
      'Disabled'
    ]
  }]);
  if (contextWarnings.value.includes('Both')) {
    config.features.context_warnings = { warn_85: true, warn_90: true };
  } else if (contextWarnings.value.includes('Only')) {
    config.features.context_warnings = { warn_85: false, warn_90: true };
  } else {
    config.features.context_warnings = { warn_85: false, warn_90: false };
  }

  // Statusline configuration
  console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
  console.log(color('  Statusline Configuration', colors.bold));
  console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));

  const statuslineChoice = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: 'cc-sessions includes a statusline that shows context usage, current task, mode, and git branch. Would you like to use it?',
    choices: [
      'Yes, use cc-sessions statusline',
      'No, I have my own statusline'
    ]
  }]);

  if (statuslineChoice.value.includes('Yes')) {
    // Configure statusline in .claude/settings.json
    const settingsFile = path.join(projectRoot, '.claude', 'settings.json');
    let settings = {};

    if (fs.existsSync(settingsFile)) {
      settings = JSON.parse(fs.readFileSync(settingsFile, 'utf8'));
    }

    // Set statusline command
    settings.statusLine = {
      type: 'command',
      command: 'node $CLAUDE_PROJECT_DIR/sessions/statusline.js'
    };

    fs.writeFileSync(settingsFile, JSON.stringify(settings, null, 2));
    console.log(color('✓ Statusline configured in .claude/settings.json', colors.green));
  } else {
    console.log(color('\nYou can add the cc-sessions statusline later by adding this to .claude/settings.json:', colors.yellow));
    console.log(color('{\n  "statusLine": {\n    "type": "command",\n    "command": "node $CLAUDE_PROJECT_DIR/sessions/statusline.js"\n  }\n}', colors.yellow));
  }

  console.log(color('\n✓ Configuration complete!\n', colors.green));
  return config;
}

async function installerDecisionFlow() {
  console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
  console.log(color('  Welcome to cc-sessions!', colors.bold));
  console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));

  // First-time user detection
  const firstTime = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: 'Is this your first time using cc-sessions?',
    choices: ['Yes', 'No']
  }]);

  let didImport = false;

  if (firstTime.value === 'No') {
    // Version detection for existing users
    const versionCheck = await inquirer.prompt([{
      type: 'list',
      name: 'value',
      message: 'Have you used cc-sessions v0.3.0 or later (released October 2025)?',
      choices: ['Yes', 'No']
    }]);

    if (versionCheck.value === 'Yes') {
      // Config/agent import workflow
      const importChoice = await inquirer.prompt([{
        type: 'list',
        name: 'value',
        message: 'Would you like to import your configuration and agents?',
        choices: ['Yes', 'No']
      }]);

      if (importChoice.value === 'Yes') {
        const importSource = await inquirer.prompt([{
          type: 'list',
          name: 'value',
          message: 'Where is your cc-sessions configuration?',
          choices: ['Local directory', 'Git repository URL', 'Skip import']
        }]);

        if (importSource.value !== 'Skip import') {
          const sourcePathAnswer = await inquirer.prompt([{
            type: 'input',
            name: 'value',
            message: color('Path or URL: ', colors.cyan)
          }]);
          const sourcePath = sourcePathAnswer.value.trim();

          // [PLACEHOLDER] Import config and agents, then present for interactive modification
          // TODO: Implement config import with interactive modification feature
          console.log(color('\n⚠️  Config import not yet implemented. Continuing with interactive configuration...', colors.yellow));
        } else {
          console.log(color('\nSkipping import. Continuing with interactive configuration...', colors.cyan));
        }
      } else {
        console.log(color('\nContinuing with interactive configuration...', colors.cyan));
      }
    } else {
      // Treat as first-time user
      console.log(color('\nTreating as first-time user. Continuing with setup...', colors.cyan));
    }
  }

  // Run interactive configuration if we didn't import
  if (!didImport) {
    const config = await interactiveConfiguration();
  }

  // Kickstart decision
  console.log(color('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', colors.cyan));
  console.log(color('  Learn cc-sessions with Kickstart', colors.bold));
  console.log(color('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n', colors.cyan));

  console.log('cc-sessions is an opinionated interactive workflow. You can learn how to use');
  console.log('it *with* Claude Code - we built a custom "session" called kickstart.\n');
  console.log('Kickstart will:');
  console.log('  • Teach you the features of cc-sessions');
  console.log('  • Help you set up your first task');
  console.log('  • Show you the 4 core protocols you can run');
  console.log('  • Help you customize cc-sessions subagents for your codebase\n');
  console.log('Time: 15-30 minutes\n');

  const kickstartChoice = await inquirer.prompt([{
    type: 'list',
    name: 'value',
    message: 'Would you like to run kickstart on your first session?',
    choices: [
      'Yes (auto-start full kickstart tutorial)',
      'Just subagents (customize subagents but skip tutorial)',
      'No (skip tutorial, remove kickstart files)'
    ]
  }]);

  // Import editState from shared_state
  const sharedStatePath = path.join(PROJECT_ROOT, 'sessions', 'hooks', 'shared_state.js');
  const { editState } = require(sharedStatePath);

  if (kickstartChoice.value.includes('Yes')) {
    // Set metadata for full kickstart mode
    editState((s) => {
      s.metadata.kickstart = { mode: 'full' };
    });
    console.log(color('\n✓ Kickstart will auto-start on your first session', colors.green));
  } else if (kickstartChoice.value.includes('Just subagents')) {
    // Set metadata for subagents-only mode
    editState((s) => {
      s.metadata.kickstart = { mode: 'subagents' };
    });
    console.log(color('\n✓ Kickstart will guide you through subagent customization only', colors.green));
  } else {
    // No - skip kickstart
    // Don't set any metadata, run cleanup immediately
    console.log(color('\n⏭️  Skipping kickstart onboarding...', colors.cyan));
    kickstartCleanup();
    console.log(color('\n✓ Kickstart files removed', colors.green));
  }

  // Return kickstart choice for success message
  if (kickstartChoice.value.includes('Yes')) {
    return 'full';
  } else if (kickstartChoice.value.includes('Just subagents')) {
    return 'subagents';
  } else {
    return 'skip';
  }
}

// Utility functions

function copyFile(src, dest) {
  if (fs.existsSync(src)) {
    const destDir = path.dirname(dest);
    if (!fs.existsSync(destDir)) {
      fs.mkdirSync(destDir, { recursive: true });
    }
    fs.copyFileSync(src, dest);

    // Preserve executable permissions on Unix
    if (process.platform !== 'win32') {
      try {
        const stats = fs.statSync(src);
        fs.chmodSync(dest, stats.mode);
      } catch (error) {
        // Ignore chmod errors
      }
    }
  }
}

function copyDirectory(src, dest) {
  if (!fs.existsSync(src)) return;

  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true });
  }

  const entries = fs.readdirSync(src, { withFileTypes: true });

  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    if (entry.isDirectory()) {
      copyDirectory(srcPath, destPath);
    } else {
      copyFile(srcPath, destPath);
    }
  }
}

function createBackup(projectRoot) {
  // Create timestamped backup of tasks and agents before reinstall
  const now = new Date();
  const timestamp = now.toISOString().replace(/[-:]/g, '').split('.')[0].replace('T', '-').slice(0, 15);
  const backupDir = path.join(projectRoot, '.claude', `.backup-${timestamp}`);

  const relPath = path.relative(projectRoot, backupDir);
  console.log(color(`\n💾 Creating backup at ${relPath}/...`, colors.cyan));

  fs.mkdirSync(backupDir, { recursive: true });

  // Backup all task files (includes done/, indexes/, and all task files)
  const tasksSrc = path.join(projectRoot, 'sessions', 'tasks');
  let taskCount = 0;
  if (fs.existsSync(tasksSrc)) {
    const tasksDest = path.join(backupDir, 'tasks');
    copyDirectory(tasksSrc, tasksDest);

    // Count task files for user feedback and verification
    function countTasksInDir(dir) {
      let count = 0;
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          count += countTasksInDir(fullPath);
        } else if (entry.name.endsWith('.md')) {
          count++;
        }
      }
      return count;
    }

    taskCount = countTasksInDir(tasksSrc);
    const backedUpCount = countTasksInDir(tasksDest);

    if (taskCount !== backedUpCount) {
      console.log(color(`   ✗ Backup verification failed: ${backedUpCount}/${taskCount} files backed up`, colors.red));
      throw new Error('Backup verification failed - aborting to prevent data loss');
    }

    console.log(color(`   ✓ Backed up ${taskCount} task files`, colors.green));
  }

  // Backup all agents
  const agentsSrc = path.join(projectRoot, '.claude', 'agents');
  let agentCount = 0;
  if (fs.existsSync(agentsSrc)) {
    const agentsDest = path.join(backupDir, 'agents');
    copyDirectory(agentsSrc, agentsDest);

    const agentFiles = fs.readdirSync(agentsSrc).filter(f => f.endsWith('.md'));
    const backedUpAgents = fs.readdirSync(agentsDest).filter(f => f.endsWith('.md'));
    agentCount = agentFiles.length;

    if (agentCount !== backedUpAgents.length) {
      console.log(color(`   ✗ Backup verification failed: ${backedUpAgents.length}/${agentCount} agents backed up`, colors.red));
      throw new Error('Backup verification failed - aborting to prevent data loss');
    }

    console.log(color(`   ✓ Backed up ${agentCount} agent files`, colors.green));
  }

  return backupDir;
}

function restoreTasks(projectRoot, backupDir) {
  // Restore tasks from backup after installation
  console.log(color('\n♻️  Restoring tasks...', colors.cyan));

  try {
    const tasksBackup = path.join(backupDir, 'tasks');
    if (fs.existsSync(tasksBackup)) {
      const tasksDest = path.join(projectRoot, 'sessions', 'tasks');
      copyDirectory(tasksBackup, tasksDest);

      // Count restored task files
      function countTasksInDir(dir) {
        let count = 0;
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        for (const entry of entries) {
          const fullPath = path.join(dir, entry.name);
          if (entry.isDirectory()) {
            count += countTasksInDir(fullPath);
          } else if (entry.name.endsWith('.md')) {
            count++;
          }
        }
        return count;
      }

      const taskCount = countTasksInDir(tasksBackup);
      console.log(color(`   ✓ Restored ${taskCount} task files`, colors.green));
    }
  } catch (e) {
    const relPath = path.relative(projectRoot, backupDir);
    console.log(color(`   ✗ Restore failed: ${e.message}`, colors.red));
    console.log(color(`   Your backup is safe at: ${relPath}/`, colors.yellow));
    console.log(color('   Manually copy files from backup/tasks/ to sessions/tasks/', colors.yellow));
    // Don't throw - let user recover manually
  }
}

// Run installer
main().catch(error => {
  console.error(color('\n❌ Fatal error:', colors.red), error);
  process.exit(1);
});
