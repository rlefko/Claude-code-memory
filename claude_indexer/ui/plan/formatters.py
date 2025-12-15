"""Formatters for plan validation findings.

This module provides thoroughness-aware formatting of PlanValidationFinding
objects for both human display and Claude consumption.

Milestone 13.4.4: Iterate on findings format
Milestone 13.4.5: Add configuration for thoroughness level
"""

from enum import Enum
from typing import TYPE_CHECKING

from claude_indexer.rules.base import Severity

if TYPE_CHECKING:
    from .guardrails.base import PlanValidationFinding


class ThoroughnessLevel(str, Enum):
    """Thoroughness level for findings output.

    Controls the amount of detail included in findings output:
    - MINIMAL: Summary only, no evidence or suggestions
    - STANDARD: Summary + suggestion (default)
    - THOROUGH: Summary + suggestion + evidence
    - EXHAUSTIVE: All details including revision hints and confidence
    """

    MINIMAL = "minimal"
    STANDARD = "standard"
    THOROUGH = "thorough"
    EXHAUSTIVE = "exhaustive"


# Severity icons for human-readable output
SEVERITY_ICONS: dict[Severity, str] = {
    Severity.CRITICAL: "[CRITICAL]",
    Severity.HIGH: "[HIGH]",
    Severity.MEDIUM: "[MEDIUM]",
    Severity.LOW: "[LOW]",
}

# Category display names
CATEGORY_NAMES: dict[str, str] = {
    "coverage": "Coverage Requirements",
    "consistency": "Consistency Checks",
    "architecture": "Architecture Alignment",
    "performance": "Performance Patterns",
}


def format_plan_findings_for_display(
    findings: list["PlanValidationFinding"],
    thoroughness: ThoroughnessLevel = ThoroughnessLevel.STANDARD,
    group_by_severity: bool = True,
) -> str:
    """Format findings for human-readable display.

    Args:
        findings: List of PlanValidationFinding to format.
        thoroughness: Level of detail to include.
        group_by_severity: Whether to group findings by severity.

    Returns:
        Formatted multi-line string for terminal/log output.
    """
    if not findings:
        return "[Plan Validation: All quality checks passed]"

    lines: list[str] = []

    # Add summary header
    summary = _build_summary_header(findings)
    lines.append(summary)
    lines.append("")

    if group_by_severity:
        # Group and format by severity
        severity_order = [
            Severity.CRITICAL,
            Severity.HIGH,
            Severity.MEDIUM,
            Severity.LOW,
        ]
        for severity in severity_order:
            severity_findings = [f for f in findings if f.severity == severity]
            if severity_findings:
                lines.append(f"=== {SEVERITY_ICONS[severity]} ===")
                for finding in severity_findings:
                    lines.extend(_format_single_finding(finding, thoroughness))
                lines.append("")
    else:
        # Format in order without grouping
        for finding in findings:
            lines.extend(_format_single_finding(finding, thoroughness))
            lines.append("")

    return "\n".join(lines).rstrip()


def format_plan_findings_for_claude(
    findings: list["PlanValidationFinding"],
    thoroughness: ThoroughnessLevel = ThoroughnessLevel.THOROUGH,
) -> str:
    """Format findings for Claude's self-repair consumption.

    Uses a structured format optimized for Claude to parse and act on.

    Args:
        findings: List of PlanValidationFinding to format.
        thoroughness: Level of detail to include.

    Returns:
        Multi-line string suitable for Claude self-repair.
    """
    if not findings:
        return ""

    lines: list[str] = []

    # Header with blocking status
    has_blocking = any(
        f.severity in {Severity.CRITICAL, Severity.HIGH} for f in findings
    )
    header = (
        "=== PLAN VALIDATION BLOCKED ==="
        if has_blocking
        else "=== PLAN VALIDATION WARNINGS ==="
    )
    lines.append("")
    lines.append(header)
    lines.append("")

    # Sort by severity (critical first)
    severity_order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
    }
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.severity, 3))

    for finding in sorted_findings:
        lines.extend(_format_finding_for_claude(finding, thoroughness))
        lines.append("---")

    # Summary footer
    lines.append("")
    critical_count = sum(1 for f in findings if f.severity == Severity.CRITICAL)
    high_count = sum(1 for f in findings if f.severity == Severity.HIGH)
    medium_count = sum(1 for f in findings if f.severity == Severity.MEDIUM)
    low_count = sum(1 for f in findings if f.severity == Severity.LOW)

    lines.append(
        f"Found {len(findings)} issue(s): "
        f"{critical_count} critical, {high_count} high, "
        f"{medium_count} medium, {low_count} low"
    )

    if has_blocking:
        lines.append("Please address the critical/high issues to proceed.")

    lines.append("")
    return "\n".join(lines)


