"""Unit tests for Plan QA verification.

Tests that the verifier correctly detects quality issues in plan text.

Milestone 12.1: Plan QA Verifier
"""

import pytest

from claude_indexer.hooks.plan_qa import (
    PlanQAConfig,
    PlanQAResult,
    PlanQAVerifier,
    verify_plan_qa,
)


class TestPlanQAResult:
    """Test PlanQAResult dataclass."""

    def test_default_result_is_valid(self):
        """Default result should be valid with no issues."""
        result = PlanQAResult()

        assert result.is_valid is True
        assert result.has_issues() is False

    def test_has_issues_with_missing_tests(self):
        """Result with missing tests has issues."""
        result = PlanQAResult(missing_tests=["Missing test for feature"])

        assert result.has_issues() is True

    def test_has_issues_with_missing_docs(self):
        """Result with missing docs has issues."""
        result = PlanQAResult(missing_docs=["Missing docs for API"])

        assert result.has_issues() is True

    def test_has_issues_with_duplicates(self):
        """Result with potential duplicates has issues."""
        result = PlanQAResult(potential_duplicates=["New code without check"])

        assert result.has_issues() is True

    def test_has_issues_with_architecture(self):
        """Result with architecture warnings has issues."""
        result = PlanQAResult(architecture_warnings=["O(n^2) complexity"])

        assert result.has_issues() is True

    def test_format_feedback_no_issues(self):
        """Format feedback for passing plan."""
        result = PlanQAResult()
        feedback = result.format_feedback()

        assert "All quality checks passed" in feedback

    def test_format_feedback_with_missing_tests(self):
        """Format feedback includes test warnings."""
        result = PlanQAResult(missing_tests=["Code changes without tests"])
        feedback = result.format_feedback()

        assert "[WARN]" in feedback
        assert "Missing Test Coverage" in feedback
        assert "Code changes without tests" in feedback

    def test_format_feedback_with_missing_docs(self):
        """Format feedback includes doc warnings."""
        result = PlanQAResult(missing_docs=["User-facing without docs"])
        feedback = result.format_feedback()

        assert "Missing Documentation" in feedback

    def test_format_feedback_with_duplicates(self):
        """Format feedback includes duplicate warnings."""
        result = PlanQAResult(potential_duplicates=["New code no check"])
        feedback = result.format_feedback()

        assert "Potential Duplicates" in feedback

    def test_format_feedback_with_architecture(self):
        """Format feedback includes architecture warnings."""
        result = PlanQAResult(architecture_warnings=["Performance concern"])
        feedback = result.format_feedback()

        assert "Architecture Concerns" in feedback

    def test_format_feedback_with_suggestions(self):
        """Format feedback includes suggestions."""
        result = PlanQAResult(
            missing_tests=["test issue"],
            suggestions=["Add test task"],
        )
        feedback = result.format_feedback()

        assert "[SUGGESTIONS]" in feedback
        assert "Add test task" in feedback

    def test_format_feedback_structure(self):
        """Format feedback has correct structure."""
        result = PlanQAResult(missing_tests=["issue"])
        feedback = result.format_feedback()

        assert feedback.startswith("\n=== Plan QA Feedback ===")
        assert feedback.endswith("=== End Plan QA ===")

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = PlanQAResult(
            is_valid=True,
            missing_tests=["test"],
            missing_docs=["doc"],
            potential_duplicates=["dup"],
            architecture_warnings=["arch"],
            suggestions=["suggestion"],
            verification_time_ms=10.5678,
        )
        d = result.to_dict()

        assert d["is_valid"] is True
        assert d["has_issues"] is True
        assert d["missing_tests"] == ["test"]
        assert d["missing_docs"] == ["doc"]
        assert d["potential_duplicates"] == ["dup"]
        assert d["architecture_warnings"] == ["arch"]
        assert d["suggestions"] == ["suggestion"]
        assert d["verification_time_ms"] == 10.57  # Rounded


