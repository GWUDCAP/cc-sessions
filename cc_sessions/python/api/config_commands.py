#!/usr/bin/env python3

# ===== IMPORTS ===== #

## ===== STDLIB ===== ##
from typing import Any, List, Optional, Dict
import json
##-##

## ===== 3RD-PARTY ===== ##
##-##

## ===== LOCAL ===== ##
from hooks.shared_state import load_config, edit_config, TriggerCategory, GitAddPattern, GitCommitStyle, UserOS, UserShell, CCTools, IconStyle
##-##

#-#

"""
╔═════════════════════════════════════════════════════╗
║     ██╗ █████╗ █████╗ ██╗  ██╗██████╗██████╗ █████╗ ║
║    ██╔╝██╔═══╝██╔══██╗███╗ ██║██╔═══╝╚═██╔═╝██╔═══╝ ║
║   ██╔╝ ██║    ██║  ██║████╗██║█████╗   ██║  ██║     ║
║  ██╔╝  ██║    ██║  ██║██╔████║██╔══╝   ██║  ██║ ██╗ ║
║ ██╔╝   ╚█████╗╚█████╔╝██║╚███║██║    ██████╗╚█████║ ║
║ ╚═╝     ╚════╝ ╚════╝ ╚═╝ ╚══╝╚═╝    ╚═════╝ ╚════╝ ║
╚═════════════════════════════════════════════════════╝
"""

# ===== FUNCTIONS ===== #

#!> Main config handler
def handle_config_command(args: List[str], json_output: bool = False, from_slash: bool = False) -> Any:
    """
    Handle configuration commands.

    Usage:
        config                          - Show full config
        config phrases <operation>      - Manage trigger phrases
        config git <operation>          - Manage git preferences
        config env <operation>          - Manage environment settings
        config features <operation>     - Manage feature toggles
        config validate                 - Validate configuration
    """
    # Handle no args and help
    if not args or args[0].lower() in ['help', '']:
        # Return root level help doc for /sessions config help
        if from_slash: return format_config_help()
        # Show full config when no args
        config = load_config()
        if json_output: return config.to_dict()
        return format_config_human(config)

    # Get config subsystem command
    section = args[0].lower()
    # Get arguments for subsystem command
    section_args = args[1:] if len(args) > 1 else []

    # Handle show command
    if section == 'show':
        config = load_config()
        if json_output: return config.to_dict()
        return format_config_human(config)
    elif section in ['trigger', 'triggers', 'phrases']: return handle_phrases_command(section_args, json_output, from_slash)
    elif section == 'git': return handle_git_command(section_args, json_output, from_slash)
    elif section == 'env': return handle_env_command(section_args, json_output, from_slash)
    elif section == 'features': return handle_features_command(section_args, json_output, from_slash)
    elif section == 'read': return handle_read_command(section_args, json_output, from_slash)
    elif section == 'write': return handle_write_command(section_args, json_output, from_slash)
    elif section == 'tools': return handle_tools_command(section_args, json_output, from_slash)
    elif section == 'validate': return validate_config(json_output)
    else:
        if from_slash: return f"Unknown command: {section}\n\n{format_config_help()}"
        raise ValueError(f"Unknown config section: {section}. Valid sections: phrases, git, env, features, readonly, validate")

def format_config_help() -> str:
    """Format help output for slash command."""
    lines = [   "Sessions Configuration Commands:", "",
                "  /sessions config show           - Display current configuration",
                "  /sessions config trigger ...    - Manage trigger phrases",
                "  /sessions config git ...        - Manage git preferences",
                "  /sessions config env ...        - Manage environment settings",
                "  /sessions config features ...   - Manage feature toggles",
                "  /sessions config read ...       - Manage bash read patterns",
                "  /sessions config write ...      - Manage bash write patterns",
                "  /sessions config tools ...      - Manage blocked tools", "",
                "Use '/sessions config <section> help' for section-specific help"]
    return "\n".join(lines)

def format_config_human(config) -> str:
    """Format full config for human reading."""
    # Helper to safely get value from enum or string
    def get_value(field): return field.value if hasattr(field, 'value') else field

    lines = ["=== Sessions Configuration ===", "", "Trigger Phrases:",]

    for category in TriggerCategory:
        phrases = getattr(config.trigger_phrases, category.value, [])
        if phrases: lines.append(f"  {category.value}: {', '.join(phrases)}")

    lines.extend(["",   "Git Preferences:",
                            f"  Add Pattern: {get_value(config.git_preferences.add_pattern)}",
                            f"  Default Branch: {config.git_preferences.default_branch}",
                            f"  Commit Style: {get_value(config.git_preferences.commit_style)}",
                            f"  Auto Merge: {config.git_preferences.auto_merge}",
                            f"  Auto Push: {config.git_preferences.auto_push}",
                            f"  Has Submodules: {config.git_preferences.has_submodules}", "",
                        "Environment:",
                            f"  OS: {get_value(config.environment.os)}",
                            f"  Shell: {get_value(config.environment.shell)}",
                            f"  Developer Name: {config.environment.developer_name}", "",
                        "Features:",
                            f"  Branch Enforcement: {config.features.branch_enforcement}",
                            f"  Task Detection: {config.features.task_detection}",
                            f"  Auto Ultrathink: {config.features.auto_ultrathink}",
                            f"  Sessions Enabled: {config.features.sessions_enabled}",
                            f"  Icon Style: {get_value(config.features.icon_style)}",
                            f"  Context Warnings (85%): {config.features.context_warnings.warn_85}",
                            f"  Context Warnings (90%): {config.features.context_warnings.warn_90}", ])

    return "\n".join(lines)
