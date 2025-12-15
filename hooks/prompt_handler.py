#!/usr/bin/env python3
"""
UserPromptSubmit Hook - Memory-First Context Injection.

Runs before Claude processes user prompts to:
1. Detect prompt intent (search, implement, debug, refactor)
2. Detect Plan Mode activation (Milestone 7.1)
3. Inject appropriate MCP tool suggestions
4. Reinforce memory-first development approach

Performance target: <50ms total execution
"""

import json
import os
import re
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_indexer.hooks.plan_mode_detector import (  # noqa: E402
    detect_plan_mode,
)

# Intent patterns (compiled for performance)
PATTERNS = {
    "search": re.compile(r"\b(find|search|look for|where is|locate|show me)\b", re.I),
    "debug": re.compile(
        r"\b(error|bug|fix|issue|problem|broken|failing|crash)\b", re.I
    ),
    "implement": re.compile(r"\b(add|create|implement|build|write|make)\b", re.I),
    "refactor": re.compile(
        r"\b(refactor|improve|clean up|optimize|restructure)\b", re.I
    ),
    "understand": re.compile(
        r"\b(how does|what does|explain|understand|architecture)\b", re.I
    ),
    "code_terms": re.compile(
        r"\b(function|class|component|module|service|api|endpoint)\b", re.I
    ),
}

SENSITIVE_PATTERNS = re.compile(
    r"\b(password|secret|api[_-]?key|token|credential|private[_-]?key)\s*[:=]",
    re.I,
)


def detect_intent(prompt: str) -> list:
    """Detect prompt intent categories."""
    intents = []
    for intent, pattern in PATTERNS.items():
        if pattern.search(prompt):
            intents.append(intent)
    return intents


def build_context(intents: list, collection: str) -> str:
    """Build context injection based on detected intents."""
    prefix = f"mcp__{collection}-memory__"

    suggestions = []

    if "search" in intents or "understand" in intents:
        suggestions.append(
            f'Use `{prefix}search_similar("query")` to find relevant code'
        )

    if "debug" in intents:
        suggestions.append(
            f'Check `{prefix}search_similar("error description", '
            f'entityTypes=["debugging_pattern"])` for past solutions'
        )

    if "implement" in intents and "code_terms" in intents:
        suggestions.append(
            f"Search for existing patterns with `{prefix}search_similar()` "
            f"before implementing"
        )

    if "refactor" in intents:
        suggestions.append(
            f'Use `{prefix}read_graph(entity="Name", mode="smart")` '
            f"to understand dependencies"
        )

    if not suggestions:
        # Default reminder for all code-related prompts
        if "code_terms" in intents:
            suggestions.append(
                f"This project has semantic memory. Use "
                f"`{prefix}search_similar()` before reading files."
            )

    return "\n".join(suggestions) if suggestions else ""


def check_sensitive(prompt: str) -> str | None:
    """Check for sensitive content in prompt."""
    if SENSITIVE_PATTERNS.search(prompt):
        return "Warning: Prompt may contain sensitive data."
    return None


def main():
    """Run the prompt handler hook."""
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)
        prompt = input_data.get("prompt", "")

        # Get collection from environment or default
        collection = os.environ.get("CLAUDE_MEMORY_COLLECTION", "project")

        # Analyze prompt
        intents = detect_intent(prompt)

        # Build context
        context_parts = []

        # Check for sensitive content (warning only)
        sensitive_warning = check_sensitive(prompt)
        if sensitive_warning:
            context_parts.append(sensitive_warning)

        # Plan Mode detection (Milestone 7.1)
        plan_result, _plan_ctx = detect_plan_mode(prompt)
        if plan_result.is_plan_mode:
            src = plan_result.source.value if plan_result.source else "unknown"
            context_parts.append(
                f"[Plan Mode Active: {src}, "
                f"confidence={plan_result.confidence:.0%}]"
            )

        # Add tool suggestions based on intent
        tool_context = build_context(intents, collection)
        if tool_context:
            context_parts.append(tool_context)

        # Output context if any
        if context_parts:
            print("\n".join(context_parts))

        sys.exit(0)

    except Exception as e:
        # Fail open - don't block on errors
        sys.stderr.write(f"prompt_handler warning: {e}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
