"""
Performance benchmark tests for Plan Mode components.

These tests validate latency targets:
- Plan Mode Detection: <10ms p95
- Guidelines Generation: <20ms p95
- Exploration Hints: <30ms p95
- Plan QA Verification: <50ms p95
- Guardrail Validation: <500ms
- Auto-Revision: <200ms
- Total Overhead: <100ms (excluding validation)

Milestone 13.2: Performance Optimization
"""

import time
from pathlib import Path

import pytest

# Import Plan Mode modules
from claude_indexer.hooks.plan_mode_detector import (
    PlanModeDetector,
    detect_plan_mode,
)
from claude_indexer.hooks.plan_qa import (
    PlanQAVerifier,
    verify_plan_qa,
)
from claude_indexer.hooks.planning.exploration import ExplorationHintsGenerator
from claude_indexer.hooks.planning.guidelines import PlanningGuidelinesGenerator
from claude_indexer.hooks.planning.injector import (
    PlanContextInjectionConfig,
    PlanContextInjector,
)
from claude_indexer.rules.base import Severity
from claude_indexer.ui.plan.guardrails.auto_revision import create_auto_revision_engine
from claude_indexer.ui.plan.guardrails.base import (
    PlanRevision,
    PlanValidationContext,
    PlanValidationFinding,
    RevisionType,
)
from claude_indexer.ui.plan.guardrails.config import PlanGuardrailConfig
from claude_indexer.ui.plan.guardrails.engine import create_guardrail_engine
from claude_indexer.ui.plan.task import ImplementationPlan, Task, TaskGroup

pytestmark = [
    pytest.mark.benchmark,
    pytest.mark.slow,
]


# Performance targets (in seconds)
DETECTION_TARGET_P95 = 0.010  # 10ms
GUIDELINES_TARGET_P95 = 0.020  # 20ms
HINTS_TARGET_P95 = 0.030  # 30ms
PLAN_QA_TARGET_P95 = 0.050  # 50ms
VALIDATION_TARGET_P95 = 0.500  # 500ms
AUTO_REVISION_TARGET_P95 = 0.200  # 200ms
TOTAL_OVERHEAD_TARGET_P95 = 0.100  # 100ms (excluding validation)


# Test fixtures


@pytest.fixture
def benchmark_iterations() -> int:
    """Return the number of iterations for benchmark tests."""
    return 10


@pytest.fixture
def sample_prompts() -> list[str]:
    """Return sample prompts for detection benchmarks."""
    return [
        "@plan Create a user authentication system with OAuth support",
        "@agent-plan Design a caching layer for the API",
        "Create a detailed plan for implementing search functionality",
        "Write a step-by-step plan for database migration",
        "Make a plan for refactoring the payment module with phases and milestones",
        "Design a comprehensive implementation plan for adding analytics",
        "Implement a new feature for user dashboards",
        "Add a button to the settings page",  # Non-plan prompt
        "Fix the bug in login handling",  # Non-plan prompt
        "How do I use the API?",  # Non-plan prompt
    ]


@pytest.fixture
def sample_plan_text() -> str:
    """Return sample plan text for QA verification benchmarks."""
    return """
## Implementation Plan: User Authentication System

### Phase 1: Backend
1. Create AuthService class for handling authentication logic
2. Implement JWT token generation and validation
3. Add user session management with Redis caching
4. Build API endpoints for login, logout, and refresh

### Phase 2: Frontend
1. Create login form component with validation
2. Implement OAuth button integration
3. Add session persistence in local storage
4. Build protected route wrapper

### Phase 3: Testing
1. Add unit tests for AuthService
2. Write integration tests for auth API endpoints
3. Create E2E tests for login flow

### Phase 4: Documentation
1. Update API documentation with auth endpoints
2. Add security guidelines to README

### Notes
- Verified no existing implementation
- Will extend existing UserService for profile data
- Consider O(n^2) complexity in token validation - needs optimization
"""


@pytest.fixture
def sample_plan_text_minimal() -> str:
    """Return minimal plan text for fast QA benchmarks."""
    return """
1. Create AuthService function
2. Add unit tests
3. Update documentation
"""


@pytest.fixture
def collection_name() -> str:
    """Return collection name for MCP prefix generation."""
    return "benchmark-test"