#!<

#!> Trigger phrases handlers
def handle_phrases_command(args: List[str], json_output: bool = False, from_slash: bool = False) -> Any:
    """
    Handle trigger phrase commands.
    
    Usage:
        config phrases list [category]
        config phrases add <category> "<phrase>"
        config phrases remove <category> "<phrase>"
        config phrases clear <category>
    """
    if not args or (args and args[0].lower() == 'help'):
        if from_slash: return format_phrases_help()
        # List all phrases
        config = load_config()
        phrases = config.trigger_phrases.list_phrases()
        if json_output: return {"phrases": phrases}
        return format_phrases_human(phrases)
    
    action = args[0].lower()

    # Map friendly category names for slash commands
    def map_category(cat: str) -> str:
        if not from_slash: return cat
        mapping = { 'go': 'implementation_mode',
                    'no': 'discussion_mode',
                    'create': 'task_creation',
                    'start': 'task_startup',
                    'complete': 'task_completion',
                    'compact': 'context_compaction'}
        return mapping.get(cat, cat)

    if action == 'list':
        config = load_config()
        if len(args) > 1:
            # List specific category
            category = map_category(args[1])
            phrases = config.trigger_phrases.list_phrases(category)
        else: phrases = config.trigger_phrases.list_phrases() # List all
        if json_output: return {"phrases": phrases}
        return format_phrases_human(phrases)
    
    elif action == 'add':
        if len(args) < 2:
            if from_slash:
                return "Missing category for add command\nUsage: /sessions config trigger add <category> <phrase>\nValid categories: go, no, create, start, complete, compact\n\nExample: /sessions config trigger add go 'proceed'"
            raise ValueError("Usage: config phrases add <category> \"<phrase>\"")

        category = map_category(args[1])

        # Check for valid category
        valid_categories = ['implementation_mode', 'discussion_mode', 'task_creation', 'task_startup', 'task_completion', 'context_compaction']
        if category not in valid_categories:
            if from_slash:
                return f"Invalid category '{args[1]}'\nValid categories: go, no, create, start, complete, compact\n\nUse '/sessions config trigger help' for more info"
            raise ValueError(f"Invalid category: {category}")

        # Collect remaining args as phrase
        if len(args) < 3:
            if from_slash:
                return "Missing phrase to add\nUsage: /sessions config trigger add <category> <phrase>\n\nExample: /sessions config trigger add go 'proceed'"
            raise ValueError("Missing phrase")

        phrase = ' '.join(args[2:])
        
        with edit_config() as config: added = config.trigger_phrases.add_phrase(category, phrase)
        
        if json_output: return {"added": added, "category": category, "phrase": phrase}
        if added: return f"Added '{phrase}' to {category}"
        else: return f"'{phrase}' already exists in {category}"
    
    elif action == 'remove':
        if len(args) < 2:
            if from_slash:
                return "Missing category for remove command\nUsage: /sessions config trigger remove <category> <phrase>\nValid categories: go, no, create, start, complete, compact"
            raise ValueError("Usage: config phrases remove <category> \"<phrase>\"")

        category = map_category(args[1])

        # Check for valid category
        valid_categories = ['implementation_mode', 'discussion_mode', 'task_creation', 'task_startup', 'task_completion', 'context_compaction']
        if category not in valid_categories:
            if from_slash:
                return f"Invalid category '{args[1]}'\nValid categories: go, no, create, start, complete, compact\n\nUse '/sessions config trigger help' for more info"
            raise ValueError(f"Invalid category: {category}")

        # Collect remaining args as phrase
        if len(args) < 3:
            if from_slash:
                return "Missing phrase to remove\nUsage: /sessions config trigger remove <category> <phrase>"
            raise ValueError("Missing phrase")

        phrase = ' '.join(args[2:])
        
        with edit_config() as config: removed = config.trigger_phrases.remove_phrase(category, phrase)
        
        if json_output: return {"removed": removed, "category": category, "phrase": phrase}
        if removed: return f"Removed '{phrase}' from {category}"
        else: return f"'{phrase}' not found in {category}"
    
    elif action == 'clear':
        if len(args) < 2: raise ValueError("Usage: config phrases clear <category>")
        category = args[1]
        with edit_config() as config:
            # Clear the category by setting it to empty list
            category_enum = config.trigger_phrases._coax_phrase_type(category)
            setattr(config.trigger_phrases, category_enum.value, [])
        if json_output: return {"cleared": category}
        return f"Cleared all phrases in {category}"
    
    elif action == 'show':
        # Show specific category
        if len(args) < 2: raise ValueError("Usage: config phrases show <category>")
        category = args[1]
        config = load_config()
        phrases = config.trigger_phrases.list_phrases(category)
        if json_output: return {"phrases": phrases}
        return format_phrases_human(phrases)
    
    else:
        if from_slash: return f"Unknown trigger command: {action}\n\n{format_phrases_help()}"
        raise ValueError(f"Unknown phrases action: {action}. Valid actions: list, add, remove, clear, show")

