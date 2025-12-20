"""
Planning guidelines generator for Plan Mode.

Generates contextual planning guidelines for injection into Claude's context.
These guidelines help Claude produce implementation plans that are thorough,
context-aware, and aligned with project best practices.

Performance target: <20ms generation time

Milestone 7.2: Hook Infrastructure Extension
"""

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Module-level cache for project patterns (keyed by path and mtime)
_pattern_cache: dict[tuple[str, float], list[str]] = {}
_MAX_PATTERN_CACHE_SIZE = 32


@dataclass
class PlanningGuidelinesConfig:
    """Configuration for planning guidelines generation.

    Attributes:
        enabled: Whether guidelines generation is enabled
        include_code_reuse_check: Include code reuse verification section
        include_testing_requirements: Include testing requirements section
        include_documentation_requirements: Include documentation section
        include_architecture_alignment: Include architecture alignment section
        include_performance_considerations: Include performance section
        custom_guidelines: Additional custom guidelines to append
        project_patterns_path: Path to CLAUDE.md for project patterns
    """

    enabled: bool = True
    include_code_reuse_check: bool = True
    include_testing_requirements: bool = True
    include_documentation_requirements: bool = True
    include_architecture_alignment: bool = True
    include_performance_considerations: bool = True
    custom_guidelines: list[str] = field(default_factory=list)
    project_patterns_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "enabled": self.enabled,
            "include_code_reuse_check": self.include_code_reuse_check,
            "include_testing_requirements": self.include_testing_requirements,
            "include_documentation_requirements": (
                self.include_documentation_requirements
            ),
            "include_architecture_alignment": self.include_architecture_alignment,
            "include_performance_considerations": (
                self.include_performance_considerations
            ),
            "custom_guidelines": self.custom_guidelines,
            "project_patterns_path": self.project_patterns_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanningGuidelinesConfig":
        """Create from dictionary."""
        return cls(
            enabled=data.get("enabled", True),
            include_code_reuse_check=data.get("include_code_reuse_check", True),
            include_testing_requirements=data.get("include_testing_requirements", True),
            include_documentation_requirements=data.get(
                "include_documentation_requirements", True
            ),
            include_architecture_alignment=data.get(
                "include_architecture_alignment", True
            ),
            include_performance_considerations=data.get(
                "include_performance_considerations", True
            ),
            custom_guidelines=data.get("custom_guidelines", []),
            project_patterns_path=data.get("project_patterns_path"),
        )


@dataclass
class PlanningGuidelines:
    """Generated planning guidelines.

    Attributes:
        full_text: Complete guidelines text for injection
        sections: Dictionary of section_name -> section_content
        mcp_commands: Pre-built MCP commands for reference
        project_patterns: Patterns extracted from CLAUDE.md
        generation_time_ms: Time taken for generation
    """

    full_text: str
    sections: dict[str, str] = field(default_factory=dict)
    mcp_commands: list[str] = field(default_factory=list)
    project_patterns: list[str] = field(default_factory=list)
    generation_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "full_text_length": len(self.full_text),
            "sections": list(self.sections.keys()),
            "mcp_commands_count": len(self.mcp_commands),
            "project_patterns_count": len(self.project_patterns),
            "generation_time_ms": round(self.generation_time_ms, 2),
        }


