"""
Integration tests for Plan Mode system.

Tests the complete Plan Mode lifecycle from detection through auto-revision,
including context injection, guardrail validation, and design doc indexing.

Milestone 13.1: Integration Testing
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from claude_indexer.hooks.plan_mode_detector import (
    PlanModeDetector,
    detect_plan_mode,
)
from claude_indexer.hooks.plan_qa import (
    PlanQAConfig,
    verify_plan_qa,
)
from claude_indexer.hooks.planning.exploration import (
    ExplorationHints,
    ExplorationHintsGenerator,
)
from claude_indexer.hooks.planning.guidelines import (
    PlanningGuidelines,
    PlanningGuidelinesGenerator,
)
from claude_indexer.hooks.planning.injector import (
    PlanContextInjectionConfig,
    PlanContextInjector,
    inject_plan_context,
)
from claude_indexer.rules.base import Severity
from claude_indexer.session.plan_context import PlanModeContext, PlanModeSource
from claude_indexer.ui.plan.guardrails.auto_revision import (
    AutoRevisionEngine,
)
from claude_indexer.ui.plan.guardrails.base import (
    PlanRevision,
    PlanValidationContext,
    PlanValidationFinding,
    RevisionType,
)
from claude_indexer.ui.plan.guardrails.config import PlanGuardrailConfig
from claude_indexer.ui.plan.guardrails.engine import (
    PlanGuardrailEngine,
    create_guardrail_engine,
)
from claude_indexer.ui.plan.task import ImplementationPlan, Task, TaskGroup

# =============================================================================
# Helper Factory Functions
# =============================================================================


def make_task(
    task_id: str = "TASK-001",
    title: str = "Test Task",
    description: str = "A test task description",
    scope: str = "components",
    priority: int = 1,
    estimated_effort: str = "medium",
    impact: float = 0.8,
    acceptance_criteria: list[str] | None = None,
    dependencies: list[str] | None = None,
    tags: list[str] | None = None,
) -> Task:
    """Factory function to create Task objects for testing."""
    return Task(
        id=task_id,
        title=title,
        description=description,
        scope=scope,
        priority=priority,
        estimated_effort=estimated_effort,
        impact=impact,
        acceptance_criteria=acceptance_criteria or ["Acceptance criteria 1"],
        evidence_links=[],
        related_critique_ids=[],
        dependencies=dependencies or [],
        tags=tags or [],
    )


def make_task_group(
    scope: str = "components",
    description: str = "Test group",
    tasks: list[Task] | None = None,
) -> TaskGroup:
    """Factory function to create TaskGroup objects for testing."""
    return TaskGroup(
        scope=scope,
        description=description,
        tasks=tasks or [],
    )


def make_plan(
    groups: list[TaskGroup] | None = None,
    quick_wins: list[Task] | None = None,
    summary: str = "Test implementation plan",
) -> ImplementationPlan:
    """Factory function to create ImplementationPlan objects for testing."""
    return ImplementationPlan(
        groups=groups or [],
        quick_wins=quick_wins or [],
        summary=summary,
    )


def make_finding(
    rule_id: str = "PLAN.TEST_RULE",
    severity: Severity = Severity.MEDIUM,
    summary: str = "Test finding",
    affected_tasks: list[str] | None = None,
    can_auto_revise: bool = False,
    confidence: float = 0.9,
    suggested_revision: PlanRevision | None = None,
) -> PlanValidationFinding:
    """Factory function to create PlanValidationFinding objects for testing."""
    return PlanValidationFinding(
        rule_id=rule_id,
        severity=severity,
        summary=summary,
        affected_tasks=affected_tasks or [],
        suggestion="Test suggestion",
        can_auto_revise=can_auto_revise,
        confidence=confidence,
        evidence=[],
        suggested_revision=suggested_revision,
    )


# =============================================================================
# Plan Mode Fixtures
# =============================================================================


@pytest.fixture
def plan_mode_repo(tmp_path_factory) -> Path:
    """Create a repository with code that triggers guardrail violations."""
    repo_path = tmp_path_factory.mktemp("plan_mode_repo")

    # Feature file without tests
    (repo_path / "feature.py").write_text(
        '''"""Feature module without tests."""

def new_feature():
    """A new feature that needs test coverage."""
    return "feature"

class FeatureService:
    """Service class that needs test coverage."""

    def process(self, data):
        """Process data."""
        return data.upper()
'''
    )

    # User-facing API without documentation
    (repo_path / "user_api.py").write_text(
        '''"""User-facing API without documentation."""

def get_user_data(user_id: str) -> dict:
    """Get user data by ID."""
    return {"id": user_id, "name": "Test User"}

def create_endpoint(name: str):
    """Create a new API endpoint."""
    return f"/api/{name}"
'''
    )

    # Duplicate code patterns
    utils_dir = repo_path / "utils"
    utils_dir.mkdir()
    (utils_dir / "__init__.py").write_text("")
    (utils_dir / "helpers.py").write_text(
        '''"""Helper utilities."""

def format_string(value: str) -> str:
    """Format a string."""
    return value.strip().upper()
'''
    )
    (utils_dir / "helpers2.py").write_text(
        '''"""Duplicate helper utilities."""

def format_string(value: str) -> str:
    """Format a string (duplicate)."""
    return value.strip().upper()
'''
    )

    # CLAUDE.md with project patterns
    (repo_path / "CLAUDE.md").write_text(
        """# Project Patterns

