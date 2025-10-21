# cc-sessions

A Claude Code workflow framework that enforces structured AI pair programming through Discussion-Alignment-Implementation-Check (DAIC) methodology.

## What It Does

cc-sessions transforms Claude Code into a disciplined workflow system where Claude must discuss approaches before writing code, maintains persistent task context across sessions, and provides specialized agents for complex operations. Available in both Python and JavaScript with complete feature parity.

## Core Concepts

### DAIC Enforcement
- **Discussion Mode**: Default state. Edit/Write/MultiEdit tools blocked until explicit approval
- **Implementation Mode**: Activated by trigger phrases ("yert", "make it so", "run that")
- **Todo-Based Boundaries**: Approved TodoWrite lists define exact implementation scope
- **Todo Change Detection**: Blocks unauthorized todo modifications with detailed diff and required "SHAME RITUAL" response format
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
- **Feature Toggles**: branch_enforcement, task_detection, auto_ultrathink, icon_style, context warnings
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
- `cc_sessions/hooks/shared_state.py|.js` - State/config management, enums (IconStyle, etc.), atomic file operations, directory task helpers
- `sessions/sessions-state.json` - Unified runtime state (git-ignored)
- `sessions/sessions-config.json` - User preferences and customization (includes icon_style enum)

### Hook System
- `cc_sessions/hooks/sessions_enforce.py|.js` - Pre-tool DAIC enforcement with command analysis
- `cc_sessions/hooks/sessions_enforce.py:319-376|.js:397-454` - Todo change blocking with diff display and "SHAME RITUAL" format
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

## Installation

### Prerequisites
- **Claude Code v2.0.8** - Versions 2.0.9+ have an upstream bug affecting parallel tool execution (see Known Issues below)
- Python 3.8+ OR Node.js 16+ (not both)

### Python (No Node.js required)
```bash
pipx install cc-sessions          # Recommended
pip install cc-sessions            # Direct install
uv pip install cc-sessions         # UV package manager
```

### JavaScript (No Python required)
```bash
npx cc-sessions
```

### Development Setup

For local development, install cc-sessions in symlinked mode from the repository:

**Python Development**:
```bash
cd /path/to/cc-sessions
python cc_sessions/install.py
```

**JavaScript Development**:
```bash
cd /path/to/cc-sessions
node cc_sessions/install.js
```

The installer detects `CLAUDE_PROJECT_DIR` environment variable and creates symlinked hooks that point back to your repository for live development.

**Building Packages**:

Python:
```bash
python -m build
# Creates dist/cc_sessions-*.tar.gz and dist/cc_sessions-*.whl
```

JavaScript:
```bash
npm pack
# Creates cc-sessions-*.tgz
```

**Testing Local Changes**:
After modifying hook or API files:
1. Changes are immediately reflected (symlinked development)
2. Start a new Claude Code session to test hook behavior
3. Use `/sessions` commands to test API changes

Both installers:
- Detect existing installations and create timestamped backups
- Preserve task files and agent customizations automatically
- Add runtime files to `.gitignore` (sessions-state.json, transcripts/)
- Initialize state/config files early
- Auto-detect terminal Nerd Font capability and prompt for icon style preference

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
sessions config features toggle <key>       # Toggle boolean features or cycle enum values
sessions config features set <key> <value>  # Set feature value (e.g., icon_style nerd_fonts|emoji|ascii)
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

### Todo Change Detection
- **Diff Display**: Shows original vs proposed todos with counts and numbered lists
- **Dynamic Injection**: User's trigger phrases from config automatically included in prompt
- **Prescribed Format**: Claude must respond with "SHAME RITUAL" message explaining violation
- **State Clearing**: Clears active todos and returns to discussion mode for re-approval
- **Natural Gate**: Next TodoWrite attempt succeeds after user approval since no existing todos to compare

### Directory Task Support
- **Helper Functions**: `is_directory_task()`, `get_task_file_path()` in shared_state
- **Subtask Detection**: `is_subtask()`, `is_parent_task()` for workflow control
- **Creation Protocol**: Explicit user confirmation of directory structure
- **Startup Guidance**: Planning-focused protocol for parent README.md
- **Merge Prevention**: Subtasks stay on feature branch until all complete

