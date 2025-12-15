"""Unit tests for exploration hints generator.

Milestone 7.2: Hook Infrastructure Extension
"""

import pytest

from claude_indexer.hooks.planning.exploration import (
    ExplorationHints,
    ExplorationHintsConfig,
    ExplorationHintsGenerator,
)


class TestExplorationHintsConfig:
    """Test ExplorationHintsConfig dataclass."""

    def test_default_config(self):
        """Default config should enable all hints."""
        config = ExplorationHintsConfig()

        assert config.enabled is True
        assert config.max_entity_hints == 3
        assert config.include_duplicate_check is True
        assert config.include_test_discovery is True
        assert config.include_doc_discovery is True
        assert config.include_architecture_hints is True

    def test_to_dict(self):
        """Config should serialize to dictionary."""
        config = ExplorationHintsConfig(
            max_entity_hints=5,
            include_test_discovery=False,
        )

        data = config.to_dict()

        assert data["max_entity_hints"] == 5
        assert data["include_test_discovery"] is False

    def test_from_dict(self):
        """Config should deserialize from dictionary."""
        data = {
            "enabled": False,
            "max_entity_hints": 2,
            "include_duplicate_check": False,
        }

        config = ExplorationHintsConfig.from_dict(data)

        assert config.enabled is False
        assert config.max_entity_hints == 2
        assert config.include_duplicate_check is False