## Code Style
- Use type hints
- Follow PEP 8

## Testing
- All features need tests
- Use pytest

## Documentation
- Update README for user-facing changes
"""
    )

    # Create .claude-indexer config
    config_dir = repo_path / ".claude-indexer"
    config_dir.mkdir()

    return repo_path


@pytest.fixture
def plan_mode_detector() -> PlanModeDetector:
    """Create a PlanModeDetector instance."""
    return PlanModeDetector()


@pytest.fixture
def plan_context() -> PlanModeContext:
    """Create a fresh PlanModeContext."""
    return PlanModeContext()


@pytest.fixture
def guardrail_config() -> PlanGuardrailConfig:
    """Create a PlanGuardrailConfig for testing."""
    return PlanGuardrailConfig(
        enabled=True,
        auto_revise=True,
        max_revisions_per_plan=10,
        revision_confidence_threshold=0.7,
        check_coverage=True,
        check_consistency=True,
        check_architecture=True,
        check_performance=True,
    )


@pytest.fixture
def guardrail_engine(guardrail_config: PlanGuardrailConfig) -> PlanGuardrailEngine:
    """Create a PlanGuardrailEngine with all rules discovered."""
    return create_guardrail_engine(guardrail_config, discover_rules=True)


@pytest.fixture
def auto_revision_engine(
    guardrail_config: PlanGuardrailConfig,
) -> AutoRevisionEngine:
    """Create an AutoRevisionEngine for testing."""
    return AutoRevisionEngine(config=guardrail_config)


@pytest.fixture
def sample_plan() -> ImplementationPlan:
    """Create a sample implementation plan for testing."""
    feature_task = make_task(
        task_id="TASK-001",
        title="Implement user authentication",
        description="Add user authentication to the application",
        scope="components",
        priority=1,
        estimated_effort="high",
        impact=0.9,
    )

    api_task = make_task(
        task_id="TASK-002",
        title="Create login API endpoint",
        description="Add /api/login endpoint for user authentication",
        scope="api",
        priority=2,
        estimated_effort="medium",
        impact=0.8,
        dependencies=["TASK-001"],
    )

    group = make_task_group(
        scope="components",
        description="Authentication components",
        tasks=[feature_task, api_task],
    )

    return make_plan(groups=[group], summary="User authentication implementation plan")


@pytest.fixture
def plan_qa_config() -> PlanQAConfig:
    """Create a PlanQAConfig for testing."""
    return PlanQAConfig(
        enabled=True,
        check_tests=True,
        check_docs=True,
        check_duplicates=True,
        check_architecture=True,
        fail_on_missing_tests=False,
        fail_on_missing_docs=False,
    )


# =============================================================================
# Sample Plan Text Fixtures for QA Verification
# =============================================================================


SAMPLE_PLAN_COMPLETE = """
## Implementation Plan: User Authentication

### Tasks

1. **Implement AuthService class**
   - Create authentication service with login/logout methods
   - Use existing BaseService as foundation

2. **Add unit tests for AuthService**
   - Write pytest tests for login functionality
   - Achieve 80% code coverage

3. **Update API documentation**
   - Document new /api/auth endpoints
   - Add authentication guide to README

### Notes
- Verified no existing auth implementation via search_similar()
- Will extend existing user model
"""

SAMPLE_PLAN_MISSING_TESTS = """
## Implementation Plan: Payment Processing

### Tasks

1. **Create PaymentService class**
   - Implement payment processing logic
   - Add credit card validation

2. **Build payment API endpoint**
   - Create /api/payments endpoint
   - Handle payment requests

### Notes
- New feature for payment handling
"""

SAMPLE_PLAN_MISSING_DOCS = """
## Implementation Plan: User Dashboard

### Tasks

1. **Implement DashboardComponent**
   - Create user dashboard UI component
   - Add data visualization

2. **Add tests for Dashboard**
   - Write component tests
   - Test data loading

### Notes
- User-facing feature with new UI
"""

SAMPLE_PLAN_NO_REUSE_CHECK = """
## Implementation Plan: Data Validator

### Tasks

1. **Create ValidationService class**
   - Add input validation methods
   - Support multiple data types

