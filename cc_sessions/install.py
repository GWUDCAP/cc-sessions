#!/usr/bin/env python3

# ===== IMPORTS ===== #

## ===== STDLIB ===== ##
import shutil, json, sys, os, subprocess, tempfile, contextlib
from pathlib import Path
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
    print(color('\n╔════════════════════════════════════════════════════════════╗', Colors.CYAN))
    print(color('║ ██████╗██████╗██████╗██████╗██████╗ █████╗ ██╗  ██╗██████╗ ║', Colors.CYAN))
    print(color('║ ██╔═══╝██╔═══╝██╔═══╝██╔═══╝╚═██╔═╝██╔══██╗███╗ ██║██╔═══╝ ║',Colors.CYAN))
    print(color('║ ██████╗█████╗ ██████╗██████╗  ██║  ██║  ██║████╗██║██████╗ ║',Colors.CYAN))
    print(color('║ ╚═══██║██╔══╝ ╚═══██║╚═══██║  ██║  ██║  ██║██╔████║╚═══██║ ║',Colors.CYAN))
    print(color('║ ██████║██████╗██████║██████║██████╗╚█████╔╝██║╚███║██████║ ║',Colors.CYAN))
    print(color('║ ╚═════╝╚═════╝╚═════╝╚═════╝╚═════╝ ╚════╝ ╚═╝ ╚══╝╚═════╝ ║',Colors.CYAN)) 
    print(color('║        cc-sessions: an opinionated approach to             ║',Colors.CYAN))
    print(color('╚══════  productive development with Claude Code   ══════════╝',Colors.CYAN))
#!<

#!> Configuration header
def print_config_header() -> None:
    print(color('╔══════════════════════════════════════════════╗',Colors.CYAN))
    print(color('║  █████╗ █████╗ ██╗  ██╗██████╗██████╗ █████╗ ║',Colors.CYAN))
    print(color('║ ██╔═══╝██╔══██╗███╗ ██║██╔═══╝╚═██╔═╝██╔═══╝ ║',Colors.CYAN))
    print(color('║ ██║    ██║  ██║████╗██║█████╗   ██║  ██║     ║',Colors.CYAN))
    print(color('║ ██║    ██║  ██║██╔████║██╔══╝   ██║  ██║ ██╗ ║',Colors.CYAN))
    print(color('║ ╚█████╗╚█████╔╝██║╚███║██║    ██████╗╚█████║ ║',Colors.CYAN))
    print(color('║  ╚════╝ ╚════╝ ╚═╝ ╚══╝╚═╝    ╚═════╝ ╚════╝ ║',Colors.CYAN))
    print(color('╚════════ interactive configuration ═══════════╝',Colors.CYAN))
#!<

#!> Git preferences header
def print_git_section() -> None:
    print(color('╔═════════════════════════════════════════════╗', Colors.CYAN))
    print(color('║ ██████╗ █████╗ ██╗ ██╗█████╗  █████╗██████╗ ║', Colors.CYAN))
    print(color('║ ██╔═══╝██╔══██╗██║ ██║██╔═██╗██╔═══╝██╔═══╝ ║', Colors.CYAN))
    print(color('║ ██████╗██║  ██║██║ ██║█████╔╝██║    █████╗  ║', Colors.CYAN))
    print(color('║ ╚═══██║██║  ██║██║ ██║██╔═██╗██║    ██╔══╝  ║', Colors.CYAN))
    print(color('║ ██████║╚█████╔╝╚████╔╝██║ ██║╚█████╗██████╗ ║', Colors.CYAN))
    print(color('║ ╚═════╝ ╚════╝  ╚═══╝ ╚═╝ ╚═╝ ╚════╝╚═════╝ ║', Colors.CYAN))
    print(color('╚═════════ configure git preferences ═════════╝', Colors.CYAN))
#!<

#!> Environment settings header
def print_env_section() -> None:
    print(color('╔══════════════════════════════════════════════════════╗', Colors.CYAN))
    print(color('║ ██████╗██╗  ██╗██╗ ██╗██████╗█████╗  █████╗ ██╗  ██╗ ║', Colors.CYAN))
    print(color('║ ██╔═══╝███╗ ██║██║ ██║╚═██╔═╝██╔═██╗██╔══██╗███╗ ██║ ║', Colors.CYAN))
    print(color('║ █████╗ ████╗██║██║ ██║  ██║  █████╔╝██║  ██║████╗██║ ║', Colors.CYAN))
    print(color('║ ██╔══╝ ██╔████║╚████╔╝  ██║  ██╔═██╗██║  ██║██╔████║ ║', Colors.CYAN))
    print(color('║ ██████╗██║╚███║ ╚██╔╝ ██████╗██║ ██║╚█████╔╝██║╚███║ ║', Colors.CYAN))
    print(color('║ ╚═════╝╚═╝ ╚══╝  ╚═╝  ╚═════╝╚═╝ ╚═╝ ╚════╝ ╚═╝ ╚══╝ ║', Colors.CYAN))
    print(color('╚════════════════ environment settings ════════════════╝', Colors.CYAN))
#!<

#!> Tool blocking
def print_blocking_header() -> None:
    print(color('╔══════════════════════════════════════════════════════════════╗', Colors.CYAN))
    print(color('║ █████╗ ██╗      █████╗  █████╗██╗  ██╗██████╗██╗  ██╗ █████╗ ║', Colors.CYAN))
    print(color('║ ██╔═██╗██║     ██╔══██╗██╔═══╝██║ ██╔╝╚═██╔═╝███╗ ██║██╔═══╝ ║', Colors.CYAN))
    print(color('║ █████╔╝██║     ██║  ██║██║    █████╔╝   ██║  ████╗██║██║     ║', Colors.CYAN))
    print(color('║ ██╔═██╗██║     ██║  ██║██║    ██╔═██╗   ██║  ██╔████║██║ ██╗ ║', Colors.CYAN))
    print(color('║ █████╔╝███████╗╚█████╔╝╚█████╗██║  ██╗██████╗██║╚███║╚█████║ ║', Colors.CYAN))
    print(color('║ ╚════╝ ╚══════╝ ╚════╝  ╚════╝╚═╝  ╚═╝╚═════╝╚═╝ ╚══╝ ╚════╝ ║', Colors.CYAN))
    print(color('╚══════════════ blocked tools and bash commands ═══════════════╝', Colors.CYAN))
#!<

