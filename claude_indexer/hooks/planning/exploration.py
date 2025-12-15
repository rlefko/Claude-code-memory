"""
Exploration hints generator for Plan Mode.

Generates hints to guide Claude's sub-agent parallel exploration.
These hints suggest MCP commands for:
- Duplicate checking (before implementing new code)
- Test discovery (existing test patterns)
- Documentation discovery (existing doc patterns)
- Architecture analysis (entity relationships)

Performance target: <30ms generation time

Milestone 7.2: Hook Infrastructure Extension
"""

import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any


# Module-level LRU cache for entity extraction (max 128 prompts)
@lru_cache(maxsize=128)
def _cached_extract_entities(prompt: str) -> tuple[str, ...]:
    """Cache-friendly entity extraction.

    Returns tuple for hashability (required by lru_cache).
    """
    entities: set[str] = set()

    # CamelCase
    for match in ExplorationHintsGenerator.CAMEL_CASE.findall(prompt):
        entities.add(match)

    # snake_case
    for match in ExplorationHintsGenerator.SNAKE_CASE.findall(prompt):
        entities.add(match)

    # Quoted terms (filter short ones)
    for match in ExplorationHintsGenerator.QUOTED_TERMS.findall(prompt):
        if len(match) > 2:
            entities.add(match)

    # Technical terms
    for match in ExplorationHintsGenerator.TECHNICAL_TERMS.findall(prompt):
        entities.add(match.lower())

    # Convert to tuple and limit to 10
    return tuple(list(entities)[:10])


@dataclass
class ExplorationHintsConfig:
    """Configuration for exploration hints generation.

    Attributes:
        enabled: Whether hints generation is enabled
        max_entity_hints: Maximum architecture hints per entity
        include_duplicate_check: Include duplicate checking hint
        include_test_discovery: Include test discovery hint
        include_doc_discovery: Include documentation discovery hint
        include_architecture_hints: Include entity architecture hints
    """

    enabled: bool = True
    max_entity_hints: int = 3
    include_duplicate_check: bool = True
    include_test_discovery: bool = True
    include_doc_discovery: bool = True
    include_architecture_hints: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "enabled": self.enabled,
            "max_entity_hints": self.max_entity_hints,
            "include_duplicate_check": self.include_duplicate_check,
            "include_test_discovery": self.include_test_discovery,
            "include_doc_discovery": self.include_doc_discovery,
            "include_architecture_hints": self.include_architecture_hints,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExplorationHintsConfig":
        """Create from dictionary."""
        return cls(
            enabled=data.get("enabled", True),
            max_entity_hints=data.get("max_entity_hints", 3),
            include_duplicate_check=data.get("include_duplicate_check", True),
            include_test_discovery=data.get("include_test_discovery", True),
            include_doc_discovery=data.get("include_doc_discovery", True),
            include_architecture_hints=data.get("include_architecture_hints", True),
        )


@dataclass
class ExplorationHints:
    """Generated exploration hints.

    Attributes:
        hints: List of formatted hint strings
        extracted_entities: Entities extracted from prompt
        mcp_commands: List of generated MCP commands
        generation_time_ms: Time taken for generation
    """

    hints: list[str] = field(default_factory=list)
    extracted_entities: list[str] = field(default_factory=list)
    mcp_commands: list[str] = field(default_factory=list)
    generation_time_ms: float = 0.0

    def format_for_injection(self) -> str:
        """Format hints for context injection.

        Returns:
            Formatted hints text or empty string if no hints
        """
        if not self.hints:
            return ""

        lines = [
            "",
            "=== EXPLORATION HINTS ===",
            "",
            "Consider running these queries to inform your plan:",
            "",
        ]

        for hint in self.hints:
            lines.append(hint)
            lines.append("")

        lines.append("=== END EXPLORATION HINTS ===")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "hints_count": len(self.hints),
            "extracted_entities": self.extracted_entities,
            "mcp_commands_count": len(self.mcp_commands),
            "generation_time_ms": round(self.generation_time_ms, 2),
        }


