"""
Plan Mode context for Claude Code Memory.

This module provides the PlanModeContext dataclass that tracks all state
related to Plan Mode detection and lifecycle.

Milestone 7.1: Plan Mode Detection
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PlanModeSource(Enum):
    """How Plan Mode was detected."""

    EXPLICIT_MARKER = "explicit_marker"  # @agent-plan, @plan, --plan
    PLANNING_KEYWORD = "planning_keyword"  # "create a plan", etc.
    ENVIRONMENT_VAR = "environment_var"  # CLAUDE_PLAN_MODE=true
    SESSION_PERSISTED = "session_persisted"  # From session state


@dataclass
class PlanModeContext:
    """Tracks Plan Mode state for a Claude Code session.

    This context is created when Plan Mode is detected and persists
    across turns in the same session.

    Attributes:
        is_active: Whether Plan Mode is currently active
        source: How Plan Mode was detected
        confidence: Detection confidence score (0.0-1.0)
        activated_at: Timestamp when Plan Mode was activated
        detected_markers: List of markers/patterns that triggered detection
        turn_count: Number of turns in Plan Mode
        session_id: Associated session ID (links to SessionContext)

    Example:
        context = PlanModeContext(
            is_active=True,
            source=PlanModeSource.EXPLICIT_MARKER,
            confidence=1.0,
            detected_markers=["@plan"],
        )
    """

    is_active: bool = False
    source: PlanModeSource | None = None
    confidence: float = 0.0
    activated_at: float = 0.0
    detected_markers: list[str] = field(default_factory=list)
    turn_count: int = 0
    session_id: str | None = None

    def activate(
        self,
        source: PlanModeSource,
        confidence: float,
        markers: list[str],
        session_id: str | None = None,
    ) -> None:
        """Activate Plan Mode with detected parameters.

        Args:
            source: Detection source
            confidence: Confidence score (0.0-1.0)
            markers: Detected patterns/markers
            session_id: Optional session ID
        """
        self.is_active = True
        self.source = source
        self.confidence = confidence
        self.detected_markers = markers
        self.activated_at = time.time()
        self.turn_count = 1
        if session_id:
            self.session_id = session_id

    def deactivate(self) -> None:
        """Deactivate Plan Mode."""
        self.is_active = False
        self.source = None
        self.confidence = 0.0
        self.detected_markers = []
        self.activated_at = 0.0

    def increment_turn(self) -> None:
        """Increment turn counter for active Plan Mode."""
        if self.is_active:
            self.turn_count += 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "is_active": self.is_active,
            "source": self.source.value if self.source else None,
            "confidence": self.confidence,
            "activated_at": self.activated_at,
            "detected_markers": self.detected_markers,
            "turn_count": self.turn_count,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanModeContext":
        """Deserialize from dictionary.

        Args:
            data: Dictionary containing plan mode data

        Returns:
            PlanModeContext instance
        """
        source = PlanModeSource(data["source"]) if data.get("source") else None
        return cls(
            is_active=data.get("is_active", False),
            source=source,
            confidence=data.get("confidence", 0.0),
            activated_at=data.get("activated_at", 0.0),
            detected_markers=data.get("detected_markers", []),
            turn_count=data.get("turn_count", 0),
            session_id=data.get("session_id"),
        )

    def __str__(self) -> str:
        """Human-readable string representation."""
        if self.is_active:
            source_val = self.source.value if self.source else "unknown"
            return (
                f"PlanModeContext(active, source={source_val}, "
                f"confidence={self.confidence:.0%}, turns={self.turn_count})"
            )
        return "PlanModeContext(inactive)"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"PlanModeContext("
            f"is_active={self.is_active!r}, "
            f"source={self.source!r}, "
            f"confidence={self.confidence}, "
            f"activated_at={self.activated_at}, "
            f"detected_markers={self.detected_markers!r}, "
            f"turn_count={self.turn_count}, "
            f"session_id={self.session_id!r})"
        )