#!> Read only commands section
def print_read_only_section() -> None:
    print(color('╔═══════════════════════════════════════════════════════════════════╗', Colors.CYAN))
    print(color('║ █████╗ ██████╗ █████╗ █████╗       ██╗     ██████╗██╗  ██╗██████╗ ║', Colors.CYAN))
    print(color('║ ██╔═██╗██╔═══╝██╔══██╗██╔═██╗      ██║     ╚═██╔═╝██║ ██╔╝██╔═══╝ ║', Colors.CYAN))
    print(color('║ █████╔╝█████╗ ███████║██║ ██║█████╗██║       ██║  █████╔╝ █████╗  ║', Colors.CYAN))
    print(color('║ ██╔═██╗██╔══╝ ██╔══██║██║ ██║╚════╝██║       ██║  ██╔═██╗ ██╔══╝  ║', Colors.CYAN))
    print(color('║ ██║ ██║██████╗██║  ██║█████╔╝      ███████╗██████╗██║  ██╗██████╗ ║', Colors.CYAN))
    print(color('║ ╚═╝ ╚═╝╚═════╝╚═╝  ╚═╝╚════╝       ╚══════╝╚═════╝╚═╝  ╚═╝╚═════╝ ║', Colors.CYAN))
    print(color('╚═══════════════ bash commands claude can use freely ═══════════════╝', Colors.CYAN))
#!<

#!> Write-like commands section
def print_write_like_section() -> None:
    print(color("╔════════════════════════════════════════════════════════════════════════════╗",Colors.CYAN))
    print(color("║ ██╗    ██╗█████╗ ██████╗██████╗██████╗      ██╗     ██████╗██╗  ██╗██████╗ ║",Colors.CYAN))
    print(color("║ ██║    ██║██╔═██╗╚═██╔═╝╚═██╔═╝██╔═══╝      ██║     ╚═██╔═╝██║ ██╔╝██╔═══╝ ║",Colors.CYAN))
    print(color("║ ██║ █╗ ██║█████╔╝  ██║    ██║  █████╗ █████╗██║       ██║  █████╔╝ █████╗  ║",Colors.CYAN))
    print(color("║ ██║███╗██║██╔═██╗  ██║    ██║  ██╔══╝ ╚════╝██║       ██║  ██╔═██╗ ██╔══╝  ║",Colors.CYAN))
    print(color("║ ╚███╔███╔╝██║ ██║██████╗  ██║  ██████╗      ███████╗██████╗██║  ██╗██████╗ ║",Colors.CYAN))
    print(color("║  ╚══╝╚══╝ ╚═╝ ╚═╝╚═════╝  ╚═╝  ╚═════╝      ╚══════╝╚═════╝╚═╝  ╚═╝╚═════╝ ║",Colors.CYAN))
    print(color("╚═══════════════ commands claude can't use in discussion mode ═══════════════╝",Colors.CYAN))
#!<

#!> Extrasafe section
def print_extrasafe_section() -> None:
    print(color("╔════════════════════════════════════════════════════════════════════╗",Colors.CYAN))
    print(color("║ ██████╗██╗  ██╗██████╗█████╗  █████╗ ██████╗ █████╗ ██████╗██████╗ ║",Colors.CYAN))
    print(color("║ ██╔═══╝╚██╗██╔╝╚═██╔═╝██╔═██╗██╔══██╗██╔═══╝██╔══██╗██╔═══╝██╔═══╝ ║",Colors.CYAN))
    print(color("║ █████╗  ╚███╔╝   ██║  █████╔╝███████║██████╗███████║█████╗ █████╗  ║",Colors.CYAN))
    print(color("║ ██╔══╝  ██╔██╗   ██║  ██╔═██╗██╔══██║╚═══██║██╔══██║██╔══╝ ██╔══╝  ║",Colors.CYAN))
    print(color("║ ██████╗██╔╝ ██╗  ██║  ██║ ██║██║  ██║██████║██║  ██║██║    ██████╗ ║",Colors.CYAN))
    print(color("║ ╚═════╝╚═╝  ╚═╝  ╚═╝  ╚═╝ ╚═╝╚═╝  ╚═╝╚═════╝╚═╝  ╚═╝╚═╝    ╚═════╝ ║",Colors.CYAN))
    print(color("╚════════════ toggle blocking for unrecognized commands ═════════════╝",Colors.CYAN))
#!<

#!> Trigger phrases
def print_triggers_header() -> None:
    print(color('╔══════════════════════════════════════════════════════════╗',Colors.CYAN))
    print(color('║ ██████╗█████╗ ██████╗ █████╗ █████╗██████╗█████╗ ██████╗ ║',Colors.CYAN))
    print(color('║ ╚═██╔═╝██╔═██╗╚═██╔═╝██╔═══╝██╔═══╝██╔═══╝██╔═██╗██╔═══╝ ║',Colors.CYAN))
    print(color('║   ██║  █████╔╝  ██║  ██║    ██║    █████╗ █████╔╝██████╗ ║',Colors.CYAN))
    print(color('║   ██║  ██╔═██╗  ██║  ██║ ██╗██║ ██╗██╔══╝ ██╔═██╗╚═══██║ ║',Colors.CYAN))
    print(color('║   ██║  ██║ ██║██████╗╚█████║╚█████║██████╗██║ ██║██████║ ║',Colors.CYAN))
    print(color('║   ╚═╝  ╚═╝ ╚═╝╚═════╝ ╚════╝ ╚════╝╚═════╝╚═╝ ╚═╝╚═════╝ ║',Colors.CYAN))
    print(color('╚════════ natural language controls for Claude Code ═══════╝',Colors.CYAN))
#!<

#!> Implementation mode triggers section
def print_go_triggers_section() -> None:
    print(color('╔══════════════════════════════════════════════════════════════════════════╗',Colors.CYAN))
    print(color('║ ██████╗███╗  ███╗██████╗ ██╗     ██████╗███╗  ███╗██████╗██╗  ██╗██████╗ ║',Colors.CYAN))
    print(color('║ ╚═██╔═╝████╗████║██╔══██╗██║     ██╔═══╝████╗████║██╔═══╝███╗ ██║╚═██╔═╝ ║',Colors.CYAN))
    print(color('║   ██║  ██╔███║██║██████╔╝██║     █████╗ ██╔███║██║█████╗ ████╗██║  ██║   ║',Colors.CYAN))
    print(color('║   ██║  ██║╚══╝██║██╔═══╝ ██║     ██╔══╝ ██║╚══╝██║██╔══╝ ██╔████║  ██║   ║',Colors.CYAN))
    print(color('║ ██████╗██║    ██║██║     ███████╗██████╗██║    ██║██████╗██║╚███║  ██║   ║',Colors.CYAN))
    print(color('║ ╚═════╝╚═╝    ╚═╝╚═╝     ╚══════╝╚═════╝╚═╝    ╚═╝╚═════╝╚═╝ ╚══╝  ╚═╝   ║',Colors.CYAN))
    print(color('╚════════════ activate implementation mode (claude can code) ══════════════╝',Colors.CYAN))
