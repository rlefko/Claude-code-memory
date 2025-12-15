"""Plan guardrail engine for orchestrating plan validation.

This module provides the PlanGuardrailEngine class that manages rule
registration, discovery, and execution for validating implementation plans.
"""

import importlib.util
import inspect
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from claude_indexer.rules.base import Severity

from .base import PlanValidationContext, PlanValidationFinding, PlanValidationRule

if TYPE_CHECKING:
    from .config import PlanGuardrailConfig


@dataclass
class PlanGuardrailEngineConfig:
    """Configuration for the plan guardrail engine."""

    # Maximum time for a single rule in fast mode (ms)
    fast_rule_timeout_ms: float = 100.0
    # Whether to continue on rule errors
    continue_on_error: bool = True
    # Minimum confidence to include findings
    min_confidence: float = 0.7
    # Future: enable parallel rule execution
    parallel_execution: bool = False


@dataclass
class RuleExecutionResult:
    """Result from executing a single rule."""

    rule_id: str
    findings: list[PlanValidationFinding] = field(default_factory=list)
    execution_time_ms: float = 0.0
    error: str | None = None


@dataclass
class PlanGuardrailResult:
    """Aggregated result from plan validation.

    Contains all findings from rule execution along with
    execution statistics and any errors encountered.
    """

    findings: list[PlanValidationFinding] = field(default_factory=list)
    rules_executed: int = 0
    rules_skipped: int = 0
    execution_time_ms: float = 0.0
    errors: list[tuple[str, str]] = field(default_factory=list)  # (rule_id, error)

    @property
    def has_findings(self) -> bool:
        """Check if any findings were generated."""
        return len(self.findings) > 0

    @property
    def has_errors(self) -> bool:
        """Check if any errors occurred during validation."""
        return len(self.errors) > 0

    @property
    def has_blocking_findings(self) -> bool:
        """Check if any findings would block the plan.

        Returns True if any findings have HIGH or CRITICAL severity.
        """
        blocking_severities = {Severity.HIGH, Severity.CRITICAL}
        return any(f.severity in blocking_severities for f in self.findings)

    @property
    def findings_by_severity(self) -> dict[Severity, list[PlanValidationFinding]]:
        """Group findings by severity level."""
        result: dict[Severity, list[PlanValidationFinding]] = {}
        for finding in self.findings:
            if finding.severity not in result:
                result[finding.severity] = []
            result[finding.severity].append(finding)
        return result

    def findings_by_category(
        self, rules: dict[str, PlanValidationRule]
    ) -> dict[str, list[PlanValidationFinding]]:
        """Group findings by rule category.

        Args:
            rules: Mapping of rule_id to rule for category lookup.

        Returns:
            Dictionary mapping category to list of findings.
        """
        result: dict[str, list[PlanValidationFinding]] = {}
        for finding in self.findings:
            rule = rules.get(finding.rule_id)
            category = rule.category if rule else "unknown"
            if category not in result:
                result[category] = []
            result[category].append(finding)
        return result

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "findings": [f.to_dict() for f in self.findings],
            "rules_executed": self.rules_executed,
            "rules_skipped": self.rules_skipped,
            "execution_time_ms": self.execution_time_ms,
            "errors": [{"rule_id": e[0], "error": e[1]} for e in self.errors],
            "has_blocking_findings": self.has_blocking_findings,
        }

    def format_for_display(
        self,
        config: "PlanGuardrailConfig | None" = None,
    ) -> str:
        """Format findings for human-readable display.

        Args:
            config: Optional config for thoroughness level.

        Returns:
            Formatted string.
        """
        from ..formatters import ThoroughnessLevel, format_plan_findings_for_display

        thoroughness = ThoroughnessLevel.STANDARD
        group_by_severity = True

        if config:
            thoroughness = ThoroughnessLevel(config.thoroughness_level)
            group_by_severity = config.group_findings_by_severity

        return format_plan_findings_for_display(
            self.findings,
            thoroughness=thoroughness,
            group_by_severity=group_by_severity,
        )

    def format_for_claude(
        self,
        config: "PlanGuardrailConfig | None" = None,
    ) -> str:
        """Format findings for Claude consumption.

        Args:
            config: Optional config for thoroughness level.

        Returns:
            Formatted string.
        """
        from ..formatters import ThoroughnessLevel, format_plan_findings_for_claude

        thoroughness = ThoroughnessLevel.THOROUGH
        if config:
            thoroughness = ThoroughnessLevel(config.thoroughness_level)

        return format_plan_findings_for_claude(
            self.findings,
            thoroughness=thoroughness,
        )