@pytest.fixture
def guardrail_config() -> PlanGuardrailConfig:
    """Return guardrail configuration for benchmarks."""
    return PlanGuardrailConfig(
        enabled=True,
        auto_revise=True,
        max_revisions_per_plan=5,
    )


@pytest.fixture
def sample_plan() -> ImplementationPlan:
    """Create a sample implementation plan for benchmarks."""
    tasks = [
        Task(
            id="TASK-001",
            title="Create AuthService class",
            description="Implement authentication service with OAuth support",
            scope="backend",
            priority=1,
            estimated_effort="medium",
            impact=0.8,
            acceptance_criteria=["OAuth2 flow works", "Token generation secure"],
            dependencies=[],
            tags=["auth", "backend"],
        ),
        Task(
            id="TASK-002",
            title="Build login API endpoint",
            description="Create REST endpoint for user login",
            scope="backend",
            priority=2,
            estimated_effort="low",
            impact=0.7,
            acceptance_criteria=["Returns JWT on success"],
            dependencies=["TASK-001"],
            tags=["api", "auth"],
        ),
        Task(
            id="TASK-003",
            title="Implement frontend login form",
            description="Create React login component",
            scope="frontend",
            priority=3,
            estimated_effort="medium",
            impact=0.6,
            acceptance_criteria=["Form validates input", "Handles errors"],
            dependencies=["TASK-002"],
            tags=["ui", "auth"],
        ),
    ]

    groups = [
        TaskGroup(
            scope="backend",
            description="Backend authentication tasks",
            tasks=tasks[:2],
        ),
        TaskGroup(
            scope="frontend",
            description="Frontend authentication tasks",
            tasks=tasks[2:],
        ),
    ]

    return ImplementationPlan(
        name="User Authentication",
        description="Implement user authentication system",
        groups=groups,
        quick_wins=[tasks[1]],
    )


@pytest.fixture
def sample_findings(sample_plan: ImplementationPlan) -> list[PlanValidationFinding]:
    """Create sample findings for auto-revision benchmarks."""
    return [
        PlanValidationFinding(
            rule_id="PLAN.TEST_REQUIREMENT",
            severity=Severity.MEDIUM,
            summary="Feature task without test coverage",
            affected_tasks=["TASK-001"],
            suggestion="Add test task for AuthService",
            can_auto_revise=True,
            confidence=0.9,
            suggested_revision=PlanRevision(
                revision_type=RevisionType.ADD_TASK,
                rationale="Add test task for AuthService",
                new_task=Task(
                    id="TASK-TST-001",
                    title="Add tests for AuthService",
                    description="Write unit tests for authentication service",
                    scope="backend",
                    priority=4,
                    estimated_effort="low",
                    impact=0.5,
                    acceptance_criteria=["Unit tests pass"],
                    dependencies=["TASK-001"],
                    tags=["testing"],
                ),
            ),
        ),
        PlanValidationFinding(
            rule_id="PLAN.DOC_REQUIREMENT",
            severity=Severity.LOW,
            summary="User-facing change without documentation",
            affected_tasks=["TASK-003"],
            suggestion="Add documentation task",
            can_auto_revise=True,
            confidence=0.85,
            suggested_revision=PlanRevision(
                revision_type=RevisionType.ADD_TASK,
                rationale="Add documentation task for login form",
                new_task=Task(
                    id="TASK-DOC-001",
                    title="Document login form usage",
                    description="Update docs with login form usage",
                    scope="docs",
                    priority=5,
                    estimated_effort="low",
                    impact=0.3,
                    acceptance_criteria=["Docs updated"],
                    dependencies=["TASK-003"],
                    tags=["documentation"],
                ),
            ),
        ),
    ]