#!<

#!> Discussion mode triggers section
def print_no_triggers_section() -> None:
    print(color('╔═══════════════════════════════════════════════════╗',Colors.CYAN))
    print(color('║ █████╗ ██████╗██████╗ █████╗██╗ ██╗██████╗██████╗ ║',Colors.CYAN))
    print(color('║ ██╔═██╗╚═██╔═╝██╔═══╝██╔═══╝██║ ██║██╔═══╝██╔═══╝ ║',Colors.CYAN))
    print(color('║ ██║ ██║  ██║  ██████╗██║    ██║ ██║██████╗██████╗ ║',Colors.CYAN))
    print(color('║ ██║ ██║  ██║  ╚═══██║██║    ██║ ██║╚═══██║╚═══██║ ║',Colors.CYAN))
    print(color('║ █████╔╝██████╗██████║╚█████╗╚████╔╝██████║██████║ ║',Colors.CYAN))
    print(color('║ ╚════╝ ╚═════╝╚═════╝ ╚════╝ ╚═══╝ ╚═════╝╚═════╝ ║',Colors.CYAN))
    print(color('╚════════════ activate discussion mode ════════════╝',Colors.CYAN))
#!<

#!> Create triggers section
def print_create_section() -> None:
    print(color('╔═════════════════════════════════════════════╗',Colors.CYAN))
    print(color('║  █████╗█████╗ ██████╗ █████╗ ██████╗██████╗ ║',Colors.CYAN))
    print(color('║ ██╔═══╝██╔═██╗██╔═══╝██╔══██╗╚═██╔═╝██╔═══╝ ║',Colors.CYAN))
    print(color('║ ██║    █████╔╝█████╗ ███████║  ██║  █████╗  ║',Colors.CYAN))
    print(color('║ ██║    ██╔═██╗██╔══╝ ██╔══██║  ██║  ██╔══╝  ║',Colors.CYAN))
    print(color('║ ╚█████╗██║ ██║██████╗██║  ██║  ██║  ██████╗ ║',Colors.CYAN))
    print(color('║  ╚════╝╚═╝ ╚═╝╚═════╝╚═╝  ╚═╝  ╚═╝  ╚═════╝ ║',Colors.CYAN))
    print(color('╚══════ activate task creation protocol ══════╝',Colors.CYAN))
#!<

#!> Startup triggers section
def print_startup_section() -> None:
    print(color('╔═════════════════════════════════════════════════════╗',Colors.CYAN))
    print(color('║ ██████╗██████╗ █████╗ █████╗ ██████╗██╗ ██╗██████╗  ║',Colors.CYAN))
    print(color('║ ██╔═══╝╚═██╔═╝██╔══██╗██╔═██╗╚═██╔═╝██║ ██║██╔══██╗ ║',Colors.CYAN))
    print(color('║ ██████╗  ██║  ███████║█████╔╝  ██║  ██║ ██║██████╔╝ ║',Colors.CYAN))
    print(color('║ ╚═══██║  ██║  ██╔══██║██╔═██╗  ██║  ██║ ██║██╔═══╝  ║',Colors.CYAN))
    print(color('║ ██████║  ██║  ██║  ██║██║ ██║  ██║  ╚████╔╝██║      ║',Colors.CYAN))
    print(color('║ ╚═════╝  ╚═╝  ╚═╝  ╚═╝╚═╝ ╚═╝  ╚═╝   ╚═══╝ ╚═╝      ║',Colors.CYAN))
    print(color('╚══════════ activate task startup protocol ═══════════╝',Colors.CYAN))
#!<

#!> Completion triggers section
def print_complete_section() -> None:
    print(color('╔════════════════════════════════════════════════════════════════╗',Colors.CYAN))
    print(color('║  █████╗ █████╗ ███╗  ███╗██████╗ ██╗     ██████╗██████╗██████╗ ║',Colors.CYAN))
    print(color('║ ██╔═══╝██╔══██╗████╗████║██╔══██╗██║     ██╔═══╝╚═██╔═╝██╔═══╝ ║',Colors.CYAN))
    print(color('║ ██║    ██║  ██║██╔███║██║██████╔╝██║     █████╗   ██║  █████╗  ║',Colors.CYAN))
    print(color('║ ██║    ██║  ██║██║╚══╝██║██╔═══╝ ██║     ██╔══╝   ██║  ██╔══╝  ║',Colors.CYAN))
    print(color('║ ╚█████╗╚█████╔╝██║    ██║██║     ███████╗██████╗  ██║  ██████╗ ║',Colors.CYAN))
    print(color('║  ╚════╝ ╚════╝ ╚═╝    ╚═╝╚═╝     ╚══════╝╚═════╝  ╚═╝  ╚═════╝ ║',Colors.CYAN))
    print(color('╚══════════════ activate task completion protocol ═══════════════╝',Colors.CYAN))
#!<

#!> Compaction triggers section
def print_compact_section() -> None:
    print(color('╔═════════════════════════════════════════════════════════╗',Colors.CYAN))
    print(color('║  █████╗ █████╗ ███╗  ███╗██████╗  █████╗  █████╗██████╗ ║',Colors.CYAN))
    print(color('║ ██╔═══╝██╔══██╗████╗████║██╔══██╗██╔══██╗██╔═══╝╚═██╔═╝ ║',Colors.CYAN))
    print(color('║ ██║    ██║  ██║██╔███║██║██████╔╝███████║██║      ██║   ║',Colors.CYAN))
    print(color('║ ██║    ██║  ██║██║╚══╝██║██╔═══╝ ██╔══██║██║      ██║   ║',Colors.CYAN))
    print(color('║ ╚█████╗╚█████╔╝██║    ██║██║     ██║  ██║╚█████╗  ██║   ║',Colors.CYAN))
    print(color('║  ╚════╝ ╚════╝ ╚═╝    ╚═╝╚═╝     ╚═╝  ╚═╝ ╚════╝  ╚═╝   ║',Colors.CYAN))
    print(color('╚═════════ activate context compaction protocol ══════════╝',Colors.CYAN))
#!<

