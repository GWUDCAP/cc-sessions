#!/usr/bin/env python3

# ===== IMPORTS ===== #

## ===== STDLIB ===== ##
from importlib.metadata import version, PackageNotFoundError
import requests, json, sys, shutil, os, subprocess, platform
from typing import Dict, List, Optional, Tuple
##-##

## ===== 3RD-PARTY ===== ##
##-##

## ===== LOCAL ===== ##
from shared_state import edit_state, PROJECT_ROOT, load_config, SessionsProtocol, get_task_file_path, is_directory_task
##-##

#-#

# ===== GLOBALS ===== #
sessions_dir = PROJECT_ROOT / 'sessions'

STATE = None
CONFIG = load_config()

# Early exit if sessions are disabled
if not CONFIG.features.sessions_enabled:
    sys.exit(0)

developer_name = CONFIG.environment.developer_name

# Initialize context
context = f"You are beginning a new context window with the developer, {developer_name}.\n\n"

# Quick configuration checks
needs_setup = False
quick_checks = []

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
##-##

#-#

"""
╔═══════════════════════════════════════════════════════════════════════════════════════════════╗
║ ██████╗██████╗██████╗██████╗██████╗ █████╗ ██╗  ██╗      ██████╗██████╗ █████╗ █████╗ ██████╗ ║
║ ██╔═══╝██╔═══╝██╔═══╝██╔═══╝╚═██╔═╝██╔══██╗███╗ ██║      ██╔═══╝╚═██╔═╝██╔══██╗██╔═██╗╚═██╔═╝ ║
║ ██████╗█████╗ ██████╗██████╗  ██║  ██║  ██║████╗██║      ██████╗  ██║  ███████║█████╔╝  ██║   ║
║ ╚═══██║██╔══╝ ╚═══██║╚═══██║  ██║  ██║  ██║██╔████║      ╚═══██║  ██║  ██╔══██║██╔═██╗  ██║   ║
║ ██████║██████╗██████║██████║██████╗╚█████╔╝██║╚███║      ██████║  ██║  ██║  ██║██║ ██║  ██║   ║
║ ╚═════╝╚═════╝╚═════╝╚═════╝╚═════╝ ╚════╝ ╚═╝ ╚══╝      ╚═════╝  ╚═╝  ╚═╝  ╚═╝╚═╝ ╚═╝  ╚═╝   ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════╝
SessionStart Hook

Initializes session state and loads task context:
- Checks for required components (daic command, tiktoken)  
- Clears session warning flags and stale state
- Loads current task or lists available tasks
- Updates task status from pending to in-progress
"""

# ===== FUNCTIONS ===== #

def parse_index_file(index_path) -> Optional[Tuple[Dict, List[str]]]:
    """Parse an index file and extract metadata and task lines."""
    if not index_path.exists():
        return None

    try:
        content = index_path.read_text()
        lines = content.split('\n')
    except (IOError, UnicodeDecodeError):
        return None

    # Extract frontmatter using simple string parsing (like task files)
    metadata = {}
    if lines and lines[0] == '---':
        for i, line in enumerate(lines[1:], 1):
            if line == '---':
                break
            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip()

    # Extract task lines (those starting with - `)
    task_lines = []
    for line in lines:
        if line.strip().startswith('- `'):
            task_lines.append(line.strip())

    return metadata, task_lines

