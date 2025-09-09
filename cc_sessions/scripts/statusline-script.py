#!/usr/bin/env python3
"""Claude Code StatusLine Script - Windows-compatible Full Version"""

import json
import sys
import os
import subprocess
import math
from pathlib import Path
from typing import Dict, Any, Optional

# Force unbuffered output for Windows
os.environ['PYTHONUNBUFFERED'] = '1'

# ANSI color codes (simplified for Windows compatibility)
COLORS = {
    'green': '\033[32m',
    'orange': '\033[33m',
    'red': '\033[31m',
    'cyan': '\033[36m',
    'purple': '\033[35m',
    'blue': '\033[34m',
    'yellow': '\033[33m',
    'gray': '\033[90m',
    'light_gray': '\033[37m',
    'reset': '\033[0m'
}


def safe_print(text: str):
    """Print with explicit flush for Windows compatibility"""
    print(text, flush=True)
    sys.stdout.flush()


def calculate_context(input_data: Dict[str, Any]) -> str:
    """Calculate context breakdown and progress bar"""
    try:
        transcript_path = input_data.get('transcript_path', '')
        model_name = input_data.get('model', {}).get('display_name', 'Claude')
        
        # Determine usable context limit (80% of theoretical before auto-compact)
        if 'Sonnet' in model_name:
            context_limit = 160000  # 800k usable for 1M Sonnet models
        else:
            context_limit = 160000  # 160k usable for 200k models
        
        total_tokens = 0
        
        if transcript_path and os.path.exists(transcript_path):
            # Parse transcript to get real token usage
            try:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                most_recent_usage = None
                most_recent_timestamp = None
                
                for line in lines:
                    try:
                        data = json.loads(line.strip())
                        
                        # Skip sidechain entries
                        if data.get('isSidechain', False):
                            continue
                        
                        # Check for usage data in main-chain messages
                        message = data.get('message', {})
                        if message.get('usage'):
                            timestamp = data.get('timestamp')
                            if timestamp and (not most_recent_timestamp or timestamp > most_recent_timestamp):
                                most_recent_timestamp = timestamp
                                most_recent_usage = message['usage']
                    except:
                        continue
                
                # Calculate context length
                if most_recent_usage:
                    total_tokens = (
                        most_recent_usage.get('input_tokens', 0) +
                        most_recent_usage.get('cache_read_input_tokens', 0) +
                        most_recent_usage.get('cache_creation_input_tokens', 0)
                    )
            except:
                total_tokens = 0
        else:
            # Default values when no transcript available
            total_tokens = 17900
        
        # Calculate progress percentage
        if total_tokens > 0:
            progress_pct = round(total_tokens * 100 / context_limit, 1)
            progress_pct_int = int(total_tokens * 100 / context_limit)
            if progress_pct_int > 100:
                progress_pct = 100.0
                progress_pct_int = 100
        else:
            progress_pct = 0.0
            progress_pct_int = 0
        
        # Format token count in 'k' format
        formatted_tokens = f"{total_tokens // 1000}k"
        formatted_limit = f"{context_limit // 1000}k"
        
        # Create progress bar
        filled_blocks = min(progress_pct_int // 10, 10)
        empty_blocks = 10 - filled_blocks
        
        # Select color based on usage
        if progress_pct_int < 50:
            bar_color = COLORS['green']
        elif progress_pct_int < 80:
            bar_color = COLORS['orange']
        else:
            bar_color = COLORS['red']
        
 # Build progress bar (using ASCII characters for Windows)
        progress_bar = bar_color
        progress_bar += '#' * filled_blocks  # Changed from '█' to '#'
        progress_bar += COLORS['gray']
        progress_bar += '-' * empty_blocks    # Changed from '░' to '-'
        return progress_bar
    
    except Exception as e:
        return f"Context: Error {str(e)}"


def get_current_task(cwd: str) -> str:
    """Get current task with color"""
    try:
        task_file = os.path.join(cwd, '.claude', 'state', 'current_task.json')
        
        if os.path.exists(task_file):
            with open(task_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                task_name = data.get('task', 'None')
        else:
            task_name = 'None'
        
        return f"{COLORS['cyan']}Task: {task_name}{COLORS['reset']}"
    except:
        return f"{COLORS['cyan']}Task: None{COLORS['reset']}"


def get_daic_mode(cwd: str) -> str:
    """Get DAIC mode with color"""
    try:
        mode_file = os.path.join(cwd, '.claude', 'state', 'daic-mode.json')
        
        if os.path.exists(mode_file):
            with open(mode_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                mode = data.get('mode', 'discussion')
        else:
            mode = 'discussion'
        
        if mode == 'discussion':
            return f"{COLORS['purple']}DAIC: Discussion{COLORS['reset']}"
        else:
            return f"{COLORS['green']}DAIC: Implementation{COLORS['reset']}"
    except:
        return f"{COLORS['purple']}DAIC: Discussion{COLORS['reset']}"


def count_edited_files(cwd: str) -> str:
    """Count edited files with color"""
    try:
        git_dir = os.path.join(cwd, '.git')
        
        if os.path.exists(git_dir):
            # Run git status command
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=5,
                shell=True  # Added for Windows compatibility
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n') if result.stdout else []
                modified_count = sum(
                    1 for line in lines 
                    if line and (line[0] in 'AM' or (len(line) > 1 and line[1] in 'AM'))
                )
            else:
                modified_count = 0
        else:
            modified_count = 0
        
        return f"{COLORS['yellow']}* {modified_count} files{COLORS['reset']}"  # Changed from '✎' to '*'

    except:
        return f"{COLORS['yellow']}✎ 0 files{COLORS['reset']}"


def count_open_tasks(cwd: str) -> str:
    """Count open tasks with color"""
    try:
        tasks_dir = os.path.join(cwd, 'sessions', 'tasks')
        
        open_count = 0
        if os.path.exists(tasks_dir):
            for filename in os.listdir(tasks_dir):
                if filename.endswith('.md'):
                    task_file = os.path.join(tasks_dir, filename)
                    try:
                        with open(task_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Count as open if not marked as done or completed
                            if not any(status in content.lower() for status in ['status: done', 'status: completed']):
                                open_count += 1
                    except:
                        continue
        
        return f"{COLORS['blue']}[{open_count} open]{COLORS['reset']}"
    except:
        return f"{COLORS['blue']}[0 open]{COLORS['reset']}"


def main():
    """Main entry point"""
    try:
        # Read JSON input from stdin
        if sys.platform == 'win32':
            sys.stdout.reconfigure(encoding='utf-8')
        input_json = sys.stdin.read()
        input_data = json.loads(input_json)
        
        # Extract basic info
        workspace = input_data.get('workspace', {})
        cwd = workspace.get('current_dir') or input_data.get('cwd', '')
        
        # Build the complete statusline
        progress_info = calculate_context(input_data)
        task_info = get_current_task(cwd)
        daic_info = get_daic_mode(cwd)
        files_info = count_edited_files(cwd)
        tasks_info = count_open_tasks(cwd)
        
        # Output with explicit flush for Windows
        safe_print(f"{progress_info} | {task_info}")
        safe_print(f"{daic_info} | {files_info} | {tasks_info}")
        
    except Exception as e:
        # Fallback output on any error
        safe_print(f"StatusLine Error: {str(e)}")


if __name__ == '__main__':
    main()