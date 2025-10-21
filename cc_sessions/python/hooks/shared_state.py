#!/usr/bin/env python3

# ===== IMPORTS ===== #

## ===== STDLIB ===== ##
from __future__ import annotations

from typing import Optional, List, Dict, Any, Iterator, Literal, Union
from importlib.metadata import version, PackageNotFoundError
from dataclasses import dataclass, asdict, field
from contextlib import contextmanager, suppress
import json, os, tempfile, shutil, sys
from time import monotonic, sleep
from pathlib import Path
from enum import Enum
##-##

## ===== 3RD-PARTY ===== ##
##-##

## ===== LOCAL ===== ##
##-##

#-#

# ===== GLOBALS ===== #
def find_project_root() -> Path:
    if (p := os.environ.get("CLAUDE_PROJECT_DIR")): return Path(p)
    cur = Path.cwd()
    for parent in (cur, *cur.parents):
        if (parent / ".claude").exists(): return parent
    print("Error: Could not find project root (no .claude directory).", file=sys.stderr)
    sys.exit(2)

PROJECT_ROOT = find_project_root()
STATE_FILE = PROJECT_ROOT / "sessions" / "sessions-state.json"
LOCK_DIR  = STATE_FILE.with_suffix(".lock")
CONFIG_FILE = PROJECT_ROOT / "sessions" / "sessions-config.json"

# Mode description strings
DISCUSSION_MODE_MSG = "You are now in Discussion Mode and should focus on discussing and investigating with the user (no edit-based tools)"
IMPLEMENTATION_MODE_MSG = "You are now in Implementation Mode and may use tools to execute the agreed upon actions - when you are done return immediately to Discussion Mode"
#-#

"""
╔════════════════════════════════════════════════════════════════════════════════════════╗
║ ██████╗██╗  ██╗ █████╗ █████╗ ██████╗█████╗       ██████╗██████╗ █████╗ ██████╗██████╗ ║
║ ██╔═══╝██║  ██║██╔══██╗██╔═██╗██╔═══╝██╔═██╗      ██╔═══╝╚═██╔═╝██╔══██╗╚═██╔═╝██╔═══╝ ║
║ ██████╗███████║███████║█████╔╝█████╗ ██║ ██║      ██████╗  ██║  ███████║  ██║  █████╗  ║
║ ╚═══██║██╔══██║██╔══██║██╔═██╗██╔══╝ ██║ ██║      ╚═══██║  ██║  ██╔══██║  ██║  ██╔══╝  ║
║ ██████║██║  ██║██║  ██║██║ ██║██████╗█████╔╝      ██████║  ██║  ██║  ██║  ██║  ██████╗ ║
║ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝ ╚═╝╚═════╝╚════╝       ╚═════╝  ╚═╝  ╚═╝  ╚═╝  ╚═╝  ╚═════╝ ║
╚════════════════════════════════════════════════════════════════════════════════════════╝
SharedState Module

Provides centralized state management for hooks:
- DAIC mode tracking and toggling
- Task state persistence  
- Active todo list management
- Project root detection

Release note (v0.3.0):
So ppl are already asking about paralellism so we're going to maybe make this less pain in the dik by providing some locking and atomic writing despite not really needing it for the main thread rn. If it becomes super annoying then multi-session bros will have to take ritalin.
"""

# ===== DECLARATIONS ===== #

## ===== EXCEPTIONS ===== ##
class StateError(RuntimeError): pass

class StashOccupiedError(RuntimeError): pass
##-##

## ===== ENUMS ===== ##

#!> Config enums
class TriggerCategory(str, Enum):
    IMPLEMENTATION_MODE = "implementation_mode"
    DISCUSSION_MODE = "discussion_mode"
    TASK_CREATION = "task_creation"
    TASK_STARTUP = "task_startup"
    TASK_COMPLETION = "task_completion"
    CONTEXT_COMPACTION = "context_compaction"

class GitAddPattern(str, Enum):
    ASK = "ask"
    ALL = "all"

class GitCommitStyle(str, Enum):
    REG = "conventional"
    SIMP = "simple"
    OP = "detailed"

class UserOS(str, Enum):
    LINUX = "linux" # All Linux distros and Unix-likes
    MACOS = "macos"
    WINDOWS = "windows"

