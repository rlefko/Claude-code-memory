#!/bin/bash
# After-write hook for Claude Code Memory
# Triggered after Write/Edit operations (PostToolUse hook)
#
# Two responsibilities:
# 1. Run fast quality rules (<300ms) - synchronous with warning output
# 2. Queue file for incremental indexing - non-blocking async
#
# Input: JSON via stdin with tool_name, tool_input (file_path, content, etc.)
# Exit codes:
#   0 = Success (messages shown in verbose mode)
#   1 = Non-blocking warning (findings shown to user)
#   2 = Not used (post-hooks don't block)
#
# Performance budget: 300ms total
#   - stdin reading: <50ms
#   - fast rules: <200ms
#   - queue operation: <50ms

set -e

# Cross-platform stdin read with timeout (prevents hang in background mode)
read_stdin_with_timeout() {
    local timeout_secs="${1:-5}"
    if command -v timeout &> /dev/null; then
        timeout "$timeout_secs" cat
    elif command -v gtimeout &> /dev/null; then
        gtimeout "$timeout_secs" cat
    else
        # Fallback: use read with built-in timeout (line by line)
        local input=""
        while IFS= read -r -t "$timeout_secs" line; do
            input+="$line"$'\n'
        done
        printf '%s' "$input"
    fi
}

# Read JSON input from stdin with timeout
INPUT=$(read_stdin_with_timeout 5) || exit 0

# Extract file path from tool input
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Skip if no file path (shouldn't happen for Write/Edit)
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Skip non-code files that don't need quality checks
case "$FILE_PATH" in
    *.log|*.tmp|*.bak|*.swp|*.pyc|*.pyo|__pycache__/*|.git/*|node_modules/*|.venv/*|.claude/*|.index_cache/*)
        exit 0
        ;;
esac

# Find project root by looking for .git or .mcp.json
find_project_root() {
    local dir="$1"
    while [ "$dir" != "/" ]; do
        if [ -d "$dir/.git" ] || [ -f "$dir/.mcp.json" ]; then
            echo "$dir"
            return 0
        fi
        dir=$(dirname "$dir")
    done
    return 1
}

# Get project root from file path
PROJECT_DIR=$(find_project_root "$(dirname "$FILE_PATH")")
if [ -z "$PROJECT_DIR" ]; then
    # Fallback to current directory
    PROJECT_DIR=$(pwd)
fi

# Get collection name from environment (set by setup.sh) or .mcp.json
COLLECTION="${CLAUDE_MEMORY_COLLECTION:-}"

if [ -z "$COLLECTION" ]; then
    # Try to read from .mcp.json in project directory
    if [ -f "$PROJECT_DIR/.mcp.json" ]; then
        COLLECTION=$(jq -r '.mcpServers | keys[0] | sub("-memory$"; "")' "$PROJECT_DIR/.mcp.json" 2>/dev/null)
    fi
fi

# Check if claude-indexer is available
if ! command -v claude-indexer &> /dev/null; then
    # Not installed globally, skip silently
    exit 0
fi

# ============================================================
# Phase 1: Fast Quality Rules (<200ms)
# ============================================================

# Run fast quality checks and capture output
RULE_OUTPUT=""
RULE_EXIT_CODE=0

# Only run if file exists and is a code file
if [ -f "$FILE_PATH" ]; then
    # Run fast rules with JSON output
    RULE_OUTPUT=$(claude-indexer post-write "$FILE_PATH" --json 2>/dev/null) || RULE_EXIT_CODE=$?
fi

# ============================================================
# Phase 2: Queue for Async Indexing (<50ms)
# ============================================================

# Queue file for background indexing if we have collection info
if [ -n "$COLLECTION" ]; then
    # Use single-file indexing (fast ~100ms) via background process
    # Nohup ensures it continues after this hook exits
    (nohup claude-indexer file -p "$PROJECT_DIR" -c "$COLLECTION" "$FILE_PATH" --quiet 2>/dev/null &) 2>/dev/null
fi

# ============================================================
# Output Results
# ============================================================

# Parse findings from JSON output
if [ -n "$RULE_OUTPUT" ] && [ "$RULE_EXIT_CODE" -ne 0 ]; then
    # Extract status and findings count
    STATUS=$(echo "$RULE_OUTPUT" | jq -r '.status // "ok"')
    TOTAL=$(echo "$RULE_OUTPUT" | jq -r '.summary.total // 0')
    CRITICAL=$(echo "$RULE_OUTPUT" | jq -r '.summary.critical // 0')
    HIGH=$(echo "$RULE_OUTPUT" | jq -r '.summary.high // 0')

    if [ "$STATUS" = "warn" ] && [ "$TOTAL" -gt 0 ]; then
        # Format findings for display
        echo ""
        echo "=== Quality Check Warnings ==="
        echo ""

        # Extract and display each finding
        echo "$RULE_OUTPUT" | jq -r '.findings[] | "[\(.severity | ascii_upcase)] \(.rule_id)\n   \(.file_path):\(.line_number // "?")\n   \(.summary)\n"'

        # Show summary
        echo "---"
        echo "Found $TOTAL issue(s): $CRITICAL critical, $HIGH high"
        echo ""

        # Exit with warning code (shown to user but doesn't block)
        exit 1
    fi
fi

# Always succeed - this is a post-hook, we don't want to block
exit 0