def _build_summary_header(findings: list["PlanValidationFinding"]) -> str:
    """Build a summary header for findings output."""
    by_severity: dict[Severity, int] = {}
    for f in findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    parts = []
    for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
        count = by_severity.get(sev, 0)
        if count > 0:
            parts.append(f"{count} {sev.value}")

    return f"=== Plan Validation: {', '.join(parts)} ==="


def _format_single_finding(
    finding: "PlanValidationFinding",
    thoroughness: ThoroughnessLevel,
) -> list[str]:
    """Format a single finding for human display."""
    lines: list[str] = []

    icon = SEVERITY_ICONS.get(finding.severity, "[INFO]")
    lines.append(f"{icon} {finding.rule_id}")
    lines.append(f"  {finding.summary}")

    # Add affected tasks
    if finding.affected_tasks:
        tasks_str = ", ".join(finding.affected_tasks[:3])
        if len(finding.affected_tasks) > 3:
            tasks_str += f" (+{len(finding.affected_tasks) - 3} more)"
        lines.append(f"  Affects: {tasks_str}")

    # Add suggestion for STANDARD and above
    if thoroughness != ThoroughnessLevel.MINIMAL and finding.suggestion:
        lines.append(f"  Suggestion: {finding.suggestion}")

    # Add evidence for THOROUGH and above
    if thoroughness in {ThoroughnessLevel.THOROUGH, ThoroughnessLevel.EXHAUSTIVE}:
        for evidence in finding.evidence[:2]:  # Limit to 2 pieces of evidence
            lines.append(f"  Evidence: {evidence.description}")

    # Add revision info for EXHAUSTIVE
    if thoroughness == ThoroughnessLevel.EXHAUSTIVE:
        if finding.can_auto_revise:
            lines.append("  [Auto-revision available]")
        lines.append(f"  Confidence: {finding.confidence:.0%}")

    return lines


def _format_finding_for_claude(
    finding: "PlanValidationFinding",
    thoroughness: ThoroughnessLevel,
) -> list[str]:
    """Format a single finding for Claude consumption."""
    lines: list[str] = []

    severity = finding.severity.value.upper()
    lines.append(f"{severity}: {finding.rule_id}")
    lines.append(f"Summary: {finding.summary}")

    if finding.affected_tasks:
        lines.append(f"Affected tasks: {', '.join(finding.affected_tasks)}")

    if finding.suggestion:
        lines.append(f"Suggestion: {finding.suggestion}")

    # Add evidence for THOROUGH and above
    if thoroughness in {ThoroughnessLevel.THOROUGH, ThoroughnessLevel.EXHAUSTIVE}:
        for evidence in finding.evidence:
            lines.append(f"Evidence: {evidence.description}")

    # Add auto-revision hint for EXHAUSTIVE
    if thoroughness == ThoroughnessLevel.EXHAUSTIVE and finding.can_auto_revise:
        lines.append("Note: Auto-revision can fix this issue")

    return lines


__all__ = [
    "ThoroughnessLevel",
    "format_plan_findings_for_display",
    "format_plan_findings_for_claude",
    "SEVERITY_ICONS",
    "CATEGORY_NAMES",
]