class TestPlanQAConfig:
    """Test PlanQAConfig dataclass."""

    def test_default_config(self):
        """Default config enables all checks, warn-only mode."""
        config = PlanQAConfig()

        assert config.enabled is True
        assert config.check_tests is True
        assert config.check_docs is True
        assert config.check_duplicates is True
        assert config.check_architecture is True
        assert config.fail_on_missing_tests is False
        assert config.fail_on_missing_docs is False

    def test_to_dict(self):
        """Config serializes to dictionary."""
        config = PlanQAConfig(
            enabled=True,
            check_tests=False,
            fail_on_missing_tests=True,
        )
        d = config.to_dict()

        assert d["enabled"] is True
        assert d["check_tests"] is False
        assert d["fail_on_missing_tests"] is True

    def test_from_dict(self):
        """Config deserializes from dictionary."""
        data = {
            "enabled": False,
            "check_docs": False,
            "fail_on_missing_docs": True,
        }
        config = PlanQAConfig.from_dict(data)

        assert config.enabled is False
        assert config.check_docs is False
        assert config.fail_on_missing_docs is True
        # Defaults preserved for unspecified
        assert config.check_tests is True

    def test_from_dict_empty(self):
        """Empty dictionary uses defaults."""
        config = PlanQAConfig.from_dict({})

        assert config.enabled is True
        assert config.check_tests is True


class TestMissingTestDetection:
    """Test detection of missing test tasks."""

    @pytest.fixture
    def verifier(self):
        """Create verifier instance."""
        return PlanQAVerifier()

    @pytest.mark.parametrize(
        "plan_text",
        [
            "1. Implement user authentication function",
            "2. Create a new UserService class",
            "3. Add validation component",
            "4. Build API endpoint for users",
            "5. Write handler method for login",
            "6. Develop the payment module",
            "7. Modify the existing controller",
            "8. Update the schema logic",
        ],
    )
    def test_detects_code_changes_without_tests(self, verifier, plan_text):
        """Code changes without tests are detected."""
        result = verifier.verify_plan(plan_text)

        assert len(result.missing_tests) > 0
        assert "no test tasks" in result.missing_tests[0].lower()

    @pytest.mark.parametrize(
        "plan_text",
        [
            "1. Implement auth\n2. Add unit tests for auth",
            "1. Create service\n2. Write pytest tests",
            "1. Build component\n2. Add integration tests",
            "1. Implement feature\n2. Create test suite",
            "1. Add endpoint\n2. Include tests for endpoint",
            "1. Modify handler\n2. Testing for the handler changes",
            "1. Build module\n2. Verify with tests",
        ],
    )
    def test_passes_with_test_tasks(self, verifier, plan_text):
        """Plans with test tasks pass."""
        result = verifier.verify_plan(plan_text)

        assert len(result.missing_tests) == 0

    def test_no_code_changes_no_test_requirement(self, verifier):
        """Plans without code changes don't require tests."""
        plan_text = "1. Update documentation\n2. Fix typo in README"
        result = verifier.verify_plan(plan_text)

        assert len(result.missing_tests) == 0


class TestMissingDocDetection:
    """Test detection of missing documentation tasks."""

    @pytest.fixture
    def verifier(self):
        """Create verifier instance."""
        return PlanQAVerifier()

    @pytest.mark.parametrize(
        "plan_text",
        [
            "1. Add new CLI command for users",
            "2. Create public API endpoint",
            "3. Update user-facing dashboard",
            "4. Add config option for timeout",
            "5. Build new frontend page",
            "6. Create customer interface",
        ],
    )
    def test_detects_user_facing_without_docs(self, verifier, plan_text):
        """User-facing changes without docs are detected."""
        result = verifier.verify_plan(plan_text)

        assert len(result.missing_docs) > 0
        assert "documentation" in result.missing_docs[0].lower()

    @pytest.mark.parametrize(
        "plan_text",
        [
            "1. Add API endpoint\n2. Update API documentation",
            "1. Create CLI command\n2. Add README section",
            "1. Build frontend page\n2. Update the docs",
            "1. Add config option\n2. Document the new setting",
            "1. Create interface\n2. Write documentation for users",
        ],
    )
    def test_passes_with_doc_tasks(self, verifier, plan_text):
        """Plans with doc tasks pass."""
        result = verifier.verify_plan(plan_text)

        assert len(result.missing_docs) == 0

    def test_internal_changes_no_doc_requirement(self, verifier):
        """Internal changes don't require docs."""
        plan_text = "1. Refactor internal service implementation"
        result = verifier.verify_plan(plan_text)

        assert len(result.missing_docs) == 0