def format_phrases_help() -> str:
    """Format phrases help for slash command."""
    lines = [   "Trigger Phrase Commands:", "",
                "  /sessions config trigger list [category]           - List trigger phrases",
                "  /sessions config trigger add <category> <phrase>   - Add trigger phrase",
                "  /sessions config trigger remove <category> <phrase> - Remove trigger phrase", "",
                "Categories:",
                "  go       - implementation_mode triggers (yert, make it so, run that)",
                "  no       - discussion_mode triggers (stop, silence)",
                "  create   - task_creation triggers (mek:, mekdis)",
                "  start    - task_startup triggers (start^, begin task:)",
                "  complete - task_completion triggers (finito)",
                "  compact  - context_compaction triggers (lets compact, squish)"]
    return "\n".join(lines)

def format_phrases_human(phrases: Dict[str, List[str]]) -> str:
    """Format phrases for human reading."""
    lines = ["Trigger Phrases:"]
    for category, phrase_list in phrases.items():
        if phrase_list:
            lines.append(f"  {category}:")
            for phrase in phrase_list: lines.append(f"    - {phrase}")
        else: lines.append(f"  {category}: (none)")
    return "\n".join(lines)
#!<

#!> Git preferences handlers
def handle_git_command(args: List[str], json_output: bool = False, from_slash: bool = False) -> Any:
    """
    Handle git preference commands.

    Usage:
        config git show
        config git set <key> <value>
    """
    if not args or args[0].lower() in ['help', '']:
        if from_slash: return format_git_help()
        # If not from slash and no args, show git preferences
        if not args: return handle_git_show(json_output)

    if args and args[0] == 'show': return handle_git_show(json_output)

    # Handle old 'set' command or direct subcommands
    action = args[0].lower()

    # Map direct subcommands to set operations
    if action in ['add', 'branch', 'commit', 'merge', 'push', 'repo']:
        key = action
        if len(args) < 2:
            if from_slash: return format_git_missing_value(key)
            raise ValueError(f"Missing value for git {key}")
        value = ' '.join(args[1:]) if action == 'branch' else args[1]
    elif action == 'set':
        if len(args) < 3:
            if from_slash: return "Missing key and value\nUsage: /sessions config git <setting> <value>"
            raise ValueError("Usage: config git set <key> <value>")
        key = args[1].lower()
        value = args[2]
    else:
        if from_slash: return f"Unknown git command: {action}\n\n{format_git_help()}"
        raise ValueError(f"Unknown git command: {args[0]}")

    with edit_config() as config:
        if key in ['add', 'add_pattern']:
            # Map friendly values
            if from_slash:
                if value not in ['ask', 'all']:
                    return f"Invalid value '{value}' for git add\nValid options: ask (prompt for files) or all (stage everything)\n\nUse '/sessions config git help' for more info"
            try: config.git_preferences.add_pattern = GitAddPattern(value)
            except ValueError as e:
                if from_slash: return f"Invalid add pattern: {value}. Valid options: ask, all"
                raise ValueError(f"Invalid add pattern: {value}. Valid options: ask, all")

        elif key in ['branch', 'default_branch']: config.git_preferences.default_branch = value

        elif key in ['commit', 'commit_style']:
            # Map friendly values
            style = value
            if from_slash:
                style_map = {'reg': 'conventional', 'simp': 'simple', 'op': 'detailed'}
                style = style_map.get(value, value)
                if style not in ['conventional', 'simple', 'detailed']:
                    return f"Invalid style '{value}'\nValid styles: conventional, simple, detailed\n  conventional - feat: add feature (conventional commits)\n  simple       - Add feature (simple descriptions)\n  detailed     - Add feature with extended description\n\nUse '/sessions config git help' for more info"
            try: config.git_preferences.commit_style = GitCommitStyle(style)
            except ValueError as e:
                if from_slash:
                    return f"Invalid commit style: {value}. Valid options: conventional, simple, detailed"
                raise ValueError(f"Invalid commit style: {value}. Valid options: conventional, simple, detailed")

        elif key in ['merge', 'auto_merge']:
            if from_slash:
                if value == 'auto': config.git_preferences.auto_merge = True
                elif value == 'ask': config.git_preferences.auto_merge = False
                else: return f"Invalid value '{value}' for merge\nValid options: auto (merge automatically) or ask (prompt first)\n\nUse '/sessions config git help' for more info"
            else: config.git_preferences.auto_merge = value.lower() in ['true', 'yes', '1', 'auto']

        elif key in ['push', 'auto_push']:
            if from_slash:
                if value == 'auto': config.git_preferences.auto_push = True
                elif value == 'ask': config.git_preferences.auto_push = False
                else: return f"Invalid value '{value}' for push\nValid options: auto (push automatically) or ask (prompt first)\n\nUse '/sessions config git help' for more info"
            else: config.git_preferences.auto_push = value.lower() in ['true', 'yes', '1', 'auto']

        elif key in ['repo', 'has_submodules']:
            if from_slash:
                if value == 'super': config.git_preferences.has_submodules = True
                elif value == 'mono': config.git_preferences.has_submodules = False
                else: return f"Invalid value '{value}' for repo type\nValid options: super (has submodules) or mono (single repo)\n\nUse '/sessions config git help' for more info"
            else: config.git_preferences.has_submodules = value.lower() in ['true', 'yes', '1', 'super']

        else:
            if from_slash: return f"Unknown git setting: {key}\n\n{format_git_help()}"
            raise ValueError(f"Unknown git setting: {key}")

    if json_output: return {"updated": key, "value": value}
    return f"Updated git {key} to {value}"

