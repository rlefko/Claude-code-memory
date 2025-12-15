"""Tests for plan validation guardrails configuration.

Tests the PlanGuardrailConfig and RuleConfig classes.
"""

import pytest

from claude_indexer.ui.plan.guardrails.config import (
    PlanGuardrailConfig,
    RuleConfig,
)


class TestRuleConfig:
    """Tests for RuleConfig class."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = RuleConfig()
        assert config.enabled is True
        assert config.severity == "MEDIUM"
        assert config.threshold is None
        assert config.auto_revise is True

    def test_custom_values(self):
        """Test creating config with custom values."""
        config = RuleConfig(
            enabled=False,
            severity="HIGH",
            threshold=0.8,
            auto_revise=False,
        )
        assert config.enabled is False
        assert config.severity == "HIGH"
        assert config.threshold == 0.8
        assert config.auto_revise is False

    def test_extra_fields_allowed(self):
        """Test that extra fields are allowed."""
        config = RuleConfig(custom_field="test")
        assert config.custom_field == "test"

    def test_dict_conversion(self):
        """Test converting to/from dict."""
        original = RuleConfig(severity="HIGH", threshold=0.9)
        data = original.dict()
        restored = RuleConfig(**data)
        assert restored.severity == "HIGH"
        assert restored.threshold == 0.9


class TestPlanGuardrailConfig:
    """Tests for PlanGuardrailConfig class."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = PlanGuardrailConfig()
        assert config.enabled is True
        assert config.rules == {}
        assert config.severity_thresholds == {"block": "HIGH", "warn": "MEDIUM"}
        assert config.check_coverage is True
        assert config.check_consistency is True
        assert config.check_architecture is True
        assert config.check_performance is True
        assert config.auto_revise is True
        assert config.max_revisions_per_plan == 10
        assert config.revision_confidence_threshold == 0.7
        assert config.max_findings_per_rule == 10

    def test_custom_values(self):
        """Test creating config with custom values."""
        config = PlanGuardrailConfig(
            enabled=False,
            check_coverage=False,
            auto_revise=False,
            max_revisions_per_plan=5,
            revision_confidence_threshold=0.9,
        )
        assert config.enabled is False
        assert config.check_coverage is False
        assert config.auto_revise is False
        assert config.max_revisions_per_plan == 5
        assert config.revision_confidence_threshold == 0.9

    def test_with_rule_configs(self):
        """Test creating config with rule-specific settings."""
        config = PlanGuardrailConfig(
            rules={
                "PLAN.TEST_REQUIREMENT": RuleConfig(severity="HIGH"),
                "PLAN.DUPLICATE_DETECTION": RuleConfig(enabled=False),
            }
        )
        assert "PLAN.TEST_REQUIREMENT" in config.rules
        assert config.rules["PLAN.TEST_REQUIREMENT"].severity == "HIGH"
        assert config.rules["PLAN.DUPLICATE_DETECTION"].enabled is False


class TestIsRuleEnabled:
    """Tests for is_rule_enabled method."""

    def test_global_disabled(self):
        """Test all rules disabled when global disabled."""
        config = PlanGuardrailConfig(enabled=False)
        assert config.is_rule_enabled("PLAN.TEST_REQUIREMENT", "coverage") is False

    def test_category_disabled(self):
        """Test rules disabled when category disabled."""
        config = PlanGuardrailConfig(check_coverage=False)
        assert config.is_rule_enabled("PLAN.TEST_REQUIREMENT", "coverage") is False
        assert config.is_rule_enabled("PLAN.DUPLICATE_DETECTION", "consistency") is True

    def test_rule_specific_disabled(self):
        """Test individual rule disabled."""
        config = PlanGuardrailConfig(
            rules={
                "PLAN.TEST_REQUIREMENT": RuleConfig(enabled=False),
            }
        )
        assert config.is_rule_enabled("PLAN.TEST_REQUIREMENT", "coverage") is False
        assert config.is_rule_enabled("PLAN.DOC_REQUIREMENT", "coverage") is True

    def test_rule_enabled_by_default(self):
        """Test rules enabled by default."""
        config = PlanGuardrailConfig()
        assert config.is_rule_enabled("PLAN.TEST_REQUIREMENT", "coverage") is True
        assert config.is_rule_enabled("UNKNOWN_RULE", "unknown") is True

    def test_all_categories(self):
        """Test all category toggles."""
        config = PlanGuardrailConfig(
            check_coverage=False,
            check_consistency=False,
            check_architecture=False,
            check_performance=False,
        )
        assert config.is_rule_enabled("RULE", "coverage") is False
        assert config.is_rule_enabled("RULE", "consistency") is False
        assert config.is_rule_enabled("RULE", "architecture") is False
        assert config.is_rule_enabled("RULE", "performance") is False


class TestGetRuleConfig:
    """Tests for get_rule_config method."""

    def test_rule_exists(self):
        """Test getting existing rule config."""
        config = PlanGuardrailConfig(
            rules={
                "PLAN.TEST_REQUIREMENT": RuleConfig(severity="HIGH"),
            }
        )
        rule_config = config.get_rule_config("PLAN.TEST_REQUIREMENT")
        assert rule_config is not None
        assert rule_config.severity == "HIGH"

    def test_rule_not_exists(self):
        """Test getting non-existing rule config."""
        config = PlanGuardrailConfig()
        rule_config = config.get_rule_config("NONEXISTENT")
        assert rule_config is None


