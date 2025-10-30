# Changelog

## [Unreleased]

### Added
- Accept aliases like `nerd-fonts` when setting the statusline icon style through `sessions config features`. This makes the CLI friendlier by matching the terminology used in docs and installer prompts.

### Fixed
- Toggling `icon_style` now works even if legacy configs store the value as a plain string or boolean, ensuring seamless upgrades without manual file edits.

## [0.3.6] - 2025-10-17

### Fixed
- **Installer PATH Warnings**: Removed obsolete Windows PATH checking (#66)
  - Installers no longer output confusing messages about sessions command not being on PATH
  - Reflects new architecture where sessions command is project-local by design
  - Thanks to @Schadenfreund for reporting

## [0.3.5] - 2025-10-16

### Fixed

- **Nx Monorepo Compatibility**: Fixed nx throwing error about missing package name (#62)
  - JavaScript installer now creates sessions/package.json with "name" field set to "sessions-api"
  - Resolves "ProjectsWithNoNameError" when running nx commands
  - Thanks to @taybin for reporting

- **Statusline Task Counter**: Fixed task counter showing 1 when no tasks exist (#61)
  - Python and JavaScript statuslines now exclude `indexes/` directory from task count
  - Only actual task files and task directories are counted
  - Thanks to @bhayden53 for reporting

- **Package Version Tracking**: Fixed sessions-state.json being initialized with "unknown" version
  - Python: Added `_get_package_version()` helper as default factory for SessionsState.version field
  - JavaScript: Added `_getPackageVersion()` helper called during SessionsState construction
  - New installations now correctly store installed package version in state file

- **Missing Function Exports**: Fixed JavaScript shared_state.js missing exports (#63)
  - Added `isSubtask` and `isParentTask` to module.exports
  - Resolves "isSubtask is not a function" error during task completion protocol
  - Thanks to @harshmoorjani for reporting

## [0.3.4] - 2025-10-15

### Added
- rough windows support for new sessions API entrypoint

## [0.3.3] - 2025-10-15

### Fixed

- **ESM Project Compatibility**: JavaScript installer now creates `sessions/package.json` with `{"type": "commonjs"}` to ensure installed hooks, API, and statusline scripts can use `require()` syntax even in projects with `"type": "module"`

- **Sessions Command Installation**: Removed unreliable global bin entries and implemented project-local wrapper approach
  - Created OS-specific wrapper scripts (`sessions` for Unix, `sessions.bat` for Windows)
  - Installers copy language-specific wrappers to `sessions/bin/`
  - All hooks detect OS at runtime and output correct command syntax
  - Slash command uses project-local wrapper instead of global bin
  - Works reliably across all environments without requiring `npm install -g`

## [0.3.2] - 2025-10-14

### Fixed

- Python 3.9 installer hotfix

## [0.3.1] - 2025-10-14

### Fixed
- teehee lil python string escaping bug issoke

## [0.3.0] - 2025-10-14

### Major Changes

- **JavaScript Support**: cc-sessions now available as both Python and Node.js packages with identical features. Choose your preferred language during installation.

- **Unified Sessions API**: All commands now accessed through single `sessions` command with three subsystems:
  - `sessions state` - View and manage session state
  - `sessions config` - Customize behavior, triggers, and preferences
  - `sessions tasks` - Task management and filtering

- **Natural Language Protocol Activation**: Trigger phrases now activate full workflow protocols
  - Task creation: "mek:" or "mekdis"
  - Task startup: "start^:" with @task-file
  - Task completion: "finito"
  - Context compaction: "squish" or "lets compact"
  - All phrases customizable through configuration

- **Todo Validation System**: Approved todo lists are now locked and tracked
  - Prevents Claude from modifying approved todos during implementation
  - Validates todos match original approval before execution
  - Returns to discussion mode if Claude attempts to change the plan

- **Directory Tasks**: Create multi-phase projects with subtasks that share a feature branch

- **Kickstart Tutorial**: Interactive onboarding teaches you cc-sessions by using it
  - Full mode: 15-30 minutes covering all features with agent customization
  - Subagents-only mode: 5 minutes focused on agent customization

### Added

- **CI Environment Detection**: Hooks automatically bypass DAIC in GitHub Actions and other CI environments
  - Thanks to @oppianmatt (matt@oppian.com) for implementation guidance (#14)
- **Nerd Fonts & Git Info**: Enhanced statusline with icons and git branch tracking (↑N ahead, ↓N behind)
  - Configured during installation, toggle later with `sessions config features toggle use_nerd_fonts`
  - Thanks to @dnviti (dnviti@gmail.com) for the ideas (#21)
- **Safe Uninstaller**: Run `sessions uninstall` for interactive removal with automatic backups
  - Thanks to @gabelul for the concept (#45)
- **Task Indexes**: Filter tasks by service area with `sessions tasks idx`
- **Feature Toggles**: Enable/disable behaviors at runtime
  - `sessions config features show` - View all options
  - `sessions config features toggle <key>` - Toggle setting
- **Custom Bash Patterns**: Define project-specific read/write commands
  - `sessions config read|write list` - Manage patterns
- **Tool Blocking Control**: Add or remove blocked tools at runtime
  - `sessions config tools block|unblock <tool>`

### Changed

- **Interactive Installer**: Now configures all preferences during installation (developer name, trigger phrases, git workflow, feature toggles)
- **Slash Commands**: `/add-trigger` and similar commands replaced by `/sessions` with subsystem routing
- **Enhanced Command Detection**: 70+ read-only bash commands now recognized, better pipeline and redirection handling
- **README**: Rewritten for clarity with installation badges and concise feature descriptions
- **CLAUDE.md**: Expanded with complete architecture and integration documentation

### Removed

- **Auto-Update Installation**: Removed broken auto-update system (notifications still work, manual updates required)
- **Legacy Commands**: Individual slash commands consolidated into `/sessions`

### Breaking Changes

- State and config files moved to `sessions/` directory
- Slash command syntax changed: `/add-trigger` → `/sessions config phrases add`
- Old state files from v0.2.x not preserved during upgrade

### Upgrading from v0.2.x

1. Run installer - it creates backups, guides you through configuration, and offers kickstart tutorial
2. Task files preserved automatically
3. Kickstart tutorial (optional) walks you through agent customization

## [0.2.8] - 2025-09-04

### Changed
- **No More Sudo Required**: The `daic` command no longer requires sudo for installation
- **Package Manager Integration**: `daic` is now installed as a package command:
  - Python: Automatically available when installed via pip/pipx
  - Node.js: Automatically available when installed via npm  
- **Fallback Location**: Local fallback moved from `.claude/bin` to `sessions/bin`
- **Cleaner Directory Structure**: cc-sessions specific files moved out of `.claude/` to keep it clean for Claude Code

### Added
- `cc_sessions/daic.py` - Python entry point for pip installations
- `daic.js` - Node.js entry point for npm installations
- Console scripts entry in `pyproject.toml`
- Bin entry in `package.json`

### Removed
- Sudo fallback logic from all installers
- Global `/usr/local/bin` installation attempt

## [0.2.7] - Previous Release
- Initial public release