class TestDuplicateVerification:
    """Test detection of duplicate verification."""

    @pytest.fixture
    def verifier(self):
        """Create verifier instance."""
        return PlanQAVerifier()

    def test_detects_new_code_without_check(self, verifier):
        """New code without duplicate check is flagged."""
        plan_text = "1. Create new AuthService class"
        result = verifier.verify_plan(plan_text)

        assert len(result.potential_duplicates) > 0
        assert "duplicate" in result.potential_duplicates[0].lower()

    @pytest.mark.parametrize(
        "plan_text",
        [
            "1. Create service\n(Verified no existing implementation)",
            "1. Add handler (checked for duplicate code)",
            "1. Extend existing AuthService",
            "1. Use search_similar to find patterns\n2. Create handler",
            "1. Checked for similar code\n2. Implement new module",
            "1. Will extend existing user module",
            "1. Based on existing patterns\n2. Add new component",
            "1. Confirmed no existing solution\n2. Build service",
            "1. Reuse existing utility\n2. Create wrapper",
        ],
    )
    def test_passes_with_reuse_check(self, verifier, plan_text):
        """Plans mentioning reuse check pass."""
        result = verifier.verify_plan(plan_text)

        assert len(result.potential_duplicates) == 0


class TestArchitectureChecks:
    """Test detection of architecture concerns."""

    @pytest.fixture
    def verifier(self):
        """Create verifier instance."""
        return PlanQAVerifier()

    @pytest.mark.parametrize(
        "plan_text,expected_concern",
        [
            ("Implement O(n^2) sorting algorithm", "O(n^2)"),
            ("Use nested loop for comparison", "nested loop"),
            ("Make synchronous HTTP calls", "synchronous http"),
            ("Store unbounded array of results", "unbounded"),
            ("Watch for N+1 query issues", "N+1"),
        ],
    )
    def test_detects_architecture_concerns(self, verifier, plan_text, expected_concern):
        """Architecture concerns are detected."""
        result = verifier.verify_plan(plan_text)

        assert len(result.architecture_warnings) > 0
        assert any(
            expected_concern.lower() in w.lower() for w in result.architecture_warnings
        )

    def test_limits_warnings_to_three(self, verifier):
        """Only first 3 architecture warnings are reported."""
        plan_text = """
        Use nested loop for O(n^2) with synchronous HTTP calls
        and unbounded memory with N+1 queries and circular dependency
        """
        result = verifier.verify_plan(plan_text)

        assert len(result.architecture_warnings) <= 3


class TestConfiguration:
    """Test configuration options."""

    def test_disabled_config(self):
        """Disabled config skips all checks."""
        config = PlanQAConfig(enabled=False)
        verifier = PlanQAVerifier(config=config)
        result = verifier.verify_plan("Create function without tests")

        assert result.is_valid is True
        assert result.has_issues() is False

    def test_selective_check_tests(self):
        """Can disable test checking."""
        config = PlanQAConfig(check_tests=False)
        verifier = PlanQAVerifier(config=config)
        result = verifier.verify_plan("Create function")

        assert len(result.missing_tests) == 0

    def test_selective_check_docs(self):
        """Can disable doc checking."""
        config = PlanQAConfig(check_docs=False)
        verifier = PlanQAVerifier(config=config)
        result = verifier.verify_plan("Add API endpoint")

        assert len(result.missing_docs) == 0

    def test_selective_check_duplicates(self):
        """Can disable duplicate checking."""
        config = PlanQAConfig(check_duplicates=False)
        verifier = PlanQAVerifier(config=config)
        result = verifier.verify_plan("Create new service class")

        assert len(result.potential_duplicates) == 0

    def test_selective_check_architecture(self):
        """Can disable architecture checking."""
        config = PlanQAConfig(check_architecture=False)
        verifier = PlanQAVerifier(config=config)
        result = verifier.verify_plan("Use nested loop")

        assert len(result.architecture_warnings) == 0

    def test_strict_mode_tests(self):
        """Strict mode marks plan as invalid for missing tests."""
        config = PlanQAConfig(fail_on_missing_tests=True)
        verifier = PlanQAVerifier(config=config)
        result = verifier.verify_plan("Create function")

        assert result.is_valid is False

    def test_strict_mode_docs(self):
        """Strict mode marks plan as invalid for missing docs."""
        config = PlanQAConfig(fail_on_missing_docs=True)
        verifier = PlanQAVerifier(config=config)
        result = verifier.verify_plan("Add API endpoint")

        assert result.is_valid is False

    def test_warn_mode_keeps_valid(self):
        """Warn mode (default) keeps plan valid despite issues."""
        config = PlanQAConfig(fail_on_missing_tests=False)
        verifier = PlanQAVerifier(config=config)
        result = verifier.verify_plan("Create function")

        assert result.is_valid is True
        assert result.has_issues() is True