class TestShouldAutoRevise:
    """Tests for should_auto_revise method."""

    def test_global_disabled(self):
        """Test no auto-revise when globally disabled."""
        config = PlanGuardrailConfig(auto_revise=False)
        assert config.should_auto_revise("PLAN.TEST_REQUIREMENT", 0.9) is False

    def test_confidence_below_threshold(self):
        """Test no auto-revise when confidence too low."""
        config = PlanGuardrailConfig(revision_confidence_threshold=0.8)
        assert config.should_auto_revise("PLAN.TEST_REQUIREMENT", 0.7) is False
        assert config.should_auto_revise("PLAN.TEST_REQUIREMENT", 0.8) is True
        assert config.should_auto_revise("PLAN.TEST_REQUIREMENT", 0.9) is True

    def test_rule_specific_disabled(self):
        """Test no auto-revise when rule-specific disabled."""
        config = PlanGuardrailConfig(
            rules={
                "PLAN.TEST_REQUIREMENT": RuleConfig(auto_revise=False),
            }
        )
        assert config.should_auto_revise("PLAN.TEST_REQUIREMENT", 0.9) is False
        assert config.should_auto_revise("PLAN.OTHER_RULE", 0.9) is True

    def test_auto_revise_enabled(self):
        """Test auto-revise enabled with good confidence."""
        config = PlanGuardrailConfig()
        assert config.should_auto_revise("PLAN.TEST_REQUIREMENT", 0.9) is True


class TestSeverityShouldBlock:
    """Tests for severity_should_block method."""

    def test_default_thresholds(self):
        """Test default threshold (HIGH blocks)."""
        config = PlanGuardrailConfig()
        assert config.severity_should_block("critical") is True
        assert config.severity_should_block("high") is True
        assert config.severity_should_block("medium") is False
        assert config.severity_should_block("low") is False

    def test_custom_threshold(self):
        """Test custom block threshold."""
        config = PlanGuardrailConfig(
            severity_thresholds={"block": "MEDIUM", "warn": "LOW"}
        )
        assert config.severity_should_block("critical") is True
        assert config.severity_should_block("high") is True
        assert config.severity_should_block("medium") is True
        assert config.severity_should_block("low") is False

    def test_case_insensitive(self):
        """Test severity comparison is case insensitive."""
        config = PlanGuardrailConfig()
        assert config.severity_should_block("HIGH") is True
        assert config.severity_should_block("High") is True
        assert config.severity_should_block("CRITICAL") is True

    def test_invalid_severity(self):
        """Test invalid severity returns False."""
        config = PlanGuardrailConfig()
        assert config.severity_should_block("invalid") is False
        assert config.severity_should_block("") is False


class TestValidation:
    """Tests for Pydantic validation."""

    def test_max_revisions_bounds(self):
        """Test max_revisions_per_plan bounds."""
        # Valid
        config = PlanGuardrailConfig(max_revisions_per_plan=1)
        assert config.max_revisions_per_plan == 1

        config = PlanGuardrailConfig(max_revisions_per_plan=50)
        assert config.max_revisions_per_plan == 50

        # Invalid
        with pytest.raises(ValueError):
            PlanGuardrailConfig(max_revisions_per_plan=0)

        with pytest.raises(ValueError):
            PlanGuardrailConfig(max_revisions_per_plan=51)

    def test_confidence_threshold_bounds(self):
        """Test revision_confidence_threshold bounds."""
        # Valid
        config = PlanGuardrailConfig(revision_confidence_threshold=0.0)
        assert config.revision_confidence_threshold == 0.0

        config = PlanGuardrailConfig(revision_confidence_threshold=1.0)
        assert config.revision_confidence_threshold == 1.0

        # Invalid
        with pytest.raises(ValueError):
            PlanGuardrailConfig(revision_confidence_threshold=-0.1)

        with pytest.raises(ValueError):
            PlanGuardrailConfig(revision_confidence_threshold=1.1)

    def test_max_findings_per_rule_bounds(self):
        """Test max_findings_per_rule bounds."""
        # Valid
        config = PlanGuardrailConfig(max_findings_per_rule=1)
        assert config.max_findings_per_rule == 1

        config = PlanGuardrailConfig(max_findings_per_rule=100)
        assert config.max_findings_per_rule == 100

        # Invalid
        with pytest.raises(ValueError):
            PlanGuardrailConfig(max_findings_per_rule=0)

        with pytest.raises(ValueError):
            PlanGuardrailConfig(max_findings_per_rule=101)


class TestDictConversion:
    """Tests for dict conversion."""

    def test_to_dict(self):
        """Test converting config to dict."""
        config = PlanGuardrailConfig(
            check_coverage=False,
            rules={
                "PLAN.TEST": RuleConfig(severity="HIGH"),
            },
        )
        data = config.dict()
        assert data["check_coverage"] is False
        assert "PLAN.TEST" in data["rules"]
        assert data["rules"]["PLAN.TEST"]["severity"] == "HIGH"

    def test_from_dict(self):
        """Test creating config from dict."""
        data = {
            "enabled": True,
            "check_coverage": False,
            "auto_revise": True,
            "rules": {
                "PLAN.TEST": {"severity": "HIGH", "enabled": False},
            },
        }
        config = PlanGuardrailConfig(**data)
        assert config.check_coverage is False
        assert "PLAN.TEST" in config.rules
        assert config.rules["PLAN.TEST"].severity == "HIGH"
        assert config.rules["PLAN.TEST"].enabled is False
