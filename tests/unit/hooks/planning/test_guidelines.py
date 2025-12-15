"""Unit tests for planning guidelines generator.

Milestone 7.2: Hook Infrastructure Extension
"""

from claude_indexer.hooks.planning.guidelines import (
    PlanningGuidelines,
    PlanningGuidelinesConfig,
    PlanningGuidelinesGenerator,
)


class TestPlanningGuidelinesConfig:
    """Test PlanningGuidelinesConfig dataclass."""

    def test_default_config(self):
        """Default config should enable all sections."""
        config = PlanningGuidelinesConfig()

        assert config.enabled is True
        assert config.include_code_reuse_check is True
        assert config.include_testing_requirements is True
        assert config.include_documentation_requirements is True
        assert config.include_architecture_alignment is True
        assert config.include_performance_considerations is True
        assert config.custom_guidelines == []

    def test_to_dict(self):
        """Config should serialize to dictionary."""
        config = PlanningGuidelinesConfig(
            include_testing_requirements=False,
            custom_guidelines=["Custom guideline"],
        )

        data = config.to_dict()

        assert data["enabled"] is True
        assert data["include_testing_requirements"] is False
        assert data["custom_guidelines"] == ["Custom guideline"]

    def test_from_dict(self):
        """Config should deserialize from dictionary."""
        data = {
            "enabled": False,
            "include_code_reuse_check": False,
            "custom_guidelines": ["Test guideline"],
        }

        config = PlanningGuidelinesConfig.from_dict(data)

        assert config.enabled is False
        assert config.include_code_reuse_check is False
        assert config.custom_guidelines == ["Test guideline"]


class TestPlanningGuidelinesGenerator:
    """Test planning guidelines generation."""

    def test_generates_guidelines(self):
        """Generator should produce guidelines."""
        generator = PlanningGuidelinesGenerator(collection_name="test-project")
        guidelines = generator.generate()

        assert isinstance(guidelines, PlanningGuidelines)
        assert len(guidelines.full_text) > 0
        assert "PLANNING QUALITY GUIDELINES" in guidelines.full_text

    def test_includes_mcp_prefix(self):
        """Guidelines should include correct MCP prefix."""
        generator = PlanningGuidelinesGenerator(collection_name="my-project")
        guidelines = generator.generate()

        assert "mcp__my-project-memory__" in guidelines.full_text

    def test_includes_all_sections_by_default(self):
        """Default config should include all 5 sections."""
        generator = PlanningGuidelinesGenerator(collection_name="test")
        guidelines = generator.generate()

        assert "Code Reuse Check" in guidelines.full_text
        assert "Testing Requirements" in guidelines.full_text
        assert "Documentation Requirements" in guidelines.full_text
        assert "Architecture Alignment" in guidelines.full_text
        assert "Performance Considerations" in guidelines.full_text

    def test_config_disables_sections(self):
        """Configuration should disable specific sections."""
        config = PlanningGuidelinesConfig(
            include_testing_requirements=False,
            include_documentation_requirements=False,
        )
        generator = PlanningGuidelinesGenerator(
            collection_name="test",
            config=config,
        )
        guidelines = generator.generate()

        assert "Testing Requirements" not in guidelines.full_text
        assert "Documentation Requirements" not in guidelines.full_text
        # Other sections should still be present
        assert "Code Reuse Check" in guidelines.full_text

    def test_generation_latency_under_20ms(self):
        """Generation should complete in under 20ms."""
        generator = PlanningGuidelinesGenerator(collection_name="test")
        guidelines = generator.generate()

        assert guidelines.generation_time_ms < 20

    def test_generates_mcp_commands(self):
        """Should generate MCP commands list."""
        generator = PlanningGuidelinesGenerator(collection_name="test")
        guidelines = generator.generate()

        assert len(guidelines.mcp_commands) > 0
        assert any("search_similar" in cmd for cmd in guidelines.mcp_commands)
        assert any("read_graph" in cmd for cmd in guidelines.mcp_commands)

    def test_sections_dict_populated(self):
        """Should populate sections dictionary."""
        generator = PlanningGuidelinesGenerator(collection_name="test")
        guidelines = generator.generate()

        assert "code_reuse" in guidelines.sections
        assert "testing" in guidelines.sections
        assert "documentation" in guidelines.sections
        assert "architecture" in guidelines.sections
        assert "performance" in guidelines.sections

    def test_custom_guidelines_included(self):
        """Custom guidelines should be included."""
        config = PlanningGuidelinesConfig(
            custom_guidelines=["Always use TypeScript", "Follow SOLID principles"],
        )
        generator = PlanningGuidelinesGenerator(collection_name="test", config=config)
        guidelines = generator.generate()

        assert "Always use TypeScript" in guidelines.full_text
        assert "Follow SOLID principles" in guidelines.full_text

    def test_loads_project_patterns(self, tmp_path):
        """Should load patterns from CLAUDE.md if present."""
        # Create test CLAUDE.md
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            """
# Project Guidelines

## Code Style
- Use snake_case for functions
- Use PascalCase for classes
- Always add docstrings
        """
        )

        generator = PlanningGuidelinesGenerator(
            collection_name="test",
            project_path=tmp_path,
        )
        guidelines = generator.generate()

        assert len(guidelines.project_patterns) > 0
        assert any("snake_case" in p for p in guidelines.project_patterns)

    def test_handles_missing_claude_md(self, tmp_path):
        """Should handle missing CLAUDE.md gracefully."""
        generator = PlanningGuidelinesGenerator(
            collection_name="test",
            project_path=tmp_path,
        )
        guidelines = generator.generate()

        # Should still generate guidelines
        assert "PLANNING QUALITY GUIDELINES" in guidelines.full_text
        # Should indicate no patterns found
        assert "No project patterns detected" in guidelines.full_text

    def test_compact_mode(self):
        """Compact mode should produce shorter output."""
        generator = PlanningGuidelinesGenerator(collection_name="test")
        compact = generator.generate_compact()

        # Compact should be much shorter than full
        full = generator.generate()
        assert len(compact) < len(full.full_text)
        assert "[Planning Mode]" in compact
        assert "search_similar" in compact

    def test_to_dict(self):
        """Guidelines should serialize to dictionary."""
        generator = PlanningGuidelinesGenerator(collection_name="test")
        guidelines = generator.generate()

        data = guidelines.to_dict()

        assert "full_text_length" in data
        assert "sections" in data
        assert "mcp_commands_count" in data
        assert "generation_time_ms" in data


class TestGuidelinesIntegration:
    """Integration tests for guidelines generation."""

    def test_end_to_end_generation(self, tmp_path):
        """Test complete guidelines generation workflow."""
        # Create project structure
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            """
## Architecture
- Use repository pattern for data access
- Implement dependency injection
        """
        )

        config = PlanningGuidelinesConfig(
            include_code_reuse_check=True,
            include_testing_requirements=True,
        )

        generator = PlanningGuidelinesGenerator(
            collection_name="integration-test",
            project_path=tmp_path,
            config=config,
        )

        guidelines = generator.generate()

        # Verify structure
        assert guidelines.full_text.startswith("\n=== PLANNING QUALITY GUIDELINES ===")
        assert guidelines.full_text.endswith("=== END PLANNING GUIDELINES ===\n")

        # Verify MCP prefix
        assert "mcp__integration-test-memory__" in guidelines.full_text

        # Verify patterns loaded
        assert any("repository pattern" in p for p in guidelines.project_patterns)

        # Verify performance
        assert guidelines.generation_time_ms < 20