#!> Feature toggles header
def print_features_header() -> None:
    print(color('╔═══════════════════════════════════════════════════════════╗',Colors.CYAN))
    print(color('║ ██████╗██████╗ █████╗ ██████╗██╗ ██╗█████╗ ██████╗██████╗ ║',Colors.CYAN))
    print(color('║ ██╔═══╝██╔═══╝██╔══██╗╚═██╔═╝██║ ██║██╔═██╗██╔═══╝██╔═══╝ ║',Colors.CYAN))
    print(color('║ █████╗ █████╗ ███████║  ██║  ██║ ██║█████╔╝█████╗ ██████╗ ║',Colors.CYAN))
    print(color('║ ██╔══╝ ██╔══╝ ██╔══██║  ██║  ██║ ██║██╔═██╗██╔══╝ ╚═══██║ ║',Colors.CYAN))
    print(color('║ ██║    ██████╗██║  ██║  ██║  ╚████╔╝██║ ██║██████╗██████║ ║',Colors.CYAN))
    print(color('║ ╚═╝    ╚═════╝╚═╝  ╚═╝  ╚═╝   ╚═══╝ ╚═╝ ╚═╝╚═════╝╚═════╝ ║',Colors.CYAN))
    print(color('╚════════════ turn on/off cc-sessions features ═════════════╝',Colors.CYAN))
#!<

#!> Statusline header
def print_statusline_header() -> None:
    print(color('╔═══════════════════════════════════════════════════════════════════════════╗',Colors.CYAN))
    print(color('║ ██████╗██████╗ █████╗ ██████╗██╗ ██╗██████╗██╗     ██████╗██╗  ██╗██████╗ ║',Colors.CYAN))
    print(color('║ ██╔═══╝╚═██╔═╝██╔══██╗╚═██╔═╝██║ ██║██╔═══╝██║     ╚═██╔═╝███╗ ██║██╔═══╝ ║',Colors.CYAN))
    print(color('║ ██████╗  ██║  ███████║  ██║  ██║ ██║██████╗██║       ██║  ████╗██║█████╗  ║',Colors.CYAN))
    print(color('║ ╚═══██║  ██║  ██╔══██║  ██║  ██║ ██║╚═══██║██║       ██║  ██╔████║██╔══╝  ║',Colors.CYAN))
    print(color('║ ██████║  ██║  ██║  ██║  ██║  ╚████╔╝██████║███████╗██████╗██║╚███║██████╗ ║',Colors.CYAN))
    print(color('║ ╚═════╝  ╚═╝  ╚═╝  ╚═╝  ╚═╝   ╚═══╝ ╚═════╝╚══════╝╚═════╝╚═╝ ╚══╝╚═════╝ ║',Colors.CYAN))
    print(color('╚═════════════ cc-sessions custom statusline w/ modes + tasks ══════════════╝',Colors.CYAN))
#!<

#!> Kickstart header
def print_kickstart_header() -> None:
    print(color('╔════════════════════════════════════════════════════════════════════╗',Colors.CYAN))
    print(color('║ ██╗  ██╗██████╗ █████╗██╗  ██╗██████╗██████╗ █████╗ █████╗ ██████╗ ║',Colors.CYAN))
    print(color('║ ██║ ██╔╝╚═██╔═╝██╔═══╝██║ ██╔╝██╔═══╝╚═██╔═╝██╔══██╗██╔═██╗╚═██╔═╝ ║',Colors.CYAN))
    print(color('║ █████╔╝   ██║  ██║    █████╔╝ ██████╗  ██║  ███████║█████╔╝  ██║   ║',Colors.CYAN))
    print(color('║ ██╔═██╗   ██║  ██║    ██╔═██╗ ╚═══██║  ██║  ██╔══██║██╔═██╗  ██║   ║',Colors.CYAN))
    print(color('║ ██║  ██╗██████╗╚█████╗██║  ██╗██████║  ██║  ██║  ██║██║ ██║  ██║   ║',Colors.CYAN))
    print(color('║ ╚═╝  ╚═╝╚═════╝ ╚════╝╚═╝  ╚═╝╚═════╝  ╚═╝  ╚═╝  ╚═╝╚═╝ ╚═╝  ╚═╝   ║',Colors.CYAN))
    print(color('╚════════════════════════════════════════════════════════════════════╝',Colors.CYAN))


#!<

def get_readonly_commands_list():
    """Get the list of read-only commands from sessions_enforce.py for display."""
    # This is a subset for display purposes - the full list is in sessions_enforce.py
    return ['cat', 'ls', 'pwd', 'cd', 'echo', 'grep', 'find', 'git status', 'git log',
            'git diff', 'docker ps', 'kubectl get', 'npm list', 'pip show', 'head', 'tail',
            'less', 'more', 'file', 'stat', 'du', 'df', 'ps', 'top', 'htop', 'who', 'w',
            '...(70+ commands total)']

def get_write_commands_list():
    """Get the list of write-like commands from sessions_enforce.py for display."""
    return ['rm', 'mv', 'cp', 'chmod', 'chown', 'mkdir', 'rmdir', 'systemctl', 'service',
            'apt', 'yum', 'npm install', 'pip install', 'make', 'cmake', 'sudo', 'kill',
            '...(and more)']
##-##

## ===== HELPERS ===== ##

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
    _ = ss.load_config()
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

#!> Git preferences
def gather_git_preferences(config: dict) -> dict:
    print_git_section()

    #!> Default branch
    print("Default branch name (e.g. 'main', 'master', 'develop', etc.):")
    print(color("*This is the branch you will merge to when completing tasks*", Colors.YELLOW))
    default_branch = input(color("[main] ", Colors.CYAN)) or 'main'
    with ss.edit_config() as conf:
        conf.git_preferences.default_branch = default_branch
    #!<

    #!> Submodules
    has_submodules = inquirer.list_input(
        message="Does this repository use git submodules?",
        choices=['Yes', 'No'],
        default='Yes')
    with ss.edit_config() as conf:
        conf.git_preferences.has_submodules = (has_submodules == 'Yes')
    #!<

    #!> Staging pattern
    add_pattern = inquirer.list_input(
        message="When committing, how should files be staged?",
        choices=['Ask me each time', 'Stage all modified files automatically'])
    with ss.edit_config() as conf:
        conf.git_preferences.add_pattern = ss.GitAddPattern.ASK if 'Ask' in add_pattern else ss.GitAddPattern.ALL
    #!<

    #!> Commit style
    commit_style = inquirer.list_input(
        message="Commit message style:",
        choices=['Detailed (multi-line with description)', 'Conventional (type: subject format)', 'Simple (single line)'])
    with ss.edit_config() as conf:
        if 'Detailed' in commit_style:
            conf.git_preferences.commit_style = ss.GitCommitStyle.OP
        elif 'Conventional' in commit_style:
            conf.git_preferences.commit_style = ss.GitCommitStyle.REG
        else:
            conf.git_preferences.commit_style = ss.GitCommitStyle.SIMP
    #!<

    #!> Auto-merge
    auto_merge = inquirer.list_input(
        message="After task completion:",
        choices=['Ask me first', f'Auto-merge to {default_branch}'])
    with ss.edit_config() as conf:
        conf.git_preferences.auto_merge = ('Auto-merge' in auto_merge)
    #!<

    #!> Auto-push
    auto_push = inquirer.list_input(
        message="After committing/merging:",
        choices=['Ask me first', 'Auto-push to remote'])
    with ss.edit_config() as conf:
        conf.git_preferences.auto_push = ('Auto-push' in auto_push)
    #!<

    return config
