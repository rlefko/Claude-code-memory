"""
Missing retry logic detection rule.

Detects network operations and external calls that don't have
retry logic, which can lead to failures on transient errors.
"""

import re
from typing import TYPE_CHECKING

from ..base import BaseRule, Evidence, RuleContext, Severity, Trigger

if TYPE_CHECKING:
    from ..base import Finding


class MissingRetryRule(BaseRule):
    """Detect network operations without retry logic.

    Identifies HTTP requests, API calls, and database operations
    that don't have retry mechanisms, which can cause failures
    on transient network errors.
    """

    # Network/external call patterns that should have retry logic
    # Format: (pattern, description, base_confidence)
    RETRY_CANDIDATES = {
        "python": [
            # HTTP clients
            (
                r"requests\.(get|post|put|delete|patch)\s*\(",
                "HTTP {method} request without retry logic",
                0.60,
            ),
            (
                r"httpx\.(get|post|put|delete|patch)\s*\(",
                "httpx {method} request without retry logic",
                0.55,
            ),
            # Database operations
            (
                r"cursor\.execute\s*\(",
                "Database execute without retry logic",
                0.50,
            ),
            (
                r"session\.execute\s*\(",
                "Database session execute without retry logic",
                0.50,
            ),
            # External service calls
            (
                r"boto3\.client\([^)]+\)\.\w+\s*\(",
                "AWS API call without retry logic",
                0.45,
            ),
            (
                r"\.send_message\s*\(",
                "Message send operation without retry logic",
                0.50,
            ),
            # Redis/cache operations
            (
                r"redis(?:_client)?\.(?:get|set|hget|hset|lpush|rpush)\s*\(",
                "Redis operation without retry logic",
                0.45,
            ),
        ],
        "javascript": [
            # HTTP calls
            (
                r"\bfetch\s*\(",
                "fetch() call without retry logic",
                0.55,
            ),
            (
                r"axios\.(get|post|put|delete|patch)\s*\(",
                "axios {method} request without retry logic",
                0.55,
            ),
            (
                r"axios\s*\(\s*\{",
                "axios request without retry logic",
                0.55,
            ),
            # Database
            (
                r"\.query\s*\(",
                "Database query without retry logic",
                0.45,
            ),
            (
                r"\.execute\s*\(",
                "Database execute without retry logic",
                0.45,
            ),
            # External APIs
            (
                r"await\s+\w+Client\.\w+\s*\(",
                "API client call without retry logic",
                0.45,
            ),
        ],
        "typescript": [
            # Same as JavaScript with type annotations
            (
                r"\bfetch\s*\(",
                "fetch() call without retry logic",
                0.55,
            ),
            (
                r"axios\.(get|post|put|delete|patch)\s*\(",
                "axios {method} request without retry logic",
                0.55,
            ),
            (
                r"axios\s*\(\s*\{",
                "axios request without retry logic",
                0.55,
            ),
            (
                r"\.query\s*\(",
                "Database query without retry logic",
                0.45,
            ),
            (
                r"await\s+\w+Client\.\w+\s*\(",
                "API client call without retry logic",
                0.45,
            ),
        ],
    }

    # Patterns indicating retry logic is present
    RETRY_INDICATORS = [
        # Python retry libraries
        r"@retry\b",
        r"@tenacity\.retry",
        r"@backoff\.",
        r"from\s+tenacity\s+import",
        r"from\s+backoff\s+import",
        r"import\s+tenacity",
        r"import\s+backoff",
        r"from\s+retrying\s+import",
        r"Retrying\(",
        r"retry_call\s*\(",
        # JavaScript retry packages
        r"p-retry",
        r"async-retry",
        r"axios-retry",
        r"retry\s*\(",
        r"withRetry\s*\(",
        r"retryable\s*\(",
        # Manual retry patterns
        r"while.*retry",
        r"while.*attempt",
        r"for.*range.*try",
        r"for.*attempt",
        r"max_retries",
        r"maxRetries",
        r"retry_count",
        r"retryCount",
        r"attempts?\s*[<>=]",
        r"backoff",
        r"exponential",
        # Function names suggesting retry
        r"def\s+.*retry.*\(",
        r"function\s+.*retry.*\(",
        r"const\s+.*retry.*\s*=",
        r"async\s+function\s+.*retry",
    ]

    # Context that suggests retry is handled at a higher level
    CONTEXT_RETRY_PATTERNS = [
        r"class.*Retry",
        r"class.*Client.*retry",
        r"with.*retry",
        r"@.*retry",
        r"retry_policy",
        r"retryPolicy",
    ]

    @property
    def rule_id(self) -> str:
        return "RESILIENCE.MISSING_RETRY"

    @property
    def name(self) -> str:
        return "Missing Retry Logic Detection"

    @property
    def category(self) -> str:
        return "resilience"

    @property
    def default_severity(self) -> Severity:
        return Severity.MEDIUM

    @property
    def triggers(self) -> list[Trigger]:
        return [Trigger.ON_WRITE, Trigger.ON_STOP, Trigger.ON_COMMIT]

    @property
    def supported_languages(self) -> list[str] | None:
        return ["python", "javascript", "typescript"]

    @property
    def description(self) -> str:
        return (
            "Detects network operations and external calls without retry logic. "
            "Transient failures are common with external services, and retry "
            "mechanisms with backoff help improve reliability."
        )

    @property
    def is_fast(self) -> bool:
        return True

    def _has_retry_nearby(
        self, lines: list[str], line_num: int, context_lines: int = 20
    ) -> bool:
        """Check for retry patterns in the surrounding context."""
        start = max(0, line_num - context_lines)
        end = min(len(lines), line_num + context_lines)
        context = "\n".join(lines[start:end])

        for pattern in self.RETRY_INDICATORS:
            if re.search(pattern, context, re.IGNORECASE):
                return True

        return False

    def _has_file_level_retry(self, content: str) -> bool:
        """Check for file-level retry configuration."""
        # Check imports and class-level patterns
        for pattern in self.RETRY_INDICATORS[:8]:  # Import patterns
            if re.search(pattern, content, re.IGNORECASE):
                return True

        for pattern in self.CONTEXT_RETRY_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False

    def _is_in_retry_wrapper(self, lines: list[str], line_num: int) -> bool:
        """Check if the call is inside a retry wrapper or loop."""
        # Look at function/loop context
        for i in range(max(0, line_num - 15), line_num):
            line = lines[i].lower()
            if any(
                p in line
                for p in [
                    "while",
                    "for",
                    "@retry",
                    "@backoff",
                    "def retry",
                    "def with_retry",
                    "async def retry",
                ]
            ):
                # Check if it's actually a retry loop
                context = "\n".join(lines[i : line_num + 1])
                if re.search(r"(retry|attempt|backoff)", context, re.IGNORECASE):
                    return True

        return False

    def _get_remediation_hint(self, language: str) -> list[str]:
        """Get language-specific remediation hints."""
        if language == "python":
            return [
                "Use tenacity: @retry(stop=stop_after_attempt(3), "
                "wait=wait_exponential())",
                "Use backoff: @backoff.on_exception(backoff.expo, "
                "Exception, max_tries=3)",
                "Implement manual retry: for attempt in range(3): try: ... "
                "except: time.sleep(2**attempt)",
                "Consider idempotency - retries may not be safe for all operations",
            ]
        elif language in ("javascript", "typescript"):
            return [
                "Use p-retry: await pRetry(() => fetch(url), { retries: 3 })",
                "Use async-retry: await retry(async () => fetch(url), "
                "{ retries: 3 })",
                "For axios: use axios-retry or implement interceptor",
                "Consider idempotency - retries may not be safe for all operations",
            ]
        return ["Add retry logic with exponential backoff for reliability"]

    def check(self, context: RuleContext) -> list["Finding"]:
        """Check for network operations without retry logic.

        Args:
            context: RuleContext with file content

        Returns:
            List of findings for missing retry logic
        """
        findings = []
        language = context.language
        lines = context.lines
        content = context.content

        # Get patterns for this language
        patterns = self.RETRY_CANDIDATES.get(language, [])
        if not patterns:
            return findings

        # Check for file-level retry configuration
        has_file_retry = self._has_file_level_retry(content)

        # If file has retry imports/config, significantly reduce confidence
        if has_file_retry:
            return findings  # Likely has retry at higher level

        for line_num, line in enumerate(lines):
            # Skip if line not in diff
            if not context.is_line_in_diff(line_num + 1):
                continue

            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            for pattern, description, base_confidence in patterns:
                match = re.search(pattern, line)
                if match:
                    # Check for retry in context
                    if self._has_retry_nearby(lines, line_num):
                        continue

                    # Check if inside retry wrapper
                    if self._is_in_retry_wrapper(lines, line_num):
                        continue

                    # Adjust confidence
                    confidence = base_confidence

                    # Lower confidence in test files
                    file_path = str(context.file_path).lower()
                    if "test" in file_path or "spec" in file_path:
                        confidence *= 0.3

                    # Lower confidence if function name contains "retry"
                    if "retry" in "\n".join(lines[max(0, line_num - 10) : line_num]):
                        confidence *= 0.4

                    # Skip if confidence is too low
                    if confidence < 0.25:
                        continue

                    # Format description with method name
                    desc = description
                    if "{method}" in desc and match.lastindex:
                        desc = desc.replace("{method}", match.group(1))

                    # Get code snippet
                    snippet = line.strip()
                    if len(snippet) > 100:
                        snippet = snippet[:100] + "..."

                    findings.append(
                        self._create_finding(
                            summary=desc,
                            file_path=str(context.file_path),
                            line_number=line_num + 1,
                            evidence=[
                                Evidence(
                                    description=desc,
                                    line_number=line_num + 1,
                                    code_snippet=snippet,
                                    data={
                                        "pattern": pattern,
                                        "match": match.group(0),
                                    },
                                )
                            ],
                            remediation_hints=self._get_remediation_hint(language),
                            confidence=confidence,
                        )
                    )
                    break  # Only one finding per line

        return findings
