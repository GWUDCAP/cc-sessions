#!/usr/bin/env python3

# ===== IMPORTS ===== #

## ===== STDLIB ===== ##
from pathlib import Path
import json, sys, os, platform
##-##

## ===== 3RD-PARTY ===== ##
##-##

## ===== LOCAL ===== ##
  # Add sessions to path if CLAUDE_PROJECT_DIR is available (symlink setup)
if 'CLAUDE_PROJECT_DIR' in os.environ:
    sessions_path = os.path.join(os.environ['CLAUDE_PROJECT_DIR'], 'sessions')
    hooks_path = os.path.join(sessions_path, 'hooks')
    if hooks_path not in sys.path:
        sys.path.insert(0, hooks_path)

try:
    # Try direct import (works with sessions in path or package install)
    from shared_state import load_state, edit_state, Mode, PROJECT_ROOT, CCTodo, load_config, SessionsProtocol, is_directory_task, is_subtask, is_parent_task
except ImportError:
    # Fallback to package import
    from cc_sessions.hooks.shared_state import load_state, edit_state, Mode, PROJECT_ROOT, CCTodo, load_config, SessionsProtocol, is_directory_task, is_subtask, is_parent_task
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

# Skip user messages hook in CI environments
if is_ci_environment():
    sys.exit(0)
##-##

input_data = json.load(sys.stdin)
prompt = input_data.get("prompt", "")
transcript_path = input_data.get("transcript_path", "")

STATE = load_state()
CONFIG = load_config()

# Early exit if sessions are disabled
if not CONFIG.features.sessions_enabled:
    sys.exit(0)

# Check if this is a slash command we handle via API
prompt_stripped = prompt.strip()
api_commands = ['/mode', '/state', '/config', '/add-trigger', '/remove-trigger']
is_api_command = any(prompt_stripped.startswith(cmd) for cmd in api_commands) if prompt_stripped else False

# Only add ultrathink if not an API command
if CONFIG.features.auto_ultrathink and not is_api_command: context = "[[ ultrathink ]]\n\n"
else: context = ""

#!> Trigger phrase detection
def phrase_matches(phrase, text):
    """Check if phrase matches text. Case-sensitive if phrase is all caps, case-insensitive otherwise."""
    if phrase.isupper():
        return phrase in text
    else:
        return phrase.lower() in text.lower()

implementation_phrase_detected = any(phrase_matches(phrase, prompt) for phrase in CONFIG.trigger_phrases.implementation_mode)
discussion_phrase_detected = any(phrase_matches(phrase, prompt) for phrase in CONFIG.trigger_phrases.discussion_mode)
task_creation_detected = any(phrase_matches(phrase, prompt) for phrase in CONFIG.trigger_phrases.task_creation)
task_completion_detected = any(phrase_matches(phrase, prompt) for phrase in CONFIG.trigger_phrases.task_completion)
task_start_detected = any(phrase_matches(phrase, prompt) for phrase in CONFIG.trigger_phrases.task_startup)
compaction_detected = any(phrase_matches(phrase, prompt) for phrase in CONFIG.trigger_phrases.context_compaction)
#!<

#!> Flags
had_active_todos = False
#!<

#-#

"""
╔═══════════════════════════════════════════════════════════════════════════════════════════╗
║ ██████╗ █████╗  █████╗ ███╗  ███╗██████╗ ██████╗  ██╗  ██╗ █████╗  █████╗ ██╗  ██╗██████╗ ║
║ ██╔══██╗██╔═██╗██╔══██╗████╗████║██╔══██╗╚═██╔═╝  ██║  ██║██╔══██╗██╔══██╗██║ ██╔╝██╔═══╝ ║
║ ██████╔╝█████╔╝██║  ██║██╔███║██║██████╔╝  ██║    ███████║██║  ██║██║  ██║█████╔╝ ██████╗ ║
║ ██╔═══╝ ██╔═██╗██║  ██║██║╚══╝██║██╔═══╝   ██║    ██╔══██║██║  ██║██║  ██║██╔═██╗ ╚═══██║ ║
║ ██║     ██║ ██║╚█████╔╝██║    ██║██║       ██║    ██║  ██║╚█████╔╝╚█████╔╝██║  ██╗██████║ ║
║ ╚═╝     ╚═╝ ╚═╝ ╚════╝ ╚═╝    ╚═╝╚═╝       ╚═╝    ╚═╝  ╚═╝ ╚════╝  ╚════╝ ╚═╝  ╚═╝╚═════╝ ║
╚═══════════════════════════════════════════════════════════════════════════════════════════╝
UserPromptSubmit Hook

Manages DAIC mode transitions and protocol triggers:
- Detects trigger phrases for mode switching and protocol activation  
- Monitors context window usage and provides warnings
- Auto-loads protocol todos when protocols are triggered
- Clears active todos when switching contexts
"""