def list_open_tasks_grouped() -> str:
    """List open tasks grouped by their indexes."""
    tasks_dir = PROJECT_ROOT / 'sessions' / 'tasks'
    indexes_dir = tasks_dir / 'indexes'

    # Helper to get status from a task file
    def get_task_status(task_path):
        try:
            with task_path.open('r', encoding='utf-8') as f:
                lines = f.readlines()[:10]
            for line in lines:
                if line.startswith('status:'):
                    status = line.split(':')[1].strip()
                    if status != 'complete':
                        return status
        except (IOError, UnicodeDecodeError):
            pass
        return None

    # Step 1: Collect all .md files directly under tasks/ (exclude TEMPLATE.md)
    file_tasks_map = {}  # name -> status
    if tasks_dir.exists():
        for file in sorted(tasks_dir.glob('*.md')):
            if file.name != 'TEMPLATE.md':
                status = get_task_status(file)
                if status:
                    file_tasks_map[file.name] = status

    # Step 2: Collect all subdirectories (exclude indexes/ and done/)
    dir_tasks_map = {}  # dirname -> {status, subtasks: []}
    if tasks_dir.exists():
        for task_dir in sorted([d for d in tasks_dir.iterdir() if d.is_dir() and d.name not in ['done', 'indexes']]):
            readme_file = task_dir / 'README.md'
            if readme_file.exists():
                status = get_task_status(readme_file)
                if status:
                    dir_tasks_map[task_dir.name] = {'status': status, 'subtasks': []}

                    # Collect subtasks
                    for subtask in sorted(task_dir.glob('*.md')):
                        if subtask.name not in ['TEMPLATE.md', 'README.md']:
                            subtask_status = get_task_status(subtask)
                            if subtask_status:
                                dir_tasks_map[task_dir.name]['subtasks'].append({
                                    'name': f"{task_dir.name}/{subtask.name}",
                                    'status': subtask_status
                                })

    # Step 3: Parse index files
    index_info = {}
    if indexes_dir.exists():
        for index_file in sorted(indexes_dir.glob('*.md')):
            result = parse_index_file(index_file)
            if result:
                metadata, task_lines = result
                if metadata and 'index' in metadata:
                    index_id = metadata['index']
                    index_info[index_id] = {
                        'name': metadata.get('name', index_id),
                        'description': metadata.get('description', ''),
                        'tasks': []
                    }

                    # Extract task names from the lines
                    for line in task_lines:
                        if '`' in line:
                            try:
                                start = line.index('`') + 1
                                end = line.index('`', start)
                                task = line[start:end]
                                index_info[index_id]['tasks'].append(task)
                            except ValueError:
                                continue

    # Step 4: For each index, match against file tasks
    for index_id in index_info:
        valid_tasks = []
        for task in index_info[index_id]['tasks']:
            if task in file_tasks_map:
                valid_tasks.append({'name': task, 'status': file_tasks_map[task]})
                del file_tasks_map[task]  # Remove from unindexed
        index_info[index_id]['tasks'] = valid_tasks

    # Step 5: For each index, match against directory tasks and expand
    for index_id in index_info:
        expanded_tasks = []
        for task in index_info[index_id]['tasks']:
            expanded_tasks.append(task)  # Keep existing file tasks

        # Re-parse to get original task list for this index
        original_tasks = []
        if indexes_dir.exists():
            for index_file in sorted(indexes_dir.glob('*.md')):
                result = parse_index_file(index_file)
                if result:
                    metadata, task_lines = result
                    if metadata and metadata.get('index') == index_id:
                        for line in task_lines:
                            if '`' in line:
                                try:
                                    start = line.index('`') + 1
                                    end = line.index('`', start)
                                    original_tasks.append(line[start:end])
                                except ValueError:
                                    continue

        for task in original_tasks:
            # Check if it's a directory reference (with or without trailing /)
            dir_name = task.rstrip('/')
            if dir_name in dir_tasks_map:
                # Add the directory itself with / suffix
                expanded_tasks.append({'name': f"{dir_name}/", 'status': dir_tasks_map[dir_name]['status']})
                # Add all subtasks
                for subtask in dir_tasks_map[dir_name]['subtasks']:
                    expanded_tasks.append(subtask)
                del dir_tasks_map[dir_name]  # Remove from unindexed

        index_info[index_id]['tasks'] = expanded_tasks

    # Step 6: Build output
    output = "No active task set. Available tasks:\n\n"

    # Display indexed tasks
    for index_id, info in sorted(index_info.items()):
        if info['tasks']:
            output += f"## {info['name']}\n"
            if info['description']:
                output += f"{info['description']}\n"
            for task in info['tasks']:
                output += f"  • {task['name']} ({task['status']})\n"
            output += "\n"

    # Display unindexed tasks (remaining in file_tasks_map and dir_tasks_map)
    unindexed_tasks = []
    for name, status in file_tasks_map.items():
        unindexed_tasks.append({'name': name, 'status': status})
    for name, data in dir_tasks_map.items():
        unindexed_tasks.append({'name': f"{name}/", 'status': data['status']})
        for subtask in data['subtasks']:
            unindexed_tasks.append(subtask)

    if unindexed_tasks:
        output += "## Uncategorized\n"
        for task in sorted(unindexed_tasks, key=lambda x: x['name']):
            output += f"  • {task['name']} ({task['status']})\n"
        output += "\n"

    # Add startup instructions
    output += f"""To select a task:
- Type in one of your startup commands: {CONFIG.trigger_phrases.task_startup}
- Include the task file you would like to start using `@`
- Hit Enter to activate task startup
"""
    return output

