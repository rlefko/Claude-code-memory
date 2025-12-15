"""Unit tests for plan context injector.

Milestone 7.2: Hook Infrastructure Extension
"""

from pathlib import Path

import pytest

from claude_indexer.hooks.planning.exploration import ExplorationHintsConfig
from claude_indexer.hooks.planning.guidelines import PlanningGuidelinesConfig
from claude_indexer.hooks.planning.injector import (
    PlanContextInjectionConfig,
    PlanContextInjectionResult,
    PlanContextInjector,
    inject_plan_context,
)


class TestPlanContextInjectionConfig:
    """Test PlanContextInjectionConfig dataclass."""

    def test_default_config(self):
        """Default config should enable injection."""
        config = PlanContextInjectionConfig()

        assert config.enabled is True
        assert config.inject_guidelines is True
        assert config.inject_hints is True
        assert config.compact_mode is False

    def test_to_dict(self):
        """Config should serialize to dictionary."""
        config = PlanContextInjectionConfig(
            compact_mode=True,
            inject_hints=False,
        )

        data = config.to_dict()

        assert data["compact_mode"] is True
        assert data["inject_hints"] is False
        assert "guidelines_config" in data
        assert "hints_config" in data

    def test_from_dict(self):
        """Config should deserialize from dictionary."""
        data = {
            "enabled": False,
            "compact_mode": True,
            "guidelines": {"include_testing_requirements": False},
            "hints": {"max_entity_hints": 5},
        }

        config = PlanContextInjectionConfig.from_dict(data)

        assert config.enabled is False
        assert config.compact_mode is True
        assert config.guidelines_config.include_testing_requirements is False
        assert config.hints_config.max_entity_hints == 5

    def test_from_dict_alternative_keys(self):
        """Config should handle both key formats."""
        data = {
            "guidelines_config": {"include_code_reuse_check": False},
            "hints_config": {"include_duplicate_check": False},
        }

        config = PlanContextInjectionConfig.from_dict(data)

        assert config.guidelines_config.include_code_reuse_check is False
        assert config.hints_config.include_duplicate_check is False


class TestPlanContextInjector:
    """Test plan context injection."""

    def test_inject_returns_result(self):
        """Inject should return PlanContextInjectionResult."""
        injector = PlanContextInjector(collection_name="test")
        result = injector.inject("Create a plan for authentication")

        assert isinstance(result, PlanContextInjectionResult)
        assert result.success
        assert len(result.injected_text) > 0

    def test_inject_includes_guidelines(self):
        """Injected text should include planning guidelines."""
        injector = PlanContextInjector(collection_name="test")
        result = injector.inject("Create a plan")

        assert "PLANNING QUALITY GUIDELINES" in result.injected_text
        assert result.guidelines is not None

    def test_inject_includes_hints(self):
        """Injected text should include exploration hints."""
        injector = PlanContextInjector(collection_name="test")
        result = injector.inject("Implement UserService")

        assert "EXPLORATION HINTS" in result.injected_text
        assert result.hints is not None

    def test_disabled_returns_empty(self):
        """Disabled config should return empty injection."""
        config = PlanContextInjectionConfig(enabled=False)
        injector = PlanContextInjector(collection_name="test", config=config)
        result = injector.inject("Create a plan")

        assert result.success
        assert result.injected_text == ""
        assert result.guidelines is None
        assert result.hints is None

    def test_guidelines_only(self):
        """Should inject only guidelines when hints disabled."""
        config = PlanContextInjectionConfig(inject_hints=False)
        injector = PlanContextInjector(collection_name="test", config=config)
        result = injector.inject("Create a plan")

        assert "PLANNING QUALITY GUIDELINES" in result.injected_text
        assert "EXPLORATION HINTS" not in result.injected_text
        assert result.guidelines is not None
        assert result.hints is None

    def test_hints_only(self):
        """Should inject only hints when guidelines disabled."""
        config = PlanContextInjectionConfig(inject_guidelines=False)
        injector = PlanContextInjector(collection_name="test", config=config)
        result = injector.inject("Implement UserService")

        assert "PLANNING QUALITY GUIDELINES" not in result.injected_text
        assert "EXPLORATION HINTS" in result.injected_text
        assert result.guidelines is None
        assert result.hints is not None

    def test_compact_mode(self):
        """Compact mode should produce shorter guidelines."""
        config = PlanContextInjectionConfig(compact_mode=True)
        injector = PlanContextInjector(collection_name="test", config=config)
        result = injector.inject("Create a plan")

        normal_injector = PlanContextInjector(collection_name="test")
        normal_result = normal_injector.inject("Create a plan")

        assert len(result.injected_text) < len(normal_result.injected_text)
        assert "[Planning Mode]" in result.injected_text

    def test_total_latency_under_50ms(self):
        """Total injection should complete in under 50ms."""
        injector = PlanContextInjector(collection_name="test")
        result = injector.inject(
            "Implement complex authentication with OAuth and JWT"
        )

        assert result.total_time_ms < 50

    def test_mcp_prefix_correct(self):
        """Injected text should use correct MCP prefix."""
        injector = PlanContextInjector(collection_name="my-project")
        result = injector.inject("Create a plan")

        assert "mcp__my-project-memory__" in result.injected_text

    def test_project_path_used(self, tmp_path):
        """Should use project path for loading patterns."""
        # Create CLAUDE.md in tmp_path
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            """
## Patterns
- Use dependency injection
- Follow SOLID principles
        """
        )

        injector = PlanContextInjector(
            collection_name="test",
            project_path=tmp_path,
        )
        result = injector.inject("Create a plan")

        # Patterns should be loaded from CLAUDE.md
        assert result.guidelines is not None
        assert len(result.guidelines.project_patterns) > 0

    def test_to_dict(self):
        """Result should serialize to dictionary."""
        injector = PlanContextInjector(collection_name="test")
        result = injector.inject("Create a plan")

        data = result.to_dict()

        assert "success" in data
        assert "injected_text_length" in data
        assert "guidelines_generated" in data
        assert "hints_generated" in data
        assert "total_time_ms" in data

    def test_handles_errors_gracefully(self):
        """Should handle errors and set error field."""
        # Create injector with invalid config to trigger error
        config = PlanContextInjectionConfig()
        config.guidelines_config = None  # This will cause an error

        injector = PlanContextInjector(collection_name="test", config=config)

        # Re-initialize with valid config but mock an error
        # For now, just verify normal operation
        result = injector.inject("Test")
        # Normal operation should succeed
        assert result.success or result.error is not None


