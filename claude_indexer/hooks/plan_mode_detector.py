"""
Plan Mode detector for Claude Code Memory.

Detects when Claude Code enters Plan Mode through multiple signals:
1. Explicit markers (@agent-plan, @plan, --plan, plan mode)
2. Planning keywords with confidence scoring
3. Environment variable (CLAUDE_PLAN_MODE)
4. Session state persistence

Performance target: <10ms detection latency
Accuracy target: >95% detection accuracy

Milestone 7.1: Plan Mode Detection
"""

import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from ..session.plan_context import PlanModeContext, PlanModeSource

# Pre-compiled patterns for performance (<10ms target)
# Explicit markers - 1.0 confidence
EXPLICIT_PATTERNS = re.compile(
    r"@agent-plan|@plan\b|--plan\b|plan\s*mode", re.IGNORECASE
)

# Planning keywords - 0.7 base confidence
# More permissive pattern to handle words between verb and "plan"
PLANNING_KEYWORDS = re.compile(
    r"\b(create|make|write|design|implement|develop|draft|formulate)\s+"
    r"(a\s+)?(\w+\s+){0,3}plan\b",
    re.IGNORECASE,
)

# Additional planning indicators for boosting confidence
PLANNING_BOOSTERS = re.compile(
    r"\b(step[- ]by[- ]step|phases?|milestones?|tasks?|timeline|roadmap)\b",
    re.IGNORECASE,
)

# Negative indicators (reduce confidence if present)
NON_PLANNING_INDICATORS = re.compile(
    r"\b(execute|run|apply|implement this|do it|start coding|"
    r"write the code)\b",
    re.IGNORECASE,
)


@dataclass
class PlanModeDetectionResult:
    """Result of Plan Mode detection.

    Attributes:
        is_plan_mode: Whether Plan Mode was detected
        confidence: Detection confidence (0.0-1.0)
        source: How Plan Mode was detected
        detected_markers: Patterns/markers that triggered detection
        detection_time_ms: Time taken for detection
        reasoning: Human-readable explanation
    """

    is_plan_mode: bool = False
    confidence: float = 0.0
    source: PlanModeSource | None = None
    detected_markers: list[str] = field(default_factory=list)
    detection_time_ms: float = 0.0
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_plan_mode": self.is_plan_mode,
            "confidence": round(self.confidence, 3),
            "source": self.source.value if self.source else None,
            "detected_markers": self.detected_markers,
            "detection_time_ms": round(self.detection_time_ms, 2),
            "reasoning": self.reasoning,
        }