# ===== FUNCTIONS ===== #
def load_protocol_file(relative_path):
    """Load a protocol file or chunk from sessions/protocols/"""
    file_path = PROJECT_ROOT / 'sessions' / 'protocols' / relative_path
    if not file_path.exists(): return ""
    with open(file_path, 'r', encoding='utf-8', errors='backslashreplace') as f: return f.read()

def format_todos_for_protocol(todos):
    """Format a list of CCTodo objects for display in protocols."""
    lines = ["## Protocol Todos", "<!-- Use TodoWrite to add these todos exactly as written -->"]
    for todo in todos:
        lines.append(f"□ {todo.content}")
    return "\n".join(lines)

def get_context_length_from_transcript(transcript_path):
    """Get current context length from the most recent main-chain message in transcript"""
    try:
        with open(transcript_path, 'r', encoding='utf-8', errors='backslashreplace') as f: lines = f.readlines()

        most_recent_usage = None
        most_recent_timestamp = None
        # Parse each JSONL entry
        for line in lines:
            try:
                data = json.loads(line.strip())
                # Skip sidechain entries (subagent calls)
                if data.get('isSidechain', False): continue

                # Check if this entry has usage data
                if data.get('message', {}).get('usage'):
                    entry_time = data.get('timestamp')
                    # Track the most recent main-chain entry with usage
                    if entry_time and (not most_recent_timestamp or entry_time > most_recent_timestamp):
                        most_recent_timestamp = entry_time
                        most_recent_usage = data['message']['usage']
            except json.JSONDecodeError: continue

        # Calculate context length from most recent usage
        if most_recent_usage:
            context_length = (
                most_recent_usage.get('input_tokens', 0) +
                most_recent_usage.get('cache_read_input_tokens', 0) +
                most_recent_usage.get('cache_creation_input_tokens', 0)
            )
            return context_length
    except Exception: pass
    return 0
#-#

# ===== EXECUTION ===== #

## ===== TOKEN MONITORING ===== ##
# Check context usage and warn if needed
if transcript_path and os.path.exists(transcript_path):
    context_length = get_context_length_from_transcript(transcript_path)

    if context_length > 0:
        # Calculate percentage of usable context (opus 160k/sonnet 800k practical limit before auto-compact)
        usable_tokens = 160000
        if STATE.model == "sonnet": usable_tokens = 800000
        usable_percentage = (context_length / usable_tokens) * 100

        # Token warnings (only show once per session)
        if usable_percentage >= 90 and not STATE.flags.context_90 and CONFIG.features.context_warnings.warn_90:
            context += f"\n[90% WARNING] {context_length:,}/{usable_tokens:,} tokens used ({usable_percentage:.1f}%). CRITICAL: Run sessions/protocols/task-completion.md to wrap up this task cleanly!\n"
            with edit_state() as s: s.flags.context_90 = True; STATE = s
        elif usable_percentage >= 85 and not STATE.flags.context_85 and CONFIG.features.context_warnings.warn_85:
            context += f"\n[Warning] Context window is {usable_percentage:.1f}% full ({context_length:,}/{usable_tokens:,} tokens). The danger zone is >90%. You will receive another warning when you reach 90% - don't panic but gently guide towards context compaction or task completion (if task is nearly complete). Task completion often satisfies compaction requirements and should allow the user to clear context safely, so you do not need to worry about fitting in both processes.\n"
            with edit_state() as s: s.flags.context_85 = True; STATE = s
