#!/usr/bin/env python3

# ===== IMPORTS ===== #

## ===== STDLIB ===== ##
import json, sys, math, bisect, os
from collections import deque
from pathlib import Path
from datetime import datetime, timezone
##-##

## ===== 3RD-PARTY ===== ##
##-##

## ===== LOCAL ===== ##
from shared_state import edit_state, PROJECT_ROOT, load_config
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
            if not lines:
                return transcript_path

            last_line = lines[-1].strip()
            if not last_line:
                return transcript_path

            last_msg = json.loads(last_line)
            last_timestamp = last_msg.get('timestamp')

            if not last_timestamp:
                return transcript_path

            # Parse ISO timestamp and compare to current time
            last_time = datetime.fromisoformat(last_timestamp.replace('Z', '+00:00'))
            current_time = datetime.now(timezone.utc)
            age_seconds = (current_time - last_time).total_seconds()

            # If transcript is fresh, return it
            if age_seconds <= stale_threshold:
                return transcript_path

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
                        if not candidate_lines:
                            continue

                        # Check last line for session ID
                        candidate_last = json.loads(candidate_lines[-1].strip())
                        candidate_session_id = candidate_last.get('sessionId')

                        if candidate_session_id == session_id:
                            # Verify this transcript is fresh
                            candidate_timestamp = candidate_last.get('timestamp')
                            if candidate_timestamp:
                                candidate_time = datetime.fromisoformat(candidate_timestamp.replace('Z', '+00:00'))
                                candidate_age = (current_time - candidate_time).total_seconds()

                                if candidate_age <= stale_threshold:
                                    return str(candidate)
                except:
                    continue

            # No fresh transcript found, return original
            return transcript_path

    except:
        # Any error, return original path
        return transcript_path

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

# Skip subagent hooks in CI environments
if is_ci_environment():
    sys.exit(0)
##-##

# Load input from stdin
try: input_data = json.load(sys.stdin)
except json.JSONDecodeError as e: print(f"Error: Invalid JSON input: {e}", file=sys.stderr); sys.exit(1)

# Load config and check if sessions are enabled
CONFIG = load_config()
if not CONFIG.features.sessions_enabled:
    sys.exit(0)

# Check if this is a Task tool call
tool_name = input_data.get("tool_name", "")
if tool_name != "Task": sys.exit(0)

# Get the transcript path and session ID from the input data
transcript_path = input_data.get("transcript_path", "")
session_id = input_data.get("session_id", "")
if not transcript_path: sys.exit(0)

# Detect and recover from stale transcript
if transcript_path:
    transcript_path = find_current_transcript(transcript_path, session_id)

# Get the transcript into memory
with open(transcript_path, 'r', encoding='utf-8', errors='backslashreplace') as f: transcript = [json.loads(line) for line in f]
transcript = deque(transcript)
#-#

"""
╔═══════════════════════════════════════════════════════════════════╗
║ ██████╗██╗ ██╗█████╗  █████╗  █████╗██████╗██╗  ██╗██████╗██████╗ ║
║ ██╔═══╝██║ ██║██╔═██╗██╔══██╗██╔═══╝██╔═══╝███╗ ██║╚═██╔═╝██╔═══╝ ║
║ ██████╗██║ ██║█████╔╝███████║██║    █████╗ ████╗██║  ██║  ██████╗ ║
║ ╚═══██║██║ ██║██╔═██╗██╔══██║██║ ██╗██╔══╝ ██╔████║  ██║  ╚═══██║ ║
║ ██████║╚████╔╝█████╔╝██║  ██║╚█████║██████╗██║╚███║  ██║  ██████║ ║
║ ╚═════╝ ╚═══╝ ╚════╝ ╚═╝  ╚═╝ ╚════╝╚═════╝╚═╝ ╚══╝  ╚═╝  ╚═════╝ ║
╚═══════════════════════════════════════════════════════════════════╝
PreToolUse:Task:subagent_type hooks

This module handles PreToolUse processing for the Task tool:
    - Chunks the transcript for subagents based on token limits
    - Saves transcript chunks to designated directories
    - Sets flags to manage subagent context
"""

