"""
Plan Mode context injection for Claude Code Memory.

This package provides components for injecting planning guidelines and
exploration hints when Claude Code enters Plan Mode.

Milestone 7.2: Hook Infrastructure Extension

Components:
- PlanningGuidelinesGenerator: Generates planning quality guidelines
- ExplorationHintsGenerator: Extracts entities and generates MCP hints
- PlanContextInjector: Coordinates injection into prompt context

Usage:
    from claude_indexer.hooks.planning import inject_plan_context

    result = inject_plan_context(
        prompt="Implement user authentication",
        collection_name="my-project",
    )
    if result.success:
        print(result.injected_text)
"""

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
from .injector import (
    PlanContextInjectionConfig,
    PlanContextInjectionResult,
    PlanContextInjector,
    inject_plan_context,
)

__all__ = [
    # Guidelines
    "PlanningGuidelines",
    "PlanningGuidelinesConfig",
    "PlanningGuidelinesGenerator",
    # Exploration
    "ExplorationHints",
    "ExplorationHintsConfig",
    "ExplorationHintsGenerator",
    # Injector
    "PlanContextInjectionConfig",
    "PlanContextInjectionResult",
    "PlanContextInjector",
    "inject_plan_context",
]
