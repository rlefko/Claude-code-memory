"""Tests for plan guardrail engine module.

Tests the PlanGuardrailEngine, PlanGuardrailResult, and related classes.
"""

import tempfile
import time
from pathlib import Path

import pytest

from claude_indexer.rules.base import Severity
from claude_indexer.ui.plan.guardrails.base import (
    PlanValidationContext,
    PlanValidationFinding,
    PlanValidationRule,
)
from claude_indexer.ui.plan.guardrails.config import PlanGuardrailConfig
from claude_indexer.ui.plan.guardrails.engine import (
    PlanGuardrailEngine,
    PlanGuardrailEngineConfig,
    PlanGuardrailResult,
    RuleExecutionResult,
    create_guardrail_engine,
)
from claude_indexer.ui.plan.task import ImplementationPlan, Task, TaskGroup

# --- Mock Rules for Testing ---


class MockCoverageRule(PlanValidationRule):
    """Mock coverage rule for testing."""

    @property
    def rule_id(self) -> str:
        return "PLAN.MOCK_COVERAGE"

    @property
    def name(self) -> str:
        return "Mock Coverage Rule"

    @property
    def category(self) -> str:
        return "coverage"

    @property
    def default_severity(self) -> Severity:
        return Severity.MEDIUM

    @property
    def is_fast(self) -> bool:
        return True

    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]:
        return [
            self._create_finding(
                summary="Mock coverage finding",
                confidence=0.9,
            )
        ]

    def suggest_revision(self, finding, context):
        return None


class MockConsistencyRule(PlanValidationRule):
    """Mock consistency rule for testing."""

    @property
    def rule_id(self) -> str:
        return "PLAN.MOCK_CONSISTENCY"

    @property
    def name(self) -> str:
        return "Mock Consistency Rule"

    @property
    def category(self) -> str:
        return "consistency"

    @property
    def default_severity(self) -> Severity:
        return Severity.HIGH

    @property
    def is_fast(self) -> bool:
        return False  # Slow rule

    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]:
        return [
            self._create_finding(
                summary="Mock consistency finding",
                confidence=0.85,
            )
        ]

    def suggest_revision(self, finding, context):
        return None


class MockLowConfidenceRule(PlanValidationRule):
    """Mock rule that produces low confidence findings."""

    @property
    def rule_id(self) -> str:
        return "PLAN.MOCK_LOW_CONFIDENCE"

    @property
    def name(self) -> str:
        return "Mock Low Confidence Rule"

    @property
    def category(self) -> str:
        return "coverage"

    @property
    def default_severity(self) -> Severity:
        return Severity.LOW

    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]:
        return [
            self._create_finding(
                summary="Low confidence finding",
                confidence=0.3,  # Below threshold
            )
        ]

    def suggest_revision(self, finding, context):
        return None


class MockErrorRule(PlanValidationRule):
    """Mock rule that raises an error."""

    @property
    def rule_id(self) -> str:
        return "PLAN.MOCK_ERROR"

    @property
    def name(self) -> str:
        return "Mock Error Rule"

    @property
    def category(self) -> str:
        return "architecture"

    @property
    def default_severity(self) -> Severity:
        return Severity.MEDIUM

    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]:
        raise RuntimeError("Mock rule error")

    def suggest_revision(self, finding, context):
        return None


class MockManyFindingsRule(PlanValidationRule):
    """Mock rule that produces many findings."""

    @property
    def rule_id(self) -> str:
        return "PLAN.MOCK_MANY"

    @property
    def name(self) -> str:
        return "Mock Many Findings Rule"

    @property
    def category(self) -> str:
        return "performance"

    @property
    def default_severity(self) -> Severity:
        return Severity.LOW

    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]:
        return [
            self._create_finding(
                summary=f"Finding {i}",
                confidence=0.9,
            )
            for i in range(20)  # More than max_findings_per_rule
        ]

    def suggest_revision(self, finding, context):
        return None