def handle_git_show(json_output: bool = False) -> Any:
    """Show git preferences."""
    config = load_config()
    git_prefs = config.git_preferences

    # Helper to safely get value from enum or string
    def get_value(field): return field.value if hasattr(field, 'value') else field

    if json_output:
        return { "git_preferences": {
                    "add_pattern": get_value(git_prefs.add_pattern),
                    "default_branch": git_prefs.default_branch,
                    "commit_style": get_value(git_prefs.commit_style),
                    "auto_merge": git_prefs.auto_merge,
                    "auto_push": git_prefs.auto_push,
                    "has_submodules": git_prefs.has_submodules, } }

    lines = [   "Git Preferences:",
                f"  Add Pattern: {get_value(git_prefs.add_pattern)}",
                f"  Default Branch: {git_prefs.default_branch}",
                f"  Commit Style: {get_value(git_prefs.commit_style)}",
                f"  Auto Merge: {git_prefs.auto_merge}",
                f"  Auto Push: {git_prefs.auto_push}",
                f"  Has Submodules: {git_prefs.has_submodules}", ]
    return "\n".join(lines)

def format_git_help() -> str:
    """Format git help for slash command."""
    lines = [   "Git Preference Commands:", "",
                "  /sessions config git show                - Display git preferences",
                "  /sessions config git add <ask|all>       - Set staging behavior",
                "  /sessions config git branch <name>       - Set default branch",
                "  /sessions config git commit <style>      - Set commit style",
            "    Styles: conventional, simple, detailed",
                "  /sessions config git merge <auto|ask>    - Set merge behavior",
                "  /sessions config git push <auto|ask>     - Set push behavior",
                "  /sessions config git repo <super|mono>   - Set repository type" ]
    return "\n".join(lines)

def format_git_missing_value(key: str) -> str:
    """Format missing value error for git settings."""
    messages = {
        'add': "Missing value for git add\nOptions: ask (prompt for files) or all (stage everything)\n\nUsage: /sessions config git add <ask|all>",
        'branch': "Missing branch name\nUsage: /sessions config git branch <name>\n\nExample: /sessions config git branch main",
        'commit': "Missing commit style\nValid styles: conventional, simple, detailed\n\nUsage: /sessions config git commit <style>",
        'merge': "Missing merge preference\nOptions: auto (merge automatically) or ask (prompt first)\n\nUsage: /sessions config git merge <auto|ask>",
        'push': "Missing push preference\nOptions: auto (push automatically) or ask (prompt first)\n\nUsage: /sessions config git push <auto|ask>",
        'repo': "Missing repository type\nOptions: super (has submodules) or mono (single repo)\n\nUsage: /sessions config git repo <super|mono>"
    }
    return messages.get(key, f"Missing value for git {key}")
#!<

