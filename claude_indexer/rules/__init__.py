"""
Code Quality Rule Engine for Claude Code Memory.

This package provides a comprehensive rule engine for detecting
code quality issues including security vulnerabilities, tech debt,
resilience problems, documentation gaps, and git safety concerns.

Example usage:
    from claude_indexer.rules import RuleEngine, RuleContext, Trigger

    # Create and configure engine
    engine = RuleEngine()
    engine.load_rules()

    # Create context from file
    context = RuleContext.from_file(Path("my_file.py"))

    # Run rules
    result = engine.run(context, trigger=Trigger.ON_STOP)

    # Check results
    if result.should_block():
        print(f"Found {len(result.findings)} blocking issues")
"""

from .base import (
    BaseRule,
    DiffHunk,
    Evidence,
    Finding,
    RuleContext,
    Severity,
    Trigger,
)
from .config import (
    CategoryConfig,
    PerformanceConfig,
    RuleConfig,
    RuleEngineConfig,
    RuleEngineConfigLoader,
    get_default_config,
)
from .discovery import RuleDiscovery, discover_rules
from .engine import (
    RuleEngine,
    RuleEngineResult,
    RuleError,
    RuleExecutionResult,
    create_rule_engine,
)
from .fix import AutoFix, apply_fixes

__all__ = [
    # Base types
    "Severity",
    "Trigger",
    "DiffHunk",
    "Evidence",
    "Finding",
    "RuleContext",
    "BaseRule",
    # Fix types
    "AutoFix",
    "apply_fixes",
    # Configuration
    "RuleConfig",
    "CategoryConfig",
    "PerformanceConfig",
    "RuleEngineConfig",
    "RuleEngineConfigLoader",
    "get_default_config",
    # Discovery
    "RuleDiscovery",
    "discover_rules",
    # Engine
    "RuleEngine",
    "RuleEngineResult",
    "RuleExecutionResult",
    "RuleError",
    "create_rule_engine",
]