class MockSlowRule(PlanValidationRule):
    """Mock rule with configurable delay for timing tests."""

    def __init__(self, delay_ms: float = 50.0, suffix: str = ""):
        super().__init__()
        self.delay_ms = delay_ms
        self.suffix = suffix

    @property
    def rule_id(self) -> str:
        return f"PLAN.MOCK_SLOW{self.suffix}"

    @property
    def name(self) -> str:
        return f"Mock Slow Rule {self.suffix}"

    @property
    def category(self) -> str:
        return "performance"

    @property
    def default_severity(self) -> Severity:
        return Severity.LOW

    @property
    def is_fast(self) -> bool:
        return False

    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]:
        time.sleep(self.delay_ms / 1000.0)  # Convert ms to seconds
        return [
            self._create_finding(
                summary=f"Slow finding {self.suffix}",
                confidence=0.9,
            )
        ]

    def suggest_revision(self, finding, context):
        return None


# --- Fixtures ---


@pytest.fixture
def sample_task() -> Task:
    """Create a sample task for testing."""
    return Task(
        id="TASK-0001",
        title="Implement feature",
        description="Add new feature",
        scope="components",
        priority=1,
        estimated_effort="medium",
        impact=0.8,
    )


@pytest.fixture
def sample_plan(sample_task: Task) -> ImplementationPlan:
    """Create a sample implementation plan."""
    return ImplementationPlan(
        groups=[
            TaskGroup(
                scope="components",
                description="Component updates",
                tasks=[sample_task],
            )
        ],
        quick_wins=[],
        summary="Test plan",
    )


@pytest.fixture
def sample_config() -> PlanGuardrailConfig:
    """Create a sample guardrail config."""
    return PlanGuardrailConfig(
        enabled=True,
        check_coverage=True,
        check_consistency=True,
        check_architecture=True,
        check_performance=True,
        max_findings_per_rule=10,
    )


@pytest.fixture
def sample_context(
    sample_plan: ImplementationPlan,
    sample_config: PlanGuardrailConfig,
) -> PlanValidationContext:
    """Create a sample validation context."""
    return PlanValidationContext(
        plan=sample_plan,
        config=sample_config,
    )


# --- Test Classes ---