class ExplorationHintsGenerator:
    """Generates exploration hints for Plan Mode.

    Extracts entities from user prompts and generates targeted
    MCP commands to help Claude explore relevant code.

    Example:
        generator = ExplorationHintsGenerator(
            collection_name="my-project",
        )
        hints = generator.generate("Implement user authentication with OAuth")
        print(hints.format_for_injection())
    """

    # Entity extraction patterns (pre-compiled for performance)
    CAMEL_CASE = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b")
    SNAKE_CASE = re.compile(r"\b([a-z]+(?:_[a-z]+)+)\b")
    QUOTED_TERMS = re.compile(r"[\"']([^\"']+)[\"']")
    TECHNICAL_TERMS = re.compile(
        r"\b(api|auth(?:entication)?|database|service|controller|"
        r"handler|manager|provider|factory|repository|client|"
        r"validator|parser|serializer|middleware|hook|plugin|"
        r"component|module|endpoint|route|model|schema|config)\b",
        re.IGNORECASE,
    )

    def __init__(
        self,
        collection_name: str,
        config: ExplorationHintsConfig | None = None,
    ):
        """Initialize hints generator.

        Args:
            collection_name: Qdrant collection name for MCP prefix
            config: Optional configuration
        """
        self.collection_name = collection_name
        self.config = config or ExplorationHintsConfig()
        self._mcp_prefix = f"mcp__{collection_name}-memory__"

    def generate(self, prompt: str) -> ExplorationHints:
        """Generate exploration hints from user prompt.

        Args:
            prompt: User's prompt text

        Returns:
            ExplorationHints with extracted entities and suggested commands
        """
        start_time = time.perf_counter()

        entities = self._extract_entities(prompt)
        hints: list[str] = []
        mcp_commands: list[str] = []

        if self.config.include_duplicate_check and entities:
            hint, cmd = self._generate_duplicate_hint(entities[0])
            hints.append(hint)
            mcp_commands.append(cmd)

        if self.config.include_test_discovery:
            hint, cmd = self._generate_test_hint(entities)
            hints.append(hint)
            mcp_commands.append(cmd)

        if self.config.include_doc_discovery:
            hint, cmd = self._generate_doc_hint()
            hints.append(hint)
            mcp_commands.append(cmd)

        if self.config.include_architecture_hints:
            for entity in entities[: self.config.max_entity_hints]:
                hint, cmd = self._generate_architecture_hint(entity)
                hints.append(hint)
                mcp_commands.append(cmd)

        generation_time_ms = (time.perf_counter() - start_time) * 1000

        return ExplorationHints(
            hints=hints,
            extracted_entities=entities,
            mcp_commands=mcp_commands,
            generation_time_ms=generation_time_ms,
        )

    def _extract_entities(self, prompt: str) -> list[str]:
        """Extract likely code entities from prompt.

        Uses multiple patterns:
        1. CamelCase (e.g., UserService, AuthController)
        2. snake_case (e.g., user_service, auth_handler)
        3. Quoted terms (e.g., "login", 'authentication')
        4. Technical terms (e.g., api, database, middleware)

        Uses caching for repeated prompts.

        Args:
            prompt: User prompt text

        Returns:
            List of extracted entities, deduplicated and limited to 10
        """
        # Use cached extraction and convert back to list
        return list(_cached_extract_entities(prompt))

    def _generate_duplicate_hint(self, entity: str) -> tuple[str, str]:
        """Generate duplicate check hint.

        Args:
            entity: Primary entity to check for duplicates

        Returns:
            Tuple of (formatted hint, MCP command)
        """
        cmd = (
            f'{self._mcp_prefix}search_similar("{entity}", '
            f'entityTypes=["function", "class"])'
        )
        hint = f"## Duplicate Check\n{cmd}"
        return hint, cmd

    def _generate_test_hint(self, entities: list[str]) -> tuple[str, str]:
        """Generate test discovery hint.

        Args:
            entities: Extracted entities for test search

        Returns:
            Tuple of (formatted hint, MCP command)
        """
        query = entities[0] if entities else "test"
        cmd = (
            f'{self._mcp_prefix}search_similar("{query} test", '
            f'entityTypes=["file", "function"])'
        )
        hint = f"## Test Discovery\n{cmd}"
        return hint, cmd

    def _generate_doc_hint(self) -> tuple[str, str]:
        """Generate documentation discovery hint.

        Returns:
            Tuple of (formatted hint, MCP command)
        """
        cmd = (
            f'{self._mcp_prefix}search_similar("documentation README", '
            f'entityTypes=["documentation", "file"])'
        )
        hint = f"## Documentation\n{cmd}"
        return hint, cmd

    def _generate_architecture_hint(self, entity: str) -> tuple[str, str]:
        """Generate architecture analysis hint for entity.

        Args:
            entity: Entity to analyze

        Returns:
            Tuple of (formatted hint, MCP command)
        """
        cmd = f'{self._mcp_prefix}read_graph(entity="{entity}", mode="smart")'
        hint = f"## {entity} Analysis\n{cmd}"
        return hint, cmd