#-#

# ===== EXECUTION ===== #

#!> 1. Clear flags and todos for new session
with edit_state() as s: 
    s.flags.clear_flags()
    s.todos.clear_active()
    restored = s.todos.restore_stashed()
    STATE = s
context += "Cleared session flags and active todos for new session.\n\n"

if restored:
    context += f"""Restored {restored} stashed todos from previous session:\n\n{STATE.todos.active}\n\nTo clear, use `cd .claude/hooks && python -c \"from shared_state import edit_state; with edit_state() as s: s.todos.clear_stashed()\"`\n\n"""
#!<

#!> 2. Nuke transcripts dir
transcripts_dir = sessions_dir / 'transcripts'
if transcripts_dir.exists(): shutil.rmtree(transcripts_dir, ignore_errors=True)
#!<

#!> 3. Load current task or list available tasks
# Check for active task
if (task_file := STATE.current_task.file_path) and task_file.exists():
    # Check if task status is pending and update to in-progress
    task_content = task_file.read_text()
    task_updated = False

    # Parse task frontmatter to check status
    if task_content.startswith('---'):
        lines = task_content.split('\n')
        for i, line in enumerate(lines[1:], 1):
            if line.startswith('---'):
                break
            if line.startswith('status: pending'):
                lines[i] = 'status: in-progress'
                task_updated = True
                # Write back the updated content
                task_file.write_text('\n'.join(lines))
                task_content = '\n'.join(lines)
                break

        # Output the full task state
        context += f"""Current task state:
```json
{json.dumps(STATE.current_task.task_state, indent=2)}
```

Loading task file: {STATE.current_task.file}
{"=" * 60}
{task_content}
{"=" * 60}

"""

    context += f"""Since you are resuming an in-progress task, follow these instructions:

    1. Analyze the task requirements and work completed thoroughly
    2. Analyze any next steps itemized in the task file and, if necessary, ask any questions from the user for clarification.
    3. Propose implementation plan with structured format:

```markdown
[PLAN: Implementation Approach]
Based on the task requirements, I propose the following implementation:

□ [Specific action 1]
  → [Expanded explanation of what this involves]

□ [Specific action 2]
  → [Expanded explanation of what this involves]

□ [Specific action 3]
  → [Expanded explanation of what this involves]

To approve these todos, you may use any of your implementation mode trigger phrases: 
{CONFIG.trigger_phrases.implementation_mode}
```

3. Iterate based on user feedback until approved
4. Upon approval, convert proposed todos to TodoWrite exactly as written

**IMPORTANT**: Until your todos are approved, you are seeking the user's approval of an explicitly proposed and properly explained list of execution todos. Besides answering user questions during discussion, your messages should end with an expanded explanation of each todo, the clean list of todos, and **no further messages**.

**For the duration of the task**:
- Discuss before implementing
- Constantly seek user input and approval

Once approved, remember:
- *Immediately* load your proposed todo items *exactly* as you proposed them using ToDoWrite
- Work logs are maintained by the logging agent (not manually)

After completion of the last task in any todo list:
- *Do not* try to run any write-based tools (you will be automatically put into discussion mode)
- Repeat todo proposal and approval workflow for any additional write/edit-based work"""