class PlanModeDetector:
    """Detects Plan Mode activation from user prompts and context.

    Uses multiple detection methods with confidence scoring:
    1. Explicit markers (1.0 confidence): @agent-plan, @plan, --plan
    2. Planning keywords (0.7 base): "create a plan", etc.
    3. Environment variable (1.0 confidence): CLAUDE_PLAN_MODE=true
    4. Session persistence: Maintains state across turns

    Example:
        detector = PlanModeDetector()
        result = detector.detect("@plan Create a feature implementation plan")
        if result.is_plan_mode:
            print(f"Plan Mode detected via {result.source}")
    """

    # Confidence thresholds
    CONFIDENCE_THRESHOLD = 0.6
    EXPLICIT_CONFIDENCE = 1.0
    KEYWORD_BASE_CONFIDENCE = 0.7
    BOOSTER_INCREMENT = 0.1
    NEGATIVE_DECREMENT = 0.15
    ENV_CONFIDENCE = 1.0

    # Environment variable name
    ENV_VAR_NAME = "CLAUDE_PLAN_MODE"

    def __init__(
        self,
        plan_context: PlanModeContext | None = None,
        confidence_threshold: float | None = None,
    ):
        """Initialize the detector.

        Args:
            plan_context: Optional existing plan context for state
            confidence_threshold: Override default threshold
        """
        self.plan_context = plan_context or PlanModeContext()
        self.confidence_threshold = (
            confidence_threshold or self.CONFIDENCE_THRESHOLD
        )

    def detect(self, prompt: str) -> PlanModeDetectionResult:
        """Detect Plan Mode from a user prompt.

        Checks multiple signals in order of precedence:
        1. Explicit markers (highest priority)
        2. Environment variable
        3. Planning keywords with confidence scoring
        4. Session persistence

        Args:
            prompt: User prompt text

        Returns:
            PlanModeDetectionResult with detection outcome
        """
        start_time = time.time()

        # Check explicit markers first (highest confidence)
        result = self._check_explicit_markers(prompt)
        if result.is_plan_mode:
            result.detection_time_ms = (time.time() - start_time) * 1000
            return result

        # Check environment variable
        result = self._check_environment_variable()
        if result.is_plan_mode:
            result.detection_time_ms = (time.time() - start_time) * 1000
            return result

        # Check planning keywords with confidence
        result = self._check_planning_keywords(prompt)
        if result.is_plan_mode:
            result.detection_time_ms = (time.time() - start_time) * 1000
            return result

        # Check session persistence (Plan Mode active from previous turn)
        result = self._check_session_persistence()
        if result.is_plan_mode:
            result.detection_time_ms = (time.time() - start_time) * 1000
            return result

        # No Plan Mode detected
        result = PlanModeDetectionResult(
            is_plan_mode=False,
            confidence=0.0,
            reasoning="No Plan Mode indicators detected",
        )
        result.detection_time_ms = (time.time() - start_time) * 1000
        return result

    def _check_explicit_markers(self, prompt: str) -> PlanModeDetectionResult:
        """Check for explicit Plan Mode markers.

        Args:
            prompt: User prompt text

        Returns:
            PlanModeDetectionResult
        """
        matches = EXPLICIT_PATTERNS.findall(prompt)
        if matches:
            # Normalize matches to lowercase for consistency
            markers = [m.lower().strip() for m in matches]
            return PlanModeDetectionResult(
                is_plan_mode=True,
                confidence=self.EXPLICIT_CONFIDENCE,
                source=PlanModeSource.EXPLICIT_MARKER,
                detected_markers=markers,
                reasoning=f"Explicit marker detected: {', '.join(markers)}",
            )
        return PlanModeDetectionResult()

    def _check_environment_variable(self) -> PlanModeDetectionResult:
        """Check for CLAUDE_PLAN_MODE environment variable.

        Returns:
            PlanModeDetectionResult
        """
        env_value = os.environ.get(self.ENV_VAR_NAME, "").lower()
        if env_value in ("true", "1", "yes", "on"):
            return PlanModeDetectionResult(
                is_plan_mode=True,
                confidence=self.ENV_CONFIDENCE,
                source=PlanModeSource.ENVIRONMENT_VAR,
                detected_markers=[f"{self.ENV_VAR_NAME}={env_value}"],
                reasoning=f"Environment variable {self.ENV_VAR_NAME} is set",
            )
        return PlanModeDetectionResult()

    def _check_planning_keywords(self, prompt: str) -> PlanModeDetectionResult:
        """Check for planning keywords with confidence scoring.

        Base confidence starts at 0.7 for keyword match, then:
        - +0.1 for each planning booster (step-by-step, phases, etc.)
        - -0.15 for negative indicators (execute, run, etc.)

        Args:
            prompt: User prompt text

        Returns:
            PlanModeDetectionResult
        """
        keyword_matches = PLANNING_KEYWORDS.findall(prompt)
        if not keyword_matches:
            return PlanModeDetectionResult()

        # Start with base confidence
        confidence = self.KEYWORD_BASE_CONFIDENCE
        markers = [" ".join(m).strip() for m in keyword_matches if any(m)]

        # Check for boosters
        booster_matches = PLANNING_BOOSTERS.findall(prompt)
        if booster_matches:
            boost = min(len(booster_matches) * self.BOOSTER_INCREMENT, 0.3)
            confidence += boost
            markers.extend([b.lower() for b in booster_matches])

        # Check for negative indicators
        negative_matches = NON_PLANNING_INDICATORS.findall(prompt)
        if negative_matches:
            confidence -= len(negative_matches) * self.NEGATIVE_DECREMENT

        # Clamp confidence
        confidence = max(0.0, min(1.0, confidence))

        # Check threshold
        if confidence >= self.confidence_threshold:
            return PlanModeDetectionResult(
                is_plan_mode=True,
                confidence=confidence,
                source=PlanModeSource.PLANNING_KEYWORD,
                detected_markers=markers,
                reasoning=(
                    f"Planning keywords detected "
                    f"with {confidence:.0%} confidence"
                ),
            )

        return PlanModeDetectionResult(
            is_plan_mode=False,
            confidence=confidence,
            reasoning=(
                f"Planning keywords found but confidence {confidence:.0%} "
                f"below threshold {self.confidence_threshold:.0%}"
            ),
        )

    def _check_session_persistence(self) -> PlanModeDetectionResult:
        """Check if Plan Mode is active from session state.

        Returns:
            PlanModeDetectionResult
        """
        if self.plan_context.is_active:
            return PlanModeDetectionResult(
                is_plan_mode=True,
                confidence=self.plan_context.confidence,
                source=PlanModeSource.SESSION_PERSISTED,
                detected_markers=["session_state"],
                reasoning="Plan Mode persisted from previous turn",
            )
        return PlanModeDetectionResult()

    def update_context(
        self, result: PlanModeDetectionResult, session_id: str | None = None
    ) -> None:
        """Update PlanModeContext based on detection result.

        Args:
            result: Detection result
            session_id: Optional session ID
        """
        if result.is_plan_mode:
            if not self.plan_context.is_active:
                # Activating for first time
                self.plan_context.activate(
                    source=result.source,
                    confidence=result.confidence,
                    markers=result.detected_markers,
                    session_id=session_id,
                )
            else:
                # Already active, increment turn
                self.plan_context.increment_turn()
        # Note: We don't deactivate automatically - controlled externally

    def deactivate_plan_mode(self) -> None:
        """Explicitly deactivate Plan Mode."""
        self.plan_context.deactivate()


def detect_plan_mode(
    prompt: str,
    plan_context: PlanModeContext | None = None,
    session_id: str | None = None,
) -> tuple[PlanModeDetectionResult, PlanModeContext]:
    """Convenience function for Plan Mode detection.

    This is the main entry point for the hook integration.

    Args:
        prompt: User prompt text
        plan_context: Optional existing plan context
        session_id: Optional session ID

    Returns:
        Tuple of (detection result, updated plan context)
    """
    detector = PlanModeDetector(plan_context=plan_context)
    result = detector.detect(prompt)
    detector.update_context(result, session_id)
    return result, detector.plan_context