#!> Environment settings handlers
def handle_env_command(args: List[str], json_output: bool = False, from_slash: bool = False) -> Any:
    """
    Handle environment setting commands.

    Usage:
        config env show
        config env set <key> <value>
    """
    if not args or args[0].lower() in ['help', '']:
        if from_slash:
            return format_env_help()
        # If not from slash and no args, show env settings
        if not args:
            return handle_env_show(json_output)

    if args and args[0] == 'show':
        return handle_env_show(json_output)

    # Handle old 'set' command or direct subcommands
    action = args[0].lower()

    # Map direct subcommands to set operations
    if action in ['os', 'shell', 'name']:
        key = action
        if len(args) < 2:
            if from_slash:
                return format_env_missing_value(key)
            raise ValueError(f"Missing value for env {key}")
        value = ' '.join(args[1:]) if action == 'name' else args[1]
    elif action == 'set':
        if len(args) < 3:
            if from_slash:
                return "Missing key and value\nUsage: /sessions config env <setting> <value>"
            raise ValueError("Usage: config env set <key> <value>")
        key = args[1].lower()
        value = ' '.join(args[2:]) if key in ['developer_name', 'name'] else args[2]
    else:
        if from_slash:
            return f"Unknown env command: {action}\n\n{format_env_help()}"
        raise ValueError(f"Unknown env command: {args[0]}")

    with edit_config() as config:
        if key == 'os':
            # Map friendly values
            os_val = value
            if from_slash:
                os_map = {'mac': 'macos', 'win': 'windows'}
                os_val = os_map.get(value.lower(), value.lower())
                if os_val not in ['linux', 'macos', 'windows']:
                    return f"Invalid OS '{value}'\nValid options: linux, macos, windows\n\nUse '/sessions config env help' for more info"
            try:
                config.environment.os = UserOS(os_val)
            except ValueError:
                if from_slash:
                    return f"Invalid OS: {value}. Valid values: linux, macos, windows"
                raise ValueError(f"Invalid os: {value}. Valid values: linux, macos, windows")

        elif key == 'shell':
            # Map friendly values
            shell_val = value
            if from_slash:
                shell_map = {'pwr': 'powershell'}
                shell_val = shell_map.get(value.lower(), value.lower())
                if shell_val not in ['bash', 'zsh', 'fish', 'powershell', 'cmd']:
                    return f"Invalid shell '{value}'\nValid options: bash, zsh, fish, powershell, cmd\n\nUse '/sessions config env help' for more info"
            try:
                config.environment.shell = UserShell(shell_val)
            except ValueError:
                if from_slash:
                    return f"Invalid shell: {value}. Valid values: bash, zsh, fish, powershell, cmd"
                raise ValueError(f"Invalid shell: {value}. Valid values: bash, zsh, fish, powershell, cmd")

        elif key in ['developer_name', 'name']:
            config.environment.developer_name = value

        else:
            if from_slash:
                return f"Unknown env setting: {key}\n\n{format_env_help()}"
            raise ValueError(f"Unknown environment setting: {key}")

    if json_output:
        return {"updated": key, "value": value}
    return f"Updated env {key} to {value}"

def handle_env_show(json_output: bool = False) -> Any:
    """Show environment settings."""
    config = load_config()
    env = config.environment

    # Helper to safely get value from enum or string
    def get_value(field):
        return field.value if hasattr(field, 'value') else field

    if json_output:
        return {
            "environment": {
                "os": get_value(env.os),
                "shell": get_value(env.shell),
                "developer_name": env.developer_name,
            }
        }

    lines = [
        "Environment Settings:",
        f"  OS: {get_value(env.os)}",
        f"  Shell: {get_value(env.shell)}",
        f"  Developer Name: {env.developer_name}",
    ]
    return "\n".join(lines)

def format_env_help() -> str:
    """Format env help for slash command."""
    lines = [
        "Environment Commands:",
        "",
        "  /sessions config env show            - Display environment settings",
        "  /sessions config env os <os>         - Set operating system",
        "    Options: linux, macos, windows",
        "  /sessions config env shell <shell>   - Set shell preference",
        "    Options: bash, zsh, fish, powershell, cmd",
        "  /sessions config env name <name>     - Set developer name"
    ]
    return "\n".join(lines)

def format_env_missing_value(key: str) -> str:
    """Format missing value error for env settings."""
    messages = {
        'os': "Missing operating system\nValid options: linux, macos, windows\n\nUsage: /sessions config env os <os>",
        'shell': "Missing shell preference\nValid options: bash, zsh, fish, powershell, cmd\n\nUsage: /sessions config env shell <shell>",
        'name': "Missing developer name\nUsage: /sessions config env name <name>\n\nExample: /sessions config env name John"
    }
    return messages.get(key, f"Missing value for env {key}")
#!<

