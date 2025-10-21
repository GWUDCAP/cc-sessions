# ===== IMPORTS ===== #

## ===== STDLIB ===== ##
import json, sys, subprocess, os
from pathlib import Path
from datetime import datetime, timezone
##-##

## ===== WINDOWS UTF-8 STDOUT FIX ===== ##
# Windows uses cp1252 by default, which can't encode Unicode block characters (█, ░)
# Force UTF-8 encoding for stdout to prevent UnicodeEncodeError
if sys.platform == 'win32':
    import io
    # Reconfigure stdout with UTF-8 encoding
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
##-##

## ===== 3RD-PARTY ===== ##
##-##

## ===== LOCAL ===== ##
if 'CLAUDE_PROJECT_DIR' in os.environ:
    PROJECT_ROOT = Path(os.environ['CLAUDE_PROJECT_DIR']).resolve()
    sys.path.insert(0, str(PROJECT_ROOT))
    # Use local symlinked sessions package when in development mode
    from sessions.hooks.shared_state import edit_state, Model, Mode, find_git_repo, load_state, IconStyle
else:
    # Use installed cc-sessions package in production
    from cc_sessions.hooks.shared_state import edit_state, Model, Mode, find_git_repo, load_state, IconStyle
##-##

#-#

# ===== FUNCTIONS ===== #

