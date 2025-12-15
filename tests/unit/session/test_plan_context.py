"""Unit tests for PlanModeContext.

Tests the Plan Mode state tracking dataclass.

Milestone 7.1: Plan Mode Detection
"""

import time

from claude_indexer.session.plan_context import PlanModeContext, PlanModeSource


class TestPlanModeContextInitialization:
    """Test PlanModeContext initialization."""

    def test_default_initialization(self):
        """Default initialization should create inactive context."""
        ctx = PlanModeContext()

        assert ctx.is_active is False
        assert ctx.source is None
        assert ctx.confidence == 0.0
        assert ctx.activated_at == 0.0
        assert ctx.detected_markers == []
        assert ctx.turn_count == 0
        assert ctx.session_id is None

    def test_initialization_with_values(self):
        """Initialization with values should set fields correctly."""
        ctx = PlanModeContext(
            is_active=True,
            source=PlanModeSource.EXPLICIT_MARKER,
            confidence=1.0,
            activated_at=1234567890.0,
            detected_markers=["@plan"],
            turn_count=3,
            session_id="test-session",
        )

        assert ctx.is_active is True
        assert ctx.source == PlanModeSource.EXPLICIT_MARKER
        assert ctx.confidence == 1.0
        assert ctx.activated_at == 1234567890.0
        assert ctx.detected_markers == ["@plan"]
        assert ctx.turn_count == 3
        assert ctx.session_id == "test-session"


class TestPlanModeContextActivation:
    """Test PlanModeContext activation."""

    def test_activate_sets_all_fields(self):
        """Activation should set all fields correctly."""
        ctx = PlanModeContext()
        before_time = time.time()

        ctx.activate(
            source=PlanModeSource.EXPLICIT_MARKER,
            confidence=1.0,
            markers=["@plan"],
            session_id="sess-123",
        )

        after_time = time.time()

        assert ctx.is_active is True
        assert ctx.source == PlanModeSource.EXPLICIT_MARKER
        assert ctx.confidence == 1.0
        assert "@plan" in ctx.detected_markers
        assert ctx.session_id == "sess-123"
        assert ctx.turn_count == 1
        assert before_time <= ctx.activated_at <= after_time

    def test_activate_without_session_id(self):
        """Activation without session_id should work."""
        ctx = PlanModeContext()
        ctx.activate(
            source=PlanModeSource.PLANNING_KEYWORD,
            confidence=0.8,
            markers=["create plan"],
        )

        assert ctx.is_active is True
        assert ctx.session_id is None

    def test_activate_with_multiple_markers(self):
        """Activation with multiple markers should preserve all."""
        ctx = PlanModeContext()
        ctx.activate(
            source=PlanModeSource.PLANNING_KEYWORD,
            confidence=0.9,
            markers=["create plan", "milestones", "phases"],
        )

        assert len(ctx.detected_markers) == 3
        assert "create plan" in ctx.detected_markers
        assert "milestones" in ctx.detected_markers
        assert "phases" in ctx.detected_markers


class TestPlanModeContextDeactivation:
    """Test PlanModeContext deactivation."""

    def test_deactivate_clears_all_fields(self):
        """Deactivation should clear all fields."""
        ctx = PlanModeContext()
        ctx.activate(PlanModeSource.EXPLICIT_MARKER, 1.0, ["@plan"], "session-1")

        ctx.deactivate()

        assert ctx.is_active is False
        assert ctx.source is None
        assert ctx.confidence == 0.0
        assert ctx.detected_markers == []
        assert ctx.activated_at == 0.0

    def test_deactivate_inactive_context(self):
        """Deactivating inactive context should be safe."""
        ctx = PlanModeContext()

        ctx.deactivate()  # Should not raise

        assert ctx.is_active is False


class TestPlanModeContextTurnCount:
    """Test turn count management."""

    def test_increment_turn_when_active(self):
        """Turn count should increment when active."""
        ctx = PlanModeContext()
        ctx.activate(PlanModeSource.EXPLICIT_MARKER, 1.0, ["@plan"])

        assert ctx.turn_count == 1

        ctx.increment_turn()
        assert ctx.turn_count == 2

        ctx.increment_turn()
        assert ctx.turn_count == 3

    def test_increment_turn_when_inactive(self):
        """Turn count should not increment when inactive."""
        ctx = PlanModeContext()

        ctx.increment_turn()

        assert ctx.turn_count == 0


