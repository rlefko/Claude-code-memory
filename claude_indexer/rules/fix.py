"""
Auto-fix capability for code quality rules.

This module provides the AutoFix dataclass and related utilities
for automatically fixing code quality issues detected by rules.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .base import Finding


@dataclass
class AutoFix:
    """Represents an automatic fix for a finding.

    AutoFix contains the information needed to replace problematic
    code with corrected code, including the exact location and
    the old/new code strings.
    """

    finding: "Finding"
    old_code: str
    new_code: str
    line_start: int  # 1-indexed, inclusive
    line_end: int  # 1-indexed, inclusive
    description: str

    def apply(self, content: str) -> str:
        """Apply the fix to file content.

        Args:
            content: Original file content

        Returns:
            Modified file content with fix applied
        """
        lines = content.split("\n")

        # Convert to 0-indexed
        start_idx = self.line_start - 1
        end_idx = self.line_end  # end_idx is exclusive after conversion

        # Replace the lines
        new_lines = self.new_code.split("\n")
        lines[start_idx:end_idx] = new_lines

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "finding_rule_id": self.finding.rule_id,
            "finding_file_path": self.finding.file_path,
            "old_code": self.old_code,
            "new_code": self.new_code,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "description": self.description,
        }

    def preview(self, context_lines: int = 3) -> str:
        """Generate a human-readable preview of the fix.

        Args:
            context_lines: Number of context lines to show

        Returns:
            Formatted diff-like preview string
        """
        lines = []
        lines.append(f"# Fix for {self.finding.rule_id}")
        lines.append(f"# {self.description}")
        lines.append(f"# Lines {self.line_start}-{self.line_end}")
        lines.append("")
        lines.append("--- old")
        lines.append("+++ new")
        lines.append(f"@@ -{self.line_start},{self.line_end - self.line_start + 1} @@")

        for line in self.old_code.split("\n"):
            lines.append(f"-{line}")
        for line in self.new_code.split("\n"):
            lines.append(f"+{line}")

        return "\n".join(lines)


def apply_fixes(content: str, fixes: list[AutoFix]) -> str:
    """Apply multiple fixes to content.

    Fixes are applied in reverse line order to avoid offset issues.

    Args:
        content: Original file content
        fixes: List of AutoFix objects to apply

    Returns:
        Modified file content with all fixes applied
    """
    # Sort fixes by line number in reverse order
    sorted_fixes = sorted(fixes, key=lambda f: f.line_start, reverse=True)

    result = content
    for fix in sorted_fixes:
        result = fix.apply(result)

    return result