#!<

#!> Environment settings
def gather_environment_settings(config: dict) -> dict:
    print_env_section()

    developer_name = input(color("What should Claude call you? [developer] ", Colors.CYAN)) or 'developer'
    with ss.edit_config() as conf:
        conf.environment.developer_name = developer_name

    # Detect OS
    os_name = platform.system()
    detected_os = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'macos'}.get(os_name, 'linux')

    os_choice = inquirer.list_input(
        message=f"Detected OS: {detected_os.capitalize()}",
        choices=choices_filtered([
            f'{detected_os.capitalize()} is correct',
            'Switch to Windows' if detected_os != 'windows' else None,
            'Switch to macOS' if detected_os != 'macos' else None,
            'Switch to Linux' if detected_os != 'linux' else None
        ]),
        default=f'{detected_os.capitalize()} is correct'
    )
    with ss.edit_config() as conf:
        if 'Windows' in os_choice: conf.environment.os = ss.UserOS.WINDOWS
        elif 'macOS' in os_choice: conf.environment.os = ss.UserOS.MACOS
        elif 'Linux' in os_choice: conf.environment.os = ss.UserOS.LINUX
        else: conf.environment.os = ss.UserOS(detected_os)

    # Detect shell
    detected_shell = os.environ.get('SHELL', 'bash').split('/')[-1]

    shell_choice = inquirer.list_input(
        message=f"Detected shell: {detected_shell}",
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
        if 'bash' in shell_choice: conf.environment.shell = ss.UserShell.BASH
        elif 'zsh' in shell_choice: conf.environment.shell = ss.UserShell.ZSH
        elif 'fish' in shell_choice: conf.environment.shell = ss.UserShell.FISH
        elif 'powershell' in shell_choice: conf.environment.shell = ss.UserShell.POWERSHELL
        elif 'cmd' in shell_choice: conf.environment.shell = ss.UserShell.CMD
        else:
            try:
                conf.environment.shell = ss.UserShell(detected_shell)
            except Exception:
                conf.environment.shell = ss.UserShell.BASH

    return config
#!<

#!> Blocked Actions settings
def gather_blocked_actions(config: dict) -> dict:
    print_blocking_header()

    print("Which tools should be blocked in discussion mode?")
    print(color("*Use Space to toggle, Enter to submit*\n", Colors.YELLOW))

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
            try:
                conf.blocked_actions.implementation_only_tools.append(ss.CCTools(t))
            except Exception:
                pass

    #!> Bash read-like patterns
    print_read_only_section()

    print("In Discussion mode, Claude can only use read-like tools (including commands in")
    print("the Bash tool).\n")
    print("To do this, we parse Claude's Bash tool input in Discussion mode to check for")
    print("write-like and read-only bash commands from a known list.\n")
    print("You might have some CLI commands that you want to mark as \"safe\" to use in")
    print("Discussion mode. For reference, here are the commands we already auto-approve")
    print("in Discussion mode:\n")
    print(color(f"  {', '.join(get_readonly_commands_list())}\n", Colors.YELLOW))
    print("Type any additional command you would like to auto-allow in Discussion mode and")
    print("hit \"enter\" to add it. You may add as many as you like. When you're done, hit")
    print("enter again to move to the next configuration option:\n")

    custom_read = []
    while True:
        cmd = input(color("> ", Colors.CYAN)).strip()
        if not cmd: break
        custom_read.append(cmd)
        print(color(f"✓ Added '{cmd}' to read-only commands", Colors.GREEN))

    with ss.edit_config() as conf:
        conf.blocked_actions.bash_read_patterns = custom_read
    #!<

    #!> Bash write-like patterns
    print_write_like_section()

    print("Similar to the read-only bash commands, we also check for write-like bash")
    print("commands during Discussion mode and block them.\n")
    print("You might have some CLI commands that you want to mark as \"blocked\" in")
    print("Discussion mode. For reference, here are the commands we already block in")
    print("Discussion mode:\n")
    print(color(f"  {', '.join(get_write_commands_list())}\n", Colors.YELLOW))
    print("Type any additional command you would like blocked in Discussion mode and hit")
    print("\"enter\" to add it. You may add as many as you like. When you're done, hit")
    print("\"enter\" again to move to the next configuration option:\n")

    custom_write = []
    while True:
        cmd = input(color("> ", Colors.CYAN)).strip()
        if not cmd: break
        custom_write.append(cmd)
        print(color(f"✓ Added '{cmd}' to write-like commands", Colors.GREEN))

    with ss.edit_config() as conf:
        conf.blocked_actions.bash_write_patterns = custom_write
    #!<

    #!> Extrasafe mode
    print_extrasafe_section()

    extrasafe = inquirer.list_input(
        message="What if Claude uses a bash command in discussion mode that's not in our\nread-only *or* our write-like list?",
        choices=['Extrasafe OFF (allows unrecognized commands)', 'Extrasafe ON (blocks unrecognized commands)'])
    with ss.edit_config() as conf:
        conf.blocked_actions.extrasafe = ('ON' in extrasafe)
    #!<

    return config
#!<

#!> Trigger phrases
def gather_trigger_phrases(config: dict) -> dict:
    print_triggers_header()

    print("While you can drive cc-sessions using our slash command API, the preferred way")
    print("is with (somewhat) natural language. To achieve this, we use unique trigger")
    print("phrases that automatically activate the 4 protocols and 2 driving modes in")
    print("cc-sessions:\n")
    print("  • Switch to implementation mode (default: \"yert\")")
    print("  • Switch to discussion mode (default: \"SILENCE\")")
    print("  • Create a new task/task file (default: \"mek:\")")
    print("  • Start a task/task file (default: \"start^:\")")
    print("  • Complete/archive the current task (default: \"finito\")")
    print("  • Compact context with active task (default: \"squish\")\n")

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

    if customize_triggers == 'Customize':
        #!> Implementation mode
        print_go_triggers_section()

        print("The implementation mode trigger is used when Claude proposes todos for")
        print("implementation that you agree with. Once used, the user_messages hook will")
        print("automatically switch the mode to Implementation, notify Claude, and lock in the")
        print("proposed todo list to ensure Claude doesn't go rogue.\n")
        print("To add your own custom trigger phrase, think of something that is:")
        print("  • Easy to remember and type")
        print("  • Won't ever come up in regular operation\n")
        print("We recommend using symbols or uppercase for trigger phrases that may otherwise")
        print("be used naturally in conversation (ex. instead of \"stop\", you might use \"STOP\"")
        print("or \"st0p\" or \"--stop\").\n")
        print(f"Current phrase: \"yert\"\n")
        print("Type a trigger phrase to add and press \"enter\". When you're done, press \"enter\"")
        print("again to move on to the next step:\n")

        while True:
            phrase = input(color("> ", Colors.CYAN)).strip()
            if not phrase: break
            with ss.edit_config() as conf:
                conf.trigger_phrases.implementation_mode.append(phrase)
            print(color(f"✓ Added '{phrase}'", Colors.GREEN))
        #!<

        #!> Discussion mode
        print_no_triggers_section()

        print("The discussion mode trigger is an emergency stop that immediately switches")
        print("Claude back to discussion mode. Once used, the user_messages hook will set the")
        print("mode to discussion and inform Claude that they need to re-align.\n")
        print(f"Current phrase: \"SILENCE\"\n")

        while True:
            phrase = input(color("> ", Colors.CYAN)).strip()
            if not phrase: break
            with ss.edit_config() as conf:
                conf.trigger_phrases.discussion_mode.append(phrase)
            print(color(f"✓ Added '{phrase}'", Colors.GREEN))
        #!<

        #!> Task creation
        print_create_section()
        print("The task creation trigger activates the task creation protocol. Once used, the")
        print("user_messages hook will load the task creation protocol which guides Claude")
        print("through creating a properly structured task file with priority, success")
        print("criteria, and context manifest.\n")
        print(f"Current phrase: \"mek:\"\n")

        while True:
            phrase = input(color("> ", Colors.CYAN)).strip()
            if not phrase: break
            with ss.edit_config() as conf:
                conf.trigger_phrases.task_creation.append(phrase)
            print(color(f"✓ Added '{phrase}'", Colors.GREEN))
        #!<

        #!> Task startup
        print_startup_section()
        print("The task startup trigger activates the task startup protocol. Once used, the")
        print("user_messages hook will load the task startup protocol which guides Claude")
        print("through checking git status, creating branches, gathering context, and")
        print("proposing implementation todos.\n")
        print(f"Current phrase: \"start^:\"\n")

        while True:
            phrase = input(color("> ", Colors.CYAN)).strip()
            if not phrase: break
            with ss.edit_config() as conf:
                conf.trigger_phrases.task_startup.append(phrase)
            print(color(f"✓ Added '{phrase}'", Colors.GREEN))
        #!<

        #!> Task completion
        print_complete_section()
        print("The task completion trigger activates the task completion protocol. Once used,")
        print("the user_messages hook will load the task completion protocol which guides")
        print("Claude through running pre-completion checks, committing changes, merging to")
        print("main, and archiving the completed task.\n")
        print(f"Current phrase: \"finito\"\n")

        while True:
            phrase = input(color("> ", Colors.CYAN)).strip()
            if not phrase: break
            with ss.edit_config() as conf:
                conf.trigger_phrases.task_completion.append(phrase)
            print(color(f"✓ Added '{phrase}'", Colors.GREEN))
        #!<

        #!> Context compaction
        print_compact_section()
        print("The context compaction trigger activates the context compaction protocol. Once")
        print("used, the user_messages hook will load the context compaction protocol which")
        print("guides Claude through running logging and context-refinement agents to preserve")
        print("task state before the context window fills up.\n")
        print(f"Current phrase: \"squish\"\n")

        while True:
            phrase = input(color("> ", Colors.CYAN)).strip()
            if not phrase: break
            with ss.edit_config() as conf:
                conf.trigger_phrases.context_compaction.append(phrase)
            print(color(f"✓ Added '{phrase}'", Colors.GREEN))
        #!<

    return config
#!<

#!> Feature toggles settings
def gather_features(config: dict) -> dict:
    print_features_header()

    print("Configure optional features and behaviors:\n")

    #!> Branch enforcement
    print("When working on a task, branch enforcement blocks edits to files unless they")
    print("are in a repo that is on the task branch. If in a submodule, the submodule")
    print("also has to be listed in the task file under the \"submodules\" field.\n")
    print("This prevents Claude from doing silly things with files outside the scope of")
    print("what you're working on, which can happen frighteningly often. But, it may not")
    print("be as flexible as you want. *It also doesn't work well with non-Git VCS*.\n")

    branch_enforcement = inquirer.list_input(
        message="Branch enforcement:",
        choices=['Enabled (recommended for git workflows)', 'Disabled (for alternative VCS like Jujutsu)'])
    with ss.edit_config() as conf:
        conf.features.branch_enforcement = ('Enabled' in branch_enforcement)
    #!<

    #!> Auto-ultrathink
    print("\nAuto-ultrathink adds \"[[ ultrathink ]]\" to *every message* you submit to")
    print("Claude Code. This is the most robust way to force maximum thinking for every")
    print("message.\n")
    print("If you are not a Claude Max x20 subscriber and/or you are budget-conscious,")
    print("it's recommended that you disable auto-ultrathink and manually trigger thinking")
    print("as needed.\n")

    auto_ultrathink = inquirer.list_input(
        message="Auto-ultrathink:",
        choices=['Enabled', 'Disabled (recommended for budget-conscious users)'])
    with ss.edit_config() as conf:
        conf.features.auto_ultrathink = (auto_ultrathink == 'Enabled')
    #!<

    #!> Nerd Fonts
    nerd_fonts = inquirer.list_input(
        message="Nerd Fonts display icons in the statusline for a visual interface:",
        choices=['Enabled', 'Disabled (ASCII fallback)'])
    with ss.edit_config() as conf:
        conf.features.use_nerd_fonts = (nerd_fonts == 'Enabled')
    #!<

    #!> Context warnings
    context_warnings = inquirer.list_input(
        message="Context warnings notify you when approaching token limits (85% and 90%):",
        choices=['Both warnings enabled', 'Only 90% warning', 'Disabled'])
    with ss.edit_config() as conf:
        if 'Both' in context_warnings:
            conf.features.context_warnings.warn_85 = True
            conf.features.context_warnings.warn_90 = True
        elif 'Only' in context_warnings:
            conf.features.context_warnings.warn_85 = False
            conf.features.context_warnings.warn_90 = True
        else:
            conf.features.context_warnings.warn_85 = False
            conf.features.context_warnings.warn_90 = False
    #!<

    #!> Statusline configuration
    print_statusline_header()

    statusline_choice = inquirer.list_input(
        message="cc-sessions includes a statusline that shows context usage, current task, mode, and git branch. Would you like to use it?",
        choices=['Yes, use cc-sessions statusline', 'No, I have my own statusline'])
    if 'Yes' in statusline_choice:
        # Configure statusline in .claude/settings.json
        settings_file = ss.PROJECT_ROOT / '.claude' / 'settings.json'

        if settings_file.exists():
            with open(settings_file, 'r') as f: settings = json.load(f)
        else: settings = {}

        # Set statusline command
        settings['statusLine'] = {'type': 'command', 'command': f'python $CLAUDE_PROJECT_DIR/sessions/statusline.py'}

        with open(settings_file, 'w') as f: json.dump(settings, f, indent=2)

        print(color('✓ Statusline configured in .claude/settings.json', Colors.GREEN))
    else:
        print(color('\nYou can add the cc-sessions statusline later by adding this to .claude/settings.json:', Colors.YELLOW))
        print(color('{\n  "statusLine": {\n    "type": "command",\n    "command": "python $CLAUDE_PROJECT_DIR/sessions/statusline.py"\n  }\n}', Colors.YELLOW))
    #!<

    return config
#!<


def interactive_configuration(project_root):
    """
    Interactive configuration wizard for cc-sessions.
    Returns a dict with all user configuration choices.
    """
    print_config_header()
    config = {
        'git_preferences': {},
        'environment': {},
        'blocked_actions': {
            'implementation_only_tools': [],
            'bash_read_patterns': [],
            'bash_write_patterns': []
        },
        'trigger_phrases': {},
        'features': {}
    }

    config = gather_git_preferences(config)

    config = gather_environment_settings(config)

    config = gather_blocked_actions(config)

    config = gather_trigger_phrases(config)

    config = gather_features(config)

    print(color('\n✓ Configuration complete!\n', Colors.GREEN))
    return config
##-##

## ===== CONFIG PHASES ===== ##
def run_full_configuration():
    print_config_header()
    cfg = {'git_preferences': {}, 'environment': {}, 'blocked_actions': {}, 'trigger_phrases': {}, 'features': {}}
    gather_git_preferences(cfg)
    gather_environment_settings(cfg)
    gather_blocked_actions(cfg)
    gather_trigger_phrases(cfg)
    gather_features(cfg)
    print(color('\n✓ Configuration complete!\n', Colors.GREEN))


def run_config_editor():
    print_config_header()
    print(color('Use the menu to edit individual settings. Choose Done when finished.\n', Colors.CYAN))

    # Map menu labels to actions
    actions = [
        ('Git: Default branch', _ask_default_branch),
        ('Git: Has submodules', _ask_has_submodules),
        ('Git: Staging pattern', _ask_git_add_pattern),
        ('Git: Commit style', _ask_commit_style),
        ('Git: Auto-merge behavior', _ask_auto_merge),
        ('Git: Auto-push behavior', _ask_auto_push),
        ('Env: Developer name', _ask_developer_name),
        ('Env: Operating system', _ask_os),
        ('Env: Shell', _ask_shell),
        ('Blocked: Tools list', _edit_blocked_tools),
        ('Blocked: Bash read-only commands', _edit_bash_read_patterns),
        ('Blocked: Bash write-like commands', _edit_bash_write_patterns),
        ('Blocked: Extrasafe mode', _ask_extrasafe_mode),
        ('Triggers: Implementation mode', _edit_triggers_implementation),
        ('Triggers: Discussion mode', _edit_triggers_discussion),
        ('Triggers: Task creation', _edit_triggers_task_creation),
        ('Triggers: Task startup', _edit_triggers_task_startup),
        ('Triggers: Task completion', _edit_triggers_task_completion),
        ('Triggers: Context compaction', _edit_triggers_compaction),
        ('Features: Branch enforcement', _ask_branch_enforcement),
        ('Features: Auto-ultrathink', _ask_auto_ultrathink),
        ('Features: Nerd Fonts', _ask_nerd_fonts),
        ('Features: Context warnings', _ask_context_warnings),
        ('Features: Statusline integration', _ask_statusline),
        ('Done', None),
    ]

    label_to_fn = {label: fn for (label, fn) in actions}

    while True:
        try:
            choice = inquirer.list_input(
                message='Edit which setting?',
                choices=[label for (label, _) in actions]
            )
        except KeyboardInterrupt:
            break

        if choice == 'Done':
            break
        fn = label_to_fn.get(choice)
        if fn:
            try:
                fn()
            except Exception as e:
                print(color(f'⚠️  Error while editing setting: {e}', Colors.YELLOW))
        print()
##-##

## ===== CONFIG QUESTION FUNCTIONS ===== ##
def _ask_default_branch():
    print_git_section()
    print(color("Update default branch (target for merges)", Colors.CYAN))
    val = input(color("[main] ", Colors.CYAN)) or 'main'
    with ss.edit_config() as conf: conf.git_preferences.default_branch = val

def _ask_has_submodules():
    print_git_section()
    val = inquirer.list_input(message='Does this repo use git submodules?', choices=['Yes', 'No'])
    with ss.edit_config() as conf: conf.git_preferences.has_submodules = (val == 'Yes')

def _ask_git_add_pattern():
    print_git_section()
    val = inquirer.list_input(message='Staging behavior when committing:', choices=['Ask me each time', 'Stage all modified files automatically'])
    with ss.edit_config() as conf: conf.git_preferences.add_pattern = ss.GitAddPattern.ASK if 'Ask' in val else ss.GitAddPattern.ALL

def _ask_commit_style():
    print_git_section()
    val = inquirer.list_input(message='Commit message style:', choices=['Detailed (multi-line with description)', 'Conventional (type: subject format)', 'Simple (single line)'])
    with ss.edit_config() as conf:
        if 'Detailed' in val: conf.git_preferences.commit_style = ss.GitCommitStyle.OP
        elif 'Conventional' in val: conf.git_preferences.commit_style = ss.GitCommitStyle.REG
        else: conf.git_preferences.commit_style = ss.GitCommitStyle.SIMP

def _ask_auto_merge():
    print_git_section()
    default_branch = ss.load_config().git_preferences.default_branch
    val = inquirer.list_input(message='After task completion:', choices=['Ask me first', f'Auto-merge to {default_branch}'])
    with ss.edit_config() as conf: conf.git_preferences.auto_merge = ('Auto-merge' in val)

def _ask_auto_push():
    print_git_section()
    val = inquirer.list_input(message='After committing/merging:', choices=['Ask me first', 'Auto-push to remote'])
    with ss.edit_config() as conf: conf.git_preferences.auto_push = ('Auto-push' in val)

def _ask_developer_name():
    print_env_section()
    name = input(color("What should Claude call you? [developer] ", Colors.CYAN)) or 'developer'
    with ss.edit_config() as conf:
        conf.environment.developer_name = name

def _ask_os():
    print_env_section()
    os_name = platform.system()
    detected = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'macos'}.get(os_name, 'linux')
    val = inquirer.list_input(
        message=f"Detected OS: {detected.capitalize()}",
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

def _ask_shell():
    print_env_section()
    detected_shell = os.environ.get('SHELL', 'bash').split('/')[-1]
    val = inquirer.list_input(
        message=f"Detected shell: {detected_shell}",
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

def _edit_blocked_tools():
    gather_blocked_actions({'blocked_actions': {}})

def _edit_bash_read_patterns():
    print_read_only_section()
    print(color('Add commands to allow in Discussion mode. Press Enter on empty line to finish.\n', Colors.CYAN))
    added = []
    while True:
        cmd = input(color('> ', Colors.CYAN)).strip()
        if not cmd: break
        added.append(cmd)
        print(color(f"✓ Added '{cmd}'", Colors.GREEN))
    with ss.edit_config() as conf: conf.blocked_actions.bash_read_patterns.extend(added)

def _edit_bash_write_patterns():
    print_write_like_section()
    print(color('Add write-like commands to block in Discussion mode. Press Enter on empty line to finish.\n', Colors.CYAN))
    added = []
    while True:
        cmd = input(color('> ', Colors.CYAN)).strip()
        if not cmd: break
        added.append(cmd)
        print(color(f"✓ Added '{cmd}'", Colors.GREEN))
    with ss.edit_config() as conf: conf.blocked_actions.bash_write_patterns.extend(added)

def _ask_extrasafe_mode():
    print_extrasafe_section()
    val = inquirer.list_input(message='Extrasafe behavior for unrecognized bash commands in Discussion mode:', choices=['Extrasafe OFF (allows unrecognized commands)', 'Extrasafe ON (blocks unrecognized commands)'])
    with ss.edit_config() as conf: conf.blocked_actions.extrasafe = ('ON' in val)

def _edit_triggers_implementation():
    print_go_triggers_section()
    print(color('Add implementation-mode trigger phrases. Press Enter on empty line to finish.\n', Colors.CYAN))
    while True:
        phrase = input(color('> ', Colors.CYAN)).strip()
        if not phrase: break
        with ss.edit_config() as conf: conf.trigger_phrases.implementation_mode.append(phrase)
        print(color(f"✓ Added '{phrase}'", Colors.GREEN))

def _edit_triggers_discussion():
    print_no_triggers_section()
    print(color('Add discussion-mode trigger phrases. Press Enter on empty line to finish.\n', Colors.CYAN))
    while True:
        phrase = input(color('> ', Colors.CYAN)).strip()
        if not phrase: break
        with ss.edit_config() as conf: conf.trigger_phrases.discussion_mode.append(phrase)
        print(color(f"✓ Added '{phrase}'", Colors.GREEN))

def _edit_triggers_task_creation():
    print_create_section()
    print(color('Add task creation trigger phrases. Press Enter on empty line to finish.\n', Colors.CYAN))
    while True:
        phrase = input(color('> ', Colors.CYAN)).strip()
        if not phrase: break
        with ss.edit_config() as conf: conf.trigger_phrases.task_creation.append(phrase)
        print(color(f"✓ Added '{phrase}'", Colors.GREEN))

def _edit_triggers_task_startup():
    print_startup_section()
    print(color('Add task startup trigger phrases. Press Enter on empty line to finish.\n', Colors.CYAN))
    while True:
        phrase = input(color('> ', Colors.CYAN)).strip()
        if not phrase: break
        with ss.edit_config() as conf: conf.trigger_phrases.task_startup.append(phrase)
        print(color(f"✓ Added '{phrase}'", Colors.GREEN))

def _edit_triggers_task_completion():
    print_complete_section()
    print(color('Add task completion trigger phrases. Press Enter on empty line to finish.\n', Colors.CYAN))
    while True:
        phrase = input(color('> ', Colors.CYAN)).strip()
        if not phrase: break
        with ss.edit_config() as conf: conf.trigger_phrases.task_completion.append(phrase)
        print(color(f"✓ Added '{phrase}'", Colors.GREEN))

def _edit_triggers_compaction():
    print_compact_section()
    print(color('Add context compaction trigger phrases. Press Enter on empty line to finish.\n', Colors.CYAN))
    while True:
        phrase = input(color('> ', Colors.CYAN)).strip()
        if not phrase: break
        with ss.edit_config() as conf: conf.trigger_phrases.context_compaction.append(phrase)
        print(color(f"✓ Added '{phrase}'", Colors.GREEN))

def _ask_branch_enforcement():
    print_features_header()
    val = inquirer.list_input(message='Branch enforcement:', choices=['Enabled (recommended for git workflows)', 'Disabled (for alternative VCS like Jujutsu)'])
    with ss.edit_config() as conf: conf.features.branch_enforcement = ('Enabled' in val)

def _ask_auto_ultrathink():
    print_features_header()
    val = inquirer.list_input(message='Auto-ultrathink:', choices=['Enabled', 'Disabled (recommended for budget-conscious users)'])
    with ss.edit_config() as conf: conf.features.auto_ultrathink = (val == 'Enabled')

def _ask_nerd_fonts():
    print_features_header()
    val = inquirer.list_input(message='Nerd Fonts icons in statusline:', choices=['Enabled', 'Disabled (ASCII fallback)'])
    with ss.edit_config() as conf: conf.features.use_nerd_fonts = (val == 'Enabled')

def _ask_context_warnings():
    print_features_header()
    val = inquirer.list_input(message='Context warnings:', choices=['Both warnings enabled', 'Only 90% warning', 'Disabled'])
    with ss.edit_config() as conf:
        if 'Both' in val:
            conf.features.context_warnings.warn_85 = True
            conf.features.context_warnings.warn_90 = True
        elif 'Only' in val:
            conf.features.context_warnings.warn_85 = False
            conf.features.context_warnings.warn_90 = True
        else:
            conf.features.context_warnings.warn_85 = False
            conf.features.context_warnings.warn_90 = False

def _ask_statusline():
    print_statusline_header()
    val = inquirer.list_input(message='Use cc-sessions statusline?', choices=['Yes, use cc-sessions statusline', 'No, I have my own statusline'])
    if 'Yes' in val:
        settings_file = ss.PROJECT_ROOT / '.claude' / 'settings.json'
        if settings_file.exists(): with open(settings_file, 'r') as f: settings = json.load(f)
        else: settings = {}
        settings['statusLine'] = {'type': 'command', 'command': 'python $CLAUDE_PROJECT_DIR/sessions/statusline.py'}
        with open(settings_file, 'w') as f: json.dump(settings, f, indent=2)
        print(color('✓ Statusline configured in .claude/settings.json', Colors.GREEN))
    else: print(color('Statusline not configured.', Colors.CYAN))
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
        if did_import: run_config_editor() # Present config editor so user can tweak imported settings
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