else:
    context += list_open_tasks_grouped()
#!<

#!> 4. Check cc-sessions version with flag-based caching
try: current_version = version('cc-sessions')
except PackageNotFoundError: current_version = None

# Check update flag in metadata
update_flag = STATE.metadata.get('update_available')
latest_version = STATE.metadata.get('latest_version')

# If flag doesn't exist, check PyPI
if update_flag is None and current_version:
    try:
        resp = requests.get("https://pypi.org/pypi/cc-sessions/json", timeout=2)
        if resp.ok:
            latest_version = resp.json().get("info", {}).get("version")

            # Set flag based on semantic version comparison
            def version_tuple(v):
                """Convert version string to tuple for comparison."""
                try:
                    return tuple(map(int, v.split('.')))
                except (ValueError, AttributeError):
                    return (0, 0, 0)

            is_newer = version_tuple(latest_version) > version_tuple(current_version)

            with edit_state() as s:
                s.metadata['current_version'] = current_version
                s.metadata['latest_version'] = latest_version
                s.metadata['update_available'] = is_newer
                update_flag = s.metadata['update_available']
    except requests.RequestException:
        pass

# Display update notification if flag is True
if update_flag and latest_version and current_version:
    # Detect OS for correct sessions command
    is_windows = platform.system() == "Windows"
    sessions_cmd = "sessions/bin/sessions.bat" if is_windows else "sessions/bin/sessions"

    # Show manual update message
    # Extract first few lines from CHANGELOG for the latest version
    try:
        changelog_path = PROJECT_ROOT.parent / 'CHANGELOG.md'
        if changelog_path.exists():
            with open(changelog_path, 'r') as f:
                content = f.read()
                # Find the latest version section
                import re
                version_pattern = rf'##\s*\[{re.escape(latest_version)}\]'
                match = re.search(version_pattern, content)
                if match:
                    # Extract until next ## or end
                    start = match.end()
                    next_heading = content.find('\n## ', start)
                    section = content[start:next_heading if next_heading != -1 else start+500].strip()
                    # Get all lines of changes
                    lines = [l.strip() for l in section.split('\n') if l.strip() and l.strip().startswith('-')]
                    changelog_excerpt = '\n'.join(f"  {l}" for l in lines)
                else:
                    changelog_excerpt = None
        else:
            changelog_excerpt = None
    except:
        changelog_excerpt = None

    context += f"""
[IMPORTANT: Update Available]

A new version of cc-sessions is available: {current_version} → {latest_version}

"""
    if changelog_excerpt:
        context += f"""What's new in this version:
{changelog_excerpt}

"""

    context += f"""**BEFORE STARTING ANY WORK:**
You must stop and ask the user about this update first.

First, ask the user: "I see there's a new version of cc-sessions available ({latest_version}) with several new features. Would you like to update now? The installer will guide you through any new configuration options."

If YES:
  1. Tell them to run in their terminal: pip install --upgrade cc-sessions
  2. Wait for them to complete the installation
  3. Remind them they'll need to start a new session after updating

If NO:
  - Continue with the session normally
  - They can suppress this notification: {sessions_cmd} state update suppress
  - They can check update status anytime: {sessions_cmd} state update status

This notification will appear on every session start until they update or suppress it.

"""
#!<

#-#

# Skip session start hook in CI environments
if is_ci_environment():
    sys.exit(0)

output = {
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": context
    }
}
print(json.dumps(output))

sys.exit(0)