class UserShell(str, Enum):
    BASH = "bash"
    ZSH = "zsh"
    FISH = "fish"
    POWERSHELL = "powershell"
    CMD = "cmd"

class IconStyle(str, Enum):
    NERD_FONTS = "nerd_fonts"
    EMOJI = "emoji"
    ASCII = "ascii"

class CCTools(str, Enum):
    READ = "Read"
    WRITE = "Write"
    EDIT = "Edit"
    MULTIEDIT = "MultiEdit"
    NOTEBOOKEDIT = "NotebookEdit"
    GREP = "Grep"
    GLOB = "Glob"
    LS = "LS"
    BASH = "Bash"
    BASHOUTPUT = "BashOutput"
    KILLBASH = "KillBash"
    WEBSEARCH = "WebSearch"
    WEBFETCH = "WebFetch"
    TASK = "Task"
    TODOWRITE = "TodoWrite"
    EXITPLANMODE = "ExitPlanMode"
#!<

#!> State enums
class SessionsProtocol(str, Enum):
    COMPACT = "context-compaction"
    CREATE = "task-creation"
    START = "task-startup"
    COMPLETE = "task-completion"

class Mode(str, Enum):
    NO = "discussion"
    GO = "implementation"

class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class Model(str, Enum):
    OPUS = "opus"
    SONNET = "sonnet"
    UNKNOWN = "unknown"
#!<
##-##

## ===== DATA CLASSES ===== ##

#!> Config components
@dataclass
class TriggerPhrases:
    implementation_mode: List[str] = field(default_factory=lambda: ["yert"])
    discussion_mode: List[str] = field(default_factory=lambda: ["SILENCE"])
    task_creation: List[str] = field(default_factory=lambda: ["mek:"])
    task_startup: List[str] = field(default_factory=lambda: ["start^"])
    task_completion: List[str] = field(default_factory=lambda: ["finito"])
    context_compaction: List[str] = field(default_factory=lambda: ["squish"])

    def _coax_phrase_type(self, phrase_type: str) -> TriggerCategory:
        mapping = {
            "implement": TriggerCategory.IMPLEMENTATION_MODE,
            "discuss": TriggerCategory.DISCUSSION_MODE,
            "create": TriggerCategory.TASK_CREATION,
            "start": TriggerCategory.TASK_STARTUP,
            "complete": TriggerCategory.TASK_COMPLETION,
            "compact": TriggerCategory.CONTEXT_COMPACTION,
            "implementation_mode": TriggerCategory.IMPLEMENTATION_MODE,
            "discussion_mode": TriggerCategory.DISCUSSION_MODE,
            "task_creation": TriggerCategory.TASK_CREATION,
            "task_startup": TriggerCategory.TASK_STARTUP,
            "task_completion": TriggerCategory.TASK_COMPLETION,
            "context_compaction": TriggerCategory.CONTEXT_COMPACTION
        }
        if phrase_type in mapping: return mapping[phrase_type]
        raise ValueError(f"Unknown phrase type: {phrase_type}")

    def add_phrase(self, category: TriggerCategory, phrase: str) -> bool:
        """Add a phrase to the specified category. Returns True if added, False if already present."""
        if isinstance(category, str): category = self._coax_phrase_type(category)
        lst = getattr(self, category.value, None)
        if lst is None or not isinstance(lst, list): raise ValueError(f"Unknown trigger category: {category}")
        if phrase in lst: return False
        lst.append(phrase)
        return True

    def remove_phrase(self, category: TriggerCategory, phrase: str) -> bool:
        """Remove a phrase from the specified category. Returns True if removed, False if not found."""
        if isinstance(category, str): category = self._coax_phrase_type(category)
        lst = getattr(self, category.value, None)
        if lst is None or not isinstance(lst, list): raise ValueError(f"Unknown trigger category: {category}")
        if phrase in lst:
            lst.remove(phrase)
            return True
        return False

    def has_phrase(self, phrase: str) -> Optional[TriggerCategory]:
        """Return the category of the phrase if found, else None."""
        for category in TriggerCategory:
            lst = getattr(self, category.value, [])
            if phrase in lst: return category
        return None

    def list_phrases(self, category: Optional[Union[TriggerCategory, Literal["discuss", "implement", "create", "start", "complete", "compact"]]] = None) -> Dict[str, List[str]]:
        """Return all phrases, or those in the specified category."""
        if category:
            if isinstance(category, str): category = self._coax_phrase_type(category)
            lst = getattr(self, category.value, None)
            if lst is None or not isinstance(lst, list): raise ValueError(f"Unknown trigger category: {category}")
            return {category.value: lst}
        return {
            TriggerCategory.IMPLEMENTATION_MODE.value: self.implementation_mode,
            TriggerCategory.DISCUSSION_MODE.value: self.discussion_mode,
            TriggerCategory.TASK_CREATION.value: self.task_creation,
            TriggerCategory.TASK_STARTUP.value: self.task_startup,
            TriggerCategory.TASK_COMPLETION.value: self.task_completion,
            TriggerCategory.CONTEXT_COMPACTION.value: self.context_compaction,
        }