##-##

## ===== TRIGGER DETECTION ===== ##

#!> Discussion/Implementation mode toggling
# Implementation triggers (only work in discussion mode, skip for /add-trigger)
if not is_api_command and STATE.mode is Mode.NO and implementation_phrase_detected:
    with edit_state() as s: s.mode = Mode.GO; STATE = s
    context += """[DAIC: Implementation Mode Activated]
CRITICAL RULES:
- Convert your proposed todos to TodoWrite EXACTLY as written
- Do NOT add new todos - only implement approved items
- Do NOT remove todos - complete them or return to discussion
- Check off each todo as you complete it
- If you discover you need to change your approach, return to discussion mode using the API command
- Todo list defines your execution boundary
- When all todos are complete, you'll auto-return to discussion
"""

# Emergency stop (works in any mode)
if STATE.mode is Mode.GO and discussion_phrase_detected:  # Case sensitive
    # DEBUG: Log what triggered this
    import datetime
    debug_log_path = PROJECT_ROOT / "sessions" / "mode-revert-debug.log"
    with open(debug_log_path, "a", encoding='utf-8', errors='backslashreplace') as log:
        log.write(f"\n[{datetime.datetime.now().isoformat()}] EMERGENCY STOP TRIGGERED\n")
        log.write(f"  Prompt: {prompt[:200]}...\n")
        log.write(f"  discussion_phrase_detected: {discussion_phrase_detected}\n")
        log.write(f"  Trigger phrases: {CONFIG.trigger_phrases.discussion_mode}\n")

    with edit_state() as s: s.mode = Mode.NO; s.todos.clear_active(); STATE = s
    context += "[DAIC: EMERGENCY STOP] All tools locked. You are now in discussion mode. Re-align with your pair programmer.\n"
#!<

#!> Task creation
if not is_api_command and task_creation_detected:
    # Define todos for this protocol
    todos = [
        CCTodo(
            content='Create task file from template with appropriate priority, type, and structure',
            activeForm='Creating task file from template'),
        CCTodo(
            content='Ask user about task success and propose success criteria',
            activeForm='Asking user about task success and proposing success criteria'),
        CCTodo(
            content='Run context-gathering agent to create context manifest',
            activeForm='Running context-gathering agent to create context manifest'),
        CCTodo(
            content='Update appropriate service index files',
            activeForm='Updating appropriate service index files'),
        CCTodo(
            content='Commit the new task file',
            activeForm='Committing the new task file')]
    
    # Load and compose protocol based on config
    protocol_content = load_protocol_file('task-creation/task-creation.md')

    # Build template variables
    if CONFIG.git_preferences.has_submodules: submodules_field = "\n  - submodules: List all submodules requiring git branches for the task (all that will be affected)"
    else: submodules_field = ""
 
    template_vars = {
        'submodules_field': submodules_field,
        'todos': format_todos_for_protocol(todos)
    }

    # Format protocol with template variables
    if protocol_content: protocol_content = protocol_content.format(**template_vars)

    with edit_state() as s: 
        s.mode = Mode.GO; s.active_protocol = SessionsProtocol.CREATE
        if s.todos.active: had_active_todos = True; s.todos.stash_active()
        s.todos.active = todos
        STATE = s

    context += "[Task Creation Notice]\n"

    if protocol_content:
        context += f"User triggered task creation. Protocol:\n{protocol_content}\n"
    else:
        # Fallback to old behavior if protocol not found
        context += f"User triggered task creation. Read sessions/protocols/task-creation.md\n"

    if had_active_todos:
        context += "\nYour previous todos have been stashed and will be restored after task creation is complete.\n"
#!<