class TestPlanModeContextSerialization:
    """Test serialization/deserialization."""

    def test_to_dict_active_context(self):
        """Active context should serialize correctly."""
        ctx = PlanModeContext()
        ctx.activate(
            source=PlanModeSource.PLANNING_KEYWORD,
            confidence=0.85,
            markers=["create plan"],
            session_id="sess-456",
        )
        ctx.turn_count = 5

        data = ctx.to_dict()

        assert data["is_active"] is True
        assert data["source"] == "planning_keyword"
        assert data["confidence"] == 0.85
        assert data["detected_markers"] == ["create plan"]
        assert data["session_id"] == "sess-456"
        assert data["turn_count"] == 5
        assert data["activated_at"] > 0

    def test_to_dict_inactive_context(self):
        """Inactive context should serialize correctly."""
        ctx = PlanModeContext()

        data = ctx.to_dict()

        assert data["is_active"] is False
        assert data["source"] is None
        assert data["confidence"] == 0.0
        assert data["detected_markers"] == []
        assert data["session_id"] is None

    def test_from_dict_active_context(self):
        """Active context should deserialize correctly."""
        data = {
            "is_active": True,
            "source": "explicit_marker",
            "confidence": 1.0,
            "activated_at": 1234567890.0,
            "detected_markers": ["@plan", "@agent-plan"],
            "turn_count": 3,
            "session_id": "sess-789",
        }

        ctx = PlanModeContext.from_dict(data)

        assert ctx.is_active is True
        assert ctx.source == PlanModeSource.EXPLICIT_MARKER
        assert ctx.confidence == 1.0
        assert ctx.activated_at == 1234567890.0
        assert ctx.detected_markers == ["@plan", "@agent-plan"]
        assert ctx.turn_count == 3
        assert ctx.session_id == "sess-789"

    def test_from_dict_inactive_context(self):
        """Inactive context should deserialize correctly."""
        data = {
            "is_active": False,
            "source": None,
            "confidence": 0.0,
        }

        ctx = PlanModeContext.from_dict(data)

        assert ctx.is_active is False
        assert ctx.source is None

    def test_from_dict_with_missing_fields(self):
        """Missing fields should use defaults."""
        data = {"is_active": True, "source": "environment_var"}

        ctx = PlanModeContext.from_dict(data)

        assert ctx.is_active is True
        assert ctx.source == PlanModeSource.ENVIRONMENT_VAR
        assert ctx.confidence == 0.0  # Default
        assert ctx.detected_markers == []  # Default

    def test_roundtrip_serialization(self):
        """Serialization/deserialization should be lossless."""
        original = PlanModeContext()
        original.activate(
            source=PlanModeSource.SESSION_PERSISTED,
            confidence=0.75,
            markers=["session_state"],
            session_id="roundtrip-test",
        )
        original.turn_count = 7

        data = original.to_dict()
        restored = PlanModeContext.from_dict(data)

        assert restored.is_active == original.is_active
        assert restored.source == original.source
        assert restored.confidence == original.confidence
        assert restored.detected_markers == original.detected_markers
        assert restored.turn_count == original.turn_count
        assert restored.session_id == original.session_id


class TestPlanModeSource:
    """Test PlanModeSource enum."""

    def test_all_sources_have_values(self):
        """All sources should have string values."""
        assert PlanModeSource.EXPLICIT_MARKER.value == "explicit_marker"
        assert PlanModeSource.PLANNING_KEYWORD.value == "planning_keyword"
        assert PlanModeSource.ENVIRONMENT_VAR.value == "environment_var"
        assert PlanModeSource.SESSION_PERSISTED.value == "session_persisted"

    def test_source_from_string(self):
        """Should be able to create source from string."""
        explicit = PlanModeSource("explicit_marker")
        assert explicit == PlanModeSource.EXPLICIT_MARKER
        keyword = PlanModeSource("planning_keyword")
        assert keyword == PlanModeSource.PLANNING_KEYWORD


class TestPlanModeContextStringRepresentation:
    """Test string representations."""

    def test_str_active(self):
        """Active context str should show status."""
        ctx = PlanModeContext()
        ctx.activate(PlanModeSource.EXPLICIT_MARKER, 1.0, ["@plan"])
        ctx.turn_count = 2

        result = str(ctx)

        assert "active" in result.lower()
        assert "explicit_marker" in result
        assert "100%" in result
        assert "turns=2" in result

    def test_str_inactive(self):
        """Inactive context str should show inactive."""
        ctx = PlanModeContext()

        result = str(ctx)

        assert "inactive" in result.lower()

    def test_repr(self):
        """repr should show all fields."""
        ctx = PlanModeContext()
        ctx.activate(PlanModeSource.PLANNING_KEYWORD, 0.8, ["create plan"])

        result = repr(ctx)

        assert "PlanModeContext" in result
        assert "is_active=True" in result
        assert "PLANNING_KEYWORD" in result