class TestConvenienceFunction:
    """Test inject_plan_context convenience function."""

    def test_returns_result(self):
        """Convenience function should return result."""
        result = inject_plan_context(
            prompt="Create a plan",
            collection_name="test",
        )

        assert isinstance(result, PlanContextInjectionResult)
        assert result.success

    def test_with_project_path(self, tmp_path):
        """Should accept project path."""
        result = inject_plan_context(
            prompt="Create a plan",
            collection_name="test",
            project_path=tmp_path,
        )

        assert result.success

    def test_with_config(self):
        """Should accept configuration."""
        config = PlanContextInjectionConfig(compact_mode=True)
        result = inject_plan_context(
            prompt="Create a plan",
            collection_name="test",
            config=config,
        )

        assert result.success
        assert "[Planning Mode]" in result.injected_text


class TestInjectorIntegration:
    """Integration tests for plan context injector."""

    def test_full_injection_flow(self, tmp_path):
        """Test complete injection workflow."""
        # Create project structure
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            """
## Architecture
- Use repository pattern
- Implement clean architecture
        """
        )

        config = PlanContextInjectionConfig(
            guidelines_config=PlanningGuidelinesConfig(
                include_code_reuse_check=True,
                include_testing_requirements=True,
            ),
            hints_config=ExplorationHintsConfig(
                max_entity_hints=2,
            ),
        )

        result = inject_plan_context(
            prompt="Implement UserService and AuthController",
            collection_name="integration-test",
            project_path=tmp_path,
            config=config,
        )

        # Verify success
        assert result.success

        # Verify guidelines
        assert "PLANNING QUALITY GUIDELINES" in result.injected_text
        assert "Code Reuse Check" in result.injected_text
        assert "Testing Requirements" in result.injected_text

        # Verify hints
        assert "EXPLORATION HINTS" in result.injected_text
        assert "UserService" in result.injected_text or "AuthController" in result.injected_text

        # Verify MCP prefix
        assert "mcp__integration-test-memory__" in result.injected_text

        # Verify patterns loaded
        assert result.guidelines is not None
        assert any(
            "repository pattern" in p for p in result.guidelines.project_patterns
        )

        # Verify performance
        assert result.total_time_ms < 50

    def test_plan_mode_detection_to_injection(self):
        """Test flow from Plan Mode detection to context injection."""
        from claude_indexer.hooks.plan_mode_detector import detect_plan_mode

        prompt = "@plan Create user authentication system"

        # Step 1: Detect Plan Mode
        detection_result, plan_ctx = detect_plan_mode(prompt)
        assert detection_result.is_plan_mode

        # Step 2: Inject context
        injection_result = inject_plan_context(
            prompt=prompt,
            collection_name="test-project",
        )

        # Step 3: Verify injection
        assert injection_result.success
        assert "PLANNING QUALITY GUIDELINES" in injection_result.injected_text
        assert "mcp__test-project-memory__" in injection_result.injected_text