#!> Task completion
if not is_api_command and task_completion_detected:
    # Define todos for this protocol
    todos = [
        CCTodo(
            content='Verify all success criteria are checked off',
            activeForm='Verifying status of success criteria'),
        CCTodo(
            content='Run code-review agent and address any critical issues',
            activeForm='Running code-review agent'),
        CCTodo(
            content='Run logging agent to consolidate work logs',
            activeForm='Running logging agent to consolidate work logs'),
        CCTodo(
            content='Run service-documentation agent to update CLAUDE.md files and other documentation',
            activeForm='Running service-documentation agent to update documentation'),
        CCTodo(
            content='Mark task file complete and move to tasks/done/',
            activeForm='Archiving task file')
    ]

    # Build commit todo based on auto_merge preference and directory task status
    commit_content = 'Commit changes'
    # Check if this is a directory task - if so, don't merge until all subtasks complete
    if STATE.current_task.file and is_directory_task(STATE.current_task.file):
        commit_content += ' (directory task - no merge until all subtasks complete)'
    elif CONFIG.git_preferences.auto_merge:
        commit_content += f' and merge to {CONFIG.git_preferences.default_branch}'
    else:
        commit_content += f' and ask if user wants to merge to {CONFIG.git_preferences.default_branch}'

    todos.append(CCTodo(
        content=commit_content,
        activeForm='Committing and handling merge'))

    # Add push todo based on auto_push preference
    if CONFIG.git_preferences.auto_push:
        todos.append(CCTodo(
            content='Push changes to remote',
            activeForm='Pushing changes to remote'))
    else:
        todos.append(CCTodo(
            content='Ask if user wants to push changes to remote',
            activeForm='Asking about pushing to remote'))

    # Load and compose protocol based on config
    protocol_content = load_protocol_file('task-completion/task-completion.md')
 
    # Build template variables based on configuration
    template_vars = {
        'default_branch': CONFIG.git_preferences.default_branch,
        'todos': format_todos_for_protocol(todos)
    }

    # Git add warning (only for add_pattern == "all")
    if CONFIG.git_preferences.add_pattern == 'all': template_vars['git_add_warning'] = load_protocol_file('task-completion/git-add-warning.md')
    else: template_vars['git_add_warning'] = ''

    # Staging instructions based on add_pattern
    if CONFIG.git_preferences.add_pattern == 'all': template_vars['staging_instructions'] = load_protocol_file('task-completion/staging-all.md')
    else: template_vars['staging_instructions'] = load_protocol_file('task-completion/staging-ask.md')  # Default to 'ask' for safety

    # Commit instructions based on has_submodules
    if CONFIG.git_preferences.has_submodules: commit_instructions_content = load_protocol_file('task-completion/commit-superrepo.md')
    else: commit_instructions_content = load_protocol_file('task-completion/commit-standard.md')

    # Directory task completion check - simplified to just control merge behavior
    directory_completion_check = ''
    if STATE.current_task.file and is_directory_task(STATE.current_task.file):
        if is_parent_task(STATE.current_task.file):
            # Completing parent README.md - normal merge behavior
            directory_completion_check = load_protocol_file('task-completion/directory-task-completion.md')
            directory_completion_check = directory_completion_check.format(default_branch=CONFIG.git_preferences.default_branch)
        elif is_subtask(STATE.current_task.file):
            # Completing a subtask - commit but don't merge
            directory_completion_check = load_protocol_file('task-completion/subtask-completion.md')
            directory_completion_check = directory_completion_check.format(default_branch=CONFIG.git_preferences.default_branch)

    # Build merge and push instructions based on auto preferences (but override for subtasks)
    if STATE.current_task.file and is_subtask(STATE.current_task.file):
        merge_instruction = 'Do not merge yet - subtask in directory task'
    elif CONFIG.git_preferences.auto_merge:
        merge_instruction = f'Merge into {CONFIG.git_preferences.default_branch}'
    else:
        merge_instruction = f'Ask user if they want to merge into {CONFIG.git_preferences.default_branch}'

    if CONFIG.git_preferences.auto_push: push_instruction = 'Push the merged branch to remote'
    else: push_instruction = 'Ask user if they want to push to remote'

    # Load commit style guidance based on preference
    if CONFIG.git_preferences.commit_style == 'conventional':
        template_vars['commit_style_guidance'] = load_protocol_file('task-completion/commit-style-conventional.md')
    elif CONFIG.git_preferences.commit_style == 'simple':
        template_vars['commit_style_guidance'] = load_protocol_file('task-completion/commit-style-simple.md')
    elif CONFIG.git_preferences.commit_style == 'detailed':
        template_vars['commit_style_guidance'] = load_protocol_file('task-completion/commit-style-detailed.md')
    else:
        # Default to conventional if not specified
        template_vars['commit_style_guidance'] = load_protocol_file('task-completion/commit-style-conventional.md')

    # Format commit instructions with merge/push
    template_vars['commit_instructions'] = commit_instructions_content.format(merge_instruction=merge_instruction, push_instruction=push_instruction, commit_style_guidance=template_vars['commit_style_guidance'], default_branch=CONFIG.git_preferences.default_branch)

    # Add directory task completion check
    template_vars['directory_completion_check'] = directory_completion_check

    # Format protocol with all template variables
    if protocol_content: protocol_content = protocol_content.format(**template_vars)

    with edit_state() as s:
        s.mode = Mode.GO; s.active_protocol = SessionsProtocol.COMPLETE
        s.todos.active = todos
        STATE = s

    context += "[Task Completion Notice]\n"

    if protocol_content: context += f"User triggered task completion. Protocol:\n{protocol_content}\n"
    else: context += f"User triggered task completion. Read sessions/protocols/task-completion.md\n"
