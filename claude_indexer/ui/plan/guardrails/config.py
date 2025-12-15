"""Configuration for plan validation guardrails.

This module provides the Pydantic configuration model for controlling
plan validation behavior, rule settings, and severity thresholds.
"""

from pydantic import BaseModel, Field


class RuleConfig(BaseModel):
    """Individual rule configuration for plan guardrails."""

    enabled: bool = Field(default=True, description="Enable this rule")
    severity: str = Field(default="MEDIUM", description="Rule severity override")
    threshold: float | None = Field(
        default=None, description="Rule-specific threshold (e.g., similarity)"
    )
    auto_revise: bool = Field(
        default=True, description="Enable auto-revision for this rule"
    )

    class Config:
        extra = "allow"


class PlanGuardrailConfig(BaseModel):
    """Configuration for plan validation guardrails.

    Controls which guardrail rules run, their severity levels,
    and auto-revision behavior during plan validation.
    """

    enabled: bool = Field(default=True, description="Enable plan guardrails")
    rules: dict[str, RuleConfig] = Field(
        default_factory=dict, description="Rule-specific configuration"
    )
    severity_thresholds: dict[str, str] = Field(
        default_factory=lambda: {"block": "HIGH", "warn": "MEDIUM"},
        description="Severity thresholds for blocking vs warning",
    )

    # Category toggles for quick enable/disable
    check_coverage: bool = Field(
        default=True, description="Enable coverage rules (test/doc requirements)"
    )
    check_consistency: bool = Field(
        default=True, description="Enable consistency rules (duplicate detection)"
    )
    check_architecture: bool = Field(
        default=True, description="Enable architecture rules (pattern alignment)"
    )
    check_performance: bool = Field(
        default=True, description="Enable performance rules (anti-pattern detection)"
    )

    # Auto-revision settings
    auto_revise: bool = Field(default=True, description="Apply auto-revisions to plans")
    max_revisions_per_plan: int = Field(
        default=10, ge=1, le=50, description="Maximum revisions to apply per plan"
    )
    revision_confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for auto-revision",
    )

    # Output limits
    max_findings_per_rule: int = Field(
        default=10, ge=1, le=100, description="Maximum findings per rule"
    )

    class Config:
        extra = "allow"

    def is_rule_enabled(self, rule_id: str, category: str) -> bool:
        """Check if a specific rule is enabled.

        Args:
            rule_id: Rule identifier (e.g., 'PLAN.TEST_REQUIREMENT')
            category: Rule category (coverage, consistency, architecture, performance)

        Returns:
            True if the rule should run
        """
        if not self.enabled:
            return False

        # Check category toggle
        category_enabled = {
            "coverage": self.check_coverage,
            "consistency": self.check_consistency,
            "architecture": self.check_architecture,
            "performance": self.check_performance,
        }
        if not category_enabled.get(category, True):
            return False

        # Check rule-specific config
        if rule_id in self.rules:
            return self.rules[rule_id].enabled

        return True

    def get_rule_config(self, rule_id: str) -> RuleConfig | None:
        """Get configuration for a specific rule.

        Args:
            rule_id: Rule identifier

        Returns:
            RuleConfig if exists, None otherwise
        """
        return self.rules.get(rule_id)

    def should_auto_revise(self, rule_id: str, confidence: float) -> bool:
        """Check if auto-revision should be applied for a finding.

        Args:
            rule_id: Rule identifier
            confidence: Finding confidence score

        Returns:
            True if auto-revision should be applied
        """
        if not self.auto_revise:
            return False

        if confidence < self.revision_confidence_threshold:
            return False

        # Check rule-specific config
        if rule_id in self.rules:
            return self.rules[rule_id].auto_revise

        return True

    def severity_should_block(self, severity: str) -> bool:
        """Check if a severity level should block the plan.

        Args:
            severity: Severity level string

        Returns:
            True if the severity is high enough to block
        """
        severity_order = ["low", "medium", "high", "critical"]
        block_threshold = self.severity_thresholds.get("block", "HIGH").lower()

        try:
            severity_idx = severity_order.index(severity.lower())
            block_idx = severity_order.index(block_threshold)
            return severity_idx >= block_idx
        except ValueError:
            return False


__all__ = [
    "PlanGuardrailConfig",
    "RuleConfig",
]
