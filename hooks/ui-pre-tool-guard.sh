#!/bin/bash
# ============================================================================
# UI Pre-Tool Guard - Fast UI consistency checks for Claude Code
# ============================================================================
#
# This hook integrates with pre-tool-guard.sh to provide UI-specific
# consistency checks for CSS, JSX, TSX, Vue, and Svelte files.
#
# Performance Targets:
#   - Fast mode: <300ms (used by default)
#   - Full mode: <5s
#
# Exit codes:
#   0 = Allow (no issues or non-blocking issues)
#   1 = Warn (non-blocking issues found)
#   2 = Block (blocking issues found)
#
# Usage:
#   echo '{"tool_name":"Write","tool_input":{"file_path":"...","content":"..."}}' | ui-pre-tool-guard.sh
#
# ============================================================================

# Configuration
readonly UI_GUARD_VERSION="1.0"
readonly FAST_MODE_TIMEOUT=5  # seconds
readonly UI_EXTENSIONS=".css .scss .sass .less .jsx .tsx .vue .svelte .html .htm"

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
UI_GUARD_PY="$PROJECT_ROOT/claude_indexer/ui/cli/guard.py"

# === CROSS-PLATFORM TIMEOUT ===
run_with_timeout() {
    local timeout_secs="$1"
    shift
    if command -v timeout &> /dev/null; then
        timeout "${timeout_secs}s" "$@"
    elif command -v gtimeout &> /dev/null; then
        gtimeout "${timeout_secs}s" "$@"
    else
        "$@"  # Run without timeout
    fi
}

# === UI FILE DETECTION ===
is_ui_file() {
    local file="$1"
    local ext="${file##*.}"
    ext=".$ext"
    [[ "$UI_EXTENSIONS" == *"$ext"* ]]
}

# === MAIN ===
main() {
    # Check if Python guard exists
    if [[ ! -f "$UI_GUARD_PY" ]]; then
        # Guard not installed, allow operation
        exit 0
    fi

    # Read input (passed from pre-tool-guard.sh)
    local input
    input=$(cat)

    # Dependency check
    if ! command -v jq &>/dev/null; then
        exit 0
    fi

    # Parse file path from input
    local file_path
    file_path=$(jq -r '.tool_input.file_path // empty' <<< "$input" 2>/dev/null) || exit 0

    # Skip non-UI files
    if [[ -z "$file_path" ]] || ! is_ui_file "$file_path"; then
        exit 0
    fi

    # Run Python UI guard with timeout
    local result exit_code
    result=$(run_with_timeout "$FAST_MODE_TIMEOUT" python3 "$UI_GUARD_PY" --fast --json <<< "$input" 2>&1)
    exit_code=$?

    # Handle timeout or error
    if [[ $exit_code -eq 124 ]]; then
        # Timeout - allow operation
        echo '{"decision":"approve","reason":"UI check timed out"}' >&2
        exit 0
    fi

    if [[ -z "$result" ]]; then
        # Empty result - allow operation
        exit 0
    fi

    # Parse decision from JSON result
    local decision reason
    decision=$(jq -r '.decision // "approve"' <<< "$result" 2>/dev/null) || exit 0
    reason=$(jq -r '.reason // ""' <<< "$result" 2>/dev/null)

    # Output result to stdout (for calling script to capture)
    echo "$result"

    # Determine exit code based on decision
    case "$decision" in
        "block")
            exit 2
            ;;
        "approve")
            # Check if there are warnings
            local warn_count
            warn_count=$(jq -r '.counts.warn // 0' <<< "$result" 2>/dev/null)
            if [[ "$warn_count" -gt 0 ]]; then
                exit 1
            fi
            exit 0
            ;;
        *)
            exit 0
            ;;
    esac
}

main