class TestPlanGuardrailEngineConfig:
    """Tests for PlanGuardrailEngineConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = PlanGuardrailEngineConfig()
        assert config.fast_rule_timeout_ms == 100.0
        assert config.continue_on_error is True
        assert config.min_confidence == 0.7
        assert config.parallel_execution is False
        assert config.max_parallel_workers == 4

    def test_custom_values(self):
        """Test custom configuration values."""
        config = PlanGuardrailEngineConfig(
            fast_rule_timeout_ms=50.0,
            continue_on_error=False,
            min_confidence=0.5,
            parallel_execution=True,
            max_parallel_workers=8,
        )
        assert config.fast_rule_timeout_ms == 50.0
        assert config.continue_on_error is False
        assert config.min_confidence == 0.5
        assert config.parallel_execution is True
        assert config.max_parallel_workers == 8


class TestRuleExecutionResult:
    """Tests for RuleExecutionResult."""

    def test_basic_creation(self):
        """Test creating a basic result."""
        result = RuleExecutionResult(rule_id="TEST.RULE")
        assert result.rule_id == "TEST.RULE"
        assert result.findings == []
        assert result.execution_time_ms == 0.0
        assert result.error is None

    def test_with_findings(self):
        """Test result with findings."""
        finding = PlanValidationFinding(
            rule_id="TEST.RULE",
            severity=Severity.MEDIUM,
            summary="Test finding",
        )
        result = RuleExecutionResult(
            rule_id="TEST.RULE",
            findings=[finding],
            execution_time_ms=10.5,
        )
        assert len(result.findings) == 1
        assert result.execution_time_ms == 10.5

    def test_with_error(self):
        """Test result with error."""
        result = RuleExecutionResult(
            rule_id="TEST.RULE",
            error="Something went wrong",
        )
        assert result.error == "Something went wrong"


class TestPlanGuardrailResult:
    """Tests for PlanGuardrailResult."""

    def test_empty_result(self):
        """Test empty result properties."""
        result = PlanGuardrailResult()
        assert result.has_findings is False
        assert result.has_errors is False
        assert result.has_blocking_findings is False

    def test_has_findings(self):
        """Test has_findings property."""
        finding = PlanValidationFinding(
            rule_id="TEST.RULE",
            severity=Severity.LOW,
            summary="Test",
        )
        result = PlanGuardrailResult(findings=[finding])
        assert result.has_findings is True

    def test_has_errors(self):
        """Test has_errors property."""
        result = PlanGuardrailResult(errors=[("TEST.RULE", "Error")])
        assert result.has_errors is True

    def test_has_blocking_findings_with_high(self):
        """Test blocking with HIGH severity."""
        finding = PlanValidationFinding(
            rule_id="TEST.RULE",
            severity=Severity.HIGH,
            summary="High severity",
        )
        result = PlanGuardrailResult(findings=[finding])
        assert result.has_blocking_findings is True

    def test_has_blocking_findings_with_critical(self):
        """Test blocking with CRITICAL severity."""
        finding = PlanValidationFinding(
            rule_id="TEST.RULE",
            severity=Severity.CRITICAL,
            summary="Critical severity",
        )
        result = PlanGuardrailResult(findings=[finding])
        assert result.has_blocking_findings is True

    def test_no_blocking_with_medium(self):
        """Test no blocking with MEDIUM severity."""
        finding = PlanValidationFinding(
            rule_id="TEST.RULE",
            severity=Severity.MEDIUM,
            summary="Medium severity",
        )
        result = PlanGuardrailResult(findings=[finding])
        assert result.has_blocking_findings is False

    def test_findings_by_severity(self):
        """Test grouping findings by severity."""
        findings = [
            PlanValidationFinding(
                rule_id="R1",
                severity=Severity.HIGH,
                summary="High",
            ),
            PlanValidationFinding(
                rule_id="R2",
                severity=Severity.LOW,
                summary="Low",
            ),
            PlanValidationFinding(
                rule_id="R3",
                severity=Severity.HIGH,
                summary="High 2",
            ),
        ]
        result = PlanGuardrailResult(findings=findings)
        by_severity = result.findings_by_severity
        assert len(by_severity[Severity.HIGH]) == 2
        assert len(by_severity[Severity.LOW]) == 1

    def test_findings_by_category(self):
        """Test grouping findings by category."""
        coverage_rule = MockCoverageRule()
        consistency_rule = MockConsistencyRule()

        findings = [
            PlanValidationFinding(
                rule_id=coverage_rule.rule_id,
                severity=Severity.MEDIUM,
                summary="Coverage",
            ),
            PlanValidationFinding(
                rule_id=consistency_rule.rule_id,
                severity=Severity.HIGH,
                summary="Consistency",
            ),
        ]

        rules = {
            coverage_rule.rule_id: coverage_rule,
            consistency_rule.rule_id: consistency_rule,
        }

        result = PlanGuardrailResult(findings=findings)
        by_category = result.findings_by_category(rules)
        assert "coverage" in by_category
        assert "consistency" in by_category
        assert len(by_category["coverage"]) == 1
        assert len(by_category["consistency"]) == 1

    def test_to_dict(self):
        """Test dictionary serialization."""
        finding = PlanValidationFinding(
            rule_id="TEST.RULE",
            severity=Severity.MEDIUM,
            summary="Test",
        )
        result = PlanGuardrailResult(
            findings=[finding],
            rules_executed=3,
            rules_skipped=1,
            execution_time_ms=25.5,
            errors=[("ERR.RULE", "Error message")],
        )
        data = result.to_dict()
        assert len(data["findings"]) == 1
        assert data["rules_executed"] == 3
        assert data["rules_skipped"] == 1
        assert data["execution_time_ms"] == 25.5
        assert len(data["errors"]) == 1
        assert data["errors"][0]["rule_id"] == "ERR.RULE"
        assert data["has_blocking_findings"] is False


class TestPlanGuardrailEngine:
    """Tests for PlanGuardrailEngine."""

    def test_initialization(self, sample_config: PlanGuardrailConfig):
        """Test engine initialization."""
        engine = PlanGuardrailEngine(sample_config)
        assert engine.config == sample_config
        assert engine.rule_count == 0

    def test_initialization_with_engine_config(
        self, sample_config: PlanGuardrailConfig
    ):
        """Test engine initialization with custom engine config."""
        engine_config = PlanGuardrailEngineConfig(min_confidence=0.5)
        engine = PlanGuardrailEngine(sample_config, engine_config)
        assert engine.engine_config.min_confidence == 0.5

    def test_register_rule(self, sample_config: PlanGuardrailConfig):
        """Test registering a rule."""
        engine = PlanGuardrailEngine(sample_config)
        rule = MockCoverageRule()
        engine.register(rule)
        assert engine.rule_count == 1
        assert engine.get_rule(rule.rule_id) is rule

    def test_register_duplicate_raises(self, sample_config: PlanGuardrailConfig):
        """Test registering duplicate rule raises error."""
        engine = PlanGuardrailEngine(sample_config)
        rule = MockCoverageRule()
        engine.register(rule)
        with pytest.raises(ValueError, match="already registered"):
            engine.register(rule)

    def test_unregister_rule(self, sample_config: PlanGuardrailConfig):
        """Test unregistering a rule."""
        engine = PlanGuardrailEngine(sample_config)
        rule = MockCoverageRule()
        engine.register(rule)
        assert engine.unregister(rule.rule_id) is True
        assert engine.rule_count == 0
        assert engine.get_rule(rule.rule_id) is None

    def test_unregister_nonexistent(self, sample_config: PlanGuardrailConfig):
        """Test unregistering nonexistent rule returns False."""
        engine = PlanGuardrailEngine(sample_config)
        assert engine.unregister("NONEXISTENT") is False

    def test_get_rule_nonexistent(self, sample_config: PlanGuardrailConfig):
        """Test getting nonexistent rule returns None."""
        engine = PlanGuardrailEngine(sample_config)
        assert engine.get_rule("NONEXISTENT") is None

    def test_get_rules_by_category(self, sample_config: PlanGuardrailConfig):
        """Test getting rules by category."""
        engine = PlanGuardrailEngine(sample_config)
        coverage_rule = MockCoverageRule()
        consistency_rule = MockConsistencyRule()
        engine.register(coverage_rule)
        engine.register(consistency_rule)

        coverage_rules = engine.get_rules_by_category("coverage")
        assert len(coverage_rules) == 1
        assert coverage_rules[0].rule_id == coverage_rule.rule_id

        consistency_rules = engine.get_rules_by_category("consistency")
        assert len(consistency_rules) == 1

    def test_get_rules_by_category_empty(self, sample_config: PlanGuardrailConfig):
        """Test getting rules from empty category."""
        engine = PlanGuardrailEngine(sample_config)
        assert engine.get_rules_by_category("nonexistent") == []

    def test_get_fast_rules(self, sample_config: PlanGuardrailConfig):
        """Test getting fast rules only."""
        engine = PlanGuardrailEngine(sample_config)
        fast_rule = MockCoverageRule()  # is_fast = True
        slow_rule = MockConsistencyRule()  # is_fast = False
        engine.register(fast_rule)
        engine.register(slow_rule)

        fast_rules = engine.get_fast_rules()
        assert len(fast_rules) == 1
        assert fast_rules[0].is_fast is True

    def test_get_all_rules(self, sample_config: PlanGuardrailConfig):
        """Test getting all rules."""
        engine = PlanGuardrailEngine(sample_config)
        engine.register(MockCoverageRule())
        engine.register(MockConsistencyRule())
        assert len(engine.get_all_rules()) == 2

    def test_validate_returns_result(
        self,
        sample_config: PlanGuardrailConfig,
        sample_context: PlanValidationContext,
    ):
        """Test validate returns PlanGuardrailResult."""
        engine = PlanGuardrailEngine(sample_config)
        engine.register(MockCoverageRule())

        result = engine.validate(sample_context)
        assert isinstance(result, PlanGuardrailResult)
        assert result.rules_executed == 1
        assert len(result.findings) == 1

    def test_validate_with_rule_ids(
        self,
        sample_config: PlanGuardrailConfig,
        sample_context: PlanValidationContext,
    ):
        """Test validate with specific rule IDs."""
        engine = PlanGuardrailEngine(sample_config)
        coverage_rule = MockCoverageRule()
        consistency_rule = MockConsistencyRule()
        engine.register(coverage_rule)
        engine.register(consistency_rule)

        result = engine.validate(sample_context, rule_ids=[coverage_rule.rule_id])
        assert result.rules_executed == 1
        assert result.findings[0].rule_id == coverage_rule.rule_id

    def test_validate_skips_disabled_rules(
        self,
        sample_context: PlanValidationContext,
    ):
        """Test validate skips disabled rules."""
        config = PlanGuardrailConfig(
            enabled=True,
            check_coverage=False,  # Disable coverage
            check_consistency=True,
        )
        context = PlanValidationContext(
            plan=sample_context.plan,
            config=config,
        )
        engine = PlanGuardrailEngine(config)
        engine.register(MockCoverageRule())  # coverage category
        engine.register(MockConsistencyRule())  # consistency category

        result = engine.validate(context)
        assert result.rules_executed == 1
        assert result.rules_skipped == 1

    def test_validate_filters_low_confidence(
        self,
        sample_config: PlanGuardrailConfig,
        sample_context: PlanValidationContext,
    ):
        """Test validate filters low confidence findings."""
        engine = PlanGuardrailEngine(sample_config)
        engine.register(MockLowConfidenceRule())  # 0.3 confidence

        result = engine.validate(sample_context)
        assert result.rules_executed == 1
        assert len(result.findings) == 0  # Filtered out

    def test_validate_respects_max_findings(
        self,
        sample_context: PlanValidationContext,
    ):
        """Test validate respects max_findings_per_rule."""
        config = PlanGuardrailConfig(
            enabled=True,
            max_findings_per_rule=5,
        )
        context = PlanValidationContext(
            plan=sample_context.plan,
            config=config,
        )
        engine = PlanGuardrailEngine(config)
        engine.register(MockManyFindingsRule())  # Produces 20 findings

        result = engine.validate(context)
        assert len(result.findings) == 5  # Limited to max

    def test_validate_handles_errors(
        self,
        sample_config: PlanGuardrailConfig,
        sample_context: PlanValidationContext,
    ):
        """Test validate handles rule errors gracefully."""
        engine = PlanGuardrailEngine(sample_config)
        engine.register(MockErrorRule())

        result = engine.validate(sample_context)
        assert result.rules_executed == 1
        assert len(result.errors) == 1
        assert "Mock rule error" in result.errors[0][1]

    def test_validate_raises_when_continue_on_error_false(
        self,
        sample_config: PlanGuardrailConfig,
        sample_context: PlanValidationContext,
    ):
        """Test validate raises when continue_on_error is False."""
        engine_config = PlanGuardrailEngineConfig(continue_on_error=False)
        engine = PlanGuardrailEngine(sample_config, engine_config)
        engine.register(MockErrorRule())

        with pytest.raises(RuntimeError, match="Mock rule error"):
            engine.validate(sample_context)

    def test_validate_fast(
        self,
        sample_config: PlanGuardrailConfig,
        sample_context: PlanValidationContext,
    ):
        """Test validate_fast runs only fast rules."""
        engine = PlanGuardrailEngine(sample_config)
        fast_rule = MockCoverageRule()  # is_fast = True
        slow_rule = MockConsistencyRule()  # is_fast = False
        engine.register(fast_rule)
        engine.register(slow_rule)

        result = engine.validate_fast(sample_context)
        assert result.rules_executed == 1
        assert result.findings[0].rule_id == fast_rule.rule_id

    def test_validate_category(
        self,
        sample_config: PlanGuardrailConfig,
        sample_context: PlanValidationContext,
    ):
        """Test validate_category runs only category rules."""
        engine = PlanGuardrailEngine(sample_config)
        engine.register(MockCoverageRule())  # coverage
        engine.register(MockConsistencyRule())  # consistency

        result = engine.validate_category(sample_context, "coverage")
        assert result.rules_executed == 1
        assert result.findings[0].rule_id == "PLAN.MOCK_COVERAGE"

    def test_timing_recorded(
        self,
        sample_config: PlanGuardrailConfig,
        sample_context: PlanValidationContext,
    ):
        """Test execution time is recorded."""
        engine = PlanGuardrailEngine(sample_config)
        engine.register(MockCoverageRule())

        result = engine.validate(sample_context)
        assert result.execution_time_ms > 0


class TestDiscoverRules:
    """Tests for rule discovery functionality."""

    def test_discover_rules_empty_dir(self, sample_config: PlanGuardrailConfig):
        """Test discovery with empty directory."""
        engine = PlanGuardrailEngine(sample_config)
        with tempfile.TemporaryDirectory() as tmpdir:
            discovered = engine.discover_rules(Path(tmpdir))
        assert discovered == 0

    def test_discover_rules_nonexistent_dir(self, sample_config: PlanGuardrailConfig):
        """Test discovery with nonexistent directory."""
        engine = PlanGuardrailEngine(sample_config)
        discovered = engine.discover_rules(Path("/nonexistent/path"))
        assert discovered == 0

    def test_discover_rules_skips_init_files(self, sample_config: PlanGuardrailConfig):
        """Test discovery skips __init__.py files."""
        engine = PlanGuardrailEngine(sample_config)
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create __init__.py (should be skipped)
            init_file = Path(tmpdir) / "__init__.py"
            init_file.write_text("# init")
            discovered = engine.discover_rules(Path(tmpdir))
        assert discovered == 0

    def test_discover_rules_finds_valid_rule(self, sample_config: PlanGuardrailConfig):
        """Test discovery finds valid rule classes."""
        engine = PlanGuardrailEngine(sample_config)
        with tempfile.TemporaryDirectory() as tmpdir:
            rule_file = Path(tmpdir) / "test_rule.py"
            rule_file.write_text(
                """