def find_current_transcript(transcript_path, session_id, stale_threshold=30):
    """
    Detect stale transcripts and find the current one by session ID.

    Args:
        transcript_path: Path to the transcript file we received
        session_id: Current session ID to match
        stale_threshold: Seconds threshold for considering transcript stale

    Returns:
        Path to the current transcript (may be same as input if not stale)
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return transcript_path

    try:
        # Read last line of transcript to get last message timestamp
        with open(transcript_path, 'r', encoding='utf-8', errors='backslashreplace') as f:
            lines = f.readlines()
            if not lines: return transcript_path

            last_line = lines[-1].strip()
            if not last_line: return transcript_path

            last_msg = json.loads(last_line)
            last_timestamp = last_msg.get('timestamp')

            if not last_timestamp: return transcript_path

            # Parse ISO timestamp and compare to current time
            last_time = datetime.fromisoformat(last_timestamp.replace('Z', '+00:00'))
            current_time = datetime.now(timezone.utc)
            age_seconds = (current_time - last_time).total_seconds()

            # If transcript is fresh, return it
            if age_seconds <= stale_threshold: return transcript_path

            # Transcript is stale - search for current one
            transcript_dir = Path(transcript_path).parent
            all_transcripts = sorted(
                transcript_dir.glob('*.jsonl'),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )[:5]  # Top 5 most recent

            # Check each transcript for matching session ID
            for candidate in all_transcripts:
                try:
                    with open(candidate, 'r', encoding='utf-8', errors='backslashreplace') as cf:
                        candidate_lines = cf.readlines()
                        if not candidate_lines: continue

                        # Check last line for session ID
                        candidate_last = json.loads(candidate_lines[-1].strip())
                        candidate_session_id = candidate_last.get('sessionId')

                        if candidate_session_id == session_id:
                            # Verify this transcript is fresh
                            candidate_timestamp = candidate_last.get('timestamp')
                            if candidate_timestamp:
                                candidate_time = datetime.fromisoformat(candidate_timestamp.replace('Z', '+00:00'))
                                candidate_age = (current_time - candidate_time).total_seconds()

                                if candidate_age <= stale_threshold: return str(candidate)
                except: continue

            # No fresh transcript found, return original
            return transcript_path

    except: return transcript_path # Any error, return original path

#-#

# ===== GLOBALS ===== #

#!> Parse input + set constants
# read json input from stdin
data = json.load(sys.stdin)

cwd = data.get("cwd", ".")
model_name = data.get("model", {}).get("display_name", "unknown")
session_id = data.get("session_id", "unknown")

task_dir = PROJECT_ROOT / "sessions" / "tasks"
#!<

#!> Colors/styles - with Windows ANSI detection
def supports_ansi():
    """Check if the current environment supports ANSI color codes."""
    # Windows detection
    if sys.platform == 'win32':
        # Windows Terminal and PowerShell 7+ support ANSI
        wt_session = os.environ.get('WT_SESSION')
        pwsh_version = os.environ.get('POWERSHELL_DISTRIBUTION_CHANNEL')

        # Windows Terminal always supports ANSI
        if wt_session:
            return True

        # PowerShell 7+ supports ANSI
        if pwsh_version and 'PSCore' in pwsh_version:
            return True

        # Try to enable ANSI on Windows 10+
        try:
            import platform
            win_ver = platform.version()
            # Windows 10 build 14393+ supports ANSI with VT100 mode
            if int(win_ver.split('.')[2]) >= 14393:
                # Enable VT100 processing
                import ctypes
                kernel32 = ctypes.windll.kernel32
                # Get stdout handle
                stdout_handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
                # Get current mode
                mode = ctypes.c_ulong()
                kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode))
                # Enable ENABLE_VIRTUAL_TERMINAL_PROCESSING (0x0004)
                mode.value |= 0x0004
                kernel32.SetConsoleMode(stdout_handle, mode.value)
                return True
        except:
            pass

        # Fallback: no ANSI support on old Windows
        return False

    # Unix-like systems support ANSI
    return True

# Determine if ANSI is supported
ansi_supported = supports_ansi()

# Define colors based on ANSI support
if ansi_supported:
    green = "\033[38;5;114m"
    orange = "\033[38;5;215m"
    red = "\033[38;5;203m"
    gray = "\033[38;5;242m"
    l_gray = "\033[38;5;250m"
    cyan = "\033[38;5;111m"
    purple = "\033[38;5;183m"
    reset = "\033[0m"
else:
    # No color support - use empty strings
    green = orange = red = gray = l_gray = cyan = purple = reset = ""
#!<

#!> Determine model and context limit
curr_model = None
context_limit = 160000
if "[1m]" in model_name.lower(): context_limit = 800000
if "sonnet" in model_name.lower(): curr_model = Model.SONNET
elif "opus" in model_name.lower(): curr_model = Model.OPUS
else: curr_model = Model.UNKNOWN
#!<

#!> Update model in shared state
STATE = load_state()
if not STATE or STATE.model != curr_model:
    with edit_state() as s: s.model = curr_model; STATE = s

# Load config for icon style preference
if 'CLAUDE_PROJECT_DIR' in os.environ:
    from sessions.hooks.shared_state import load_config
else:
    from cc_sessions.hooks.shared_state import load_config
CONFIG = load_config()
icon_style = CONFIG.features.icon_style if CONFIG else IconStyle.NERD_FONTS
#!<

#-#

"""
╔═══════════════════════════════════════════════════════════════════════════╗
║ ██████╗██████╗ █████╗ ██████╗██╗ ██╗██████╗██╗     ██████╗██╗  ██╗██████╗ ║
║ ██╔═══╝╚═██╔═╝██╔══██╗╚═██╔═╝██║ ██║██╔═══╝██║     ╚═██╔═╝███╗ ██║██╔═══╝ ║
║ ██████╗  ██║  ███████║  ██║  ██║ ██║██████╗██║       ██║  ████╗██║█████╗  ║
║ ╚═══██║  ██║  ██╔══██║  ██║  ██║ ██║╚═══██║██║       ██║  ██╔████║██╔══╝  ║
║ ██████║  ██║  ██║  ██║  ██║  ╚████╔╝██████║███████╗██████╗██║╚███║██████╗ ║
║ ╚═════╝  ╚═╝  ╚═╝  ╚═╝  ╚═╝   ╚═══╝ ╚═════╝╚══════╝╚═════╝╚═╝ ╚══╝╚═════╝ ║
╚═══════════════════════════════════════════════════════════════════════════╝
Sessions default status line script
Shows:
- Context usage progress bar (with Ayu Dark colors)
- Current task name
- Current mode (Discussion or Implementation)
- Count of edited & uncommitted files in the current git repo
- Count of open tasks in sessions/tasks (files + dirs)
"""

# ===== EXECUTION ===== #

## ===== PROGRESS BAR ===== ##

#!> Pull context length from transcript
context_length = None
transcript_path = data.get('transcript_path', None)

# Detect and recover from stale transcript
if transcript_path:
    transcript_path = find_current_transcript(transcript_path, session_id)

if transcript_path:
    try:
        with open(transcript_path, 'r', encoding='utf-8', errors='backslashreplace') as f: lines = f.readlines()
        most_recent_usage = None
        most_recent_timestamp = None

        for line in lines:
            try:
                data = json.loads(line.strip())
                # Skip sidechain entries (subagent calls)
                if data.get('isSidechain', False): continue

                # Check for usage data in main-chain messages
                if data.get('message', {}).get('usage'):
                    timestamp = data.get('timestamp')
                    if timestamp and (not most_recent_timestamp or timestamp > most_recent_timestamp):
                        most_recent_timestamp = timestamp
                        most_recent_usage = data['message']['usage']
            except: continue

        # Calculate context length (input + cache tokens only, NOT output)
        if most_recent_usage:
            context_length = (most_recent_usage.get('input_tokens', 0) + most_recent_usage.get('cache_read_input_tokens', 0) + most_recent_usage.get('cache_creation_input_tokens', 0))
    except Exception as e:
        pass
#!<

#!> Use context_length and context_limit to calculate context percentage
if context_length and context_length < 17000: context_length = 17000
if context_length and context_limit:
    pct = (context_length * 100) / context_limit
    progress_pct = f"{pct:.1f}"
    progress_pct_int = int(pct)
    if progress_pct_int > 100: progress_pct = "100.0"; progress_pct_int = 100
else:
    progress_pct = "0.0"
    progress_pct_int = 0
#!<

#!> Formatting and styling
# Format token counts in 'k'
formatted_tokens = f"{context_length // 1000}k" if context_length else "17k"
formatted_limit = f"{context_limit // 1000}k" if context_limit else "160k"

# Progress bar blocks (0-10)
filled_blocks = min(progress_pct_int // 10, 10)
empty_blocks = 10 - filled_blocks

# Ayu Dark colors (referencing from memory)
# TODO: Verify Ayu Dark code conversions
if progress_pct_int < 50: bar_color =  green
elif progress_pct_int < 80: bar_color = orange
else: bar_color = red
#!<

#!> Construct progress bar string
# Build progress bar string
progress_bar = []
if icon_style == IconStyle.NERD_FONTS:
    context_icon = "󱃖 "
elif icon_style == IconStyle.EMOJI:
    context_icon = ""
else:  # ASCII
    context_icon = ""
progress_bar.append(f"{reset}{l_gray}{context_icon} ")
progress_bar.append(bar_color + ("█" * filled_blocks))
progress_bar.append(gray + ("░" * empty_blocks))
progress_bar.append(reset + f" {l_gray}{progress_pct}% ({formatted_tokens}/{formatted_limit}){reset}")

progress_bar_str = "".join(progress_bar)
#!<
##-##

## ===== GIT REPOSITORY ===== ##
# Find git repository path for use in multiple sections
git_path = find_git_repo(Path(cwd))
##-##

## ===== GIT BRANCH & UPSTREAM TRACKING ===== ##
git_branch_info = None
upstream_info = None
if git_path:
    try:
        # Get current branch
        # Use absolute paths to avoid Windows path issues
        cwd_abs = str(Path(cwd).resolve())
        branch_cmd = ["git", "-C", cwd_abs, "branch", "--show-current"]
        branch = subprocess.check_output(branch_cmd, stderr=subprocess.PIPE, encoding='utf-8', errors='replace').strip()

        if branch:
            if icon_style == IconStyle.NERD_FONTS:
                branch_icon = "󰘬 "
            elif icon_style == IconStyle.EMOJI:
                branch_icon = "Branch: "
            else:  # ASCII
                branch_icon = "Branch: "
            git_branch_info = f"{l_gray}{branch_icon}{branch}{reset}"

            # Get upstream tracking status
            try:
                ahead_cmd = ["git", "-C", cwd_abs, "rev-list", "--count", "@{u}..HEAD"]
                ahead = int(subprocess.check_output(ahead_cmd, stderr=subprocess.PIPE, encoding='utf-8', errors='replace').strip())

                behind_cmd = ["git", "-C", cwd_abs, "rev-list", "--count", "HEAD..@{u}"]
                behind = int(subprocess.check_output(behind_cmd, stderr=subprocess.PIPE, encoding='utf-8', errors='replace').strip())

                upstream_parts = []
                if ahead > 0:
                    upstream_parts.append(f"↑ {ahead}")
                if behind > 0:
                    upstream_parts.append(f"↓ {behind}")
                if upstream_parts:
                    upstream_info = f"{orange}{''.join(upstream_parts)}{reset}"
            except:
                # No upstream or error getting upstream status
                upstream_info = None
        else:
            # Detached HEAD - show commit hash with detached indicator
            commit_cmd = ["git", "-C", cwd_abs, "rev-parse", "--short", "HEAD"]
            commit = subprocess.check_output(commit_cmd, stderr=subprocess.PIPE, encoding='utf-8', errors='replace').strip()
            if commit:
                if icon_style == IconStyle.NERD_FONTS:
                    # Broken link icon to indicate detached
                    git_branch_info = f"{l_gray}󰌺 @{commit}{reset}"
                else:  # EMOJI or ASCII
                    git_branch_info = f"{l_gray}@{commit} [detached]{reset}"
    except (subprocess.CalledProcessError, OSError, ValueError) as e:
        # Git command failed - common on Windows if git not in PATH or repo issues
        git_branch_info = None
##-##

## ===== SESSIONS DISABLED CHECK ===== ##
# If sessions are disabled, show simplified statusline and exit
if not CONFIG.features.sessions_enabled:
    # Line 1 - Progress bar | Disabled message
    context_part = progress_bar_str if progress_bar_str else f"{gray}No context usage data{reset}"
    disabled_msg = f"{gray}cc-sessions disabled{reset}"
    print(f"{context_part} | {disabled_msg}")

    # Line 2 - Git branch only (if available)
    if git_branch_info:
        line2_parts = [git_branch_info]
        if upstream_info:
            line2_parts.append(upstream_info)
        print(" | ".join(line2_parts))
    else:
        print("")

    sys.exit(0)
##-##

## ===== CURRENT TASK ===== ##
curr_task = STATE.current_task.name if STATE else None
##-##

## ===== CURRENT MODE ===== ##
curr_mode = "Implement" if STATE.mode == Mode.GO else "Discuss"
if icon_style == IconStyle.NERD_FONTS:
    mode_icon = "󰷫 " if STATE.mode == Mode.GO else "󰭹 "
elif icon_style == IconStyle.EMOJI:
    mode_icon = "🛠️: " if STATE.mode == Mode.GO else "💬:"
else:  # ASCII
    mode_icon = "Mode:"
##-##

## ===== COUNT EDITED & UNCOMMITTED ===== ##
# Use subprocess to count edited and uncommitted files (unstaged or staged)
total_edited = 0
if git_path:
    try:
        # Use absolute paths for Windows compatibility
        cwd_abs = str(Path(cwd).resolve())

        # Count unstaged changes
        unstaged_cmd = ["git", "-C", cwd_abs, "diff", "--name-only"]
        unstaged_files = subprocess.check_output(unstaged_cmd, stderr=subprocess.PIPE, encoding='utf-8', errors='replace').strip().split('\n')
        unstaged_count = len([f for f in unstaged_files if f])  # Filter out empty strings

        # Count staged changes
        staged_cmd = ["git", "-C", cwd_abs, "diff", "--cached", "--name-only"]
        staged_files = subprocess.check_output(staged_cmd, stderr=subprocess.PIPE, encoding='utf-8', errors='replace').strip().split('\n')
        staged_count = len([f for f in staged_files if f])  # Filter out empty strings

        total_edited = unstaged_count + staged_count
    except (subprocess.CalledProcessError, OSError, ValueError):
        # Git command failed - set to 0 and continue
        total_edited = 0
##-##

## ===== COUNT OPEN TASKS ===== ##
open_task_count = 0
open_task_dir_count = 0

if task_dir.exists() and task_dir.is_dir():
    for file in task_dir.iterdir():
        if file.is_file() and file.name != "TEMPLATE.md" and file.suffix == ".md": open_task_count += 1
        if file.is_dir() and file.name not in ("done", "indexes"): open_task_dir_count += 1
##-##

## ===== FINAL OUTPUT ===== ##
# Line 1 - Progress bar | Task
context_part = progress_bar_str if progress_bar_str else f"{gray}No context usage data{reset}"
if icon_style == IconStyle.NERD_FONTS:
    task_icon = "󰒓 "
elif icon_style == IconStyle.EMOJI:
    task_icon = "⚙️ "
else:  # ASCII
    task_icon = "Task: "
task_part = f"{cyan}{task_icon}{curr_task}{reset}" if curr_task else f"{cyan}{task_icon}{gray}No Task{reset}"
print(f"{context_part} | {task_part}")

# Line 2 - Mode | Edited & Uncommitted with upstream | Open Tasks | Git branch
if icon_style == IconStyle.NERD_FONTS:
    tasks_icon = "󰈙 "
elif icon_style == IconStyle.EMOJI:
    tasks_icon = "💼 "
else:  # ASCII
    tasks_icon = ""
# Build uncommitted section with optional upstream indicators
uncommitted_parts = [f"{orange}✎ {total_edited}{reset}"]
if upstream_info:
    uncommitted_parts.append(upstream_info)
uncommitted_str = " ".join(uncommitted_parts)

line2_parts = [
    f"{purple}{mode_icon} {curr_mode}{reset}",
    uncommitted_str,
    f"{cyan}{tasks_icon} {open_task_count + open_task_dir_count} open{reset}"
]
if git_branch_info:
    line2_parts.append(git_branch_info)
print(" | ".join(line2_parts))
##-##

#-#
