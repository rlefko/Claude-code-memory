"""
Plan context injector for Plan Mode.

Coordinates guidelines and exploration hints generation, and
manages injection into the prompt handler context.

This is the main entry point for Plan Mode context injection.

Performance target: <50ms total injection time

Milestone 7.2: Hook Infrastructure Extension
Milestone 12.2: QA Integration Points
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .exploration import (
    ExplorationHints,
    ExplorationHintsConfig,
    ExplorationHintsGenerator,
)
from .guidelines import (
    PlanningGuidelines,
    PlanningGuidelinesConfig,
    PlanningGuidelinesGenerator,
)

if TYPE_CHECKING:
    from claude_indexer.hooks.plan_qa import PlanQAConfig, PlanQAResult


@dataclass
class PlanContextInjectionConfig:
    """Configuration for plan context injection.

    Attributes:
        enabled: Whether injection is enabled
        guidelines_config: Configuration for guidelines generator
        hints_config: Configuration for hints generator
        inject_guidelines: Whether to inject planning guidelines
        inject_hints: Whether to inject exploration hints
        compact_mode: Use abbreviated guidelines for low-latency
        qa_enabled: Whether Plan QA verification is enabled (Milestone 12.2)
        qa_config: Configuration for Plan QA verification
    """

    enabled: bool = True
    guidelines_config: PlanningGuidelinesConfig = field(
        default_factory=PlanningGuidelinesConfig
    )
    hints_config: ExplorationHintsConfig = field(default_factory=ExplorationHintsConfig)
    inject_guidelines: bool = True
    inject_hints: bool = True
    compact_mode: bool = False
    qa_enabled: bool = True
    qa_config: "PlanQAConfig | None" = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "enabled": self.enabled,
            "guidelines_config": self.guidelines_config.to_dict(),
            "hints_config": self.hints_config.to_dict(),
            "inject_guidelines": self.inject_guidelines,
            "inject_hints": self.inject_hints,
            "compact_mode": self.compact_mode,
            "qa_enabled": self.qa_enabled,
        }
        if self.qa_config is not None:
            result["qa_config"] = self.qa_config.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanContextInjectionConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            PlanContextInjectionConfig instance
        """
        guidelines_data = data.get("guidelines", data.get("guidelines_config", {}))
        hints_data = data.get("hints", data.get("hints_config", {}))

        # Handle qa_config if present
        qa_config = None
        qa_config_data = data.get("qa_config")
        if qa_config_data:
            from claude_indexer.hooks.plan_qa import PlanQAConfig

            qa_config = PlanQAConfig.from_dict(qa_config_data)

        return cls(
            enabled=data.get("enabled", True),
            guidelines_config=PlanningGuidelinesConfig.from_dict(guidelines_data),
            hints_config=ExplorationHintsConfig.from_dict(hints_data),
            inject_guidelines=data.get("inject_guidelines", True),
            inject_hints=data.get("inject_hints", True),
            compact_mode=data.get("compact_mode", False),
            qa_enabled=data.get("qa_enabled", True),
            qa_config=qa_config,
        )


@dataclass
class PlanContextInjectionResult:
    """Result of plan context injection.

    Attributes:
        success: Whether injection succeeded
        injected_text: Complete text to inject
        guidelines: Generated guidelines (if any)
        hints: Generated hints (if any)
        total_time_ms: Total injection time
        error: Error message if failed
    """

    success: bool = True
    injected_text: str = ""
    guidelines: PlanningGuidelines | None = None
    hints: ExplorationHints | None = None
    total_time_ms: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "injected_text_length": len(self.injected_text),
            "guidelines_generated": self.guidelines is not None,
            "hints_generated": self.hints is not None,
            "total_time_ms": round(self.total_time_ms, 2),
            "error": self.error,
        }


class PlanContextInjector:
    """Coordinates Plan Mode context injection.

    This class is the main entry point for Plan Mode context injection.
    It coordinates the guidelines generator and exploration hints generator,
    assembles the final injection text, and tracks timing.

    Example:
        injector = PlanContextInjector(
            collection_name="my-project",
            project_path=Path("/path/to/project"),
        )
        result = injector.inject("Implement user authentication")
        if result.success:
            print(result.injected_text)
    """

    def __init__(
        self,
        collection_name: str,
        project_path: Path | None = None,
        config: PlanContextInjectionConfig | None = None,
    ):
        """Initialize the injector.

        Args:
            collection_name: Qdrant collection name for MCP prefix
            project_path: Optional project path for loading patterns
            config: Optional configuration
        """
        self.collection_name = collection_name
        self.project_path = project_path or Path.cwd()
        self.config = config or PlanContextInjectionConfig()

        # Initialize sub-generators
        self._guidelines_generator = PlanningGuidelinesGenerator(
            collection_name=collection_name,
            project_path=self.project_path,
            config=self.config.guidelines_config,
        )
        self._hints_generator = ExplorationHintsGenerator(
            collection_name=collection_name,
            config=self.config.hints_config,
        )

    def inject(self, prompt: str) -> PlanContextInjectionResult:
        """Generate and inject Plan Mode context.

        Args:
            prompt: User's prompt text

        Returns:
            PlanContextInjectionResult with injected text and metadata
        """
        if not self.config.enabled:
            return PlanContextInjectionResult(
                success=True,
                injected_text="",
            )

        start_time = time.time()
        result = PlanContextInjectionResult()

        try:
            parts: list[str] = []

            # Generate guidelines
            if self.config.inject_guidelines:
                result.guidelines = self._guidelines_generator.generate()
                if self.config.compact_mode:
                    parts.append(self._guidelines_generator.generate_compact())
                else:
                    parts.append(result.guidelines.full_text)

            # Generate exploration hints
            if self.config.inject_hints:
                result.hints = self._hints_generator.generate(prompt)
                hints_text = result.hints.format_for_injection()
                if hints_text:
                    parts.append(hints_text)

            # Assemble final text
            result.injected_text = "\n".join(filter(None, parts))
            result.success = True

        except Exception as e:
            result.success = False
            result.error = str(e)

        result.total_time_ms = (time.time() - start_time) * 1000
        return result

    def verify_plan_output(self, plan_text: str) -> "PlanQAResult":
        """Verify plan output quality (Milestone 12.2).

        This method is called after plan generation to verify quality.
        It checks for missing tests, documentation, duplicate verification,
        and architecture concerns.

        Args:
            plan_text: Generated plan text to verify

        Returns:
            PlanQAResult with verification outcome
        """
        from claude_indexer.hooks.plan_qa import (
            PlanQAConfig,
            PlanQAResult,
            PlanQAVerifier,
        )

        if not self.config.qa_enabled:
            return PlanQAResult(is_valid=True)

        qa_config = self.config.qa_config or PlanQAConfig()
        verifier = PlanQAVerifier(config=qa_config)
        return verifier.verify_plan(plan_text)


def inject_plan_context(
    prompt: str,
    collection_name: str,
    project_path: Path | None = None,
    config: PlanContextInjectionConfig | None = None,
) -> PlanContextInjectionResult:
    """Convenience function for Plan Mode context injection.

    This is the main entry point for the hook integration.

    Args:
        prompt: User's prompt text
        collection_name: Qdrant collection name
        project_path: Optional project path
        config: Optional configuration

    Returns:
        PlanContextInjectionResult with injected text
    """
    injector = PlanContextInjector(
        collection_name=collection_name,
        project_path=project_path,
        config=config,
    )
    return injector.inject(prompt)
