"""
Swallowed exception detection rule.

Detects catch blocks that silently ignore exceptions without
logging, re-throwing, or proper handling.
"""

import re
from typing import TYPE_CHECKING

from ..base import BaseRule, Evidence, RuleContext, Severity, Trigger

if TYPE_CHECKING:
    from ..base import Finding


class SwallowedExceptionRule(BaseRule):
    """Detect silently swallowed exceptions.

    Identifies catch blocks that ignore exceptions without any
    meaningful handling like logging, re-throwing, or error tracking.
    """

    # Patterns that indicate a swallowed exception by language
    # Format: (regex, description, confidence)
    EXCEPTION_PATTERNS = {
        "python": [
            # Bare except with pass
            (
                r"except\s*:\s*pass\s*$",
                "Bare except clause with pass - exception silently ignored",
                0.95,
            ),
            # Named exception with pass
            (
                r"except\s+\w+\s*:\s*pass\s*$",
                "Exception caught and silently ignored with pass",
                0.90,
            ),
            # Exception with alias and pass
            (
                r"except\s+\w+\s+as\s+\w+\s*:\s*pass\s*$",
                "Exception caught with alias but silently ignored",
                0.90,
            ),
            # Bare except with ellipsis
            (
                r"except\s*:\s*\.\.\.\s*$",
                "Exception block with ellipsis - likely placeholder",
                0.80,
            ),
            # Named exception with ellipsis
            (
                r"except\s+\w+\s*:\s*\.\.\.\s*$",
                "Exception caught with ellipsis - likely placeholder",
                0.75,
            ),
            # Multi-line check: except followed by only pass on next line
            (
                r"except.*:\s*$",
                "Empty exception handler - check block contents",
                0.50,  # Lower confidence, needs block analysis
            ),
        ],
        "javascript": [
            # Empty catch block
            (
                r"catch\s*\(\s*\w*\s*\)\s*\{\s*\}",
                "Empty catch block - exception silently ignored",
                0.95,
            ),
            # Catch without binding (ES2019+)
            (
                r"catch\s*\{\s*\}",
                "Empty catch block without binding",
                0.95,
            ),
            # Promise .catch with empty arrow function
            (
                r"\.catch\s*\(\s*\(\s*\)\s*=>\s*\{\s*\}\s*\)",
                "Empty promise catch handler",
                0.90,
            ),
            # Promise .catch with error param but empty body
            (
                r"\.catch\s*\(\s*\(\s*\w+\s*\)\s*=>\s*\{\s*\}\s*\)",
                "Promise catch ignoring error parameter",
                0.90,
            ),
            # Promise .catch with empty function
            (
                r"\.catch\s*\(\s*function\s*\(\s*\w*\s*\)\s*\{\s*\}\s*\)",
                "Empty promise catch function",
                0.90,
            ),
            # Promise .catch with underscore (intentional ignore pattern)
            (
                r"\.catch\s*\(\s*_\s*=>\s*\{\s*\}\s*\)",
                "Promise catch with ignored error",
                0.70,
            ),
        ],
        "typescript": [
            # Same as JavaScript patterns
            (
                r"catch\s*\(\s*\w*\s*(?::\s*\w+)?\s*\)\s*\{\s*\}",
                "Empty catch block - exception silently ignored",
                0.95,
            ),
            (
                r"catch\s*\{\s*\}",
                "Empty catch block without binding",
                0.95,
            ),
            (
                r"\.catch\s*\(\s*\(\s*\)\s*=>\s*\{\s*\}\s*\)",
                "Empty promise catch handler",
                0.90,
            ),
            (
                r"\.catch\s*\(\s*\(\s*\w+(?::\s*\w+)?\s*\)\s*=>\s*\{\s*\}\s*\)",
                "Promise catch ignoring error parameter",
                0.90,
            ),
            (
                r"\.catch\s*\(\s*function\s*\(\s*\w*(?::\s*\w+)?\s*\)\s*\{\s*\}\s*\)",
                "Empty promise catch function",
                0.90,
            ),
        ],
    }

    # Patterns that indicate proper exception handling
    SAFE_PATTERNS = [
        # Logging
        r"\blog\b",
        r"\blogger\b",
        r"\blogging\b",
        r"console\.",
        r"print\s*\(",
        r"sentry",
        r"bugsnag",
        r"rollbar",
        r"trackError",
        r"reportError",
        # Re-throwing
        r"\braise\b",
        r"\bthrow\b",
        r"\brethrow\b",
        # Error state assignment
        r"error\s*=",
        r"lastError\s*=",
        r"err\s*=",
        r"setError\s*\(",
        # Return statement
        r"\breturn\b",
        # Comments indicating intentional ignore
        r"#\s*intentional",
        r"//\s*intentional",
        r"#\s*ignore",
        r"//\s*ignore",
        r"#\s*expected",
        r"//\s*expected",
        # Cleanup operations
        r"cleanup",
        r"close\s*\(",
        r"dispose\s*\(",
        r"release\s*\(",
    ]

    @property
    def rule_id(self) -> str:
        return "RESILIENCE.SWALLOWED_EXCEPTIONS"

    @property
    def name(self) -> str:
        return "Swallowed Exception Detection"

    @property
    def category(self) -> str:
        return "resilience"

    @property
    def default_severity(self) -> Severity:
        return Severity.HIGH

    @property
    def triggers(self) -> list[Trigger]:
        return [Trigger.ON_WRITE, Trigger.ON_STOP, Trigger.ON_COMMIT]

    @property
    def supported_languages(self) -> list[str] | None:
        return ["python", "javascript", "typescript"]

    @property
    def description(self) -> str:
        return (
            "Detects catch blocks that silently ignore exceptions without "
            "logging, re-throwing, or proper error handling. Swallowed "
            "exceptions can hide bugs and make debugging difficult."
        )

    @property
    def is_fast(self) -> bool:
        return True  # Pattern matching only

    def _find_block_end_python(self, lines: list[str], start_line: int) -> int:
        """Find the end of a Python except block based on indentation."""
        if start_line >= len(lines):
            return start_line

        # Get indentation of except line
        except_line = lines[start_line]
        except_indent = len(except_line) - len(except_line.lstrip())

        # Look for lines in the except block
        for i in range(start_line + 1, min(start_line + 20, len(lines))):
            line = lines[i]
            if not line.strip():  # Skip empty lines
                continue

            line_indent = len(line) - len(line.lstrip())

            # If we find a line with same or less indent, block ended
            if line_indent <= except_indent:
                return i - 1

        return min(start_line + 10, len(lines) - 1)

    def _find_block_end_js(self, lines: list[str], start_line: int) -> int:
        """Find the end of a JS/TS catch block by counting braces."""
        brace_count = 0
        started = False

        for i in range(start_line, min(start_line + 50, len(lines))):
            line = lines[i]
            for char in line:
                if char == "{":
                    brace_count += 1
                    started = True
                elif char == "}":
                    brace_count -= 1
                    if started and brace_count == 0:
                        return i

        return min(start_line + 10, len(lines) - 1)

    def _has_proper_handling(
        self, lines: list[str], start_line: int, end_line: int
    ) -> bool:
        """Check if the catch block has proper exception handling."""
        block_content = "\n".join(lines[start_line : end_line + 1]).lower()

        for pattern in self.SAFE_PATTERNS:
            if re.search(pattern, block_content, re.IGNORECASE):
                return True

        return False

    def _get_remediation_hint(self, language: str) -> list[str]:
        """Get language-specific remediation hints."""
        if language == "python":
            return [
                "Log the exception: `logging.exception('Error occurred')`",
                "Re-raise if you can't handle: `raise` or `raise from e`",
                "Track errors: `sentry_sdk.capture_exception(e)`",
                "If intentional, add comment: `# Intentionally ignored: reason`",
            ]
        elif language in ("javascript", "typescript"):
            return [
                "Log the error: `console.error('Error:', error)` or use a logger",
                "Re-throw if appropriate: `throw error`",
                "Track errors: `Sentry.captureException(error)`",
                "If intentional, add comment: `// Intentionally ignored: reason`",
            ]
        return ["Add proper exception handling or document why it's ignored"]

    def check(self, context: RuleContext) -> list["Finding"]:
        """Check for swallowed exceptions.

        Args:
            context: RuleContext with file content

        Returns:
            List of findings for swallowed exception patterns
        """
        findings = []
        language = context.language
        lines = context.lines

        # Get patterns for this language
        patterns = self.EXCEPTION_PATTERNS.get(language, [])
        if not patterns:
            return findings

        for line_num, line in enumerate(lines):
            # Skip if line not in diff (when checking incrementally)
            if not context.is_line_in_diff(line_num + 1):
                continue

            # Skip comment lines
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            for pattern, description, base_confidence in patterns:
                match = re.search(pattern, line)
                if match:
                    # Determine block boundaries
                    if language == "python":
                        block_end = self._find_block_end_python(lines, line_num)
                    else:
                        block_end = self._find_block_end_js(lines, line_num)

                    # Check if there's proper handling in the block
                    if self._has_proper_handling(lines, line_num, block_end):
                        continue

                    # Adjust confidence based on context
                    confidence = base_confidence

                    # Lower confidence for single-line patterns
                    # that might be part of a larger block
                    if base_confidence < 0.6 and block_end > line_num:
                        # Check actual block content
                        block_content = "\n".join(lines[line_num : block_end + 1])
                        if any(
                            re.search(p, block_content, re.IGNORECASE)
                            for p in self.SAFE_PATTERNS
                        ):
                            continue

                    # Get code snippet
                    snippet = line.strip()
                    if len(snippet) > 100:
                        snippet = snippet[:100] + "..."

                    findings.append(
                        self._create_finding(
                            summary=description,
                            file_path=str(context.file_path),
                            line_number=line_num + 1,
                            end_line=block_end + 1 if block_end > line_num else None,
                            evidence=[
                                Evidence(
                                    description=description,
                                    line_number=line_num + 1,
                                    code_snippet=snippet,
                                    data={
                                        "pattern": pattern,
                                        "match": match.group(0),
                                        "block_end": block_end + 1,
                                    },
                                )
                            ],
                            remediation_hints=self._get_remediation_hint(language),
                            confidence=confidence,
                        )
                    )
                    break  # Only one finding per line

        return findings