class TestPlanModeDetectionPerformance:
    """
    Plan Mode Detection performance tests.

    Target: <10ms p95
    """

    def test_detection_under_target(
        self,
        sample_prompts: list[str],
        benchmark_iterations: int,
    ):
        """Detection should complete in under 10ms p95."""
        detector = PlanModeDetector()
        timings = []

        for _ in range(benchmark_iterations):
            for prompt in sample_prompts:
                start = time.perf_counter()
                detector.detect(prompt)
                elapsed = time.perf_counter() - start
                timings.append(elapsed)

        # Calculate p95
        timings.sort()
        p95_index = int(len(timings) * 0.95)
        p95 = timings[p95_index] if p95_index < len(timings) else timings[-1]

        assert p95 < DETECTION_TARGET_P95, (
            f"Plan Mode detection p95 ({p95*1000:.2f}ms) "
            f"exceeds {DETECTION_TARGET_P95*1000}ms target"
        )

    def test_detection_convenience_function(
        self,
        sample_prompts: list[str],
        benchmark_iterations: int,
    ):
        """Convenience function should meet same target."""
        timings = []

        for _ in range(benchmark_iterations):
            for prompt in sample_prompts:
                start = time.perf_counter()
                detect_plan_mode(prompt)
                elapsed = time.perf_counter() - start
                timings.append(elapsed)

        timings.sort()
        p95_index = int(len(timings) * 0.95)
        p95 = timings[p95_index] if p95_index < len(timings) else timings[-1]

        assert p95 < DETECTION_TARGET_P95, (
            f"detect_plan_mode() p95 ({p95*1000:.2f}ms) "
            f"exceeds {DETECTION_TARGET_P95*1000}ms target"
        )

    def test_explicit_marker_detection_fast(
        self,
        benchmark_iterations: int,
    ):
        """Explicit markers should be detected very quickly (<5ms)."""
        detector = PlanModeDetector()
        prompt = "@plan Create a feature"
        timings = []

        for _ in range(benchmark_iterations * 10):  # More iterations for fast ops
            start = time.perf_counter()
            result = detector.detect(prompt)
            elapsed = time.perf_counter() - start
            timings.append(elapsed)
            assert result.is_plan_mode

        timings.sort()
        p95 = timings[int(len(timings) * 0.95)]

        assert p95 < 0.005, f"Explicit marker detection p95 ({p95*1000:.2f}ms) > 5ms"


class TestGuidelinesGenerationPerformance:
    """
    Guidelines Generation performance tests.

    Target: <20ms p95
    """

    def test_guidelines_generation_under_target(
        self,
        collection_name: str,
        benchmark_iterations: int,
        tmp_path: Path,
    ):
        """Guidelines generation should complete in under 20ms p95."""
        generator = PlanningGuidelinesGenerator(
            collection_name=collection_name,
            project_path=tmp_path,
        )
        timings = []

        for _ in range(benchmark_iterations):
            start = time.perf_counter()
            generator.generate()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        timings.sort()
        p95_index = int(len(timings) * 0.95)
        p95 = timings[p95_index] if p95_index < len(timings) else timings[-1]

        assert p95 < GUIDELINES_TARGET_P95, (
            f"Guidelines generation p95 ({p95*1000:.2f}ms) "
            f"exceeds {GUIDELINES_TARGET_P95*1000}ms target"
        )

    def test_guidelines_compact_mode_faster(
        self,
        collection_name: str,
        benchmark_iterations: int,
        tmp_path: Path,
    ):
        """Compact mode should be faster than full generation."""
        generator = PlanningGuidelinesGenerator(
            collection_name=collection_name,
            project_path=tmp_path,
        )

        full_timings = []
        compact_timings = []

        for _ in range(benchmark_iterations):
            # Full generation
            start = time.perf_counter()
            generator.generate()
            full_timings.append(time.perf_counter() - start)

            # Compact generation
            start = time.perf_counter()
            generator.generate_compact()
            compact_timings.append(time.perf_counter() - start)

        full_avg = sum(full_timings) / len(full_timings)
        compact_avg = sum(compact_timings) / len(compact_timings)

        assert compact_avg < full_avg, (
            f"Compact mode ({compact_avg*1000:.2f}ms) not faster than "
            f"full mode ({full_avg*1000:.2f}ms)"
        )

    def test_guidelines_with_claude_md_caching(
        self,
        collection_name: str,
        benchmark_iterations: int,
        tmp_path: Path,
    ):
        """Subsequent calls should benefit from caching."""
        # Create a CLAUDE.md file
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            """
# Project Guidelines

## Code Style
- Use TypeScript strict mode
- Follow ESLint rules
- Use Prettier for formatting

## Patterns
- Use repository pattern for data access
- Implement service layer for business logic
"""
        )

        generator = PlanningGuidelinesGenerator(
            collection_name=collection_name,
            project_path=tmp_path,
        )

        # First call (cold)
        cold_timings = []
        for _ in range(3):
            start = time.perf_counter()
            generator.generate()
            cold_timings.append(time.perf_counter() - start)

        # Subsequent calls (should hit cache)
        warm_timings = []
        for _ in range(benchmark_iterations):
            start = time.perf_counter()
            generator.generate()
            warm_timings.append(time.perf_counter() - start)

        warm_avg = sum(warm_timings) / len(warm_timings)

        # All calls should still meet target
        assert warm_avg < GUIDELINES_TARGET_P95, (
            f"Guidelines generation avg ({warm_avg*1000:.2f}ms) " f"exceeds target"
        )