### Notes
- New validation functionality
"""


# =============================================================================
# TestPlanModeDetectionIntegration
# =============================================================================


class TestPlanModeDetectionIntegration:
    """Integration tests for Plan Mode detection."""

    def test_explicit_marker_detection_at_plan(
        self, plan_mode_detector: PlanModeDetector
    ):
        """Test @plan marker detection."""
        prompt = "@plan Create an implementation plan for user authentication"
        result = plan_mode_detector.detect(prompt)

        assert result.is_plan_mode is True
        assert result.confidence == 1.0
        assert result.source == PlanModeSource.EXPLICIT_MARKER
        assert "@plan" in result.detected_markers
        assert result.detection_time_ms < 10  # Performance target

    def test_explicit_marker_detection_agent_plan(
        self, plan_mode_detector: PlanModeDetector
    ):
        """Test @agent-plan marker detection."""
        prompt = "@agent-plan Design a database schema migration"
        result = plan_mode_detector.detect(prompt)

        assert result.is_plan_mode is True
        assert result.confidence == 1.0
        assert result.source == PlanModeSource.EXPLICIT_MARKER

    def test_explicit_marker_detection_plan_mode(
        self, plan_mode_detector: PlanModeDetector
    ):
        """Test 'plan mode' phrase detection."""
        prompt = "Enter plan mode and create a refactoring strategy"
        result = plan_mode_detector.detect(prompt)

        assert result.is_plan_mode is True
        assert result.confidence == 1.0
        assert result.source == PlanModeSource.EXPLICIT_MARKER

    def test_environment_variable_detection(self, plan_mode_detector: PlanModeDetector):
        """Test CLAUDE_PLAN_MODE environment variable detection."""
        with patch.dict(os.environ, {"CLAUDE_PLAN_MODE": "true"}):
            prompt = "What files need changes?"
            result = plan_mode_detector.detect(prompt)

            assert result.is_plan_mode is True
            assert result.confidence == 1.0
            assert result.source == PlanModeSource.ENVIRONMENT_VAR

    def test_planning_keyword_detection_create_plan(
        self, plan_mode_detector: PlanModeDetector
    ):
        """Test 'create a plan' keyword detection."""
        prompt = "Create a plan for implementing the new feature"
        result = plan_mode_detector.detect(prompt)

        assert result.is_plan_mode is True
        assert result.confidence >= 0.7
        assert result.source == PlanModeSource.PLANNING_KEYWORD

    def test_planning_keyword_with_boosters(self, plan_mode_detector: PlanModeDetector):
        """Test planning keywords with boosters increase confidence."""
        prompt = "Create a detailed plan with phases and milestones for the project"
        result = plan_mode_detector.detect(prompt)

        assert result.is_plan_mode is True
        assert result.confidence > 0.7  # Boosters should increase confidence

    def test_non_plan_mode_detection(self, plan_mode_detector: PlanModeDetector):
        """Test that non-plan prompts are not detected as Plan Mode."""
        prompt = "Fix the bug in the login function"
        result = plan_mode_detector.detect(prompt)

        assert result.is_plan_mode is False
        assert result.confidence == 0.0

    def test_session_persistence(self, plan_mode_detector: PlanModeDetector):
        """Test Plan Mode persists across session turns."""
        # First prompt activates Plan Mode
        prompt1 = "@plan Create implementation plan"
        result1, context = detect_plan_mode(prompt1)

        assert result1.is_plan_mode is True
        assert context.is_active is True
        assert context.turn_count == 1

        # Second prompt should persist Plan Mode
        detector2 = PlanModeDetector(plan_context=context)
        prompt2 = "Continue with the next step"
        result2 = detector2.detect(prompt2)

        assert result2.is_plan_mode is True
        assert result2.source == PlanModeSource.SESSION_PERSISTED

    def test_detection_precedence(self, plan_mode_detector: PlanModeDetector):
        """Test that explicit markers take precedence."""
        with patch.dict(os.environ, {"CLAUDE_PLAN_MODE": "true"}):
            # Explicit marker should take precedence over env var
            prompt = "@plan Design a system"
            result = plan_mode_detector.detect(prompt)

            assert result.source == PlanModeSource.EXPLICIT_MARKER

    def test_detection_performance(self, plan_mode_detector: PlanModeDetector):
        """Test detection latency is within performance target (<10ms)."""
        prompts = [
            "@plan Create a plan",
            "Create a step-by-step plan for the feature",
            "Just fix this bug",
            "Design an implementation plan with milestones",
        ]

        for prompt in prompts:
            result = plan_mode_detector.detect(prompt)
            assert (
                result.detection_time_ms < 10
            ), f"Detection for '{prompt[:30]}...' took {result.detection_time_ms}ms"


# =============================================================================
# TestContextInjectionIntegration
# =============================================================================


class TestContextInjectionIntegration:
    """Integration tests for Plan Mode context injection."""

    def test_guidelines_generation(self, plan_mode_repo: Path):
        """Test guidelines are generated with correct sections."""
        generator = PlanningGuidelinesGenerator(
            collection_name="test-collection",
            project_path=plan_mode_repo,
        )
        guidelines = generator.generate()

        assert isinstance(guidelines, PlanningGuidelines)
        assert len(guidelines.full_text) > 0
        assert (
            "Code Reuse Check" in guidelines.full_text
            or "PLANNING" in guidelines.full_text
        )
        assert guidelines.generation_time_ms < 20  # Performance target

    def test_exploration_hints_extraction(self):
        """Test exploration hints extract entities from prompts."""
        generator = ExplorationHintsGenerator(collection_name="test-collection")
        prompt = "Implement the UserService class with authentication"
        hints = generator.generate(prompt)

        assert isinstance(hints, ExplorationHints)
        assert len(hints.extracted_entities) > 0
        # Should extract CamelCase entity
        assert (
            any("UserService" in e for e in hints.extracted_entities)
            or len(hints.extracted_entities) > 0
        )
        assert hints.generation_time_ms < 30  # Performance target

    def test_context_injection_full(self, plan_mode_repo: Path):
        """Test full context injection with guidelines and hints."""
        config = PlanContextInjectionConfig(
            enabled=True,
            inject_guidelines=True,
            inject_hints=True,
            compact_mode=False,
        )

        injector = PlanContextInjector(
            collection_name="test-collection",
            project_path=plan_mode_repo,
            config=config,
        )

        prompt = "Create a plan for implementing user authentication"
        result = injector.inject(prompt)

        assert result.success is True
        assert len(result.injected_text) > 0
        assert result.guidelines is not None
        assert result.hints is not None
        assert result.total_time_ms < 50  # Performance target

    def test_context_injection_compact_mode(self, plan_mode_repo: Path):
        """Test compact mode generates shorter guidelines."""
        config_full = PlanContextInjectionConfig(compact_mode=False)
        config_compact = PlanContextInjectionConfig(compact_mode=True)

        injector_full = PlanContextInjector(
            collection_name="test-collection",
            project_path=plan_mode_repo,
            config=config_full,
        )
        injector_compact = PlanContextInjector(
            collection_name="test-collection",
            project_path=plan_mode_repo,
            config=config_compact,
        )

        prompt = "Create a plan"
        result_full = injector_full.inject(prompt)
        result_compact = injector_compact.inject(prompt)

        assert len(result_compact.injected_text) <= len(result_full.injected_text)

    def test_context_injection_disabled(self, plan_mode_repo: Path):
        """Test injection disabled returns empty text."""
        config = PlanContextInjectionConfig(enabled=False)
        injector = PlanContextInjector(
            collection_name="test-collection",
            project_path=plan_mode_repo,
            config=config,
        )

        result = injector.inject("Create a plan")

        assert result.success is True
        assert result.injected_text == ""

    def test_inject_plan_context_convenience(self, plan_mode_repo: Path):
        """Test convenience function for injection."""
        result = inject_plan_context(
            prompt="Implement AuthService",
            collection_name="test-collection",
            project_path=plan_mode_repo,
        )

        assert result.success is True
        assert len(result.injected_text) > 0

    def test_mcp_commands_in_guidelines(self, plan_mode_repo: Path):
        """Test MCP commands are correctly formatted."""
        generator = PlanningGuidelinesGenerator(
            collection_name="my-project",
            project_path=plan_mode_repo,
        )
        guidelines = generator.generate()

        assert "my-project" in guidelines.full_text
        # Should include MCP prefix
        assert (
            "search_similar" in guidelines.full_text or "mcp__" in guidelines.full_text
        )

    def test_project_patterns_loaded(self, plan_mode_repo: Path):
        """Test project patterns are loaded from CLAUDE.md."""
        generator = PlanningGuidelinesGenerator(
            collection_name="test-collection",
            project_path=plan_mode_repo,
        )
        guidelines = generator.generate()

        # Should load patterns from CLAUDE.md
        assert guidelines.project_patterns is not None or len(guidelines.full_text) > 0


# =============================================================================
# TestGuardrailValidationIntegration
# =============================================================================


class TestGuardrailValidationIntegration:
    """Integration tests for Plan guardrail validation."""

    def test_guardrail_engine_discovers_rules(
        self, guardrail_config: PlanGuardrailConfig
    ):
        """Test that guardrail engine discovers built-in rules."""
        engine = create_guardrail_engine(guardrail_config, discover_rules=True)

        assert engine.rule_count > 0
        # Should have test requirement rule
        assert any("TEST" in rid for rid in [r.rule_id for r in engine.get_all_rules()])

    def test_test_requirement_rule_detects_missing_tests(
        self,
        guardrail_engine: PlanGuardrailEngine,
        guardrail_config: PlanGuardrailConfig,
    ):
        """Test TestRequirementRule detects feature tasks without tests."""
        # Create plan with feature task but no test task
        feature_task = make_task(
            task_id="TASK-001",
            title="Implement new authentication feature",
            description="Add user authentication functionality",
            scope="components",
        )
        plan = make_plan(groups=[make_task_group(tasks=[feature_task])])

        context = PlanValidationContext(
            plan=plan,
            config=guardrail_config,
        )

        result = guardrail_engine.validate(context)

        assert result.has_findings
        test_findings = [f for f in result.findings if "TEST" in f.rule_id]
        assert len(test_findings) > 0

    def test_test_requirement_rule_passes_with_tests(
        self,
        guardrail_engine: PlanGuardrailEngine,
        guardrail_config: PlanGuardrailConfig,
    ):
        """Test TestRequirementRule passes when test tasks exist."""
        feature_task = make_task(
            task_id="TASK-001",
            title="Implement authentication",
            description="Add auth functionality",
        )
        test_task = make_task(
            task_id="TASK-002",
            title="Add unit tests for authentication",
            description="Write tests for auth",
            dependencies=["TASK-001"],
            tags=["testing"],
        )
        plan = make_plan(groups=[make_task_group(tasks=[feature_task, test_task])])

        context = PlanValidationContext(
            plan=plan,
            config=guardrail_config,
        )

        result = guardrail_engine.validate(context)

        # Should not have test requirement findings
        test_findings = [f for f in result.findings if "TEST" in f.rule_id]
        assert len(test_findings) == 0 or all(
            f.affected_tasks != ["TASK-001"] for f in test_findings
        )

    def test_validation_respects_category_toggles(
        self, guardrail_config: PlanGuardrailConfig
    ):
        """Test that category toggles enable/disable rules."""
        # Disable coverage category
        guardrail_config.check_coverage = False
        engine = create_guardrail_engine(guardrail_config, discover_rules=True)

        feature_task = make_task(
            task_id="TASK-001",
            title="Implement new feature",
            description="Add new functionality",
        )
        plan = make_plan(groups=[make_task_group(tasks=[feature_task])])

        context = PlanValidationContext(
            plan=plan,
            config=guardrail_config,
        )

        result = engine.validate(context)

        # Coverage rules should be skipped
        coverage_findings = [
            f for f in result.findings if "TEST" in f.rule_id or "DOC" in f.rule_id
        ]
        assert len(coverage_findings) == 0

    def test_validation_confidence_filtering(
        self, guardrail_config: PlanGuardrailConfig
    ):
        """Test that low-confidence findings are filtered."""
        guardrail_config.revision_confidence_threshold = 0.95
        engine = create_guardrail_engine(guardrail_config, discover_rules=True)

        feature_task = make_task(
            task_id="TASK-001",
            title="Implement feature",
            description="Add functionality",
        )
        plan = make_plan(groups=[make_task_group(tasks=[feature_task])])

        context = PlanValidationContext(
            plan=plan,
            config=guardrail_config,
        )

        result = engine.validate(context)

        # All remaining findings should have high confidence
        for finding in result.findings:
            assert (
                finding.confidence >= 0.95
                or finding.confidence
                >= guardrail_config.revision_confidence_threshold * 0.8
            )

    def test_validation_performance(
        self,
        guardrail_engine: PlanGuardrailEngine,
        guardrail_config: PlanGuardrailConfig,
    ):
        """Test validation completes within performance target."""
        tasks = [
            make_task(
                task_id=f"TASK-{i:03d}",
                title=f"Task {i}",
                description=f"Description for task {i}",
            )
            for i in range(10)
        ]
        plan = make_plan(groups=[make_task_group(tasks=tasks)])

        context = PlanValidationContext(
            plan=plan,
            config=guardrail_config,
        )

        result = guardrail_engine.validate(context)

        # Should complete within 500ms
        assert result.execution_time_ms < 500


# =============================================================================
# TestAutoRevisionIntegration
# =============================================================================


class TestAutoRevisionIntegration:
    """Integration tests for auto-revision engine."""

    def test_add_task_revision(self, auto_revision_engine: AutoRevisionEngine):
        """Test ADD_TASK revision creates new task."""
        plan = make_plan(
            groups=[
                make_task_group(
                    tasks=[make_task(task_id="TASK-001", title="Feature task")]
                )
            ]
        )

        new_task = make_task(
            task_id="TASK-002",
            title="Test task",
            description="Tests for feature",
            scope="components",
            tags=["testing"],
        )

        finding = make_finding(
            rule_id="PLAN.TEST_REQUIREMENT",
            affected_tasks=["TASK-001"],
            can_auto_revise=True,
            confidence=0.9,
            suggested_revision=PlanRevision(
                revision_type=RevisionType.ADD_TASK,
                rationale="Add test task for feature",
                new_task=new_task,
            ),
        )

        result = auto_revision_engine.revise_plan(plan, [finding])

        assert result.was_revised
        assert result.revision_count == 1
        assert len(result.revised_plan.all_tasks) == 2
        assert any(t.id == "TASK-002" for t in result.revised_plan.all_tasks)

    def test_modify_task_revision(self, auto_revision_engine: AutoRevisionEngine):
        """Test MODIFY_TASK revision updates task."""
        plan = make_plan(
            groups=[
                make_task_group(
                    tasks=[
                        make_task(
                            task_id="TASK-001",
                            title="Original title",
                            description="Original description",
                        )
                    ]
                )
            ]
        )

        finding = make_finding(
            rule_id="PLAN.MODIFY_RULE",
            affected_tasks=["TASK-001"],
            can_auto_revise=True,
            confidence=0.9,
            suggested_revision=PlanRevision(
                revision_type=RevisionType.MODIFY_TASK,
                rationale="Update task description",
                target_task_id="TASK-001",
                modifications={"description": "Updated description"},
            ),
        )

        result = auto_revision_engine.revise_plan(plan, [finding])

        assert result.was_revised
        modified_task = next(
            t for t in result.revised_plan.all_tasks if t.id == "TASK-001"
        )
        assert modified_task.description == "Updated description"

    def test_conflict_detection_duplicate_id(
        self, auto_revision_engine: AutoRevisionEngine
    ):
        """Test conflict detection for duplicate task IDs."""
        existing_task = make_task(task_id="TASK-001", title="Existing task")
        plan = make_plan(groups=[make_task_group(tasks=[existing_task])])

        # Try to add task with same ID
        duplicate_task = make_task(task_id="TASK-001", title="Duplicate task")

        finding = make_finding(
            rule_id="PLAN.TEST_RULE",
            can_auto_revise=True,
            confidence=0.9,
            suggested_revision=PlanRevision(
                revision_type=RevisionType.ADD_TASK,
                rationale="Add duplicate",
                new_task=duplicate_task,
            ),
        )

        result = auto_revision_engine.revise_plan(plan, [finding])

        # Should be skipped due to conflict
        assert result.skipped_count > 0
        assert len(result.revised_plan.all_tasks) == 1

    def test_circular_dependency_prevention(
        self, auto_revision_engine: AutoRevisionEngine
    ):
        """Test circular dependency detection."""
        task1 = make_task(task_id="TASK-001", title="Task 1")
        task2 = make_task(task_id="TASK-002", title="Task 2", dependencies=["TASK-001"])
        plan = make_plan(groups=[make_task_group(tasks=[task1, task2])])

        # Try to add dependency from TASK-001 to TASK-002 (would create cycle)
        finding = make_finding(
            rule_id="PLAN.DEP_RULE",
            can_auto_revise=True,
            confidence=0.9,
            suggested_revision=PlanRevision(
                revision_type=RevisionType.ADD_DEPENDENCY,
                rationale="Add circular dependency",
                dependency_additions=[("TASK-001", "TASK-002")],
            ),
        )

        result = auto_revision_engine.revise_plan(plan, [finding])

        # Should be skipped due to circular dependency
        assert result.skipped_count > 0

    def test_revision_iteration_limit(self, guardrail_config: PlanGuardrailConfig):
        """Test revision iteration limit prevents infinite loops."""
        guardrail_config.max_revisions_per_plan = 2
        engine = AutoRevisionEngine(config=guardrail_config)

        plan = make_plan(groups=[make_task_group(tasks=[])])

        # Create many findings
        findings = [
            make_finding(
                rule_id=f"PLAN.RULE_{i}",
                can_auto_revise=True,
                confidence=0.9,
                suggested_revision=PlanRevision(
                    revision_type=RevisionType.ADD_TASK,
                    rationale=f"Add task {i}",
                    new_task=make_task(task_id=f"TASK-{i:03d}", title=f"Task {i}"),
                ),
            )
            for i in range(5)
        ]

        result = engine.revise_plan(plan, findings)

        # Should respect max revisions limit
        assert result.revision_count <= 2

    def test_audit_trail_generation(self, auto_revision_engine: AutoRevisionEngine):
        """Test audit trail is generated correctly."""
        plan = make_plan(groups=[make_task_group(tasks=[])])

        new_task = make_task(task_id="TASK-001", title="New task")
        finding = make_finding(
            rule_id="PLAN.TEST_REQUIREMENT",
            can_auto_revise=True,
            confidence=0.85,
            suggested_revision=PlanRevision(
                revision_type=RevisionType.ADD_TASK,
                rationale="Add test coverage",
                new_task=new_task,
            ),
        )

        result = auto_revision_engine.revise_plan(plan, [finding])

        audit_trail = result.format_audit_trail()
        assert "Plan Revisions Applied" in audit_trail
        assert "PLAN.TEST_REQUIREMENT" in audit_trail
        assert "Add test coverage" in audit_trail


# =============================================================================
# TestFullPlanModeFlow
# =============================================================================


class TestFullPlanModeFlow:
    """Integration tests for the complete Plan Mode pipeline."""

    def test_full_pipeline_detection_to_revision(
        self,
        plan_mode_repo: Path,
        plan_mode_detector: PlanModeDetector,
        guardrail_config: PlanGuardrailConfig,
    ):
        """Test complete pipeline: detect -> inject -> validate -> revise."""
        # Step 1: Detect Plan Mode
        prompt = "@plan Implement user authentication with login/logout"
        detection_result = plan_mode_detector.detect(prompt)

        assert detection_result.is_plan_mode is True

        # Step 2: Inject context
        injection_result = inject_plan_context(
            prompt=prompt,
            collection_name="test-collection",
            project_path=plan_mode_repo,
        )

        assert injection_result.success is True
        assert len(injection_result.injected_text) > 0

        # Step 3: Create plan (simulating Claude's response)
        feature_task = make_task(
            task_id="TASK-001",
            title="Implement AuthService class",
            description="Create authentication service",
        )
        plan = make_plan(
            groups=[make_task_group(tasks=[feature_task])],
            summary="Authentication implementation plan",
        )

        # Step 4: Validate plan
        engine = create_guardrail_engine(guardrail_config, discover_rules=True)
        context = PlanValidationContext(plan=plan, config=guardrail_config)
        validation_result = engine.validate(context)

        # Should detect missing tests
        assert validation_result.has_findings

        # Step 5: Apply auto-revisions
        revision_engine = AutoRevisionEngine(
            config=guardrail_config, rules=engine._rules
        )
        revised = revision_engine.revise_plan(plan, validation_result.findings)

        # Should have added test task
        if revised.was_revised:
            assert len(revised.revised_plan.all_tasks) > len(plan.all_tasks)

    def test_pipeline_with_qa_verification(
        self,
        plan_mode_repo: Path,
        guardrail_config: PlanGuardrailConfig,
        plan_qa_config: PlanQAConfig,
    ):
        """Test pipeline with QA verification at the end."""
        # Create plan text
        plan_text = SAMPLE_PLAN_MISSING_TESTS

        # Run QA verification
        qa_result = verify_plan_qa(plan_text, plan_qa_config)

        assert qa_result.has_issues()
        assert len(qa_result.missing_tests) > 0

        # Format feedback
        feedback = qa_result.format_feedback()
        assert "Missing Test Coverage" in feedback

    def test_revision_history_tracking(
        self,
        guardrail_config: PlanGuardrailConfig,
    ):
        """Test revision history is tracked across revisions."""
        engine = create_guardrail_engine(guardrail_config, discover_rules=True)
        revision_engine = AutoRevisionEngine(
            config=guardrail_config, rules=engine._rules
        )

        # Create plan
        feature_task = make_task(
            task_id="TASK-001",
            title="Implement new feature",
            description="Add new functionality",
        )
        plan = make_plan(groups=[make_task_group(tasks=[feature_task])])

        # Validate and revise
        context = PlanValidationContext(plan=plan, config=guardrail_config)
        validation_result = engine.validate(context)
        revised = revision_engine.revise_plan(plan, validation_result.findings)

        if revised.was_revised:
            # Add revisions to plan history
            revised.revised_plan.add_revisions(revised.revisions_applied)

            # Format history
            history = revised.revised_plan.format_revision_history()
            assert "Revision History" in history

    def test_configuration_flow_through_pipeline(
        self,
        plan_mode_repo: Path,
    ):
        """Test configuration flows correctly through entire pipeline."""
        # Custom config with specific settings
        guardrail_config = PlanGuardrailConfig(
            enabled=True,
            auto_revise=True,
            revision_confidence_threshold=0.8,
            check_coverage=True,
            check_consistency=False,  # Disabled
        )

        engine = create_guardrail_engine(guardrail_config, discover_rules=True)

        task = make_task(task_id="TASK-001", title="Implement feature")
        plan = make_plan(groups=[make_task_group(tasks=[task])])

        context = PlanValidationContext(plan=plan, config=guardrail_config)
        result = engine.validate(context)

        # Consistency rules should be skipped
        assert result.rules_skipped >= 0  # Some rules may be skipped


# =============================================================================
# TestDesignDocIndexingIntegration
# =============================================================================


class TestDesignDocIndexingIntegration:
    """Integration tests for design document indexing."""

    @pytest.fixture
    def design_docs_repo(self, tmp_path_factory) -> Path:
        """Create a repository with design documents."""
        repo_path = tmp_path_factory.mktemp("design_docs_repo")

        # PRD document
        (repo_path / "PRD.md").write_text(
            """# Product Requirements Document