# ===== EXECUTION ===== #

#!> Set subagent flag
with edit_state() as s: s.flags.subagent = True; STATE = s
#!<

#!> Trunc + clean transcript
# Remove any pre-work transcript entries
start_found = False
while not start_found and transcript:
    entry = transcript.popleft()
    message = entry.get('message')
    if message:
        content = message.get('content')
        if isinstance(content, list):
            for block in content:
                if block.get('type') == 'tool_use' and block.get('name') in ['Edit', 'MultiEdit', 'Write']: start_found = True

# Clean the transcript
clean_transcript = deque()
for entry in transcript:
    message = entry.get('message')
    message_type = entry.get('type')

    if message and message_type in ['user', 'assistant']:
        content = message.get('content')
        role = message.get('role')
        clean_entry = { 'role': role, 'content': content }
        clean_transcript.append(clean_entry)
#!<

#!> Prepare subagent dir for transcript files
subagent_type = 'shared'
if not clean_transcript: print("[Subagent] No relevant transcript entries found, skipping snapshot."); sys.exit(0)
task_call = clean_transcript[-1]
content = task_call.get('content')
if isinstance(content, list):
    for block in content:
        if block.get('type') == 'tool_use' and block.get('name') == 'Task':
            task_input = block.get('input') or {}
            subagent_type = task_input.get('subagent_type', subagent_type)

# Clear the current transcript directory
BATCH_DIR = PROJECT_ROOT / 'sessions' / 'transcripts' / subagent_type
BATCH_DIR.mkdir(parents=True, exist_ok=True)
for item in BATCH_DIR.iterdir():
    if item.is_file(): item.unlink()
#!<

#!> Chunk and save transcript batches
MAX_BYTES = 24000
usable_context = 160000
if STATE.model == "sonnet": usable_context = 800000
clean_transcript_text = json.dumps(list(clean_transcript), indent=2, ensure_ascii=False)

chunks = []
buf_chars = []
buf_bytes = 0
last_newline_idx = None
last_space_idx = None

for ch in clean_transcript_text:
    ch_b = len(ch.encode("utf-8"))

    # If overflowing, flush a chunk
    if buf_bytes + ch_b > MAX_BYTES:
        cut_idx = None
        if last_newline_idx is not None: cut_idx = last_newline_idx
        elif last_space_idx is not None: cut_idx = last_space_idx
        if cut_idx is not None and cut_idx > 0:
            # Emit chunk up to the breakpoint
            chunks.append("".join(buf_chars[:cut_idx]))
            remainder = buf_chars[cut_idx:]
            buf_chars = remainder
            buf_bytes = sum(len(c.encode("utf-8")) for c in buf_chars)
        else:
            # No breakpoints, hard cut what we got
            if buf_chars: chunks.append("".join(buf_chars))
            buf_chars = []
            buf_bytes = 0

        last_newline_idx = None
        last_space_idx = None

    buf_chars.append(ch)
    buf_bytes += ch_b

    if ch == "\n": last_newline_idx = len(buf_chars); last_space_idx = None
    elif ch == " " and last_newline_idx is None: last_space_idx = len(buf_chars)

# Flush any remaining buffer
if buf_chars: chunks.append("".join(buf_chars))

assert all(len(c.encode("utf-8")) <= MAX_BYTES for c in chunks), "Chunking failed to enforce byte limit"

for idx, chunk in enumerate(chunks, start=1):
    part_name = f"current_transcript_{idx:03d}.txt"
    part_path = BATCH_DIR / part_name
    with part_path.open('w', encoding='utf-8', newline="\n") as f: f.write(chunk)
#!<

#-#

# Allow the tool call to proceed
sys.exit(0)