from claude_indexer.rules.base import Severity
from claude_indexer.ui.plan.guardrails.base import (
    PlanValidationContext,
    PlanValidationFinding,
    PlanValidationRule,
)

class DiscoveredRule(PlanValidationRule):
    @property
    def rule_id(self):
        return "PLAN.DISCOVERED"

    @property
    def name(self):
        return "Discovered Rule"

    @property
    def category(self):
        return "coverage"

    @property
    def default_severity(self):
        return Severity.LOW

    def validate(self, context):
        return []

    def suggest_revision(self, finding, context):
        return None
"""
            )
            discovered = engine.discover_rules(Path(tmpdir))
        assert discovered == 1
        assert engine.get_rule("PLAN.DISCOVERED") is not None


class TestCreateGuardrailEngine:
    """Tests for create_guardrail_engine factory function."""

    def test_creates_engine(self, sample_config: PlanGuardrailConfig):
        """Test factory creates engine."""
        engine = create_guardrail_engine(sample_config, discover_rules=False)
        assert isinstance(engine, PlanGuardrailEngine)
        assert engine.rule_count == 0

    def test_with_discover_rules(self, sample_config: PlanGuardrailConfig):
        """Test factory with rule discovery."""
        # Default rules_dir doesn't exist yet, so discovery returns 0
        engine = create_guardrail_engine(sample_config, discover_rules=True)
        assert isinstance(engine, PlanGuardrailEngine)

    def test_with_custom_rules_dir(self, sample_config: PlanGuardrailConfig):
        """Test factory with custom rules directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = create_guardrail_engine(
                sample_config,
                discover_rules=True,
                rules_dir=Path(tmpdir),
            )
        assert isinstance(engine, PlanGuardrailEngine)