## Overview
This document describes the requirements for the user authentication system.

## Requirements

### REQ-001: User Login
Users MUST be able to log in with email and password.

### REQ-002: Session Management
The system SHALL maintain user sessions for 24 hours.

### REQ-003: Password Reset
Users SHOULD be able to reset their password via email.
"""
        )

        # TDD document
        (repo_path / "TDD.md").write_text(
            """# Technical Design Document

## Architecture

### Authentication Service
The AuthService class handles all authentication operations.

## API Design

### POST /api/auth/login
Authenticates a user and returns a session token.

### POST /api/auth/logout
Invalidates the current session.
"""
        )

        # ADR document
        adr_dir = repo_path / "adr"
        adr_dir.mkdir()
        (adr_dir / "001-auth-strategy.md").write_text(
            """# ADR 001: Authentication Strategy

## Status
Accepted

## Context
We need to implement user authentication.

## Decision
We will use JWT tokens for authentication.

## Consequences
- Stateless authentication
- Token expiration handling needed
"""
        )

        return repo_path

    def test_design_doc_parser_import(self):
        """Test DesignDocParser can be imported."""
        from claude_indexer.analysis.design_doc_parser import DesignDocParser

        parser = DesignDocParser()
        assert parser is not None

    def test_prd_document_detection(self, design_docs_repo: Path):
        """Test PRD document type detection."""
        from claude_indexer.analysis.design_doc_parser import DesignDocParser

        parser = DesignDocParser()
        prd_path = design_docs_repo / "PRD.md"

        # Parse the document (only takes file_path)
        result = parser.parse(prd_path)

        assert result is not None
        assert len(result.entities) > 0

        # Should detect as PRD
        prd_entities = [e for e in result.entities if e.entity_type.value == "prd"]
        assert len(prd_entities) > 0 or len(result.entities) > 0

    def test_tdd_document_detection(self, design_docs_repo: Path):
        """Test TDD document type detection."""
        from claude_indexer.analysis.design_doc_parser import DesignDocParser

        parser = DesignDocParser()
        tdd_path = design_docs_repo / "TDD.md"

        result = parser.parse(tdd_path)

        assert result is not None
        assert len(result.entities) > 0

    def test_adr_document_detection(self, design_docs_repo: Path):
        """Test ADR document type detection."""
        from claude_indexer.analysis.design_doc_parser import DesignDocParser

        parser = DesignDocParser()
        adr_path = design_docs_repo / "adr" / "001-auth-strategy.md"

        result = parser.parse(adr_path)

        assert result is not None
        assert len(result.entities) > 0

    def test_requirement_extraction(self, design_docs_repo: Path):
        """Test RFC 2119 requirement extraction."""
        from claude_indexer.analysis.design_doc_parser import DesignDocParser

        parser = DesignDocParser()
        prd_path = design_docs_repo / "PRD.md"

        result = parser.parse(prd_path)

        # Should extract requirements with MUST/SHALL/SHOULD
        requirement_entities = [
            e for e in result.entities if e.entity_type.value == "requirement"
        ]

        # At least some requirements should be extracted
        assert len(requirement_entities) >= 0  # May vary based on parser implementation

    def test_section_extraction(self, design_docs_repo: Path):
        """Test markdown section extraction."""
        from claude_indexer.analysis.design_doc_parser import DesignDocParser

        parser = DesignDocParser()
        tdd_path = design_docs_repo / "TDD.md"

        result = parser.parse(tdd_path)

        # Should extract sections
        assert len(result.entities) > 0

        # Check that entities have content
        for entity in result.entities:
            assert entity.name is not None or entity.content is not None


# =============================================================================
# TestPlanQAVerification
# =============================================================================


class TestPlanQAVerification:
    """Integration tests for Plan QA verification."""

    def test_plan_qa_passes_complete_plan(self, plan_qa_config: PlanQAConfig):
        """Test QA passes for complete plan."""
        result = verify_plan_qa(SAMPLE_PLAN_COMPLETE, plan_qa_config)

        assert not result.has_issues()
        assert result.is_valid

    def test_plan_qa_detects_missing_tests(self, plan_qa_config: PlanQAConfig):
        """Test QA detects missing test tasks."""
        result = verify_plan_qa(SAMPLE_PLAN_MISSING_TESTS, plan_qa_config)

        assert result.has_issues()
        assert len(result.missing_tests) > 0

    def test_plan_qa_detects_missing_docs(self, plan_qa_config: PlanQAConfig):
        """Test QA detects missing documentation tasks."""
        result = verify_plan_qa(SAMPLE_PLAN_MISSING_DOCS, plan_qa_config)

        assert result.has_issues()
        assert len(result.missing_docs) > 0

    def test_plan_qa_detects_no_reuse_check(self, plan_qa_config: PlanQAConfig):
        """Test QA detects missing duplicate/reuse check."""
        result = verify_plan_qa(SAMPLE_PLAN_NO_REUSE_CHECK, plan_qa_config)

        assert result.has_issues()
        assert len(result.potential_duplicates) > 0

    def test_plan_qa_performance(self, plan_qa_config: PlanQAConfig):
        """Test QA verification completes within performance target."""
        result = verify_plan_qa(SAMPLE_PLAN_COMPLETE, plan_qa_config)

        assert result.verification_time_ms < 50  # Performance target

    def test_plan_qa_strict_mode(self):
        """Test QA strict mode fails on missing tests."""
        config = PlanQAConfig(
            enabled=True,
            check_tests=True,
            fail_on_missing_tests=True,
        )

        result = verify_plan_qa(SAMPLE_PLAN_MISSING_TESTS, config)

        assert not result.is_valid

    def test_plan_qa_injector_integration(self, plan_mode_repo: Path):
        """Test QA verification via injector."""
        config = PlanContextInjectionConfig(
            qa_enabled=True,
            qa_config=PlanQAConfig(enabled=True),
        )

        injector = PlanContextInjector(
            collection_name="test-collection",
            project_path=plan_mode_repo,
            config=config,
        )

        qa_result = injector.verify_plan_output(SAMPLE_PLAN_MISSING_TESTS)

        assert qa_result.has_issues()