class TestExplorationHintsPerformance:
    """
    Exploration Hints Generation performance tests.

    Target: <30ms p95
    """

    def test_hints_generation_under_target(
        self,
        collection_name: str,
        sample_prompts: list[str],
        benchmark_iterations: int,
    ):
        """Hints generation should complete in under 30ms p95."""
        generator = ExplorationHintsGenerator(
            collection_name=collection_name,
        )
        timings = []

        for _ in range(benchmark_iterations):
            for prompt in sample_prompts:
                start = time.perf_counter()
                generator.generate(prompt)
                elapsed = time.perf_counter() - start
                timings.append(elapsed)

        timings.sort()
        p95_index = int(len(timings) * 0.95)
        p95 = timings[p95_index] if p95_index < len(timings) else timings[-1]

        assert p95 < HINTS_TARGET_P95, (
            f"Hints generation p95 ({p95*1000:.2f}ms) "
            f"exceeds {HINTS_TARGET_P95*1000}ms target"
        )

    def test_entity_extraction_performance(
        self,
        collection_name: str,
        benchmark_iterations: int,
    ):
        """Entity extraction should be fast."""
        generator = ExplorationHintsGenerator(collection_name=collection_name)
        prompt = """
        Implement UserAuthenticationService with OAuth2Provider integration.
        Use token_validator and session_manager for state handling.
        Connect to "users" database and "auth_tokens" collection.
        """
        timings = []

        for _ in range(benchmark_iterations * 10):
            start = time.perf_counter()
            generator._extract_entities(prompt)
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        timings.sort()
        p95 = timings[int(len(timings) * 0.95)]

        # Entity extraction should be very fast (<5ms)
        assert p95 < 0.005, f"Entity extraction p95 ({p95*1000:.2f}ms) > 5ms"


class TestPlanQAPerformance:
    """
    Plan QA Verification performance tests.

    Target: <50ms p95
    """

    def test_plan_qa_under_target(
        self,
        sample_plan_text: str,
        benchmark_iterations: int,
    ):
        """Plan QA should complete in under 50ms p95."""
        verifier = PlanQAVerifier()
        timings = []

        for _ in range(benchmark_iterations):
            start = time.perf_counter()
            verifier.verify_plan(sample_plan_text)
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        timings.sort()
        p95_index = int(len(timings) * 0.95)
        p95 = timings[p95_index] if p95_index < len(timings) else timings[-1]

        assert p95 < PLAN_QA_TARGET_P95, (
            f"Plan QA p95 ({p95*1000:.2f}ms) "
            f"exceeds {PLAN_QA_TARGET_P95*1000}ms target"
        )

    def test_plan_qa_convenience_function(
        self,
        sample_plan_text: str,
        benchmark_iterations: int,
    ):
        """Convenience function should meet same target."""
        timings = []

        for _ in range(benchmark_iterations):
            start = time.perf_counter()
            verify_plan_qa(sample_plan_text)
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        timings.sort()
        p95_index = int(len(timings) * 0.95)
        p95 = timings[p95_index] if p95_index < len(timings) else timings[-1]

        assert p95 < PLAN_QA_TARGET_P95, (
            f"verify_plan_qa() p95 ({p95*1000:.2f}ms) "
            f"exceeds {PLAN_QA_TARGET_P95*1000}ms target"
        )

    def test_plan_qa_minimal_plan_fast(
        self,
        sample_plan_text_minimal: str,
        benchmark_iterations: int,
    ):
        """Minimal plans should be verified very quickly."""
        verifier = PlanQAVerifier()
        timings = []

        for _ in range(benchmark_iterations * 10):
            start = time.perf_counter()
            verifier.verify_plan(sample_plan_text_minimal)
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        timings.sort()
        p95 = timings[int(len(timings) * 0.95)]

        # Minimal plans should be very fast (<10ms)
        assert p95 < 0.010, f"Minimal plan QA p95 ({p95*1000:.2f}ms) > 10ms"


