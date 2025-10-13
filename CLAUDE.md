# cc-sessions

A Claude Code workflow framework that enforces structured AI pair programming through Discussion-Alignment-Implementation-Check (DAIC) methodology.

## What It Does

cc-sessions transforms Claude Code into a disciplined workflow system where Claude must discuss approaches before writing code, maintains persistent task context across sessions, and provides specialized agents for complex operations. Available in both Python and JavaScript with complete feature parity.

## Core Concepts

### DAIC Enforcement
- **Discussion Mode**: Default state. Edit/Write/MultiEdit tools blocked until explicit approval
- **Implementation Mode**: Activated by trigger phrases ("yert", "make it so", "run that")
- **Todo-Based Boundaries**: Approved TodoWrite lists define exact implementation scope
- **Automatic Return**: Returns to discussion mode when all todos complete
- **Configurable**: Customize trigger phrases, blocked tools, and enforcement patterns

### Task Management
- **Priority Prefixes**: h- (high), m- (medium), l- (low), ?- (investigate)
- **Two Task Types**: File-based for focused work, directory-based for multi-phase projects
- **Branch Enforcement**: Automatic git branch creation and validation (optional, can be disabled)
- **Persistent Context**: Task state preserved across session restarts
- **Directory Tasks**: Multi-subtask workflows on a single feature branch

### Sessions State System
Unified state management in `sessions/sessions-state.json`:
- `current_task` - Active task with frontmatter integration
- `mode` - Current DAIC mode (discussion/implementation)
- `active_protocol` - Currently running protocol (CREATE/START/COMPLETE/COMPACT/None)
- `todos` - Active and stashed todo lists
- `flags` - Context warnings, subagent status
- `metadata` - Runtime state (kickstart progress, update checks)
- `api` - Protocol-specific command permissions

### Sessions Config System
User preferences in `sessions/sessions-config.json`:
- **Environment**: developer_name, os, shell
- **Trigger Phrases**: Customizable for all mode transitions
- **Git Preferences**: Branch naming, commit styles, auto-merge/push, submodules
- **Feature Toggles**: branch_enforcement, task_detection, auto_ultrathink, use_nerd_fonts, context warnings
- **Blocking Patterns**: implementation_only_tools, bash_read_patterns, bash_write_patterns

### Templated Protocols
Configuration-driven protocol system that auto-adapts based on user preferences:
- **Template Variables**: `{default_branch}`, `{submodules_field}`, `{submodule_context}`, etc.
- **Conditional Sections**: Entire protocol chunks appear/disappear based on configuration
- **Auto-Loading**: `load_protocol_file()` helper eliminates manual file reading
- **Four Main Protocols**: task-creation, task-startup, task-completion, context-compaction
- **Kickstart Onboarding**: Interactive first-run tutorial system

## Key Files

### Core State & Configuration
- `cc_sessions/hooks/shared_state.py|.js` - State/config management, atomic file operations, directory task helpers
- `sessions/sessions-state.json` - Unified runtime state (git-ignored)
- `sessions/sessions-config.json` - User preferences and customization

### Hook System
- `cc_sessions/hooks/sessions_enforce.py|.js` - Pre-tool DAIC enforcement with command analysis
- `cc_sessions/hooks/session_start.py|.js` - Session initialization and update detection
- `cc_sessions/hooks/user_messages.py|.js` - Trigger phrase detection and protocol loading
- `cc_sessions/hooks/post_tool_use.py|.js` - Todo completion detection and mode transitions
- `cc_sessions/hooks/subagent_hooks.py|.js` - Subagent context protection
- `cc_sessions/hooks/kickstart_session_start.py|.js` - Onboarding protocol loader

### Sessions API
- `cc_sessions/scripts/api/__main__.py` or `index.js` - API entry point
- `cc_sessions/scripts/api/router.py|.js` - Command routing with subsystem delegation
- `cc_sessions/scripts/api/state_commands.py|.js` - State inspection and update management
- `cc_sessions/scripts/api/config_commands.py|.js` - Configuration management with feature toggles
- `cc_sessions/scripts/api/task_commands.py|.js` - Task operations and index support
- `cc_sessions/scripts/api/protocol_commands.py|.js` - Protocol-specific commands
- `cc_sessions/scripts/api/kickstart_commands.py|.js` - Onboarding flow management