class PlanGuardrailEngine:
    """Engine for running plan validation guardrail rules.

    Manages rule registration, discovery, execution, and result aggregation.
    Supports both manual registration and auto-discovery from a rules directory.
    """

    def __init__(
        self,
        config: "PlanGuardrailConfig",
        engine_config: PlanGuardrailEngineConfig | None = None,
    ):
        """Initialize the guardrail engine.

        Args:
            config: Plan guardrail configuration.
            engine_config: Optional engine-specific configuration.
        """
        self.config = config
        self.engine_config = engine_config or PlanGuardrailEngineConfig(
            min_confidence=config.revision_confidence_threshold,
        )
        self._rules: dict[str, PlanValidationRule] = {}
        self._rules_by_category: dict[str, list[PlanValidationRule]] = {}

    def register(self, rule: PlanValidationRule) -> None:
        """Register a rule with the engine.

        Args:
            rule: Rule instance to register.

        Raises:
            ValueError: If a rule with the same ID is already registered.
        """
        if rule.rule_id in self._rules:
            raise ValueError(f"Rule {rule.rule_id} is already registered")

        self._rules[rule.rule_id] = rule

        # Index by category
        if rule.category not in self._rules_by_category:
            self._rules_by_category[rule.category] = []
        self._rules_by_category[rule.category].append(rule)

    def unregister(self, rule_id: str) -> bool:
        """Unregister a rule by ID.

        Args:
            rule_id: ID of the rule to unregister.

        Returns:
            True if rule was unregistered, False if not found.
        """
        if rule_id not in self._rules:
            return False

        rule = self._rules[rule_id]
        del self._rules[rule_id]

        if rule.category in self._rules_by_category:
            self._rules_by_category[rule.category] = [
                r
                for r in self._rules_by_category[rule.category]
                if r.rule_id != rule_id
            ]

        return True

    def get_rule(self, rule_id: str) -> PlanValidationRule | None:
        """Get a rule by ID.

        Args:
            rule_id: ID of the rule to retrieve.

        Returns:
            Rule instance or None if not found.
        """
        return self._rules.get(rule_id)

    def get_rules_by_category(self, category: str) -> list[PlanValidationRule]:
        """Get all rules in a category.

        Args:
            category: Rule category to filter by.

        Returns:
            List of rules in the category.
        """
        return self._rules_by_category.get(category, [])

    def get_fast_rules(self) -> list[PlanValidationRule]:
        """Get rules suitable for synchronous execution.

        Returns:
            List of rules where is_fast is True (<100ms).
        """
        return [r for r in self._rules.values() if r.is_fast]

    def get_all_rules(self) -> list[PlanValidationRule]:
        """Get all registered rules.

        Returns:
            List of all registered rules.
        """
        return list(self._rules.values())

    @property
    def rule_count(self) -> int:
        """Number of registered rules."""
        return len(self._rules)

    def discover_rules(self, rules_dir: Path | None = None) -> int:
        """Auto-discover and register rules from a directory.

        Scans the specified directory for Python files and registers
        any classes that subclass PlanValidationRule.

        Args:
            rules_dir: Directory to scan. Defaults to guardrails/rules/.

        Returns:
            Number of rules discovered and registered.
        """
        if rules_dir is None:
            rules_dir = Path(__file__).parent / "rules"

        if not rules_dir.exists():
            return 0

        discovered = 0

        for py_file in rules_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                # Load the module dynamically
                spec = importlib.util.spec_from_file_location(
                    f"guardrails_rules_{py_file.stem}",
                    py_file,
                )
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find all PlanValidationRule subclasses
                for _name, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, PlanValidationRule)
                        and obj is not PlanValidationRule
                        and not inspect.isabstract(obj)
                    ):
                        try:
                            rule_instance = obj()
                            self.register(rule_instance)
                            discovered += 1
                        except Exception:
                            # Skip rules that fail to instantiate
                            pass

            except Exception:
                # Skip files that fail to import
                pass

        return discovered

    def validate(
        self,
        context: PlanValidationContext,
        rule_ids: list[str] | None = None,
    ) -> PlanGuardrailResult:
        """Run rules and collect findings.

        Args:
            context: PlanValidationContext with plan and config.
            rule_ids: Optional list of specific rule IDs to run.
                     If None, runs all registered rules.

        Returns:
            PlanGuardrailResult with all findings and statistics.
        """
        start_time = time.perf_counter()

        # Determine which rules to run
        if rule_ids is not None:
            rules_to_run = [self._rules[rid] for rid in rule_ids if rid in self._rules]
        else:
            rules_to_run = list(self._rules.values())

        # Execute rules and collect findings
        all_findings: list[PlanValidationFinding] = []
        errors: list[tuple[str, str]] = []
        rules_executed = 0
        rules_skipped = 0

        for rule in rules_to_run:
            # Check if rule is enabled via config
            if not context.config.is_rule_enabled(rule.rule_id, rule.category):
                rules_skipped += 1
                continue

            # Execute rule with timing and error handling
            result = self._execute_rule(rule, context)
            rules_executed += 1

            if result.error:
                errors.append((rule.rule_id, result.error))
            else:
                # Filter findings by confidence and max findings
                filtered = self._filter_findings(result.findings, rule.rule_id)
                all_findings.extend(filtered)

        # Calculate total execution time
        total_time_ms = (time.perf_counter() - start_time) * 1000

        return PlanGuardrailResult(
            findings=all_findings,
            rules_executed=rules_executed,
            rules_skipped=rules_skipped,
            execution_time_ms=total_time_ms,
            errors=errors,
        )

    def validate_fast(
        self,
        context: PlanValidationContext,
    ) -> PlanGuardrailResult:
        """Run only fast rules for synchronous execution.

        Args:
            context: PlanValidationContext with plan and config.

        Returns:
            PlanGuardrailResult with findings from fast rules only.
        """
        fast_rule_ids = [r.rule_id for r in self.get_fast_rules()]
        return self.validate(context, rule_ids=fast_rule_ids)

    def validate_category(
        self,
        context: PlanValidationContext,
        category: str,
    ) -> PlanGuardrailResult:
        """Run all rules in a specific category.

        Args:
            context: PlanValidationContext with plan and config.
            category: Category of rules to run.

        Returns:
            PlanGuardrailResult with findings from category rules.
        """
        rule_ids = [r.rule_id for r in self.get_rules_by_category(category)]
        return self.validate(context, rule_ids=rule_ids)

    def _execute_rule(
        self,
        rule: PlanValidationRule,
        context: PlanValidationContext,
    ) -> RuleExecutionResult:
        """Execute a single rule with error handling.

        Args:
            rule: Rule to execute.
            context: Validation context.

        Returns:
            RuleExecutionResult with findings or error.
        """
        start_time = time.perf_counter()

        try:
            findings = rule.validate(context)
            execution_time_ms = (time.perf_counter() - start_time) * 1000

            return RuleExecutionResult(
                rule_id=rule.rule_id,
                findings=findings,
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            execution_time_ms = (time.perf_counter() - start_time) * 1000

            if not self.engine_config.continue_on_error:
                raise

            return RuleExecutionResult(
                rule_id=rule.rule_id,
                findings=[],
                execution_time_ms=execution_time_ms,
                error=str(e),
            )

    def _filter_findings(
        self,
        findings: list[PlanValidationFinding],
        rule_id: str,
    ) -> list[PlanValidationFinding]:
        """Filter findings based on engine configuration.

        Args:
            findings: List of findings to filter.
            rule_id: ID of the rule that generated findings.

        Returns:
            Filtered list of findings.
        """
        filtered: list[PlanValidationFinding] = []

        # Apply max findings per rule limit
        max_findings = self.config.max_findings_per_rule

        for finding in findings:
            # Check confidence threshold
            if finding.confidence < self.engine_config.min_confidence:
                continue

            filtered.append(finding)

            # Stop if we've hit the limit
            if len(filtered) >= max_findings:
                break

        return filtered


def create_guardrail_engine(
    config: "PlanGuardrailConfig",
    discover_rules: bool = True,
    rules_dir: Path | None = None,
) -> PlanGuardrailEngine:
    """Create and configure a plan guardrail engine.

    Args:
        config: Plan guardrail configuration.
        discover_rules: Whether to auto-discover rules from directory.
        rules_dir: Optional directory to discover rules from.

    Returns:
        Configured PlanGuardrailEngine instance.
    """
    engine = PlanGuardrailEngine(config)

    if discover_rules:
        engine.discover_rules(rules_dir)

    return engine


__all__ = [
    "PlanGuardrailEngine",
    "PlanGuardrailEngineConfig",
    "PlanGuardrailResult",
    "RuleExecutionResult",
    "create_guardrail_engine",
]