@dataclass
class GitPreferences:
    add_pattern: GitAddPattern = GitAddPattern.ASK
    default_branch: str = "main"
    commit_style: GitCommitStyle = GitCommitStyle.REG
    auto_merge: bool = False
    auto_push: bool = False
    has_submodules: bool = False

@dataclass
class SessionsEnv:
    os: UserOS = UserOS.LINUX
    shell: UserShell = UserShell.BASH
    developer_name: str = "developer"

    def is_windows(self) -> bool:
        return self.os == UserOS.WINDOWS

    def is_unix(self) -> bool:
        return self.os in (UserOS.LINUX, UserOS.MACOS)

@dataclass
class BlockingPatterns:
    implementation_only_tools: List[CCTools] = field(default_factory=lambda: [CCTools.EDIT, CCTools.WRITE, CCTools.MULTIEDIT, CCTools.NOTEBOOKEDIT])
    bash_read_patterns: List[str] = field(default_factory=lambda: [])
    bash_write_patterns: List[str] = field(default_factory=lambda: [])
    extrasafe: bool = False

    def _coax_cc_tool(self, tool: str) -> CCTools:
        try: return CCTools(tool)
        except ValueError: raise ValueError(f"Unknown tool: {tool}")

    def is_tool_blocked(self, tool: Union[CCTools, str]) -> bool:
        """Return True if the tool is blocked in discussion mode."""
        if isinstance(tool, str): tool = self._coax_cc_tool(tool)
        return tool in self.implementation_only_tools

    def add_blocked_tool(self, tool: CCTools) -> bool:
        """Add a tool to the blocked list. Returns True if added, False if already present."""
        if isinstance(tool, str): tool = self._coax_cc_tool(tool)
        if tool in self.implementation_only_tools: return False
        self.implementation_only_tools.append(tool)
        return True

    def remove_blocked_tool(self, tool: CCTools) -> bool:
        """Remove a tool from the blocked list. Returns True if removed, False if not found."""
        if isinstance(tool, str): tool = self._coax_cc_tool(tool)
        if tool in self.implementation_only_tools:
            self.implementation_only_tools.remove(tool)
            return True
        return False

    def add_custom_pattern(self, pattern: str) -> bool:
        """Add a custom pattern to the blocked list. Returns True if added, False if already present."""
        if pattern not in self.bash_write_patterns: self.bash_write_patterns.append(pattern)
        return True

    def remove_custom_pattern(self, pattern: str) -> bool:
        """Remove a custom pattern from the blocked list. Returns True if removed, False if not found."""
        if pattern in self.bash_write_patterns: self.bash_write_patterns.remove(pattern)
        return True

    def add_readonly_command(self, command: str) -> bool:
        """Add a command to the allowed readonly list. Returns True if added, False if already present."""
        if command in self.bash_read_patterns: return True
        self.bash_read_patterns.append(command)
        return True

    def remove_readonly_command(self, command: str) -> bool:
        """Remove a command from the readonly list. Returns True if removed, False if not found."""
        if command in self.bash_read_patterns: self.bash_read_patterns.remove(command)
        return True

@dataclass
class ContextWarnings:
    warn_85: bool = True
    warn_90: bool = True

