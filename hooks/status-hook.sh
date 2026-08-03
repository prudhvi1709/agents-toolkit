#!/bin/bash
# Agent status hook - writes session events for real-time status detection
set -e

EVENTS_DIR="${AGENT_EVENTS_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/agents-toolkit/events}"
mkdir -p "$EVENTS_DIR"

# Read JSON from stdin
INPUT=$(cat)

# Extract fields using grep/sed (no jq dependency)
HOOK_EVENT=$(echo "$INPUT" | grep -o '"hook_event_name"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/')
SESSION_ID=$(echo "$INPUT" | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/')
CWD=$(echo "$INPUT" | grep -o '"cwd"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/')
TRANSCRIPT=$(echo "$INPUT" | grep -o '"transcript_path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/')

if [ -z "$SESSION_ID" ] || [ -z "$HOOK_EVENT" ]; then
  exit 0
fi

TS=$(date +%s)

# $PPID = Claude process that invoked this hook (keys the event file by PID)
echo "{\"event\":\"$HOOK_EVENT\",\"session_id\":\"$SESSION_ID\",\"cwd\":\"$CWD\",\"transcript_path\":\"$TRANSCRIPT\",\"ts\":$TS}" > "$EVENTS_DIR/$PPID.json"