#!<

#!> Task startup
if not is_api_command and task_start_detected:
    task_reference = None
    words = prompt.split()
    for word in words:
        if word.startswith("@") and ("sessions/tasks/" in word) and word.endswith(".md"):
            task_reference = word.split('sessions/tasks/')[-1]
            break

    # Load and compose protocol based on config
    protocol_content = load_protocol_file('task-startup/task-startup.md')

    # Load conditional chunks
    if CONFIG.git_preferences.has_submodules:
        submodule_management_raw = load_protocol_file('task-startup/submodule-management.md')
        # Format the submodule management content with default_branch
        submodule_management = submodule_management_raw.format(default_branch=CONFIG.git_preferences.default_branch) if submodule_management_raw else ""
        resume_notes = load_protocol_file('task-startup/resume-notes-superrepo.md')
    else:
        submodule_management = ""
        resume_notes = load_protocol_file('task-startup/resume-notes-standard.md')

    # Check if this is a directory task and load appropriate guidance
    directory_guidance = ""
    if STATE.current_task.file and is_directory_task(STATE.current_task.file):
        if is_parent_task(STATE.current_task.file):
            # Starting parent README.md - create task branch
            directory_guidance = load_protocol_file('task-startup/directory-task-startup.md')
        elif is_subtask(STATE.current_task.file):
            # Starting a subtask - ensure on parent task branch
            directory_guidance = load_protocol_file('task-startup/subtask-startup.md')

    # Set todos based on config
    todo_branch_content = 'Create/checkout task branch and matching submodule branches' if CONFIG.git_preferences.has_submodules else 'Create/checkout task branch'
    todo_branch_active = 'Creating/checking out task branches' if CONFIG.git_preferences.has_submodules else 'Creating/checking out task branch'

    # Build todos list - will add read task todo conditionally
    todos = [
        CCTodo(
            content='Check git status and handle any uncommitted changes',
            activeForm='Checking git status and handling uncommitted changes'),
        CCTodo(
            content=todo_branch_content,
            activeForm=todo_branch_active),
        CCTodo(
            content='Verify context manifest for the task',
            activeForm='Verifying context manifest'),
        CCTodo(
            content='Gather context for the task',
            activeForm='Catching up to speed...')
    ]

    # Check if task will be auto-loaded
    # Detect OS for correct sessions command
    is_windows = platform.system() == "Windows"
    sessions_cmd = "sessions/bin/sessions.bat" if is_windows else "sessions/bin/sessions"

    context += "[Task Startup Notice]\n**If the user mentioned which task to start, *YOU MUST***:\n"
    context += "1. Return to project root directory\n"
    context += f"2. Run: `{sessions_cmd} protocol startup-load <task-file>`\n"
    context += "You must do this *BEFORE* the task startup protocol.\n"
    context += "Otherwise, ask which task they want to start, then use the command from project root.\n\n"

    # Build template variables for protocol
    git_status_scope = 'in both super-repo and all submodules' if CONFIG.git_preferences.has_submodules else ''
    
    # Build git handling instructions based on add_pattern
    if CONFIG.git_preferences.add_pattern == 'all':
        git_handling = '- Commit ALL changes'
    else:  # 'ask' pattern
        git_handling = '- Either commit changes or explicitly discuss with user'
    
    template_vars = {
        'default_branch': CONFIG.git_preferences.default_branch,
        'submodule_branch_todo': ' and matching submodule branches' if CONFIG.git_preferences.has_submodules else '',
        'submodule_context': ' (and submodules list)' if CONFIG.git_preferences.has_submodules else '',
        'submodule_management_section': submodule_management,
        'resume_notes': resume_notes,
        'directory_guidance': directory_guidance,
        'git_status_scope': git_status_scope,
        'git_handling': git_handling,
        'todos': format_todos_for_protocol(todos),
        'implementation_mode_triggers': f"[{', '.join(phrase for phrase in CONFIG.trigger_phrases.implementation_mode)}]" if CONFIG.trigger_phrases.implementation_mode else "[]"
    }

    # Format protocol with template variables
    if protocol_content: protocol_content = protocol_content.format(**template_vars)

    # Set state with todos
    with edit_state() as s:
        s.mode = Mode.GO; s.active_protocol = SessionsProtocol.START
        s.api.startup_load = True; s.todos.clear_active()
        s.todos.active = todos
        STATE = s

    # Auto-load protocol content
    if protocol_content: context += f"User triggered task startup. Protocol:\n{protocol_content}\n"
    else: context += "User triggered task startup. Read sessions/protocols/task-startup.md\n"