@dataclass
class EnabledFeatures:
    branch_enforcement: bool = True
    task_detection: bool = True
    auto_ultrathink: bool = True
    sessions_enabled: bool = True
    icon_style: IconStyle = IconStyle.NERD_FONTS
    context_warnings: ContextWarnings = field(default_factory=ContextWarnings)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EnabledFeatures":
        cw_data = d.get("context_warnings", {})
        if cw_data and isinstance(cw_data, dict): cw = ContextWarnings(**cw_data)
        else: cw = ContextWarnings()

        # Handle migration from old use_nerd_fonts boolean to new icon_style enum
        icon_style_value = d.get("icon_style")
        if icon_style_value is None:
            # Check for old boolean field
            old_use_nerd_fonts = d.get("use_nerd_fonts")
            if old_use_nerd_fonts is not None:
                # Migrate: True -> NERD_FONTS, False -> ASCII
                icon_style_value = IconStyle.NERD_FONTS if old_use_nerd_fonts else IconStyle.ASCII
            else:
                # No old or new field, use default
                icon_style_value = IconStyle.NERD_FONTS
        elif isinstance(icon_style_value, str):
            # Convert string to enum
            try:
                icon_style_value = IconStyle(icon_style_value)
            except ValueError:
                icon_style_value = IconStyle.NERD_FONTS

        return cls(
            branch_enforcement=d.get("branch_enforcement", True),
            task_detection=d.get("task_detection", True),
            auto_ultrathink=d.get("auto_ultrathink", True),
            sessions_enabled=d.get("sessions_enabled", True),
            icon_style=icon_style_value,
            context_warnings=cw
        )
#!<

#!> Config object
@dataclass
class SessionsConfig:
    trigger_phrases: TriggerPhrases = field(default_factory=TriggerPhrases)
    git_preferences: GitPreferences = field(default_factory=GitPreferences)
    environment: SessionsEnv = field(default_factory=SessionsEnv)
    blocked_actions: BlockingPatterns = field(default_factory=BlockingPatterns)
    features: EnabledFeatures = field(default_factory=EnabledFeatures)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SessionsConfig":
        return cls(
            trigger_phrases=TriggerPhrases(**d.get("trigger_phrases", {})),
            git_preferences=GitPreferences(**d.get("git_preferences", {})),
            environment=SessionsEnv(**d.get("environment", {})),
            blocked_actions=BlockingPatterns(**d.get("blocked_actions", {})),
            features=EnabledFeatures.from_dict(d.get("features", {})))

    def to_dict(self) -> Dict[str, Any]: return asdict(self)
#!<

