"""
Hooks package for Claude Code integration.

This package provides hook handlers for Claude Code's lifecycle events:
- PostToolUse: Fast quality checks after file writes
- SessionStart: Initialize memory and verify health
- Stop: End-of-turn comprehensive checks

The hooks are designed for performance (<300ms for fast checks)
and fail-open behavior (never block on errors).
"""

from .post_write import PostWriteExecutor, PostWriteResult, format_findings_for_display
from .index_queue import IndexQueue

__all__ = [
    "PostWriteExecutor",
    "PostWriteResult",
    "format_findings_for_display",
    "IndexQueue",
]
