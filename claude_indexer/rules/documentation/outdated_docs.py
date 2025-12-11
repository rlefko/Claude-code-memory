"""
Outdated documentation detection rule.

Detects documentation that doesn't match the actual code signature,
such as documented parameters that don't exist or missing parameters.
"""

import re
from typing import TYPE_CHECKING

from ..base import BaseRule, Evidence, RuleContext, Severity, Trigger

if TYPE_CHECKING:
    from ..base import Finding


class OutdatedDocsRule(BaseRule):
    """Detect documentation that doesn't match code signatures.

    Identifies cases where documented parameters don't match the
    actual function signature, or return types are mismatched.
    """

    # Python docstring parameter patterns
    PYTHON_PARAM_PATTERNS = [
        # Google style: param_name: description
        r"^\s+(\w+)\s*(?:\([^)]+\))?:",
        # Sphinx style: :param param_name:
        r":param\s+(?:\w+\s+)?(\w+):",
        # NumPy style: param_name : type
        r"^\s+(\w+)\s*:\s*\w+",
    ]

    # JSDoc parameter pattern
    JSDOC_PARAM_PATTERN = r"@param\s+(?:\{[^}]+\}\s+)?(\w+)"

    # Function signature patterns
    FUNCTION_PATTERNS = {
        "python": r"def\s+\w+\s*\(([^)]*)\)",
        "javascript": r"function\s+\w+\s*\(([^)]*)\)|=>\s*\{|=\s*(?:async\s+)?\(([^)]*)\)\s*=>",
        "typescript": r"function\s+\w+\s*(?:<[^>]+>)?\s*\(([^)]*)\)|=>\s*\{|=\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*[^=]+)?\s*=>",
    }

    @property
    def rule_id(self) -> str:
        return "DOCUMENTATION.OUTDATED_DOCS"

    @property
    def name(self) -> str:
        return "Outdated Documentation Detection"

    @property
    def category(self) -> str:
        return "documentation"

    @property
    def default_severity(self) -> Severity:
        return Severity.LOW

    @property
    def triggers(self) -> list[Trigger]:
        return [Trigger.ON_WRITE, Trigger.ON_STOP, Trigger.ON_COMMIT]

    @property
    def supported_languages(self) -> list[str] | None:
        return ["python", "javascript", "typescript"]

    @property
    def description(self) -> str:
        return (
            "Detects documentation that doesn't match the actual code signature. "
            "Outdated documentation can be more confusing than no documentation."
        )

    @property
    def is_fast(self) -> bool:
        return True

    def _extract_python_params(self, signature: str) -> set[str]:
        """Extract parameter names from Python function signature."""
        params = set()

        # Remove default values and type hints for parsing
        # Split by comma, handling nested structures
        param_parts = []
        depth = 0
        current = ""

        for char in signature:
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
            elif char == "," and depth == 0:
                param_parts.append(current.strip())
                current = ""
                continue
            current += char

        if current.strip():
            param_parts.append(current.strip())

        for part in param_parts:
            if not part:
                continue

            # Remove type hints and defaults
            param = part.split(":")[0].split("=")[0].strip()

            # Skip *args, **kwargs, self, cls
            if param.startswith("*") or param in ("self", "cls"):
                continue

            # Get just the name
            if param:
                params.add(param)

        return params

    def _extract_js_params(self, signature: str) -> set[str]:
        """Extract parameter names from JS/TS function signature."""
        params = set()

        # Split by comma, handling nested structures
        param_parts = []
        depth = 0
        current = ""

        for char in signature:
            if char in "([{<":
                depth += 1
            elif char in ")]}>":
                depth -= 1
            elif char == "," and depth == 0:
                param_parts.append(current.strip())
                current = ""
                continue
            current += char

        if current.strip():
            param_parts.append(current.strip())

        for part in param_parts:
            if not part:
                continue

            # Handle destructuring: { a, b }
            if part.strip().startswith("{"):
                continue  # Skip destructured params for now

            # Handle rest params: ...args
            if part.strip().startswith("..."):
                continue

            # Remove type annotations and defaults
            param = part.split(":")[0].split("=")[0].strip()

            # Handle optional params: param?
            param = param.rstrip("?")

            if param:
                params.add(param)

        return params

    def _extract_docstring_params_python(
        self, lines: list[str], start_line: int
    ) -> tuple[set[str], int, int]:
        """Extract documented parameters from Python docstring."""
        params = set()
        doc_start = -1
        doc_end = -1

        # Find docstring boundaries
        in_docstring = False
        doc_delimiter = None

        for i in range(start_line, min(start_line + 50, len(lines))):
            line = lines[i]
            stripped = line.strip()

            if not in_docstring:
                for delim in ['"""', "'''"]:
                    if delim in stripped:
                        in_docstring = True
                        doc_delimiter = delim
                        doc_start = i
                        # Check if docstring ends on same line
                        if stripped.count(delim) >= 2:
                            doc_end = i
                            in_docstring = False
                        break
            else:
                if doc_delimiter and doc_delimiter in stripped:
                    doc_end = i
                    break

        if doc_start < 0 or doc_end < 0:
            return params, -1, -1

        # Extract parameters from docstring
        docstring_content = "\n".join(lines[doc_start : doc_end + 1])

        # Check for Args: section (Google style)
        args_match = re.search(r"Args?:\s*\n((?:\s+\w+.*\n?)+)", docstring_content)
        if args_match:
            args_section = args_match.group(1)
            for pattern in self.PYTHON_PARAM_PATTERNS:
                for match in re.finditer(pattern, args_section, re.MULTILINE):
                    params.add(match.group(1))

        # Check for :param: (Sphinx style)
        for match in re.finditer(r":param\s+(?:\w+\s+)?(\w+):", docstring_content):
            params.add(match.group(1))

        # Check for Parameters section (NumPy style)
        params_match = re.search(
            r"Parameters\s*\n-+\s*\n((?:\s*\w+\s*:.*\n?)+)", docstring_content
        )
        if params_match:
            params_section = params_match.group(1)
            for line in params_section.split("\n"):
                match = re.match(r"\s*(\w+)\s*:", line)
                if match:
                    params.add(match.group(1))

        return params, doc_start, doc_end

    def _extract_jsdoc_params(
        self, lines: list[str], def_line: int
    ) -> tuple[set[str], int, int]:
        """Extract documented parameters from JSDoc comment."""
        params = set()
        doc_start = -1
        doc_end = -1

        # Look for JSDoc above the function
        for i in range(def_line - 1, max(-1, def_line - 30), -1):
            line = lines[i].strip()
            if line.endswith("*/"):
                doc_end = i
            elif "/**" in line:
                doc_start = i
                break
            elif doc_end < 0 and line and not line.startswith("*"):
                # No JSDoc found
                return params, -1, -1

        if doc_start < 0 or doc_end < 0:
            return params, -1, -1

        # Extract @param tags
        jsdoc_content = "\n".join(lines[doc_start : doc_end + 1])
        for match in re.finditer(self.JSDOC_PARAM_PATTERN, jsdoc_content):
            params.add(match.group(1))

        return params, doc_start, doc_end

    def _get_remediation_hint(
        self, language: str, extra_doc: set[str], missing_doc: set[str]
    ) -> list[str]:
        """Get specific remediation hints."""
        hints = []

        if extra_doc:
            hints.append(
                f"Remove documentation for parameters that no longer exist: {', '.join(sorted(extra_doc))}"
            )

        if missing_doc:
            if language == "python":
                hints.append(
                    f"Add documentation for parameters: {', '.join(sorted(missing_doc))}"
                )
            else:
                for param in sorted(missing_doc):
                    hints.append(f"Add @param {{type}} {param} - description")

        hints.append("Keep documentation in sync with code changes")

        return hints

    def check(self, context: RuleContext) -> list["Finding"]:
        """Check for outdated documentation.

        Args:
            context: RuleContext with file content

        Returns:
            List of findings for documentation/code mismatches
        """
        findings = []
        language = context.language
        lines = context.lines

        # Get function pattern for this language
        func_pattern = self.FUNCTION_PATTERNS.get(language)
        if not func_pattern:
            return findings

        for line_num, line in enumerate(lines):
            # Skip if line not in diff
            if not context.is_line_in_diff(line_num + 1):
                continue

            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            # Look for function definitions
            match = re.search(func_pattern, line)
            if not match:
                continue

            # Get the signature (may span multiple lines)
            signature = (
                match.group(1) or match.group(2)
                if match.lastindex >= 2
                else match.group(1)
            )
            if not signature:
                # Handle multi-line signatures
                full_sig = line
                paren_count = line.count("(") - line.count(")")
                for i in range(line_num + 1, min(line_num + 10, len(lines))):
                    full_sig += " " + lines[i]
                    paren_count += lines[i].count("(") - lines[i].count(")")
                    if paren_count <= 0:
                        break

                sig_match = re.search(func_pattern, full_sig)
                if sig_match:
                    signature = sig_match.group(1) or (
                        sig_match.group(2) if sig_match.lastindex >= 2 else ""
                    )

            if not signature:
                continue

            # Extract actual parameters
            if language == "python":
                actual_params = self._extract_python_params(signature)
                doc_params, doc_start, doc_end = self._extract_docstring_params_python(
                    lines, line_num + 1
                )
            else:
                actual_params = self._extract_js_params(signature)
                doc_params, doc_start, doc_end = self._extract_jsdoc_params(
                    lines, line_num
                )

            # Skip if no documentation
            if doc_start < 0:
                continue

            # Compare parameters
            extra_in_docs = doc_params - actual_params
            missing_in_docs = actual_params - doc_params

            # Skip common false positives (section headers and keywords)
            extra_in_docs.discard("return")
            extra_in_docs.discard("returns")
            extra_in_docs.discard("Returns")
            extra_in_docs.discard("type")
            extra_in_docs.discard("Type")
            extra_in_docs.discard("Raises")
            extra_in_docs.discard("raises")
            extra_in_docs.discard("Example")
            extra_in_docs.discard("Examples")
            extra_in_docs.discard("Note")
            extra_in_docs.discard("Notes")
            extra_in_docs.discard("See")
            extra_in_docs.discard("Yields")
            extra_in_docs.discard("yields")

            if not extra_in_docs and not missing_in_docs:
                continue

            # Build finding
            issues = []
            if extra_in_docs:
                issues.append(
                    f"Documented but not in signature: {', '.join(sorted(extra_in_docs))}"
                )
            if missing_in_docs:
                issues.append(
                    f"In signature but not documented: {', '.join(sorted(missing_in_docs))}"
                )

            summary = "Documentation doesn't match function signature"

            # Confidence based on specificity
            confidence = 0.70
            if len(extra_in_docs) > 0 and len(missing_in_docs) > 0:
                # Both issues = likely a rename
                confidence = 0.85
            elif len(extra_in_docs) > 1 or len(missing_in_docs) > 1:
                # Multiple mismatches
                confidence = 0.80

            snippet = line.strip()
            if len(snippet) > 100:
                snippet = snippet[:100] + "..."

            findings.append(
                self._create_finding(
                    summary=summary,
                    file_path=str(context.file_path),
                    line_number=line_num + 1,
                    end_line=doc_end + 1 if doc_end > 0 else None,
                    evidence=[
                        Evidence(
                            description="; ".join(issues),
                            line_number=(
                                doc_start + 1 if doc_start >= 0 else line_num + 1
                            ),
                            code_snippet=snippet,
                            data={
                                "actual_params": list(actual_params),
                                "documented_params": list(doc_params),
                                "extra_in_docs": list(extra_in_docs),
                                "missing_in_docs": list(missing_in_docs),
                            },
                        )
                    ],
                    remediation_hints=self._get_remediation_hint(
                        language, extra_in_docs, missing_in_docs
                    ),
                    confidence=confidence,
                )
            )

        return findings