#!<

#!> Context compaction
if not is_api_command and compaction_detected:
    # Define todos for this protocol
    todos = [
        CCTodo(
            content='Run logging agent to update work logs',
            activeForm='Running logging agent to update work logs'),
        CCTodo(
            content='Run context-refinement agent to check for discoveries',
            activeForm='Running context-refinement agent to check for discoveries'),
        CCTodo(
            content='Run service-documentation agent if service interfaces changed',
            activeForm='Running service-documentation agent if service interfaces changed')]

    # Load protocol content
    protocol_content = load_protocol_file('context-compaction/context-compaction.md')

    # Build template variables
    template_vars = {
        'todos': format_todos_for_protocol(todos)
    }

    # Format protocol with template variables
    if protocol_content: protocol_content = protocol_content.format(**template_vars)

    if STATE.todos.active: 
        had_active_todos = True
        with edit_state() as s: s.todos.stash_active(); STATE = s

    with edit_state() as s: 
        s.mode = Mode.GO; s.active_protocol = SessionsProtocol.COMPACT
        s.todos.active = todos
        STATE = s

    context += "[Context Compaction Notice]\n"

    if protocol_content:
        context += f"User triggered context compaction. Protocol:\n{protocol_content}\n"
    else:
        # Fallback to old behavior if protocol not found
        context += f"User triggered context compaction. Read sessions/protocols/context-compaction.md\n"

    if had_active_todos: context += "Your todos have been stashed and will be restored in the next session after the user clears context. Do not attempt to update or complete your previous todo list (context compaction todos are now active).\n"
#!<

#!> Iterloop detection
if "iterloop" in prompt.lower():
    context += "ITERLOOP DETECTED:\nYou have been instructed to iteratively loop over a list. Identify what list the user is referring to, then follow this loop: present one item, wait for the user to respond with questions and discussion points, only continue to the next item when the user explicitly says 'continue' or something similar\n"
#!<

##-##

#-#

# Output the context additions
output = { "hookSpecificOutput": { "hookEventName": "UserPromptSubmit", "additionalContext": context } }
print(json.dumps(output))

sys.exit(0)