#!> State components
@dataclass
class TaskState:
    name: Optional[str] = None
    file: Optional[str] = None
    branch: Optional[str] = None
    status: Optional[str] = None
    created: Optional[str] = None
    started: Optional[str] = None
    updated: Optional[str] = None
    dependencies: Optional[List[str]] = None
    submodules: Optional[List[str]] = None

    @property
    def file_path(self) -> Optional[Path]:
        if not self.file: return None
        file_path = PROJECT_ROOT / 'sessions' / 'tasks' / self.file
        if file_path.exists(): return file_path

    @property
    def task_state(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def load_task(cls, path: Optional[Path] = None, file: Optional[str] = None) -> "TaskState":
        if not file and not path: raise ValueError("Either file or path must be provided.")
        tasks_root = PROJECT_ROOT / 'sessions' / 'tasks'
        if file and not path: path = tasks_root / file
        if path and not path.exists(): raise FileNotFoundError(f"Task file {path} does not exist.")
        # Parse task file frontmatter into fields
        if path: content = path.read_text(encoding="utf-8")
        if not (fm_start := content.find("---")) == 0: raise StateError(f"Task file {path} missing frontmatter.")
        fm_end = content.find("---", fm_start + 3)
        if fm_end == -1: raise StateError(f"Task file {path} missing frontmatter end.")
        fm_content = content[fm_start + 3:fm_end].strip()
        data = {}
        for line in fm_content.splitlines():
            if ':' not in line: continue
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            if key == "submodules" or key == "modules":
                value = value.strip('[]')
                data["submodules"] = [s.strip() for s in value.split(',') if s.strip()]
            elif key == "task":
                # Handle legacy "task:" field by mapping to "name"
                data["name"] = value or None
            else: data[key] = value or None
        if not file and path: 
            try: rel = path.relative_to(tasks_root); data["file"] = str(rel)
            except ValueError: data["file"] = path.name
        else: data["file"] = file
        return cls(**data)

    def clear_task(self):
        self.name = None
        self.file = None
        self.branch = None
        self.status = None
        self.created = None
        self.started = None
        self.updated = None
        self.submodules = None

@dataclass
class CCTodo:
    content: str
    status: TodoStatus = TodoStatus.PENDING
    activeForm: Optional[str] = None


@dataclass
class SessionsFlags:
    context_85: bool = False
    context_90: bool = False
    subagent: bool = False
    noob: bool = True
    bypass_mode: bool = False

    def clear_flags(self) -> None:
        self.context_85 = False
        self.context_90 = False
        self.subagent = False
        self.bypass_mode = False

@dataclass
class SessionsTodos:
    active: List[CCTodo] = field(default_factory=list)
    stashed: List[CCTodo] = field(default_factory=list)

    def store_todos(self, todos: List[Dict[str, str]], over: bool = True) -> bool:
        """
        Store a list of todos (dicts with 'content', activeForm, and optional 'status') into active.
        Returns True if any were added, False if none.
        """
        if self.active:
            if not over: return False
            self.clear_active()
        try:
            for t in todos:
                self.active.append(CCTodo(
                    content=t.get('content', ''),
                    activeForm=t.get('activeForm'),
                    status=TodoStatus(t.get('status', 'pending')) if 'status' in t else TodoStatus.PENDING))
            return True
        except Exception as e: print(f"Error loading todos: {e}", file=sys.stderr); return False

    def all_complete(self) -> bool:
        """True if every active todo is COMPLETED (ignores stashed)."""
        return bool(self.active) and all(t.status is TodoStatus.COMPLETED for t in self.active)

    def stash_active(self, *, force: bool = True) -> int:
        """
        Move the entire active set into the single stash slot, clearing active.
        Overwrites any stashed todos unless force = False (which raises StashOccupiedError).
        Returns number moved.
        """
        if not self.stashed or force:
            n = len(self.active)
            self.stashed = list(self.active)
            self.active.clear()
            return n
        raise StashOccupiedError("Stash already occupied. Use force=True to overwrite.")

    def clear_active(self) -> int:
        """Delete all active todos. Returns number removed."""
        n = len(self.active)
        self.active.clear()
        return n

    def clear_stashed(self) -> int:
        """Delete all stashed todos. Returns number removed."""
        n = len(self.stashed)
        self.stashed.clear()
        return n

    def restore_stashed(self) -> int:
        """
        Restore the stashed set back into active *only if* the active set is
        complete or empty. Replaces active (does not append). Returns number restored.
        If stash is empty, returns 0 and does nothing.
        """
        if not self.stashed: return 0
        if self.active and not self.all_complete(): return 0
        n = len(self.stashed)
        self.active.clear()
        self.active.extend(self.stashed)
        self.stashed.clear()
        return n

    def to_list(self, which: Literal['active', 'stashed']) -> List[Dict[str, str]]:
        """Return the specified todo list as a list of dicts."""
        if which == 'active': out = [asdict(t) for t in self.active]
        elif which == 'stashed': out = [asdict(t) for t in self.stashed]

        for t in out:
            if isinstance(t.get("status"), Enum): t["status"] = t["status"].value
        return out

    def list_content(self, which: Literal['active', 'stashed']) -> List[str]:
        """Return a list of the content strings of all active todos."""
        todos = self.active if which == 'active' else self.stashed
        return [t.content for t in todos]

    def to_dict(self) -> Dict[str, Any]:
        """Return complete todos structure with both active and stashed."""
        result = {"active": self.to_list('active')}
        if self.stashed:
            result["stashed"] = self.to_list('stashed')
        return result

@dataclass
class APIPerms:
    startup_load: bool = False
    completion: bool = False
    todos_clear: bool = False

def _get_package_version() -> str:
    """Get the installed cc-sessions package version."""
    try: return version("cc-sessions")
    except PackageNotFoundError: return "unknown"
#!<

#!> State object
@dataclass
class SessionsState:
    version: str = field(default_factory=_get_package_version)
    current_task: TaskState = field(default_factory=TaskState)
    active_protocol: Optional[SessionsProtocol] = None
    api: APIPerms = field(default_factory=APIPerms)
    mode: Mode = Mode.NO
    todos: SessionsTodos = field(default_factory=SessionsTodos)
    model: Model = Model.OPUS
    flags: SessionsFlags = field(default_factory=SessionsFlags)
    # freeform bag for runtime-only / unknown keys:
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def _coerce_todo(x: Any) -> CCTodo:
        if isinstance(x, str): return CCTodo(x)
        status = x.get("status", TodoStatus.PENDING)
        if isinstance(status, str): status = TodoStatus(status)
        return CCTodo(content=x.get("content", ""), status=status)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SessionsState":
        try: pkg_version = version("cc-sessions")
        except PackageNotFoundError: pkg_version = "unknown"

        active_protocol = d.get("active_protocol")
        if active_protocol and isinstance(active_protocol, str): active_protocol = SessionsProtocol(active_protocol)

        api_data = d.get("api", {})
        if api_data and isinstance(api_data, dict): api_perms = APIPerms(**api_data)
        else: api_perms = APIPerms()
        return cls(
            version=d.get("version", pkg_version),
            current_task=TaskState(**d.get("current_task", {})),
            active_protocol=active_protocol,
            api=api_perms,
            mode=Mode(d.get("mode", Mode.NO)),
            todos=SessionsTodos(
                active=[cls._coerce_todo(t) for t in d.get("todos", {}).get("active", [])],
                stashed=[cls._coerce_todo(t) for t in d.get("todos", {}).get("stashed", [])],
            ),
            model=Model(d.get("model")) or Model.OPUS,
            flags=SessionsFlags(
                context_85=d.get("flags", {}).get("context_85") or d.get("flags", {}).get("context_warnings", {}).get("85%", False),
                context_90=d.get("flags", {}).get("context_90") or d.get("flags", {}).get("context_warnings", {}).get("90%", False),
                subagent=d.get("flags", {}).get("subagent", False),
                bypass_mode=d.get("flags", {}).get("bypass_mode", False),
            ),
            metadata=d.get("metadata", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["mode"] = self.mode.value

        # Normalize enums in nested todos for JSON
        for bucket in ("active", "stashed"):
            for t in d["todos"][bucket]:
                if isinstance(t.get("status"), Enum): t["status"] = t["status"].value

        if self.active_protocol: d["active_protocol"] = self.active_protocol.value
        else: d["active_protocol"] = None
        return d
#!<

##-##

#-#

# ===== FUNCTIONS ===== #

## ===== HELPERS ===== ##
def find_git_repo(dir_path: Path) -> Optional[Path]:
    """Walk up directory tree to find .git directory.

    Args:
        dir_path: Directory to start search from (NOT a file path)
    """
    if not isinstance(dir_path, Path): dir_path = Path(dir_path)
    current = dir_path
    while True:
        if (current / '.git').exists(): return current
        if current == PROJECT_ROOT or current.parent == current: break
        current = current.parent
    return None

def _normalize_task_path(task_path: Union[str, Path]) -> str:
    """Normalize task path to relative string from sessions/tasks/.
    Strips absolute path prefix if present."""
    path_str = str(task_path) if isinstance(task_path, Path) else task_path
    # If path is absolute, make it relative to tasks root
    tasks_root = PROJECT_ROOT / 'sessions' / 'tasks'
    if path_str.startswith(str(tasks_root)):
        path_obj = Path(path_str)
        try:
            path_str = str(path_obj.relative_to(tasks_root))
        except ValueError:
            pass  # Keep original if not under tasks_root
    # Also handle paths starting with 'sessions/tasks/'
    if path_str.startswith('sessions/tasks/'):
        path_str = path_str[len('sessions/tasks/'):]
    return path_str

def is_directory_task(task_path: Union[str, Path]) -> bool:
    """Check if a task is part of a directory task (contains a /).

    Args:
        task_path: Relative path from sessions/tasks/ (e.g., 'h-task/01-subtask.md')

    Examples:
        'h-task/01-subtask.md' → True (subtask)
        'h-task/README.md' → True (parent)
        'h-task' → True (directory reference)
        'simple-task.md' → False (regular file task)
    """
    path_str = _normalize_task_path(task_path)
    # If the string contains a slash, it's a directory task or subtask
    if '/' in path_str: return True
    # Otherwise check if it's a directory with README.md
    tasks_root = PROJECT_ROOT / 'sessions' / 'tasks'
    task_dir = tasks_root / path_str
    if task_dir.is_dir() and (task_dir / 'README.md').exists(): return True
    return False

def is_subtask(task_path: Union[str, Path]) -> bool:
    """Check if a task path points to a subtask file (not the parent README.md).

    Args:
        task_path: Relative path from sessions/tasks/

    Examples:
        'h-task/01-subtask.md' → True
        'h-task/README.md' → False
        'h-task' → False
        'h-task/' → False
        'simple-task.md' → False
    """
    path_str = _normalize_task_path(task_path)
    if '/' not in path_str: return False
    # It's a subtask if it has a slash but isn't the README.md
    return not path_str.endswith('README.md') and not path_str.endswith('/')

def is_parent_task(task_path: Union[str, Path]) -> bool:
    """Check if a task path points to a directory task's parent README.md.

    Args:
        task_path: Relative path from sessions/tasks/

    Returns:
        True if it's a directory task but NOT a subtask
    """
    return is_directory_task(task_path) and not is_subtask(task_path)

def get_task_file_path(task_path: Union[str, Path]) -> Path:
    """Get the actual .md file path for a task (handles both directory and file tasks)."""
    if isinstance(task_path, str): task_path = Path(task_path)
    if is_directory_task(task_path): return task_path / 'README.md'
    return task_path

def list_open_tasks() -> str:
    # No active task - list available tasks
    tasks_dir = PROJECT_ROOT / 'sessions' / 'tasks'
    task_files = []

    if tasks_dir.exists(): task_files = sorted([f for f in tasks_dir.glob('*.md') if f.name != 'TEMPLATE.md'])
    for task_dir in sorted([d for d in tasks_dir.iterdir() if d.is_dir() and d.name != 'done']):
        readme_file = task_dir / 'README.md'
        if readme_file.exists(): task_files.append(task_dir)
        subtask_files = sorted([f for f in task_dir.glob('*.md') if f.name not in ['TEMPLATE.md', 'README.md']])
        task_files.extend(subtask_files)

    task_startup_help = ""
    if task_files:
        task_startup_help += "No active task set. Available tasks:\n"
        for task_file in task_files:
            fpath = get_task_file_path(task_file)
            if not fpath.exists(): continue
            # Read first few lines to get task info
            with fpath.open('r', encoding='utf-8') as f: lines = f.readlines()[:10]
            task_name = f"{task_file.name}/" if is_directory_task(task_file) else task_file.name
            status = None
            for line in lines:
                if line.startswith('status:'): status = line.split(':')[1].strip(); break
            if not status: continue
            task_startup_help += f"  • {task_name} ({status})\n"
        task_startup_help += f"""
To select a task:
- Type in one of your startup commands: {load_config().trigger_phrases.task_startup}
- Include the task file you would like to start using `@`
- Hit Enter to activate task startup
"""
    else: task_startup_help += f"""No tasks found. 

To create your first task:
- Type one of your task creation commands: {load_config().trigger_phrases.task_creation}
- Write a brief explanation of the task you need to complete 
- Answer any questions Claude has for you
"""

    return task_startup_help + "\n"

##-##

## ===== STATE PROTECTION ===== ##
def _the_ol_in_out(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp:
        json.dump(obj, tmp, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, path)  # atomic across filesystems on same volume

@contextmanager
def _lock(lock_dir: Path, timeout: float = 1.0, poll: float = 0.05, stale_timeout: float = 30.0) -> Iterator[None]:
    """
    Acquire a directory-based lock with stale lock detection.
    
    Args:
        lock_dir: Directory to use as lock
        timeout: Seconds to wait for lock acquisition
        poll: Seconds between acquisition attempts
        stale_timeout: Seconds after which a lock is considered stale
    """
    lock_info_file = lock_dir / "lock_info.json"
    start = monotonic()
    
                            # Check if process exists (works on Unix0
    while True:
        # Check for stale lock first
        if lock_dir.exists():
            try:
                # Try to read lock info
                if lock_info_file.exists():
                    lock_info = json.loads(lock_info_file.read_text())
                    lock_pid = lock_info.get("pid")
                    lock_time = lock_info.get("timestamp", 0)
                    
                    # Check if lock is stale (older than stale_timeout)
                    if monotonic() - lock_time > stale_timeout:
                        print(f"Removing stale lock (age: {monotonic() - lock_time:.1f}s)", file=sys.stderr)
                        with suppress(Exception): shutil.rmtree(lock_dir)
                    # Check if owning process is dead (same machine only)
                    elif lock_pid and lock_pid != os.getpid():
                        try: os.kill(lock_pid, 0) # Check if process exists (works on Unix)
                        except (OSError, ProcessLookupError):
                            # Process doesn't exist, remove stale lock
                            print(f"Removing lock from dead process {lock_pid}", file=sys.stderr)
                            with suppress(Exception): shutil.rmtree(lock_dir)
            except (json.JSONDecodeError, KeyError, ValueError):
                # Malformed lock info, try to remove after timeout
                if monotonic() - start > timeout:
                    print(f"Removing malformed lock", file=sys.stderr)
                    with suppress(Exception): shutil.rmtree(lock_dir)
        
        # Try to acquire lock
        try:
            lock_dir.mkdir(exist_ok=False)  # atomic lock acquire
            # Write lock info atomically
            lock_info = { "pid": os.getpid(),
                "timestamp": monotonic(),
                "host": os.uname().nodename if hasattr(os, 'uname') else "unknown" }
            lock_info_file.write_text(json.dumps(lock_info))
            break
        except FileExistsError:
            if monotonic() - start > timeout:
                # Force-remove stale lock after timeout and try once more
                print(f"Force-removing lock after {timeout}s timeout", file=sys.stderr)
                shutil.rmtree(lock_dir, ignore_errors=True)
                # Try once more to acquire
                try:
                    lock_dir.mkdir(exist_ok=False)
                    # Write lock info atomically
                    lock_info = { "pid": os.getpid(),
                        "timestamp": monotonic(),
                        "host": os.uname().nodename if hasattr(os, 'uname') else "unknown" }
                    lock_info_file.write_text(json.dumps(lock_info))
                    break
                except FileExistsError:
                    # Someone else grabbed it in the meantime
                    raise TimeoutError(f"Could not acquire lock {lock_dir} even after force removal")
            sleep(poll)
    
    try: yield
    finally:
        with suppress(Exception): shutil.rmtree(lock_dir)
##-##

## ===== GEIPI ===== ##
def load_state() -> SessionsState:
    if not STATE_FILE.exists():
        initial = SessionsState()
        _the_ol_in_out(STATE_FILE, initial.to_dict())
        return initial
    try: data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Corrupt file: back it up once and start fresh
        backup = STATE_FILE.with_suffix(".bad.json")
        with suppress(Exception): STATE_FILE.replace(backup)
        fresh = SessionsState()
        _the_ol_in_out(STATE_FILE, fresh.to_dict())
        return fresh
    return SessionsState.from_dict(data)

def load_config() -> SessionsConfig:
    if not CONFIG_FILE.exists():
        initial = SessionsConfig()
        _the_ol_in_out(CONFIG_FILE, initial.to_dict())
        return initial
    try: data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Corrupt file: back it up once and start fresh
        backup = CONFIG_FILE.with_suffix(".bad.json")
        with suppress(Exception): CONFIG_FILE.replace(backup)
        fresh = SessionsConfig()
        _the_ol_in_out(CONFIG_FILE, fresh.to_dict())
        return fresh

    # Check if migration is needed from use_nerd_fonts to icon_style
    needs_migration = False
    if "features" in data and "use_nerd_fonts" in data["features"] and "icon_style" not in data["features"]:
        needs_migration = True

    config = SessionsConfig.from_dict(data)

    # If migration happened, write back the config to remove old field
    if needs_migration:
        _the_ol_in_out(CONFIG_FILE, config.to_dict())

    return config

@contextmanager
def edit_state() -> Iterator[SessionsState]:
    # Acquire lock, reload (so we operate on latest), yield, then save atomically
    with _lock(LOCK_DIR):
        state = load_state()
        try: yield state
        except Exception: raise
        else: _the_ol_in_out(STATE_FILE, state.to_dict())

@contextmanager
def edit_config() -> Iterator[SessionsConfig]:
    # Acquire lock, reload (so we operate on latest), yield, then save atomically
    with _lock(LOCK_DIR):
        config = load_config()
        try: yield config
        except Exception: raise
        else: _the_ol_in_out(CONFIG_FILE, config.to_dict())
##-##

#-#