#!> Feature toggles handlers
def handle_features_command(args: List[str], json_output: bool = False, from_slash: bool = False) -> Any:
    """
    Handle feature toggle commands.

    Usage:
        config features show
        config features set <key> <value>
        config features toggle <key>
    """
    # Handle help request and no args
    if not args:
        return handle_features_command(['show'], json_output, from_slash)

    if args[0].lower() == 'help':
        return format_features_help()

    action = args[0].lower()

    if action == 'show':
        # Show feature toggles
        config = load_config()
        features = config.features

        # Helper to safely get value from enum or string
        def get_value(field): return field.value if hasattr(field, 'value') else field

        if json_output:
            return {
                "features": {
                    "branch_enforcement": features.branch_enforcement,
                    "task_detection": features.task_detection,
                    "auto_ultrathink": features.auto_ultrathink,
                    "sessions_enabled": features.sessions_enabled,
                    "icon_style": get_value(features.icon_style),
                    "warn_85": features.context_warnings.warn_85,
                    "warn_90": features.context_warnings.warn_90,
                }
            }

        lines = [
            "Feature Toggles:",
            f"  branch_enforcement: {features.branch_enforcement}",
            f"  task_detection: {features.task_detection}",
            f"  auto_ultrathink: {features.auto_ultrathink}",
            f"  sessions_enabled: {features.sessions_enabled}",
            f"  icon_style: {get_value(features.icon_style)}",
            f"  warn_85: {features.context_warnings.warn_85}",
            f"  warn_90: {features.context_warnings.warn_90}",
        ]
        return "\n".join(lines)
    
    if action == 'set':
        if len(args) < 3:
            raise ValueError("Usage: config features set <key> <value>")
        
        key = args[1].lower()
        value = args[2]

        with edit_config() as config:
            if key in ['task_detection', 'auto_ultrathink', 'branch_enforcement', 'sessions_enabled']:
                # Boolean features
                bool_value = value.lower() in ['true', '1', 'yes', 'on']
                setattr(config.features, key, bool_value)
                final_value = bool_value

            elif key == 'icon_style':
                # Enum feature - accepts nerd_fonts, emoji, ascii
                try:
                    config.features.icon_style = IconStyle(value.lower())
                    final_value = value.lower()
                except ValueError:
                    raise ValueError(f"Invalid icon_style value: {value}. Valid values: nerd_fonts, emoji, ascii")

            elif key in ['warn_85', 'warn_90']:
                # Context warning features
                bool_value = value.lower() in ['true', '1', 'yes', 'on']
                setattr(config.features.context_warnings, key, bool_value)
                final_value = bool_value

            else:
                raise ValueError(f"Unknown feature: {key}")

        if json_output:
            return {"updated": key, "value": final_value}
        return f"Updated features.{key} to {final_value}"

    elif action == 'toggle':
        if len(args) < 2:
            raise ValueError("Usage: config features toggle <key>")

        key = args[1].lower()

        # Get current value
        config = load_config()
        if key in ['task_detection', 'auto_ultrathink', 'branch_enforcement', 'sessions_enabled']:
            current_value = getattr(config.features, key)
        elif key == 'icon_style':
            current_value = config.features.icon_style
        elif key in ['warn_85', 'warn_90']:
            current_value = getattr(config.features.context_warnings, key)
        else:
            raise ValueError(f"Unknown feature: {key}")

        # Toggle/cycle the value
        if key == 'icon_style':
            # Cycle through enum values: nerd_fonts -> emoji -> ascii -> nerd_fonts
            cycle = [IconStyle.NERD_FONTS, IconStyle.EMOJI, IconStyle.ASCII]
            current_idx = cycle.index(current_value)
            new_value = cycle[(current_idx + 1) % len(cycle)]
        else:
            # Boolean toggle
            new_value = not current_value

        # Save the toggled value
        with edit_config() as config:
            if key in ['task_detection', 'auto_ultrathink', 'branch_enforcement', 'sessions_enabled']:
                setattr(config.features, key, new_value)
            elif key == 'icon_style':
                config.features.icon_style = new_value
            elif key in ['warn_85', 'warn_90']:
                setattr(config.features.context_warnings, key, new_value)

        # Format values for display
        old_display = current_value.value if hasattr(current_value, 'value') else current_value
        new_display = new_value.value if hasattr(new_value, 'value') else new_value

        if json_output:
            return {"toggled": key, "old_value": old_display, "new_value": new_display}
        return f"Toggled {key}: {old_display} → {new_display}"

    else:
        if from_slash:
            return f"Unknown features action: {action}\n\n{format_features_help()}"
        raise ValueError(f"Unknown features action: {action}. Valid actions: show, set, toggle")

