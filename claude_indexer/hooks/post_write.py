"""
Fast rule executor for PostToolUse hook.

Optimized for <300ms execution:
- Pre-loaded rule engine (singleton pattern)
- Fast rule filtering (is_fast=True only)
- Minimal file I/O
- Efficient result serialization

This module is used by the after-write.sh hook to run
quality checks immediately after Claude writes a file.
"""

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from ..rules.base import Finding, RuleContext, Severity
from ..rules.engine import RuleEngine, RuleEngineResult, create_rule_engine


@dataclass
class PostWriteResult:
    """Result of post-write quality checks."""

    findings: list[Finding] = field(default_factory=list)
    execution_time_ms: float = 0.0
    rules_executed: int = 0
    should_warn: bool = False
    error: str | None = None

    @property
    def critical_count(self) -> int:
        """Count of critical findings."""
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        """Count of high findings."""
        return sum(1 for f in self.findings if f.severity == Severity.HIGH)

    @property
    def medium_count(self) -> int:
        """Count of medium findings."""
        return sum(1 for f in self.findings if f.severity == Severity.MEDIUM)

    @property
    def low_count(self) -> int:
        """Count of low findings."""
        return sum(1 for f in self.findings if f.severity == Severity.LOW)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": "warn" if self.should_warn else "ok",
            "findings": [f.to_dict() for f in self.findings],
            "execution_time_ms": round(self.execution_time_ms, 2),
            "rules_executed": self.rules_executed,
            "summary": {
                "total": len(self.findings),
                "critical": self.critical_count,
                "high": self.high_count,
                "medium": self.medium_count,
                "low": self.low_count,
            },
            "error": self.error,
        }

    def to_json(self, indent: int | None = None) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class PostWriteExecutor:
    """Singleton executor for fast post-write checks.

    Uses singleton pattern to avoid repeated rule loading overhead.
    The rule engine is loaded once and reused across calls.

    Example usage:
        executor = PostWriteExecutor.get_instance()
        result = executor.check_file(Path("src/main.py"))
        if result.should_warn:
            print(format_findings_for_display(result))
    """

    _instance: ClassVar["PostWriteExecutor | None"] = None
    _engine: ClassVar[RuleEngine | None] = None

    @classmethod
    def get_instance(cls) -> "PostWriteExecutor":
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None
        cls._engine = None

    def __init__(self) -> None:
        """Initialize with pre-loaded fast rules only."""
        if PostWriteExecutor._engine is None:
            PostWriteExecutor._engine = create_rule_engine(auto_load=True)

    @property
    def engine(self) -> RuleEngine:
        """Get the rule engine instance."""
        if PostWriteExecutor._engine is None:
            PostWriteExecutor._engine = create_rule_engine(auto_load=True)
        return PostWriteExecutor._engine

    def check_file(
        self,
        file_path: Path,
        content: str | None = None,
        timeout_ms: float = 200.0,
    ) -> PostWriteResult:
        """Run fast rules on a single file.

        Args:
            file_path: Path to the file to check
            content: Optional file content (avoids disk read if provided)
            timeout_ms: Maximum execution time (soft limit for logging)

        Returns:
            PostWriteResult with findings and timing information
        """
        start_time = time.time()

        try:
            # Create context from file or content
            if content is not None:
                context = RuleContext(
                    file_path=file_path,
                    content=content,
                    language=self._detect_language(file_path),
                )
            else:
                if not file_path.exists():
                    return PostWriteResult(
                        error=f"File not found: {file_path}",
                        execution_time_ms=(time.time() - start_time) * 1000,
                    )
                context = RuleContext.from_file(file_path)

            # Run fast rules only (ON_WRITE trigger + is_fast=True)
            engine_result: RuleEngineResult = self.engine.run_fast(context)

            elapsed_ms = (time.time() - start_time) * 1000

            # Log warning if we exceeded time budget
            if elapsed_ms > timeout_ms:
                import logging

                logging.getLogger(__name__).warning(
                    f"Post-write check exceeded time budget: {elapsed_ms:.1f}ms > {timeout_ms}ms"
                )

            return PostWriteResult(
                findings=engine_result.findings,
                execution_time_ms=elapsed_ms,
                rules_executed=engine_result.rules_executed,
                should_warn=len(engine_result.findings) > 0,
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return PostWriteResult(
                error=str(e),
                execution_time_ms=elapsed_ms,
            )

    def _detect_language(self, file_path: Path) -> str:
        """Detect language from file extension."""
        ext_to_lang = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".sh": "bash",
            ".bash": "bash",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".rb": "ruby",
            ".php": "php",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".md": "markdown",
            ".html": "html",
            ".css": "css",
        }
        return ext_to_lang.get(file_path.suffix.lower(), "unknown")


def format_findings_for_display(result: PostWriteResult) -> str:
    """Format findings for human-readable display.

    Args:
        result: PostWriteResult to format

    Returns:
        Multi-line string suitable for terminal output
    """
    if not result.findings:
        return ""

    lines = []

    # Group findings by severity
    severity_order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]
    severity_icons = {
        Severity.CRITICAL: "\u274c",  # Red X
        Severity.HIGH: "\u26a0\ufe0f",  # Warning
        Severity.MEDIUM: "\u2139\ufe0f",  # Info
        Severity.LOW: "\U0001f4dd",  # Memo
    }

    for severity in severity_order:
        findings = [f for f in result.findings if f.severity == severity]
        if not findings:
            continue

        for finding in findings:
            icon = severity_icons.get(severity, "")
            location = f"{finding.file_path}"
            if finding.line_number:
                location += f":{finding.line_number}"

            lines.append(f"{icon} [{severity.value.upper()}] {finding.rule_id}")
            lines.append(f"   {location}")
            lines.append(f"   {finding.summary}")

            if finding.remediation_hints:
                lines.append(f"   Suggestion: {finding.remediation_hints[0]}")

            lines.append("")

    # Add summary
    if result.execution_time_ms:
        lines.append(f"Checked in {result.execution_time_ms:.0f}ms")

    return "\n".join(lines)


def run_post_write_check(
    file_path: str,
    content: str | None = None,
    output_json: bool = False,
) -> int:
    """Run post-write checks and output results.

    This is the main entry point for the CLI command.

    Args:
        file_path: Path to file to check
        content: Optional content (avoids file read)
        output_json: Whether to output JSON format

    Returns:
        Exit code: 0 = no findings, 1 = warnings found
    """
    executor = PostWriteExecutor.get_instance()
    result = executor.check_file(Path(file_path), content=content)

    if output_json:
        print(result.to_json())
    elif result.findings:
        print(format_findings_for_display(result))
    elif result.error:
        print(f"Error: {result.error}", file=sys.stderr)

    # Exit 1 if warnings found, 0 otherwise
    return 1 if result.should_warn else 0