class TestSuggestions:
    """Test suggestion generation."""

    @pytest.fixture
    def verifier(self):
        """Create verifier instance."""
        return PlanQAVerifier()

    def test_suggests_test_task(self, verifier):
        """Suggests adding test task when missing."""
        result = verifier.verify_plan("Create new service class")

        assert any("test" in s.lower() for s in result.suggestions)

    def test_suggests_doc_task(self, verifier):
        """Suggests adding doc task when missing."""
        result = verifier.verify_plan("Add API endpoint")

        assert any("documentation" in s.lower() for s in result.suggestions)

    def test_suggests_duplicate_check(self, verifier):
        """Suggests duplicate check when missing."""
        result = verifier.verify_plan("Create new AuthService")

        assert any("search_similar" in s.lower() for s in result.suggestions)


class TestPerformance:
    """Test performance requirements."""

    @pytest.fixture
    def verifier(self):
        """Create verifier instance."""
        return PlanQAVerifier()

    def test_verification_under_50ms(self, verifier):
        """Verification completes in <50ms."""
        # Large plan text
        plan_text = "\n".join(
            [f"{i}. Task {i}: Implement feature {i}" for i in range(100)]
        )
        result = verifier.verify_plan(plan_text)

        assert result.verification_time_ms < 50

    def test_verification_time_tracked(self, verifier):
        """Verification time is recorded."""
        result = verifier.verify_plan("Create a function")

        assert result.verification_time_ms > 0


class TestConvenienceFunction:
    """Test the convenience function."""

    def test_verify_plan_qa_basic(self):
        """verify_plan_qa function works."""
        result = verify_plan_qa("Create new function")

        assert isinstance(result, PlanQAResult)
        assert result.has_issues() is True

    def test_verify_plan_qa_with_config(self):
        """verify_plan_qa accepts config."""
        config = PlanQAConfig(check_tests=False)
        result = verify_plan_qa("Create new function", config=config)

        assert len(result.missing_tests) == 0

    def test_verify_plan_qa_passing_plan(self):
        """verify_plan_qa for passing plan."""
        plan_text = """
        1. Create service (verified no existing implementation)
        2. Add unit tests
        3. Update documentation
        """
        result = verify_plan_qa(plan_text)

        assert not result.has_issues()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def verifier(self):
        """Create verifier instance."""
        return PlanQAVerifier()

    def test_empty_plan(self, verifier):
        """Empty plan has no issues."""
        result = verifier.verify_plan("")

        assert result.is_valid is True
        assert not result.has_issues()

    def test_whitespace_plan(self, verifier):
        """Whitespace-only plan has no issues."""
        result = verifier.verify_plan("   \n\t\n   ")

        assert result.is_valid is True
        assert not result.has_issues()

    def test_case_insensitive_detection(self, verifier):
        """Detection is case insensitive."""
        result1 = verifier.verify_plan("CREATE FUNCTION")
        result2 = verifier.verify_plan("create function")
        result3 = verifier.verify_plan("Create Function")

        assert result1.has_issues()
        assert result2.has_issues()
        assert result3.has_issues()

    def test_multiline_plan(self, verifier):
        """Multiline plan is processed correctly."""
        plan_text = """
        ## Implementation Plan

        ### Phase 1: Core Development
        1. Create AuthService class
        2. Implement login method

        ### Phase 2: Testing
        3. Add unit tests
        4. Add integration tests
        """
        result = verifier.verify_plan(plan_text)

        # Has test tasks, should pass test check
        assert len(result.missing_tests) == 0

    def test_special_characters(self, verifier):
        """Special characters don't break detection."""
        plan_text = "1. Create `UserService` class with @decorator"
        result = verifier.verify_plan(plan_text)

        assert result.has_issues()