def format_features_help() -> str:
    """Format features help for slash command."""
    lines = [
        "Feature Toggle Commands:",
        "",
        "  /sessions config features show              - Display all feature flags",
        "  /sessions config features set <key> <value> - Set feature value",
        "  /sessions config features toggle <key>      - Toggle feature boolean",
        "",
        "Available Features:",
        "  branch_enforcement  - Git branch validation (default: true)",
        "  task_detection      - Task-based workflow automation (default: true)",
        "  auto_ultrathink     - Enhanced AI reasoning (default: true)",
        "  sessions_enabled    - Enable/disable all cc-sessions hooks except statusline (default: true)",
        "  icon_style          - Statusline icon style: nerd_fonts, emoji, or ascii (default: nerd_fonts)",
        "  warn_85             - Context warning at 85% (default: true)",
        "  warn_90             - Context warning at 90% (default: true)",
        "",
        "Examples:",
        "  /sessions config features toggle icon_style          # Cycles through nerd_fonts -> emoji -> ascii",
        "  /sessions config features set icon_style emoji       # Set to emoji icons",
        "  /sessions config features set auto_ultrathink false",
        "  /sessions config features toggle branch_enforcement"
    ]
    return "\n".join(lines)
#!<

#!> Bash read patterns handlers
def handle_read_command(args: List[str], json_output: bool = False, from_slash: bool = False) -> Any:
    """
    Handle bash read pattern management.

    Usage:
        config read list              - List all bash read patterns
        config read add <pattern>     - Add a pattern to read list
        config read remove <pattern>  - Remove a pattern from read list
    """
    if not args or args[0] == 'list':
        # List all read patterns
        config = load_config()
        patterns = config.blocked_actions.bash_read_patterns

        if json_output:
            return {"bash_read_patterns": patterns}

        if patterns:
            lines = ["Bash Read Patterns (allowed in discussion mode):"]
            for pattern in patterns:
                lines.append(f"  - {pattern}")
            return "\n".join(lines)
        else:
            return "No custom bash read patterns configured"

    action = args[0].lower()

    if action == 'add':
        if len(args) < 2:
            if from_slash:
                return "Missing pattern for add command\nUsage: /sessions config read add <pattern>\n\nExample: /sessions config read add 'docker ps'"
            raise ValueError("Usage: config read add <pattern>")

        pattern = ' '.join(args[1:])

        with edit_config() as config:
            if pattern not in config.blocked_actions.bash_read_patterns:
                config.blocked_actions.bash_read_patterns.append(pattern)
                added = True
            else:
                added = False

        if json_output:
            return {"added": added, "pattern": pattern}
        if added:
            return f"Added '{pattern}' to bash read patterns"
        else:
            return f"'{pattern}' already exists in bash read patterns"

    elif action == 'remove':
        if len(args) < 2:
            if from_slash:
                return "Missing pattern for remove command\nUsage: /sessions config read remove <pattern>"
            raise ValueError("Usage: config read remove <pattern>")

        pattern = ' '.join(args[1:])

        with edit_config() as config:
            if pattern in config.blocked_actions.bash_read_patterns:
                config.blocked_actions.bash_read_patterns.remove(pattern)
                removed = True
            else:
                removed = False

        if json_output:
            return {"removed": removed, "pattern": pattern}
        if removed:
            return f"Removed '{pattern}' from bash read patterns"
        else:
            return f"'{pattern}' not found in bash read patterns"

    else:
        if from_slash:
            return f"Unknown read command: {action}\n\nValid actions: list, add, remove\n\nUsage:\n  /sessions config read list\n  /sessions config read add <pattern>\n  /sessions config read remove <pattern>"
        raise ValueError(f"Unknown read action: {action}. Valid actions: list, add, remove")
#!<

#!> Bash write patterns handlers
def handle_write_command(args: List[str], json_output: bool = False, from_slash: bool = False) -> Any:
    """
    Handle bash write pattern management.

    Usage:
        config write list              - List all bash write patterns
        config write add <pattern>     - Add a pattern to write list
        config write remove <pattern>  - Remove a pattern from write list
    """
    if not args or args[0] == 'list':
        # List all write patterns
        config = load_config()
        patterns = config.blocked_actions.bash_write_patterns

        if json_output:
            return {"bash_write_patterns": patterns}

        if patterns:
            lines = ["Bash Write Patterns (blocked in discussion mode):"]
            for pattern in patterns:
                lines.append(f"  - {pattern}")
            return "\n".join(lines)
        else:
            return "No custom bash write patterns configured"

    action = args[0].lower()

    if action == 'add':
        if len(args) < 2:
            if from_slash:
                return "Missing pattern for add command\nUsage: /sessions config write add <pattern>\n\nExample: /sessions config write add 'rm -rf'"
            raise ValueError("Usage: config write add <pattern>")

        pattern = ' '.join(args[1:])

        with edit_config() as config:
            if pattern not in config.blocked_actions.bash_write_patterns:
                config.blocked_actions.bash_write_patterns.append(pattern)
                added = True
            else:
                added = False

        if json_output:
            return {"added": added, "pattern": pattern}
        if added:
            return f"Added '{pattern}' to bash write patterns"
        else:
            return f"'{pattern}' already exists in bash write patterns"

    elif action == 'remove':
        if len(args) < 2:
            if from_slash:
                return "Missing pattern for remove command\nUsage: /sessions config write remove <pattern>"
            raise ValueError("Usage: config write remove <pattern>")

        pattern = ' '.join(args[1:])

        with edit_config() as config:
            if pattern in config.blocked_actions.bash_write_patterns:
                config.blocked_actions.bash_write_patterns.remove(pattern)
                removed = True
            else:
                removed = False

        if json_output:
            return {"removed": removed, "pattern": pattern}
        if removed:
            return f"Removed '{pattern}' from bash write patterns"
        else:
            return f"'{pattern}' not found in bash write patterns"

    else:
        if from_slash:
            return f"Unknown write command: {action}\n\nValid actions: list, add, remove\n\nUsage:\n  /sessions config write list\n  /sessions config write add <pattern>\n  /sessions config write remove <pattern>"
        raise ValueError(f"Unknown write action: {action}. Valid actions: list, add, remove")