class TestParallelExecution:
    """Tests for parallel rule execution (Milestone 9.2.3)."""

    def test_parallel_disabled_by_default(
        self,
        sample_config: PlanGuardrailConfig,
    ):
        """Test parallel execution is disabled by default."""
        engine = PlanGuardrailEngine(sample_config)
        assert engine.engine_config.parallel_execution is False

    def test_parallel_execution_same_results(
        self,
        sample_config: PlanGuardrailConfig,
        sample_context: PlanValidationContext,
    ):
        """Test parallel execution produces same findings as sequential."""
        # Sequential execution
        engine_seq = PlanGuardrailEngine(sample_config)
        engine_seq.register(MockCoverageRule())
        engine_seq.register(MockConsistencyRule())
        result_seq = engine_seq.validate(sample_context)

        # Parallel execution
        engine_config = PlanGuardrailEngineConfig(parallel_execution=True)
        engine_par = PlanGuardrailEngine(sample_config, engine_config)
        engine_par.register(MockCoverageRule())
        engine_par.register(MockConsistencyRule())
        result_par = engine_par.validate(sample_context)

        # Same findings count
        assert result_seq.rules_executed == result_par.rules_executed
        assert len(result_seq.findings) == len(result_par.findings)
        assert result_seq.rules_skipped == result_par.rules_skipped

        # Same finding rule IDs (order may differ)
        seq_rule_ids = {f.rule_id for f in result_seq.findings}
        par_rule_ids = {f.rule_id for f in result_par.findings}
        assert seq_rule_ids == par_rule_ids

    def test_parallel_error_handling(
        self,
        sample_config: PlanGuardrailConfig,
        sample_context: PlanValidationContext,
    ):
        """Test error handling in parallel mode."""
        engine_config = PlanGuardrailEngineConfig(parallel_execution=True)
        engine = PlanGuardrailEngine(sample_config, engine_config)
        engine.register(MockCoverageRule())
        engine.register(MockErrorRule())

        result = engine.validate(sample_context)
        assert result.rules_executed == 2
        assert len(result.errors) == 1
        assert "Mock rule error" in result.errors[0][1]
        # Coverage rule findings should still be present
        assert len(result.findings) == 1

    def test_parallel_with_empty_rules(
        self,
        sample_config: PlanGuardrailConfig,
        sample_context: PlanValidationContext,
    ):
        """Test parallel execution with no rules."""
        engine_config = PlanGuardrailEngineConfig(parallel_execution=True)
        engine = PlanGuardrailEngine(sample_config, engine_config)

        result = engine.validate(sample_context)
        assert result.rules_executed == 0
        assert result.rules_skipped == 0
        assert len(result.findings) == 0

    def test_parallel_max_workers_config(self):
        """Test max_parallel_workers configuration."""
        config = PlanGuardrailEngineConfig(
            parallel_execution=True,
            max_parallel_workers=2,
        )
        assert config.max_parallel_workers == 2

    def test_parallel_faster_with_slow_rules(
        self,
        sample_config: PlanGuardrailConfig,
        sample_context: PlanValidationContext,
    ):
        """Test parallel is faster than sequential with slow rules."""
        delay_ms = 50.0  # 50ms delay per rule

        # Sequential execution with 3 slow rules
        engine_seq = PlanGuardrailEngine(sample_config)
        engine_seq.register(MockSlowRule(delay_ms=delay_ms, suffix="_1"))
        engine_seq.register(MockSlowRule(delay_ms=delay_ms, suffix="_2"))
        engine_seq.register(MockSlowRule(delay_ms=delay_ms, suffix="_3"))

        start_seq = time.perf_counter()
        result_seq = engine_seq.validate(sample_context)
        time_seq = (time.perf_counter() - start_seq) * 1000

        # Parallel execution with 3 slow rules
        engine_config = PlanGuardrailEngineConfig(
            parallel_execution=True, max_parallel_workers=3
        )
        engine_par = PlanGuardrailEngine(sample_config, engine_config)
        engine_par.register(MockSlowRule(delay_ms=delay_ms, suffix="_1"))
        engine_par.register(MockSlowRule(delay_ms=delay_ms, suffix="_2"))
        engine_par.register(MockSlowRule(delay_ms=delay_ms, suffix="_3"))

        start_par = time.perf_counter()
        result_par = engine_par.validate(sample_context)
        time_par = (time.perf_counter() - start_par) * 1000

        # Both should execute same number of rules
        assert result_seq.rules_executed == 3
        assert result_par.rules_executed == 3

        # Sequential should take ~3x the delay (150ms+)
        # Parallel should take ~1x the delay (50ms+)
        # Allow some margin for overhead
        assert time_seq >= delay_ms * 2.5, f"Sequential took {time_seq}ms"
        assert (
            time_par < time_seq * 0.8
        ), f"Parallel ({time_par}ms) not faster than seq ({time_seq}ms)"

    def test_parallel_skips_disabled_rules(
        self,
        sample_context: PlanValidationContext,
    ):
        """Test parallel execution skips disabled rules."""
        config = PlanGuardrailConfig(
            enabled=True,
            check_coverage=False,  # Disable coverage
            check_consistency=True,
        )
        context = PlanValidationContext(
            plan=sample_context.plan,
            config=config,
        )
        engine_config = PlanGuardrailEngineConfig(parallel_execution=True)
        engine = PlanGuardrailEngine(config, engine_config)
        engine.register(MockCoverageRule())  # coverage category - disabled
        engine.register(MockConsistencyRule())  # consistency category - enabled

        result = engine.validate(context)
        assert result.rules_executed == 1
        assert result.rules_skipped == 1

    def test_parallel_filters_low_confidence(
        self,
        sample_config: PlanGuardrailConfig,
        sample_context: PlanValidationContext,
    ):
        """Test parallel execution filters low confidence findings."""
        engine_config = PlanGuardrailEngineConfig(parallel_execution=True)
        engine = PlanGuardrailEngine(sample_config, engine_config)
        engine.register(MockLowConfidenceRule())  # 0.3 confidence

        result = engine.validate(sample_context)
        assert result.rules_executed == 1
        assert len(result.findings) == 0  # Filtered out