class TestGuardrailValidationPerformance:
    """
    Guardrail Validation performance tests.

    Target: <500ms for full validation
    """

    def test_validation_under_target(
        self,
        guardrail_config: PlanGuardrailConfig,
        sample_plan: ImplementationPlan,
        benchmark_iterations: int,
    ):
        """Validation should complete in under 500ms."""
        engine = create_guardrail_engine(guardrail_config, discover_rules=True)
        context = PlanValidationContext(
            plan=sample_plan,
            config=guardrail_config,
        )
        timings = []

        for _ in range(benchmark_iterations):
            start = time.perf_counter()
            engine.validate(context)
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        timings.sort()
        p95_index = int(len(timings) * 0.95)
        p95 = timings[p95_index] if p95_index < len(timings) else timings[-1]

        assert p95 < VALIDATION_TARGET_P95, (
            f"Validation p95 ({p95*1000:.2f}ms) "
            f"exceeds {VALIDATION_TARGET_P95*1000}ms target"
        )

    def test_fast_validation_mode(
        self,
        guardrail_config: PlanGuardrailConfig,
        sample_plan: ImplementationPlan,
        benchmark_iterations: int,
    ):
        """Fast validation should be under 100ms."""
        engine = create_guardrail_engine(guardrail_config, discover_rules=True)
        context = PlanValidationContext(
            plan=sample_plan,
            config=guardrail_config,
        )
        timings = []

        for _ in range(benchmark_iterations):
            start = time.perf_counter()
            engine.validate_fast(context)
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        timings.sort()
        p95_index = int(len(timings) * 0.95)
        p95 = timings[p95_index] if p95_index < len(timings) else timings[-1]

        assert p95 < 0.100, f"Fast validation p95 ({p95*1000:.2f}ms) > 100ms"


class TestAutoRevisionPerformance:
    """
    Auto-Revision performance tests.

    Target: <200ms
    """

    def test_auto_revision_under_target(
        self,
        guardrail_config: PlanGuardrailConfig,
        sample_plan: ImplementationPlan,
        sample_findings: list[PlanValidationFinding],
        benchmark_iterations: int,
    ):
        """Auto-revision should complete in under 200ms."""
        engine = create_auto_revision_engine(guardrail_config)
        timings = []

        for _ in range(benchmark_iterations):
            start = time.perf_counter()
            engine.revise_plan(sample_plan, sample_findings)
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        timings.sort()
        p95_index = int(len(timings) * 0.95)
        p95 = timings[p95_index] if p95_index < len(timings) else timings[-1]

        assert p95 < AUTO_REVISION_TARGET_P95, (
            f"Auto-revision p95 ({p95*1000:.2f}ms) "
            f"exceeds {AUTO_REVISION_TARGET_P95*1000}ms target"
        )

    def test_auto_revision_no_findings_fast(
        self,
        guardrail_config: PlanGuardrailConfig,
        sample_plan: ImplementationPlan,
        benchmark_iterations: int,
    ):
        """Auto-revision with no findings should be very fast."""
        engine = create_auto_revision_engine(guardrail_config)
        timings = []

        for _ in range(benchmark_iterations * 10):
            start = time.perf_counter()
            engine.revise_plan(sample_plan, [])
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        timings.sort()
        p95 = timings[int(len(timings) * 0.95)]

        # No findings should be very fast (<10ms)
        assert p95 < 0.010, f"No-findings revision p95 ({p95*1000:.2f}ms) > 10ms"