### Protocols
- `cc_sessions/protocols/task-creation/` - Task creation with directory structure confirmation
- `cc_sessions/protocols/task-startup/` - Task initialization with conditional guidance
- `cc_sessions/protocols/task-completion/` - Completion workflow with commit templating
- `cc_sessions/protocols/context-compaction.md` - Mid-task context management
- `cc_sessions/protocols/kickstart/` - Interactive onboarding system (11 protocols)

### Specialized Agents
- `cc_sessions/agents/context-gathering.md` - Creates task context manifests
- `cc_sessions/agents/logging.md` - Consolidates work logs
- `cc_sessions/agents/code-review.md` - Reviews implementations
- `cc_sessions/agents/context-refinement.md` - Updates context with discoveries
- `cc_sessions/agents/service-documentation.md` - Maintains service docs

### Supporting Infrastructure
- `cc_sessions/python/statusline.py` or `javascript/statusline.js` - Claude Code statusline with git info
- `cc_sessions/install.py` (Python) or `install.js` (JavaScript) - Language-specific installers
- `cc_sessions/commands/` - Slash command wrappers
- `cc_sessions/templates/` - Task templates
- `scripts/prepare-release.py` - Pre-flight validation for releases
- `scripts/publish-release.py` - Atomic dual-package publishing workflow

## Installation

### Python (No Node.js required)
```bash
pipx install cc-sessions          # Recommended
pip install cc-sessions            # Direct install
uv pip install cc-sessions         # UV package manager
```

### JavaScript (No Python required)
```bash
npm install -g cc-sessions         # Global install
npx cc-sessions                    # One-time execution
```

### Development
```bash
./install.sh                       # From repository root
```

Both installers:
- Detect existing installations and create timestamped backups
- Preserve task files and agent customizations automatically
- Add runtime files to `.gitignore` (sessions-state.json, transcripts/)
- Initialize state/config files early

## Sessions API Commands

### State Management
```bash
sessions state                              # Show full state
sessions state <component>                  # View specific component
sessions state update suppress              # Suppress update notifications for current version
sessions state update check                 # Clear cache and force update re-check
sessions state update status                # View current and available version information
sessions mode discussion                    # Return to discussion mode
sessions flags clear                        # Clear session flags
sessions status                             # Human-readable summary
```

### Configuration
```bash
sessions config                             # Show full configuration
sessions config phrases list <category>     # View trigger phrases
sessions config phrases add <category> "<phrase>"
sessions config phrases remove <category> "<phrase>"
sessions config features show               # View all feature toggles
sessions config features toggle <key>       # Toggle boolean features
sessions config features set <key> <value>  # Set feature value
sessions config git show                    # View git preferences
sessions config git set <setting> <value>
sessions config env show                    # View environment settings
sessions config env set <setting> <value>
sessions config read|write list             # Bash pattern management
sessions config tools list|block|unblock    # Tool blocking management
```

### Task Management
```bash
sessions tasks idx list                     # List all task indexes
sessions tasks idx <name>                   # Show tasks in index
sessions tasks start @<task-name>           # Start task with validation
```

### Slash Commands
- `/sessions` - Unified interface with subsystem routing
- All commands support `--from-slash` flag for contextual output

## Key Patterns

### Hook Architecture
- **Unified State Management**: SessionsState class with atomic operations
- **Configuration-Driven Enforcement**: User-customizable behavioral patterns
- **CI Environment Detection**: Auto-bypass DAIC in GitHub Actions
- **Protocol State Management**: Active protocol tracking enables automation
- **Atomic File Operations**: 1-second timeout with force-removal after failure
- **UTF-8 Encoding**: Explicit encoding prevents platform-specific issues
- **Dual-Context Import**: Works in both package and symlinked development

### Directory Task Support
- **Helper Functions**: `is_directory_task()`, `get_task_file_path()` in shared_state
- **Subtask Detection**: `is_subtask()`, `is_parent_task()` for workflow control
- **Creation Protocol**: Explicit user confirmation of directory structure
- **Startup Guidance**: Planning-focused protocol for parent README.md
- **Merge Prevention**: Subtasks stay on feature branch until all complete

### Configuration Management
- **Type-Safe Enums**: CCTools, TriggerCategory, GitCommitStyle, UserOS, UserShell
- **Nested Dataclasses**: TriggerPhrases, BlockingPatterns, GitPreferences, SessionsEnv
- **Atomic Updates**: edit_config() context manager with file locking
- **Runtime Customization**: Add/remove triggers, manage patterns, toggle features
- **Validation**: Automatic type coercion and error handling

