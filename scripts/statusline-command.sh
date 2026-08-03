#!/usr/bin/env bash
# Claude Code status line script
# Shows: cwd | model | context% | repo(owner/name) branch | time

input=$(cat)

# --- fields from JSON ---
cwd=$(echo "$input" | jq -r '.workspace.current_dir')
model=$(echo "$input" | jq -r '.model.display_name')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
repo_owner=$(echo "$input" | jq -r '.workspace.repo.owner // empty')
repo_name=$(echo "$input" | jq -r '.workspace.repo.name // empty')

# --- current working directory (shorten $HOME to ~) ---
home="$HOME"
case "$cwd" in
  "$home") dir="~" ;;
  "$home"/*) dir="~${cwd#$home}" ;;
  *) dir="$cwd" ;;
esac

# --- model ---
model_part="$model"

# --- context window ---
ctx_part=""
if [ -n "$used" ]; then
  ctx_part="ctx:$(printf '%.0f' "$used")%"
fi

# --- git repo + branch (skip optional lock file) ---
git_part=""
if git_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null); then
  branch=$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null || git -C "$cwd" rev-parse --short HEAD 2>/dev/null)
  if [ -n "$repo_owner" ] && [ -n "$repo_name" ]; then
    git_part="${repo_owner}/${repo_name}"
  else
    git_part=$(basename "$git_root")
  fi
  [ -n "$branch" ] && git_part="${git_part} ${branch}"
fi

# --- current time ---
time_part=$(date +%H:%M)

# --- assemble line with " | " separators ---
parts=()
parts+=("$dir")
parts+=("$model_part")
[ -n "$ctx_part" ] && parts+=("$ctx_part")
[ -n "$git_part" ] && parts+=("$git_part")
parts+=("$time_part")

line=""
for part in "${parts[@]}"; do
  if [ -z "$line" ]; then
    line="$part"
  else
    line="$line | $part"
  fi
done

printf '%s' "$line"
