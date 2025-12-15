"""
Session management for Claude Code Memory.

This module provides session isolation to enable multiple concurrent
Claude Code sessions to work on different projects without interference.

Key components:
- SessionContext: Tracks session state (ID, project, collection, config)
- SessionManager: Lifecycle management for sessions
- ProjectRootDetector: Finds project root from CWD
- LockManager: File-based locking for concurrent access protection
- PlanModeContext: Plan Mode state tracking (Milestone 7.1)
"""

from .context import SessionContext
from .detector import ProjectRootDetector
from .lock import LockConflictError, LockManager
from .manager import SessionManager, get_session_context
from .plan_context import PlanModeContext, PlanModeSource

__all__ = [
    "SessionContext",
    "SessionManager",
    "ProjectRootDetector",
    "LockManager",
    "LockConflictError",
    "get_session_context",
    # Plan Mode (Milestone 7.1)
    "PlanModeContext",
    "PlanModeSource",
]
