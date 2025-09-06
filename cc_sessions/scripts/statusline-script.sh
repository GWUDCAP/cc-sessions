# Count lines of code with

# Claude Code StatusLine Script
# Provides comprehensive session information in a clean format
# System-agnostic version using Python instead of jq

# Configuration
EXECUTABLE_NAME="easyfac"  # Name pattern for executable files to check

# Read JSON input from stdin
input=$(cat)

# Extract basic info using Python (works on all systems)
cwd=$(echo "$input" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('workspace', {}).get('current_dir') or data.get('cwd', ''))")
model_name=$(echo "$input" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('model', {}).get('display_name', 'Claude'))")
session_id=$(echo "$input" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('session_id', ''))")

# Function to calculate context breakdown and progress
calculate_context() {
  # Get transcript if available
  transcript_path=$(echo "$input" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('transcript_path', ''))")

  # Determine usable context limit (80% of theoretical before auto-compact)
  if [[ "$model_name" == *"Sonnet"* ]]; then
    context_limit=800000   # 800k usable for 1M Sonnet models
  else
    context_limit=160000   # 160k usable for 200k models (Opus, etc.)
  fi

  if [[ -n "$transcript_path" && -f "$transcript_path" ]]; then
    # Parse transcript to get real token usage from most recent main-chain message
    total_tokens=$(python3 -c "
import sys, json

try:
  with open('$transcript_path', 'r') as f:
    lines = f.readlines()

  most_recent_usage = None
  most_recent_timestamp = None

  for line in lines:
    try:
      data = json.loads(line.strip())
      # Skip sidechain entries (subagent calls)
      if data.get('isSidechain', False):
        continue

      # Check for usage data in main-chain messages
      if data.get('message', {}).get('usage'):
        timestamp = data.get('timestamp')
        if timestamp and (not most_recent_timestamp or timestamp > most_recent_timestamp):
          most_recent_timestamp = timestamp
          most_recent_usage = data['message']['usage']
    except:
      continue

  # Calculate context length (input + cache tokens only, NOT output)
  if most_recent_usage:
    context_length = (
      most_recent_usage.get('input_tokens', 0) +
      most_recent_usage.get('cache_read_input_tokens', 0) +
      most_recent_usage.get('cache_creation_input_tokens', 0)
    )
    print(context_length)
  else:
    print(0)
except:
  print(0)
" 2>/dev/null)

    # Calculate actual context usage percentage
    if [[ $total_tokens -gt 0 ]]; then
      # Use Python for floating point math (bc not available on all systems)
      progress_pct=$(python3 -c "print(f'{$total_tokens * 100 / $context_limit:.1f}')")
      progress_pct_int=$(python3 -c "print(int($total_tokens * 100 / $context_limit))")
      if [[ $progress_pct_int -gt 100 ]]; then
        progress_pct="100.0"
        progress_pct_int=100
      fi
    else
      progress_pct="0.0"
      progress_pct_int=0
    fi
  else
    # Default values when no transcript available - still add default context
    total_tokens=17900
    progress_pct=$(python3 -c "print(f'{$total_tokens * 100 / $context_limit:.1f}')")
    progress_pct_int=$(python3 -c "print(int($total_tokens * 100 / $context_limit))")
  fi

  # Format token count in 'k' format
  formatted_tokens=$(python3 -c "print(f'{$total_tokens // 1000}k')")
  formatted_limit=$(python3 -c "print(f'{$context_limit // 1000}k')")

  # Create progress bar (capped at 100%) with Ayu Dark colors
  filled_blocks=$((progress_pct_int / 10))
  if [[ $filled_blocks -gt 10 ]]; then filled_blocks=10; fi
  empty_blocks=$((10 - filled_blocks))

  # Ayu Dark colors (converted to closest ANSI 256)
  if [[ $progress_pct_int -lt 50 ]]; then
    bar_color="\033[38;5;114m"  # AAD94C green
  elif [[ $progress_pct_int -lt 80 ]]; then
    bar_color="\033[38;5;215m"  # FFB454 orange
  else
    bar_color="\033[38;5;203m"  # F26D78 red
  fi
  gray_color="\033[38;5;242m"     # Dim for empty blocks
  text_color="\033[38;5;250m"     # BFBDB6 light gray
  reset="\033[0m"

  progress_bar="${bar_color}"
  for ((i=0; i<filled_blocks; i++)); do progress_bar+="█"; done
  progress_bar+="${gray_color}"
  for ((i=0; i<empty_blocks; i++)); do progress_bar+="░"; done
  progress_bar+="${reset} ${text_color}󱃖 ${progress_pct}% (${formatted_tokens}/${formatted_limit})${reset}"

  echo -e "$progress_bar"
}

# Get git status with branch and commit
get_git_status() {
  local dim_gray="\033[38;5;242m" # Dim gray for git info
  local reset="\033[0m"

  if [[ -d "$cwd/.git" ]]; then
    cd "$cwd"
    local branch=$(git branch --show-current 2>/dev/null || echo "")
    local commit=$(git rev-parse --short HEAD 2>/dev/null || echo "")
    if [[ -n "$branch" && -n "$commit" ]]; then
      echo -e "${dim_gray}󰘬 $branch 󰊢 $commit${reset}"
    fi
  fi
}

# Get current task with color and git info
get_current_task() {
  cyan="\033[38;5;111m"    # 59C2FF entity blue
  dim_gray="\033[38;5;242m" # Dim gray for git info
  reset="\033[0m"

  if [[ -f "$cwd/.claude/state/current_task.json" ]]; then
    task_name=$(python3 -c "
import sys, json
try:
  with open('$cwd/.claude/state/current_task.json', 'r') as f:
    data = json.load(f)
    print(data.get('task', 'None'))
except:
  print('None')
" 2>/dev/null)

    echo -e "${cyan}󰒓 $task_name${reset}"
  else
    echo -e "${cyan}󰒓 No Task${reset}"
  fi
}

# Get DAIC mode with color
get_daic_mode() {
  if [[ -f "$cwd/.claude/state/daic-mode.json" ]]; then
    mode=$(python3 -c "
import sys, json
try:
  with open('$cwd/.claude/state/daic-mode.json', 'r') as f:
    data = json.load(f)
    print(data.get('mode', 'discussion'))
except:
  print('discussion')
" 2>/dev/null)
    if [[ "$mode" == "discussion" ]]; then
      purple="\033[38;5;183m"  # D2A6FF constant purple
      reset="\033[0m"
      echo -e "${purple}󰭹 Discussion${reset}"
    else
      green="\033[38;5;114m"   # AAD94C string green
      reset="\033[0m"
      echo -e "${green}󰷫 Implementation${reset}"
    fi
  else
    purple="\033[38;5;183m"      # D2A6FF constant purple
    reset="\033[0m"
    echo -e "${purple}󰭹 Discussion${reset}"
  fi
}

# Count edited files with color
count_edited_files() {
  yellow="\033[38;5;215m"  # FFB454 func orange
  reset="\033[0m"
  if [[ -d "$cwd/.git" ]]; then
    cd "$cwd"
    # Count modified and staged files
    modified_count=$(git status --porcelain 2>/dev/null | grep -E '^[AM]|^.[AM]' | wc -l || echo "0")
    echo -e "${yellow}✎ $modified_count files${reset}"
  else
    echo -e "${yellow}✎ 0 files${reset}"
  fi
}

# Count open tasks with color
count_open_tasks() {
  blue="\033[38;5;111m"    # 73B8FF modified blue
  reset="\033[0m"
  tasks_dir="$cwd/sessions/tasks"
  if [[ -d "$tasks_dir" ]]; then
    # Count .md files that don't contain "Status: done" or "Status: completed"
    open_count=0
    for task_file in "$tasks_dir"/*.md; do
      if [[ -f "$task_file" ]]; then
        if ! grep -q -E "Status:\s*(done|completed)" "$task_file" 2>/dev/null; then
          ((open_count++))
        fi
      fi
    done
    echo -e "${blue}󰈙 $open_count open${reset}"
  else
    echo -e "${blue}󰈙 0 open${reset}"
  fi
}

# Count lines of code with color
count_lines_of_code() {
  local dir="$cwd"
  if [[ ! -d "$dir" ]]; then
    echo -e "\033[38;5;203m✖ code dir N/A\033[0m"
    return
  fi

  local count=$(find "$dir" -type f \
    -not -path '*/node_modules/*' \
    -not -path '*/.git/*' \
    -not -path '*/build/*' \
    -not -path '*/dist/*' \
    -not -path '*/.vs/*' \
    -not -path '*/.vscode/*' \
    \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.jsx" -o -name "*.tsx" \
    -o -name "*.java" -o -name "*.c" -o -name "*.cpp" -o -name "*.h" -o -name "*.hpp" \
    -o -name "*.cs" -o -name "*.php" -o -name "*.rb" -o -name "*.go" -o -name "*.rs" \
    -o -name "*.swift" -o -name "*.kt" -o -name "*.scala" -o -name "*.sh" -o -name "*.bash" \
    -o -name "*.sql" -o -name "*.html" -o -name "*.css" -o -name "*.scss" -o -name "*.less" \) \
    -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}' || echo "0")

  local green="\033[38;5;114m"  # AAD94C string green
  local reset="\033[0m"
  local formatted_count=$(printf "%'d" "$count" 2>/dev/null || echo "$count")
  echo -e "${green}󰓅 ${formatted_count} code${reset}"
}

# Count lines of documentation with color
count_lines_of_docs() {
  local dir="$cwd"
  if [[ ! -d "$dir" ]]; then
    echo -e "\033[38;5;203m✖ docs dir N/A\033[0m"
    return
  fi

  local count=$(find "$dir" -type f \
    -not -path '*/node_modules/*' \
    -not -path '*/.git/*' \
    -not -path '*/build/*' \
    -not -path '*/dist/*' \
    -not -path '*/.vs/*' \
    -not -path '*/.vscode/*' \
    \( -name "*.md" -o -name "*.txt" -o -name "*.rst" -o -name "*.tex" \
    -o -name "*.org" -o -name "*.adoc" -o -name "*.asciidoc" \) \
    -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}' || echo "0")

  local cyan="\033[38;5;111m"   # 59C2FF entity blue
  local reset="\033[0m"
  local formatted_count=$(printf "%'d" "$count" 2>/dev/null || echo "$count")
  echo -e "${cyan}󰈔 ${formatted_count} docs${reset}"
}

# Check executable file sizes with color
check_executable_size() {
  local dir="$cwd"
  local bin_dir="$dir/bin"

  if [[ ! -d "$bin_dir" ]]; then
    echo -e "\033[38;5;242m󰜴 no bin/\033[0m"
    return
  fi

  # Look for executables in bin/ directory
  local executables=($(find "$bin_dir" -type f -executable -name "${EXECUTABLE_NAME}*" 2>/dev/null | sort))

  if [[ ${#executables[@]} -eq 0 ]]; then
    echo -e "\033[38;5;242m󰜴 no exec\033[0m"
    return
  fi

  # Find the most recently modified executable
  local latest_exec=""
  local latest_time=0

  for exec_file in "${executables[@]}"; do
    if [[ -f "$exec_file" ]]; then
      local mod_time=$(stat -c %Y "$exec_file" 2>/dev/null || echo "0")
      if [[ $mod_time -gt $latest_time ]]; then
        latest_time=$mod_time
        latest_exec="$exec_file"
      fi
    fi
  done

  if [[ -n "$latest_exec" ]]; then
    local name=$(basename "$latest_exec")
    local size_bytes=$(stat -c %s "$latest_exec" 2>/dev/null || echo "0")

    # Convert to MB with 1 decimal place
    local size_mb=$(python3 -c "print(f'{$size_bytes / 1024 / 1024:.1f}')" 2>/dev/null || echo "0.0")

    # Color based on size (typical Go binary sizes)
    local color
    if [[ $(python3 -c "print($size_bytes < 10 * 1024 * 1024)") == "True" ]]; then
      color="\033[38;5;114m"  # Green for < 10MB
    elif [[ $(python3 -c "print($size_bytes < 50 * 1024 * 1024)") == "True" ]]; then
      color="\033[38;5;215m"  # Orange for < 50MB
    else
      color="\033[38;5;203m"  # Red for >= 50MB
    fi

    local reset="\033[0m"
    echo -e "${color}󰜴 ${name} ${size_mb}MB${reset}"
  else
    echo -e "\033[38;5;242m󰜴 no exec\033[0m"
  fi
}

# Build the complete statusline
progress_info=$(calculate_context)
task_info=$(get_current_task)
git_info=$(get_git_status)
daic_info=$(get_daic_mode)
files_info=$(count_edited_files)
tasks_info=$(count_open_tasks)
code_info=$(count_lines_of_code)
docs_info=$(count_lines_of_docs)
exec_info=$(check_executable_size)

# Output the complete statusline in two lines with color support
# Line 1: Progress bar | Current task
# Line 2: DAIC mode | Files edited | Open tasks | Lines of code | Lines of docs | Executable
echo -e "$progress_info | $task_info | $git_info"
echo -e "$daic_info | $files_info | $tasks_info | $code_info | $docs_info | $exec_info"