class TestExplorationHintsGenerator:
    """Test exploration hints generation."""

    def test_extracts_camel_case_entities(self):
        """Should extract CamelCase entities from prompt."""
        generator = ExplorationHintsGenerator(collection_name="test")
        hints = generator.generate("Implement UserService and AuthController")

        assert "UserService" in hints.extracted_entities
        assert "AuthController" in hints.extracted_entities

    def test_extracts_snake_case_entities(self):
        """Should extract snake_case entities from prompt."""
        generator = ExplorationHintsGenerator(collection_name="test")
        hints = generator.generate("Update the user_service and auth_handler")

        assert "user_service" in hints.extracted_entities
        assert "auth_handler" in hints.extracted_entities

    def test_extracts_quoted_terms(self):
        """Should extract quoted terms from prompt."""
        generator = ExplorationHintsGenerator(collection_name="test")
        hints = generator.generate("Implement the \"login flow\" and 'logout' feature")

        assert "login flow" in hints.extracted_entities
        assert "logout" in hints.extracted_entities

    def test_extracts_technical_terms(self):
        """Should extract technical terms from prompt."""
        generator = ExplorationHintsGenerator(collection_name="test")
        hints = generator.generate("Create an API endpoint for the database service")

        assert "api" in hints.extracted_entities
        assert "database" in hints.extracted_entities
        assert "service" in hints.extracted_entities
        assert "endpoint" in hints.extracted_entities

    def test_generates_duplicate_check_hint(self):
        """Should generate duplicate check hint."""
        generator = ExplorationHintsGenerator(collection_name="test")
        hints = generator.generate("Create AuthService")

        formatted = hints.format_for_injection()
        assert "Duplicate Check" in formatted
        assert "search_similar" in formatted
        assert 'entityTypes=["function", "class"]' in formatted

    def test_generates_test_discovery_hint(self):
        """Should generate test discovery hint."""
        generator = ExplorationHintsGenerator(collection_name="test")
        hints = generator.generate("Implement new feature")

        formatted = hints.format_for_injection()
        assert "Test Discovery" in formatted
        assert "test" in formatted.lower()

    def test_generates_doc_discovery_hint(self):
        """Should generate documentation discovery hint."""
        generator = ExplorationHintsGenerator(collection_name="test")
        hints = generator.generate("Add a new module")

        formatted = hints.format_for_injection()
        assert "Documentation" in formatted
        assert "README" in formatted

    def test_generates_architecture_hints(self):
        """Should generate architecture hints for entities."""
        generator = ExplorationHintsGenerator(collection_name="test")
        hints = generator.generate("Implement UserService")

        formatted = hints.format_for_injection()
        assert "UserService Analysis" in formatted
        assert "read_graph" in formatted
        assert 'mode="smart"' in formatted

    def test_generation_latency_under_30ms(self):
        """Generation should complete in under 30ms."""
        generator = ExplorationHintsGenerator(collection_name="test")
        hints = generator.generate(
            "Implement complex authentication system with OAuth and JWT"
        )

        assert hints.generation_time_ms < 30

    def test_config_limits_entity_hints(self):
        """Configuration should limit number of entity hints."""
        config = ExplorationHintsConfig(max_entity_hints=1)
        generator = ExplorationHintsGenerator(collection_name="test", config=config)
        hints = generator.generate("Create UserService AuthController SessionManager")

        # Count architecture hints (one per entity)
        arch_hints = [h for h in hints.hints if "Analysis" in h]
        assert len(arch_hints) <= 1

    def test_config_disables_hints(self):
        """Configuration should disable specific hints."""
        config = ExplorationHintsConfig(
            include_test_discovery=False,
            include_doc_discovery=False,
        )
        generator = ExplorationHintsGenerator(collection_name="test", config=config)
        # Use a prompt with an entity so duplicate check can be generated
        hints = generator.generate("Create UserService feature")

        formatted = hints.format_for_injection()
        assert "Test Discovery" not in formatted
        assert "Documentation" not in formatted
        # Duplicate check should still be present (since we have an entity)
        assert "Duplicate Check" in formatted

    def test_mcp_prefix_correct(self):
        """MCP commands should use correct collection prefix."""
        generator = ExplorationHintsGenerator(collection_name="my-project")
        hints = generator.generate("Implement AuthService")

        for cmd in hints.mcp_commands:
            assert "mcp__my-project-memory__" in cmd

    def test_format_for_injection_empty(self):
        """Empty hints should return empty string."""
        config = ExplorationHintsConfig(
            include_duplicate_check=False,
            include_test_discovery=False,
            include_doc_discovery=False,
            include_architecture_hints=False,
        )
        generator = ExplorationHintsGenerator(collection_name="test", config=config)
        hints = generator.generate("Some prompt")

        assert hints.format_for_injection() == ""

    def test_format_for_injection_structure(self):
        """Formatted output should have correct structure."""
        generator = ExplorationHintsGenerator(collection_name="test")
        hints = generator.generate("Create UserService")

        formatted = hints.format_for_injection()
        assert formatted.startswith("\n=== EXPLORATION HINTS ===")
        assert formatted.endswith("=== END EXPLORATION HINTS ===")
        assert "Consider running these queries" in formatted

    def test_to_dict(self):
        """Hints should serialize to dictionary."""
        generator = ExplorationHintsGenerator(collection_name="test")
        hints = generator.generate("Create AuthService")

        data = hints.to_dict()

        assert "hints_count" in data
        assert "extracted_entities" in data
        assert "mcp_commands_count" in data
        assert "generation_time_ms" in data

    def test_entity_extraction_limit(self):
        """Should limit extracted entities to 10."""
        generator = ExplorationHintsGenerator(collection_name="test")
        # Prompt with many potential entities
        prompt = (
            "Implement UserService AuthService PaymentService "
            "OrderService CartService ProductService "
            "InventoryService ShippingService NotificationService "
            "AnalyticsService ReportingService DashboardService "
            "user_handler auth_handler payment_handler"
        )
        hints = generator.generate(prompt)

        assert len(hints.extracted_entities) <= 10


class TestExplorationHintsIntegration:
    """Integration tests for exploration hints."""

    def test_end_to_end_generation(self):
        """Test complete hints generation workflow."""
        config = ExplorationHintsConfig(
            max_entity_hints=2,
            include_duplicate_check=True,
            include_test_discovery=True,
            include_doc_discovery=True,
            include_architecture_hints=True,
        )

        generator = ExplorationHintsGenerator(
            collection_name="integration-test",
            config=config,
        )

        hints = generator.generate("Implement UserService and auth_handler")

        # Verify extraction
        assert "UserService" in hints.extracted_entities
        assert "auth_handler" in hints.extracted_entities

        # Verify hints generated
        assert len(hints.hints) > 0

        # Verify MCP commands
        assert all(
            "mcp__integration-test-memory__" in cmd for cmd in hints.mcp_commands
        )

        # Verify formatting
        formatted = hints.format_for_injection()
        assert "=== EXPLORATION HINTS ===" in formatted

        # Verify performance
        assert hints.generation_time_ms < 30