class PlanningGuidelinesGenerator:
    """Generates planning guidelines for Plan Mode injection.

    Guidelines are structured into sections:
    1. Code Reuse Check - Search memory before implementing
    2. Testing Requirements - Include test tasks
    3. Documentation Requirements - Include doc tasks
    4. Architecture Alignment - Follow project patterns
    5. Performance Considerations - Flag anti-patterns

    Example:
        generator = PlanningGuidelinesGenerator(
            collection_name="my-project",
            project_path=Path("/path/to/project"),
        )
        guidelines = generator.generate()
        print(guidelines.full_text)
    """

    # Template sections (from MILESTONES.md lines 866-901)
    # fmt: off
    CODE_REUSE_TEMPLATE = """## 1. Code Reuse Check (CRITICAL)
Before proposing ANY new function, class, or component:
- Search the codebase: `{mcp_prefix}search_similar("functionality")`
- Check existing patterns: `{mcp_prefix}read_graph(entity="ComponentName", mode="smart")`
- If similar exists, plan to REUSE or EXTEND it
- State explicitly: "Verified no existing implementation" or "Will extend existing Y"

**read_graph tips:**
- ALWAYS use `entity="Name"` for focused results (10-20 items vs 300+ unfiltered)
- Test code is filtered by default; use `includeTests=true` to include tests
- Use `mode="smart"` for AI summary, `mode="relationships"` for raw connections
"""  # noqa: E501
    # fmt: on

    TESTING_TEMPLATE = """## 2. Testing Requirements
Every plan that modifies code MUST include:
- [ ] Unit tests for new/modified functions
- [ ] Integration tests for API changes
- Task format: "Add tests for [feature] in [test_file]"
"""

    DOCUMENTATION_TEMPLATE = """## 3. Documentation Requirements
Include documentation tasks when:
- Adding public APIs -> Update API docs
- Changing user-facing behavior -> Update README
- Adding configuration -> Update config docs
"""

    ARCHITECTURE_TEMPLATE = """## 4. Architecture Alignment
Your plan MUST align with project patterns:
{project_patterns}
"""

    PERFORMANCE_TEMPLATE = """## 5. Performance Considerations
Flag any step that may introduce:
- O(n^2) or worse complexity
- Unbounded memory usage
- Missing timeouts on network calls
"""

    # Patterns for extracting guidelines from CLAUDE.md
    PATTERN_SECTIONS = [
        re.compile(
            r"(?:Code\s*Style|Patterns?|Conventions?|Architecture)[^\n]*\n"
            r"((?:[-*]\s+[^\n]+\n?)+)",
            re.IGNORECASE | re.MULTILINE,
        ),
        re.compile(
            r"##\s*(?:Guidelines|Rules|Standards)[^\n]*\n((?:[-*]\s+[^\n]+\n?)+)",
            re.IGNORECASE | re.MULTILINE,
        ),
    ]

    def __init__(
        self,
        collection_name: str,
        project_path: Path | None = None,
        config: PlanningGuidelinesConfig | None = None,
    ):
        """Initialize guidelines generator.

        Args:
            collection_name: Qdrant collection name for MCP prefix
            project_path: Optional project path for loading CLAUDE.md
            config: Optional configuration
        """
        self.collection_name = collection_name
        self.project_path = project_path or Path.cwd()
        self.config = config or PlanningGuidelinesConfig()
        self._mcp_prefix = f"mcp__{collection_name}-memory__"

    def generate(self) -> PlanningGuidelines:
        """Generate planning guidelines.

        Returns:
            PlanningGuidelines with full text and structured sections
        """
        start_time = time.perf_counter()

        sections: dict[str, str] = {}
        mcp_commands: list[str] = []

        if self.config.include_code_reuse_check:
            sections["code_reuse"] = self._render_code_reuse_section()
            mcp_commands.extend(
                [
                    f'{self._mcp_prefix}search_similar("query")',
                    f'{self._mcp_prefix}read_graph(entity="Name", mode="relations")',
                ]
            )

        if self.config.include_testing_requirements:
            sections["testing"] = self.TESTING_TEMPLATE

        if self.config.include_documentation_requirements:
            sections["documentation"] = self.DOCUMENTATION_TEMPLATE

        project_patterns = self._load_project_patterns()
        if self.config.include_architecture_alignment:
            sections["architecture"] = self._render_architecture_section(
                project_patterns
            )

        if self.config.include_performance_considerations:
            sections["performance"] = self.PERFORMANCE_TEMPLATE

        # Add custom guidelines
        for i, custom in enumerate(self.config.custom_guidelines):
            sections[f"custom_{i}"] = custom

        # Assemble full text
        full_text = self._assemble_full_text(sections)

        generation_time_ms = (time.perf_counter() - start_time) * 1000

        return PlanningGuidelines(
            full_text=full_text,
            sections=sections,
            mcp_commands=mcp_commands,
            project_patterns=project_patterns,
            generation_time_ms=generation_time_ms,
        )

    def _render_code_reuse_section(self) -> str:
        """Render code reuse section with MCP prefix."""
        return self.CODE_REUSE_TEMPLATE.format(mcp_prefix=self._mcp_prefix)

    def _render_architecture_section(self, patterns: list[str]) -> str:
        """Render architecture section with project patterns."""
        if patterns:
            pattern_text = "\n".join(f"- {p}" for p in patterns)
        else:
            pattern_text = "- (No project patterns detected - check for CLAUDE.md)"
        return self.ARCHITECTURE_TEMPLATE.format(project_patterns=pattern_text)

    def _load_project_patterns(self) -> list[str]:
        """Load project patterns from CLAUDE.md if available.

        Searches for CLAUDE.md in:
        1. Project root
        2. .claude/ directory

        Uses caching based on file path and modification time for performance.

        Returns:
            List of extracted patterns (max 10)
        """
        # Check custom path first
        if self.config.project_patterns_path:
            custom_path = Path(self.config.project_patterns_path)
            patterns = self._load_patterns_from_file(custom_path)
            if patterns:
                return patterns

        # Standard locations
        claude_md_paths = [
            self.project_path / "CLAUDE.md",
            self.project_path / ".claude" / "CLAUDE.md",
        ]

        for path in claude_md_paths:
            patterns = self._load_patterns_from_file(path)
            if patterns:
                return patterns

        return []

    def _load_patterns_from_file(self, path: Path) -> list[str]:
        """Load patterns from a specific file with caching.

        Args:
            path: Path to the file to load

        Returns:
            List of extracted patterns, or empty list if file doesn't exist
        """
        if not path.exists():
            return []

        try:
            # Get file modification time for cache key
            mtime = path.stat().st_mtime
            cache_key = (str(path.absolute()), mtime)

            # Check cache
            if cache_key in _pattern_cache:
                return _pattern_cache[cache_key]

            # Load and extract patterns
            content = path.read_text()
            patterns = self._extract_patterns(content)

            # Store in cache (with size limit)
            if len(_pattern_cache) >= _MAX_PATTERN_CACHE_SIZE:
                # Remove oldest entry (simple LRU)
                oldest_key = next(iter(_pattern_cache))
                del _pattern_cache[oldest_key]

            _pattern_cache[cache_key] = patterns
            return patterns

        except (OSError, UnicodeDecodeError):
            return []

    def _extract_patterns(self, content: str) -> list[str]:
        """Extract patterns from CLAUDE.md content.

        Looks for:
        - Code style guidelines
        - Architecture patterns
        - Testing conventions

        Args:
            content: CLAUDE.md file content

        Returns:
            List of extracted patterns (max 10)
        """
        patterns: list[str] = []

        for regex in self.PATTERN_SECTIONS:
            matches = regex.findall(content)
            for match in matches:
                lines = match.strip().split("\n")
                for line in lines[:5]:  # Limit to 5 patterns per section
                    cleaned = line.strip().lstrip("-*").strip()
                    if cleaned and len(cleaned) > 10:
                        patterns.append(cleaned)

        return patterns[:10]  # Limit total patterns

    def _assemble_full_text(self, sections: dict[str, str]) -> str:
        """Assemble full guidelines text with header/footer.

        Args:
            sections: Dictionary of section content

        Returns:
            Complete guidelines text
        """
        lines = [
            "",
            "=== PLANNING QUALITY GUIDELINES ===",
            "",
            "When formulating this implementation plan, follow these guidelines:",
            "",
        ]

        for section_content in sections.values():
            lines.append(section_content.strip())
            lines.append("")

        lines.append("=== END PLANNING GUIDELINES ===")
        lines.append("")

        return "\n".join(lines)

    def generate_compact(self) -> str:
        """Generate compact version of guidelines for low-latency scenarios.

        Returns:
            Abbreviated guidelines text
        """
        return f"""[Planning Mode] Remember:
- Search before implementing: {self._mcp_prefix}search_similar("feature")
- Use entity-specific read_graph: {self._mcp_prefix}read_graph(entity="Name", mode="smart")
- Test code filtered by default (includeTests=true to include)
- Include test tasks for new code
- Include doc tasks for user-facing changes
"""