#!<

#!> Implementation-only tools handlers
def handle_tools_command(args: List[str], json_output: bool = False, from_slash: bool = False) -> Any:
    """
    Handle implementation-only tools management.

    Usage:
        config tools list                - List all blocked tools
        config tools block <ToolName>    - Block a tool in discussion mode
        config tools unblock <ToolName>  - Unblock a tool
    """
    if not args or args[0] == 'list':
        # List all blocked tools
        config = load_config()
        tools = config.blocked_actions.implementation_only_tools

        if json_output:
            return {"implementation_only_tools": tools}

        if tools:
            lines = ["Implementation-Only Tools (blocked in discussion mode):"]
            for tool in tools:
                lines.append(f"  - {tool}")
            return "\n".join(lines)
        else:
            return "No tools configured as implementation-only"

    action = args[0].lower()

    if action == 'block':
        if len(args) < 2:
            if from_slash:
                valid_tools = ", ".join([t.value for t in CCTools])
                return f"Missing tool name for block command\nUsage: /sessions config tools block <ToolName>\n\nValid tools: {valid_tools}"
            raise ValueError("Usage: config tools block <ToolName>")

        tool_name = args[1]

        # Validate against CCTools enum
        valid_tool_values = [t.value for t in CCTools]
        if tool_name not in valid_tool_values:
            if from_slash:
                return f"Invalid tool name: {tool_name}\n\nValid tools: {', '.join(valid_tool_values)}"
            raise ValueError(f"Invalid tool name: {tool_name}. Valid tools: {', '.join(valid_tool_values)}")

        with edit_config() as config:
            if tool_name not in config.blocked_actions.implementation_only_tools:
                config.blocked_actions.implementation_only_tools.append(tool_name)
                added = True
            else:
                added = False

        if json_output:
            return {"blocked": added, "tool": tool_name}
        if added:
            return f"Blocked '{tool_name}' in discussion mode"
        else:
            return f"'{tool_name}' is already blocked in discussion mode"

    elif action == 'unblock':
        if len(args) < 2:
            if from_slash:
                return "Missing tool name for unblock command\nUsage: /sessions config tools unblock <ToolName>"
            raise ValueError("Usage: config tools unblock <ToolName>")

        tool_name = args[1]

        with edit_config() as config:
            if tool_name in config.blocked_actions.implementation_only_tools:
                config.blocked_actions.implementation_only_tools.remove(tool_name)
                removed = True
            else:
                removed = False

        if json_output:
            return {"unblocked": removed, "tool": tool_name}
        if removed:
            return f"Unblocked '{tool_name}' (now allowed in discussion mode)"
        else:
            return f"'{tool_name}' was not blocked"

    else:
        if from_slash:
            return f"Unknown tools command: {action}\n\nValid actions: list, block, unblock\n\nUsage:\n  /sessions config tools list\n  /sessions config tools block <ToolName>\n  /sessions config tools unblock <ToolName>"
        raise ValueError(f"Unknown tools action: {action}. Valid actions: list, block, unblock")
#!<

#!> Config validation
def validate_config(json_output: bool = False) -> Any:
    """
    Validate the current configuration.
    """
    try:
        config = load_config()
        # The load itself validates the structure
        
        # Additional validation checks
        issues = []
        
        # Check for empty required fields
        if not config.git_preferences.default_branch:
            issues.append("Git default_branch is empty")
        
        if not config.environment.developer_name:
            issues.append("Developer name is empty")
        
        # Check for at least one implementation trigger phrase
        if not config.trigger_phrases.implementation_mode:
            issues.append("No implementation mode trigger phrases defined")
        
        if issues:
            if json_output:
                return {"valid": False, "issues": issues}
            return "Configuration issues found:\n" + "\n".join(f"  - {issue}" for issue in issues)
        
        if json_output:
            return {"valid": True}
        return "Configuration is valid"
        
    except Exception as e:
        if json_output:
            return {"valid": False, "error": str(e)}
        return f"Configuration error: {e}"
#!<

#-#
