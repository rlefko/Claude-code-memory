"""Output reporters for UI Guard results.

This module provides formatters for outputting UI consistency check results
in different formats suitable for CLI display and Claude Code hook responses.
"""

import json
import sys
from typing import Any, TextIO

from ..models import Finding, Severity, UIAnalysisResult


class CLIReporter:
    """CLI reporter with color-coded output.

    Format: file:line rule_id suggestion
    Colors: red=FAIL, yellow=WARN, blue=INFO

    Example output:
        src/Button.tsx:42 COLOR.NON_TOKEN Hardcoded color #ff6b6b
          -> Use token: --color-error-500 (#ef4444)
        src/Button.tsx:55 SPACING.OFF_SCALE padding: 13px off-scale
          -> Nearest: 12px (scale-12) or 16px (scale-16)

        2 issue(s) in 89ms (1 blocking)
    """

    COLORS = {
        Severity.FAIL: "\033[0;31m",  # Red
        Severity.WARN: "\033[1;33m",  # Yellow
        Severity.INFO: "\033[0;34m",  # Blue
    }
    RESET = "\033[0m"
    DIM = "\033[2m"

    def __init__(self, stream: TextIO = sys.stderr, use_color: bool | None = None):
        """Initialize the CLI reporter.

        Args:
            stream: Output stream (default: stderr).
            use_color: Whether to use ANSI colors. Auto-detects if None.
        """
        self.stream = stream
        if use_color is None:
            self.use_color = hasattr(stream, "isatty") and stream.isatty()
        else:
            self.use_color = use_color

    def report(self, result: UIAnalysisResult) -> None:
        """Output findings in CLI format.

        Args:
            result: UI analysis result to report.
        """
        if not result.findings:
            self._print_summary(result)
            return

        for finding in result.findings:
            self._report_finding(finding)

        self._print_summary(result)

    def _report_finding(self, finding: Finding) -> None:
        """Output a single finding.

        Args:
            finding: Finding to output.
        """
        location = self._format_location(finding)
        color = self.COLORS.get(finding.severity, "")
        reset = self.RESET if self.use_color else ""
        dim = self.DIM if self.use_color else ""

        if self.use_color:
            line = f"{color}{location} {finding.rule_id}{reset} {finding.summary}"
        else:
            line = f"{location} {finding.rule_id} {finding.summary}"

        print(line, file=self.stream)

        # Add remediation hints
        for hint in finding.remediation_hints:
            if self.use_color:
                print(f"  {dim}-> {hint}{reset}", file=self.stream)
            else:
                print(f"  -> {hint}", file=self.stream)

    def _format_location(self, finding: Finding) -> str:
        """Format file:line location.

        Args:
            finding: Finding to get location from.

        Returns:
            Formatted location string.
        """
        if finding.source_ref:
            return f"{finding.source_ref.file_path}:{finding.source_ref.start_line}"
        return "unknown"

    def _print_summary(self, result: UIAnalysisResult) -> None:
        """Output summary line.

        Args:
            result: UI analysis result to summarize.
        """
        total = len(result.findings)
        time_ms = result.analysis_time_ms

        if total == 0:
            summary = f"\nNo issues found ({time_ms:.0f}ms)"
        else:
            summary = f"\n{total} issue(s) in {time_ms:.0f}ms"
            if result.fail_count > 0:
                summary += f" ({result.fail_count} blocking)"

        print(summary, file=self.stream)


class JSONReporter:
    """JSON reporter for Claude Code agent consumption.

    Output format compatible with Claude Code hook response schema:
    {
        "decision": "approve" | "block",
        "reason": "summary",
        "findings": [...],  # Full Finding objects
        "analysis_time_ms": float,
        "files_analyzed": [...],
        "tier": int,
        "counts": {
            "fail": int,
            "warn": int,
            "info": int
        }
    }
    """

    def __init__(self, stream: TextIO = sys.stdout):
        """Initialize the JSON reporter.

        Args:
            stream: Output stream (default: stdout).
        """
        self.stream = stream

    def report(self, result: UIAnalysisResult) -> dict[str, Any]:
        """Output findings as JSON.

        Args:
            result: UI analysis result to report.

        Returns:
            The output dictionary (also written to stream).
        """
        output = {
            "decision": "block" if result.should_block() else "approve",
            "reason": self._build_reason(result),
            "findings": [f.to_dict() for f in result.findings],
            "analysis_time_ms": result.analysis_time_ms,
            "files_analyzed": result.files_analyzed,
            "tier": result.tier,
            "counts": {
                "fail": result.fail_count,
                "warn": result.warn_count,
                "info": result.info_count,
            },
        }

        json.dump(output, self.stream)
        return output

    def _build_reason(self, result: UIAnalysisResult) -> str:
        """Build human-readable reason summary.

        Args:
            result: UI analysis result to summarize.

        Returns:
            Human-readable summary string.
        """
        if result.fail_count == 0:
            if result.warn_count == 0 and result.info_count == 0:
                return "UI checks passed"
            return f"UI checks passed ({result.warn_count} warnings, {result.info_count} info)"

        # Summarize blocking issues
        fail_rules = [f.rule_id for f in result.findings if f.severity == Severity.FAIL]
        unique_rules = list(dict.fromkeys(fail_rules))  # Preserve order, remove dupes

        if len(unique_rules) == 1:
            return f"Blocked: {unique_rules[0]} violation"
        elif len(unique_rules) <= 3:
            return f"Blocked: {len(unique_rules)} rule violations ({', '.join(unique_rules)})"
        else:
            return f"Blocked: {len(unique_rules)} rule violations ({', '.join(unique_rules[:3])}...)"