### Protocol Loading
- **Auto-Loading Helper**: `load_protocol_file()` with template substitution
- **Template Variables**: Populated from user configuration at runtime
- **Conditional Rendering**: Sections adapt based on git preferences, submodules, etc.
- **Modular Architecture**: Main protocols reference conditional chunks
- **Format Helpers**: `format_todos_for_protocol()` for consistent display

### Specialized Agents
- **Heavy Operations**: File operations delegated to specialized agents
- **Isolated Context**: Agents work in separate context windows
- **Transcript Access**: Dedicated `sessions/transcripts/[agent-name]/` directories
- **Subagent Protection**: DAIC reminders suppressed, state editing blocked

### Update Detection System
- **Dual-Language Publishing**: Atomic workflow for PyPI and npm
- **Pre-Flight Validation**: 7 automated checks via prepare-release.py
- **Version Sync**: check-version-sync.sh ensures consistency
- **Update Detection**: Flag-based caching in STATE.metadata
- **Agent-Directive Notifications**: Prompts Claude to stop and ask user before any installation
- **Update Commands**: suppress, check, status operations for user control

## Feature Highlights

### Statusline Integration
- **Nerd Fonts Support**: Icons for context, task, mode, git branch
- **Git Branch Display**: Shows current branch or detached HEAD state
- **Upstream Tracking**: Commits ahead (↑N) and behind (↓N) indicators
- **Configurable**: Toggle via `use_nerd_fonts` feature flag

### Branch Enforcement
- **Task-to-Branch Mapping**: Automatic from task naming conventions
- **Four Failure Modes**: Wrong branch, no branch, task missing, branch missing
- **Configurable Toggle**: Disable for alternative VCS (Jujutsu, Mercurial)
- **Early Exit**: Check CONFIG.features.branch_enforcement before validation

### Kickstart Onboarding
- **Two Modes**: Full (11 protocols, 15-30 min), Subagents-only (1 protocol, 5 min)
- **Index-Based Progression**: Sequence tracking in STATE.metadata['kickstart']
- **Interactive Learning**: Practice with real commands and dummy tasks
- **Self-Cleanup**: Hybrid automated deletion + manual instruction system

### Windows Integration
- **Platform Detection**: Automatic OS configuration during install
- **UTF-8 Encoding**: Explicit encoding prevents cp1252 issues
- **Native Scripts**: daic.cmd and daic.ps1 for shell compatibility
- **Path Handling**: Windows-style paths with %CLAUDE_PROJECT_DIR%

## Architecture Notes

### Language Variants
- **Complete Feature Parity**: Python and JavaScript implementations identical
- **No Cross-Dependencies**: Each variant works standalone
- **Separate Installers**: Language-specific with no mixed requirements
- **Shared Resources**: Both include agents/ and knowledge/ directories

### State System Evolution
- **Unified File**: Replaced 6+ individual state files with single sessions-state.json
- **Active Protocol Field**: Enables protocol-driven automation
- **API Permissions**: Protocol-specific command authorization
- **Atomic Operations**: File locking with optimized timeout behavior
- **Serialization Methods**: SessionsTodos.to_dict() eliminates duplication

### Protocol System Evolution
- **Configuration-Driven Templates**: Eliminated conditional instructions
- **Runtime Adaptation**: Content populates based on user preferences
- **Modular Chunks**: Conditional sections loaded as needed
- **Structured Output**: Standardized formats ([PROPOSAL], [STATUS], etc.)

### DAIC Enforcement Evolution
- **Enhanced Command Analysis**: 70+ read-only commands recognized
- **Intelligent Argument Detection**: Finds write operations in complex commands
- **Improved Pipeline Handling**: Proper splitting and per-segment analysis
- **Redirection Detection**: Comprehensive stderr and file descriptor handling

## Related Documentation

- **RELEASE.md** - Maintainer guide for version releases
- **README.md** - User-facing feature overview
- **docs/INSTALL.md** - Detailed installation instructions
- **docs/USAGE_GUIDE.md** - Workflow and feature documentation
- **cc_sessions/knowledge/** - Internal architecture details
- **sessions/protocols/** - Installed protocol specifications

## Integration Points

### Consumes
- Claude Code hooks system
- Git (optional, can disable branch enforcement)
- Python 3.8+ OR Node.js 16+ (not both)
- File system locks for atomic operations
- CLAUDE_PROJECT_DIR for symlinked development

### Provides
- Sessions API via unified `sessions` command
- Hook-based tool blocking with user patterns
- Templated protocol system
- Agent-based specialized operations
- SessionsConfig and SessionsState APIs
- Dual-language implementation (Python/JavaScript)