### Configuration Management
- **Type-Safe Enums**: CCTools, TriggerCategory, GitCommitStyle, UserOS, UserShell, IconStyle
- **Nested Dataclasses**: TriggerPhrases, BlockingPatterns, GitPreferences, SessionsEnv, EnabledFeatures
- **Atomic Updates**: edit_config() context manager with file locking
- **Runtime Customization**: Add/remove triggers, manage patterns, toggle features
- **Validation**: Automatic type coercion and error handling
- **Automatic Migration**: Old use_nerd_fonts boolean auto-converts to icon_style enum on config load

### Icon Style System
- **IconStyle Enum**: Three values (NERD_FONTS, EMOJI, ASCII) replace old boolean flag
- **Backward Compatible**: Existing configs with use_nerd_fonts auto-migrate on first load
- **Terminal Detection**: Installers check TERM_PROGRAM, LC_TERMINAL, WT_SESSION environment variables
- **Smart Defaults**: Nerd Fonts if detected, Emoji otherwise during installation
- **Toggle Behavior**: `config features toggle icon_style` cycles through all three options
- **Set Command**: `config features set icon_style <value>` accepts nerd_fonts, emoji, or ascii
- **Statusline Support**: Both Python and JavaScript implementations handle all three styles
- **Icon Variants**: Context, Task, Mode, Tasks count, Git branch, Detached HEAD all have three-way branching

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
- **Dual-Language Publishing**: Simultaneous releases to PyPI and npm
- **Version Sync**: pyproject.toml and package.json version fields must match
- **Update Detection**: Flag-based caching in STATE.metadata
- **Agent-Directive Notifications**: Prompts Claude to stop and ask user before any installation
- **Update Commands**: suppress, check, status operations for user control

## Feature Highlights

### Statusline Integration
- **Three Icon Styles**: Nerd Fonts, Emoji fallback, or ASCII fallback
- **Terminal Detection**: Auto-detects Nerd Font capability during installation
- **Git Branch Display**: Shows current branch or detached HEAD state with appropriate icons
- **Upstream Tracking**: Commits ahead (↑N) and behind (↓N) indicators
- **Configurable**: Set via `icon_style` feature (nerd_fonts, emoji, or ascii)
- **Feature Parity**: All three styles supported in both Python and JavaScript implementations

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

## Testing

### Current Status
No automated test suite yet (package.json shows `"test": "echo \"No test specified yet\""`)

### Manual Testing Workflow
1. **Install in Development Mode**: Set up symlinked installation in a test repository
2. **Test DAIC Enforcement**: Attempt writes in discussion mode to verify blocking
3. **Test Trigger Phrases**: Use various trigger phrases to validate mode transitions
4. **Test Task Workflows**:
   - Create tasks with different priorities and types
   - Start tasks and verify context loading
   - Complete tasks and verify commit/merge behavior
5. **Test Sessions API**: Run all `/sessions` commands to verify functionality
6. **Test Feature Parity**: Verify identical behavior between Python and JavaScript implementations
7. **Test Platform Compatibility**: Validate on Linux, macOS, and Windows

### Testing Considerations
- Hook behavior requires full Claude Code session context
- State persistence should be verified across session restarts
- Branch enforcement requires git repository with commits
- Protocol template rendering should be validated with different config options

## Known Issues

### Claude Code Version Compatibility
**Issue**: Claude Code versions 2.0.9+ have a bug in stderr aggregation that causes 400 API errors during parallel tool execution.

**Symptoms**:
- "400 API Error: tool use concurrency issues" when multiple tools execute in parallel
- Occurs when commands generate stderr output (e.g., curl progress) AND PostToolUse hooks send stderr feedback (exit code 2)

**Affected Operations**:
- PostToolUse hooks that provide directory navigation confirmations (cd command)
- DAIC mode transitions
- Any parallel tool calls with mixed stderr sources

**Workaround**: Use Claude Code v2.0.8 until Anthropic fixes the upstream bug

**Details**: See README.md Current Events section or upstream issue

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
- **Todo Change Blocking**: Enhanced feedback with diff display and prescribed response format

## Related Documentation

- **README.md** - User-facing feature overview and installation guide
- **CHANGELOG.md** - Version history and release notes
- **CLAUDE.md** - This file (architecture and development guide)
- **cc_sessions/knowledge/** - Internal architecture details
- **cc_sessions/protocols/** - Protocol template sources
- **sessions/protocols/** - Installed protocol specifications (after installation)

## Integration Points

### Consumes
- Claude Code hooks system (requires v2.0.8 due to upstream bug in 2.0.9+)
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
