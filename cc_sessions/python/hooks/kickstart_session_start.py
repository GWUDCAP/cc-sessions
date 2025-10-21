#!/usr/bin/env python3

# ===== IMPORTS ===== #

## ===== STDLIB ===== ##
import sys
import json
import os
import platform
from datetime import datetime
from pathlib import Path
##-##

## ===== 3RD-PARTY ===== ##
##-##

## ===== LOCAL ===== ##
# Import from shared_state (runtime file lives in sessions/hooks)
HOOKS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = HOOKS_DIR.parent.parent
sys.path.insert(0, str(HOOKS_DIR))
from shared_state import load_state, edit_state, load_config
##-##

#-#

# ===== GLOBALS ===== #

## ===== CI DETECTION ===== ##
def is_ci_environment():
    """Check if running in a CI environment (GitHub Actions)."""
    ci_indicators = [
        'GITHUB_ACTIONS',         # GitHub Actions
        'GITHUB_WORKFLOW',        # GitHub Actions workflow
        'CI',                     # Generic CI indicator (set by GitHub Actions)
        'CONTINUOUS_INTEGRATION', # Generic CI (alternative)
    ]
    return any(os.getenv(indicator) for indicator in ci_indicators)

# Skip kickstart session start hook in CI environments
if is_ci_environment():
    sys.exit(0)
##-##

## ===== MODULE SEQUENCES ===== ##
FULL_MODE_SEQUENCE = [
    '01-discussion.md',
    '02-implementation.md',
    '03-tasks-overview.md',
    '04-task-creation.md',
    '05-task-startup.md',
    '06-task-completion.md',
    '07-compaction.md',
    '08-agents.md',
    '09-api.md',
    '10-advanced.md',
    '11-graduation.md'
]

SUBAGENTS_MODE_SEQUENCE = [
    '01-agents-only.md'
]
##-##

#-#

# ===== FUNCTIONS ===== #

def load_protocol_file(relative_path: str) -> str:
    """Load protocol markdown from protocols directory."""
    protocol_path = PROJECT_ROOT / 'sessions' / 'protocols' / relative_path
    if not protocol_path.exists():
        return f"Error: Protocol file not found: {relative_path}"
    return protocol_path.read_text()

#-#

"""
Kickstart SessionStart Hook

Handles onboarding flow for users who chose kickstart in installer:
- Checks for kickstart metadata (should ALWAYS exist if this hook is running)
- Loads first module on first run, resumes from current_index on subsequent runs
- Sequences determined by mode (full or subagents)
"""

# ===== EXECUTION ===== #

#!> 1. Load state and check kickstart metadata
STATE = load_state()
CONFIG = load_config()

# Early exit if sessions are disabled
if not CONFIG.features.sessions_enabled:
    sys.exit(0)

# Get kickstart metadata (should ALWAYS exist if this hook is running)
kickstart_meta = STATE.metadata.get('kickstart')
if not kickstart_meta:
    # This is a BUG - fail loudly
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "ERROR: kickstart_session_start hook fired but no kickstart metadata found. This is an installer bug."
        }
    }))
    sys.exit(1)

mode = kickstart_meta.get('mode')  # 'full' or 'subagents'
if not mode:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "ERROR: kickstart metadata exists but no mode specified. This is an installer bug."
        }
    }))
    sys.exit(1)
#!<

#!> 2. Output deterministic instructions for Claude to begin kickstart via API
# Detect OS for correct sessions command
is_windows = platform.system() == "Windows"
sessions_cmd = "sessions/bin/sessions.bat" if is_windows else "sessions/bin/sessions"

begin_cmd = f'{sessions_cmd} kickstart subagents' if mode == 'subagents' else f'{sessions_cmd} kickstart full'
instructions = (
    "Kickstart onboarding is enabled. Begin immediately by running:\n\n"
    f"  {begin_cmd}\n\n"
    "Then, for each module chunk returned, follow all instructions completely. When finished with a chunk, run:\n\n"
    f"  {sessions_cmd} kickstart next\n\n"
    "Repeat until kickstart is complete.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "USER INSTRUCTIONS:\n"
    "Just say 'kickstart' and press enter to begin\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": instructions
    }
}))
sys.exit(0)
#!<