class TestEndToEndPlanModePerformance:
    """
    End-to-end Plan Mode pipeline performance tests.

    Target: <100ms overhead (excluding validation)
    """

    def test_total_overhead_under_target(
        self,
        collection_name: str,
        sample_prompts: list[str],
        benchmark_iterations: int,
        tmp_path: Path,
    ):
        """Total Plan Mode overhead should be under 100ms."""
        # Create injector with all components
        config = PlanContextInjectionConfig(
            enabled=True,
            inject_guidelines=True,
            inject_hints=True,
            qa_enabled=True,
        )
        injector = PlanContextInjector(
            collection_name=collection_name,
            project_path=tmp_path,
            config=config,
        )
        detector = PlanModeDetector()

        timings = []

        for _ in range(benchmark_iterations):
            for prompt in sample_prompts[:5]:  # Use first 5 prompts
                start = time.perf_counter()

                # Full pipeline (excluding validation)
                result = detector.detect(prompt)
                if result.is_plan_mode:
                    injector.inject(prompt)

                elapsed = time.perf_counter() - start
                timings.append(elapsed)

        timings.sort()
        p95_index = int(len(timings) * 0.95)
        p95 = timings[p95_index] if p95_index < len(timings) else timings[-1]

        assert p95 < TOTAL_OVERHEAD_TARGET_P95, (
            f"Total overhead p95 ({p95*1000:.2f}ms) "
            f"exceeds {TOTAL_OVERHEAD_TARGET_P95*1000}ms target"
        )

    def test_detection_to_injection_latency(
        self,
        collection_name: str,
        benchmark_iterations: int,
        tmp_path: Path,
    ):
        """Detection + injection combined should be fast."""
        config = PlanContextInjectionConfig(
            enabled=True,
            compact_mode=True,  # Use compact for speed
        )
        injector = PlanContextInjector(
            collection_name=collection_name,
            project_path=tmp_path,
            config=config,
        )
        detector = PlanModeDetector()
        prompt = "@plan Create authentication system"

        timings = []

        for _ in range(benchmark_iterations):
            start = time.perf_counter()
            result = detector.detect(prompt)
            assert result.is_plan_mode
            injection_result = injector.inject(prompt)
            assert injection_result.success
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

        timings.sort()
        p95 = timings[int(len(timings) * 0.95)]

        # Compact mode should be under 50ms total
        assert (
            p95 < 0.050
        ), f"Detection + compact injection p95 ({p95*1000:.2f}ms) > 50ms"


class TestMemoryUsage:
    """Test memory usage stays reasonable."""

    def test_memory_stable_across_iterations(
        self,
        collection_name: str,
        sample_prompts: list[str],
        tmp_path: Path,
    ):
        """Memory usage should not grow significantly across iterations."""
        import tracemalloc

        tracemalloc.start()

        injector = PlanContextInjector(
            collection_name=collection_name,
            project_path=tmp_path,
        )

        # Run many iterations
        for _ in range(100):
            for prompt in sample_prompts:
                injector.inject(prompt)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / 1024 / 1024

        # Should use less than 50MB
        assert peak_mb < 50, f"Peak memory usage ({peak_mb:.1f}MB) exceeds 50MB"


class TestScalabilityMetrics:
    """Test that performance scales appropriately."""

    def test_detection_scales_with_prompt_length(self):
        """Detection time should scale roughly linearly with prompt length."""
        detector = PlanModeDetector()

        times_by_length: dict[int, float] = {}

        for multiplier in [1, 5, 10, 20]:
            base_prompt = "@plan Create authentication system"
            prompt = base_prompt + " " + ("with additional context " * multiplier)

            timings = []
            for _ in range(10):
                start = time.perf_counter()
                detector.detect(prompt)
                timings.append(time.perf_counter() - start)

            times_by_length[len(prompt)] = sum(timings) / len(timings)

        # Check roughly linear scaling (20x length should be < 30x time)
        lengths = sorted(times_by_length.keys())
        first_time = times_by_length[lengths[0]]
        last_time = times_by_length[lengths[-1]]
        length_ratio = lengths[-1] / lengths[0]
        time_ratio = last_time / first_time if first_time > 0 else 0

        assert (
            time_ratio < length_ratio * 1.5
        ), f"Non-linear scaling: {length_ratio:.1f}x length = {time_ratio:.1f}x time"

    def test_qa_verification_scales_with_plan_size(self):
        """QA verification should scale with plan size."""
        verifier = PlanQAVerifier()

        # Create plans of varying sizes
        times_by_size: dict[int, float] = {}

        for size in [100, 500, 1000, 2000]:
            plan_text = "Create AuthService function\n" * (size // 30)

            timings = []
            for _ in range(5):
                start = time.perf_counter()
                verifier.verify_plan(plan_text)
                timings.append(time.perf_counter() - start)

            times_by_size[size] = sum(timings) / len(timings)

        # Verify even large plans meet target
        sizes = sorted(times_by_size.keys())
        last_time = times_by_size[sizes[-1]]

        # Still under target even for large plans
        assert (
            last_time < PLAN_QA_TARGET_P95
        ), f"Large plan QA ({last_time*1000:.2f}ms) exceeds target"
