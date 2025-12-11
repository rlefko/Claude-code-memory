"""
Unit tests for the Resilience rules.

Tests for RESILIENCE.UNSAFE_NULL, RESILIENCE.UNSAFE_LOOP,
RESILIENCE.UNSAFE_RESOURCE, RESILIENCE.UNSAFE_CONCURRENCY,
RESILIENCE.SWALLOWED_EXCEPTIONS, RESILIENCE.MISSING_TIMEOUT,
and RESILIENCE.MISSING_RETRY rules.
"""

from pathlib import Path

import pytest

from claude_indexer.rules.base import RuleContext, Severity


def create_context(
    content: str, language: str, file_path: str = "test.py"
) -> RuleContext:
    """Create a RuleContext for testing."""
    return RuleContext(
        file_path=Path(file_path),
        content=content,
        language=language,
    )


# =============================================================================
# Unsafe Null Rule Tests
# =============================================================================


class TestUnsafeNullRule:
    """Tests for RESILIENCE.UNSAFE_NULL rule."""

    @pytest.fixture
    def rule(self):
        from claude_indexer.rules.resilience.unsafe_null import UnsafeNullRule

        return UnsafeNullRule()

    def test_rule_metadata(self, rule):
        """Test rule has correct metadata."""
        assert rule.rule_id == "RESILIENCE.UNSAFE_NULL"
        assert rule.category == "resilience"
        assert rule.default_severity == Severity.MEDIUM
        assert rule.is_fast is True

    def test_detects_python_get_without_check(self, rule):
        """Test detection of .get() followed by method call."""
        content = "value = data.get('key').strip()"
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "get()" in findings[0].summary.lower()

    def test_detects_python_get_indexing(self, rule):
        """Test detection of .get() followed by indexing."""
        content = "value = data.get('key')[0]"
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1

    def test_detects_regex_group_without_check(self, rule):
        """Test detection of regex match group access."""
        content = "match = re.search(pattern, text).group(1)"
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "regex" in findings[0].summary.lower()

    def test_ignores_get_with_default(self, rule):
        """Test that .get() with default is not flagged."""
        content = "value = data.get('key', 'default').strip()"
        context = create_context(content, "python")
        findings = rule.check(context)
        # This should not be flagged as it has a default
        assert len(findings) == 0

    def test_ignores_with_none_check(self, rule):
        """Test that code with None check is not flagged."""
        content = """
value = data.get('key')
if value is not None:
    result = value.strip()
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_detects_js_queryselector(self, rule):
        """Test detection of querySelector without null check."""
        content = "const el = document.querySelector('.btn').click();"
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "query" in findings[0].summary.lower()

    def test_ignores_js_optional_chaining(self, rule):
        """Test that optional chaining is not flagged."""
        content = "const el = document.querySelector('.btn')?.click();"
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_detects_js_find_without_check(self, rule):
        """Test detection of .find() followed by property access."""
        content = "const item = items.find(x => x.id === 1).name;"
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 1

    def test_detects_ts_nonnull_assertion(self, rule):
        """Test detection of non-null assertion usage."""
        content = "const value = maybeNull!.property;"
        context = create_context(content, "typescript", file_path="test.ts")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "non-null" in findings[0].summary.lower()

    def test_provides_remediation_hints(self, rule):
        """Test that findings include remediation hints."""
        content = "value = data.get('key').strip()"
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings[0].remediation_hints) > 0


# =============================================================================
# Unsafe Loop Rule Tests
# =============================================================================


class TestUnsafeLoopRule:
    """Tests for RESILIENCE.UNSAFE_LOOP rule."""

    @pytest.fixture
    def rule(self):
        from claude_indexer.rules.resilience.unsafe_loops import UnsafeLoopRule

        return UnsafeLoopRule()

    def test_rule_metadata(self, rule):
        """Test rule has correct metadata."""
        assert rule.rule_id == "RESILIENCE.UNSAFE_LOOP"
        assert rule.category == "resilience"
        assert rule.default_severity == Severity.HIGH
        assert rule.is_fast is True

    def test_detects_while_true_without_break(self, rule):
        """Test detection of while True without break."""
        content = """
while True:
    process_data()
    update_state()
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "while True" in findings[0].summary

    def test_ignores_while_true_with_break(self, rule):
        """Test that while True with break is not flagged."""
        content = """
while True:
    data = get_data()
    if not data:
        break
    process(data)
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_ignores_while_true_with_return(self, rule):
        """Test that while True with return is not flagged."""
        content = """
while True:
    data = get_data()
    if data:
        return data
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_detects_js_while_true(self, rule):
        """Test detection of JavaScript while(true)."""
        content = """
while (true) {
    processData();
    updateState();
}
"""
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 1

    def test_ignores_js_while_true_with_break(self, rule):
        """Test JavaScript while(true) with break."""
        content = """
while (true) {
    const data = getData();
    if (!data) {
        break;
    }
    process(data);
}
"""
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_detects_for_infinite(self, rule):
        """Test detection of for(;;) infinite loop."""
        content = """
for (;;) {
    doSomething();
}
"""
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 1

    def test_provides_remediation_hints(self, rule):
        """Test that findings include remediation hints."""
        content = """
while True:
    process_data()
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings[0].remediation_hints) > 0
        assert any("break" in hint.lower() for hint in findings[0].remediation_hints)


# =============================================================================
# Unsafe Resource Rule Tests
# =============================================================================


class TestUnsafeResourceRule:
    """Tests for RESILIENCE.UNSAFE_RESOURCE rule."""

    @pytest.fixture
    def rule(self):
        from claude_indexer.rules.resilience.unsafe_resources import UnsafeResourceRule

        return UnsafeResourceRule()

    def test_rule_metadata(self, rule):
        """Test rule has correct metadata."""
        assert rule.rule_id == "RESILIENCE.UNSAFE_RESOURCE"
        assert rule.category == "resilience"
        assert rule.default_severity == Severity.MEDIUM
        assert rule.is_fast is True

    def test_detects_open_without_context_manager(self, rule):
        """Test detection of open() without context manager."""
        content = """
f = open('file.txt', 'r')
data = f.read()
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "context manager" in findings[0].summary.lower()

    def test_ignores_open_with_context_manager(self, rule):
        """Test that open() with context manager is not flagged."""
        content = """
with open('file.txt', 'r') as f:
    data = f.read()
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_detects_socket_without_close(self, rule):
        """Test detection of socket without close."""
        content = """
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('localhost', 8080))
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1

    def test_detects_js_setinterval(self, rule):
        """Test detection of setInterval without clearInterval."""
        content = """
const interval = setInterval(() => {
    doSomething();
}, 1000);
"""
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "setInterval" in findings[0].summary

    def test_detects_js_eventlistener(self, rule):
        """Test detection of addEventListener without remove."""
        content = """
element.addEventListener('click', handleClick);
"""
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "listener" in findings[0].summary.lower()

    def test_detects_ts_subscribe(self, rule):
        """Test detection of subscribe without unsubscribe."""
        content = """
this.observable.subscribe(data => {
    this.handleData(data);
});
"""
        context = create_context(content, "typescript", file_path="test.ts")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "subscribe" in findings[0].summary.lower()

    def test_provides_remediation_hints(self, rule):
        """Test that findings include remediation hints."""
        content = """
f = open('file.txt', 'r')
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings[0].remediation_hints) > 0
        assert any("with" in hint.lower() for hint in findings[0].remediation_hints)


# =============================================================================
# Unsafe Concurrency Rule Tests
# =============================================================================


class TestUnsafeConcurrencyRule:
    """Tests for RESILIENCE.UNSAFE_CONCURRENCY rule."""

    @pytest.fixture
    def rule(self):
        from claude_indexer.rules.resilience.unsafe_concurrency import (
            UnsafeConcurrencyRule,
        )

        return UnsafeConcurrencyRule()

    def test_rule_metadata(self, rule):
        """Test rule has correct metadata."""
        assert rule.rule_id == "RESILIENCE.UNSAFE_CONCURRENCY"
        assert rule.category == "resilience"
        assert rule.default_severity == Severity.HIGH
        assert rule.is_fast is True

    def test_detects_global_modification(self, rule):
        """Test detection of global variable modification."""
        content = """
def update_counter():
    global counter
    counter += 1
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "global" in findings[0].summary.lower()

    def test_detects_mutable_default_list(self, rule):
        """Test detection of mutable default argument (list)."""
        content = """
def process_items(items=[]):
    items.append('new')
    return items
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "mutable" in findings[0].summary.lower()

    def test_detects_mutable_default_dict(self, rule):
        """Test detection of mutable default argument (dict)."""
        content = """
def update_config(config={}):
    config['key'] = 'value'
    return config
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "mutable" in findings[0].summary.lower()

    def test_detects_daemon_thread(self, rule):
        """Test detection of daemon thread."""
        content = """
thread = threading.Thread(target=worker)
thread.daemon = True
thread.start()
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "daemon" in findings[0].summary.lower()

    def test_ignores_with_lock(self, rule):
        """Test that code with lock is not flagged."""
        content = """
lock = threading.Lock()
def update_counter():
    global counter
    with lock:
        counter += 1
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        # Global still flagged, but lock provides some protection
        # The rule should recognize the lock context
        assert len(findings) == 0 or any(f.confidence < 1.0 for f in findings)

    def test_detects_js_blocking_loop(self, rule):
        """Test detection of blocking while loop in JS."""
        content = """
while (condition) {
    doSomething();
}
"""
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "block" in findings[0].summary.lower()

    def test_provides_remediation_hints(self, rule):
        """Test that findings include remediation hints."""
        content = """
def update():
    global counter
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings[0].remediation_hints) > 0


# =============================================================================
# Swallowed Exception Rule Tests
# =============================================================================


class TestSwallowedExceptionRule:
    """Tests for RESILIENCE.SWALLOWED_EXCEPTIONS rule."""

    @pytest.fixture
    def rule(self):
        from claude_indexer.rules.resilience.swallowed_exceptions import (
            SwallowedExceptionRule,
        )

        return SwallowedExceptionRule()

    def test_rule_metadata(self, rule):
        """Test rule has correct metadata."""
        assert rule.rule_id == "RESILIENCE.SWALLOWED_EXCEPTIONS"
        assert rule.category == "resilience"
        assert rule.default_severity == Severity.HIGH
        assert rule.is_fast is True

    def test_detects_python_except_pass(self, rule):
        """Test detection of except: pass."""
        content = """
try:
    risky_operation()
except:
    pass
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1
        # Check for various descriptive terms in the summary
        summary_lower = findings[0].summary.lower()
        assert any(
            term in summary_lower
            for term in ["swallowed", "ignored", "empty", "silently"]
        )

    def test_detects_python_named_except_pass(self, rule):
        """Test detection of except Exception: pass."""
        content = """
try:
    risky_operation()
except Exception:
    pass
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1

    def test_detects_python_except_with_alias_pass(self, rule):
        """Test detection of except Exception as e: pass."""
        content = """
try:
    risky_operation()
except Exception as e:
    pass
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1

    def test_detects_js_empty_catch(self, rule):
        """Test detection of catch(e) {}."""
        content = """
try {
    riskyOperation();
} catch (e) {}
"""
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 1

    def test_detects_js_promise_catch_empty(self, rule):
        """Test detection of .catch(() => {})."""
        content = "fetchData().catch(() => {});"
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 1

    def test_ignores_catch_with_logging(self, rule):
        """Test that catch with logging is not flagged."""
        content = """
try:
    risky_operation()
except Exception as e:
    logger.error(f"Error: {e}")
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_ignores_catch_with_rethrow(self, rule):
        """Test that catch with re-throw is not flagged."""
        content = """
try:
    risky_operation()
except ValueError:
    raise
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_ignores_js_catch_with_console(self, rule):
        """Test that JS catch with console.error is not flagged."""
        content = """
try {
    riskyOperation();
} catch (e) {
    console.error(e);
}
"""
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_provides_remediation_hints(self, rule):
        """Test that findings include remediation hints."""
        content = """
try:
    risky()
except:
    pass
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1
        assert len(findings[0].remediation_hints) > 0


# =============================================================================
# Missing Timeout Rule Tests
# =============================================================================


class TestMissingTimeoutRule:
    """Tests for RESILIENCE.MISSING_TIMEOUT rule."""

    @pytest.fixture
    def rule(self):
        from claude_indexer.rules.resilience.missing_timeout import MissingTimeoutRule

        return MissingTimeoutRule()

    def test_rule_metadata(self, rule):
        """Test rule has correct metadata."""
        assert rule.rule_id == "RESILIENCE.MISSING_TIMEOUT"
        assert rule.category == "resilience"
        assert rule.default_severity == Severity.MEDIUM
        assert rule.is_fast is True

    def test_detects_requests_get_without_timeout(self, rule):
        """Test detection of requests.get() without timeout."""
        content = "response = requests.get('https://api.example.com/data')"
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "timeout" in findings[0].summary.lower()

    def test_detects_requests_post_without_timeout(self, rule):
        """Test detection of requests.post() without timeout."""
        content = "response = requests.post('https://api.example.com/data', json=data)"
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1

    def test_ignores_requests_with_timeout(self, rule):
        """Test that requests with timeout is not flagged."""
        content = "response = requests.get('https://api.example.com/data', timeout=30)"
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_ignores_requests_with_tuple_timeout(self, rule):
        """Test that requests with tuple timeout is not flagged."""
        content = "response = requests.get(url, timeout=(3.05, 27))"
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_detects_js_fetch_without_signal(self, rule):
        """Test detection of fetch() without AbortController."""
        content = "const response = await fetch('https://api.example.com/data');"
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 1

    def test_ignores_js_fetch_with_signal(self, rule):
        """Test that fetch with signal is not flagged."""
        content = """
const controller = new AbortController();
const response = await fetch(url, { signal: controller.signal });
"""
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_detects_axios_without_timeout(self, rule):
        """Test detection of axios without timeout config."""
        content = "const response = await axios.get('https://api.example.com/data');"
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 1

    def test_ignores_axios_with_timeout(self, rule):
        """Test that axios with timeout is not flagged."""
        content = "const response = await axios.get(url, { timeout: 5000 });"
        context = create_context(content, "javascript", file_path="test.js")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_provides_remediation_hints(self, rule):
        """Test that findings include remediation hints."""
        content = "response = requests.get(url)"
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 1
        assert len(findings[0].remediation_hints) > 0
        assert any("timeout" in hint.lower() for hint in findings[0].remediation_hints)


# =============================================================================
# Missing Retry Rule Tests
# =============================================================================


class TestMissingRetryRule:
    """Tests for RESILIENCE.MISSING_RETRY rule."""

    @pytest.fixture
    def rule(self):
        from claude_indexer.rules.resilience.missing_retry import MissingRetryRule

        return MissingRetryRule()

    def test_rule_metadata(self, rule):
        """Test rule has correct metadata."""
        assert rule.rule_id == "RESILIENCE.MISSING_RETRY"
        assert rule.category == "resilience"
        assert rule.default_severity == Severity.MEDIUM
        assert rule.is_fast is True

    def test_detects_requests_without_retry(self, rule):
        """Test detection of requests call without retry."""
        content = "response = requests.get(url)"
        context = create_context(content, "python", file_path="module.py")
        findings = rule.check(context)
        assert len(findings) == 1
        assert "retry" in findings[0].summary.lower()

    def test_ignores_with_tenacity_decorator(self, rule):
        """Test that function with tenacity retry is not flagged."""
        content = """
from tenacity import retry, stop_after_attempt

@retry(stop=stop_after_attempt(3))
def fetch_data(url):
    response = requests.get(url)
    return response.json()
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_ignores_with_backoff_decorator(self, rule):
        """Test that function with backoff decorator is not flagged."""
        content = """
import backoff

@backoff.on_exception(backoff.expo, Exception, max_tries=3)
def fetch_data(url):
    response = requests.get(url)
    return response.json()
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_ignores_with_retry_loop(self, rule):
        """Test that function with retry loop is not flagged."""
        content = """
def fetch_data(url):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url)
            return response.json()
        except Exception:
            if attempt == max_retries - 1:
                raise
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        assert len(findings) == 0

    def test_detects_js_fetch_without_retry(self, rule):
        """Test detection of JS fetch without retry."""
        content = """
async function fetchData(url) {
    const response = await fetch(url);
    return response.json();
}
"""
        context = create_context(content, "javascript", file_path="module.js")
        findings = rule.check(context)
        assert len(findings) == 1

    def test_lower_confidence_in_test_files(self, rule):
        """Test that confidence is lower in test files."""
        content = "response = requests.get(url)"
        context_normal = create_context(content, "python", file_path="module.py")
        context_test = create_context(content, "python", file_path="tests/test_api.py")

        findings_normal = rule.check(context_normal)
        findings_test = rule.check(context_test)

        # Test file should have lower confidence or no findings
        if findings_test:
            assert findings_test[0].confidence < findings_normal[0].confidence

    def test_provides_remediation_hints(self, rule):
        """Test that findings include remediation hints."""
        content = """
def fetch(url):
    return requests.get(url)
"""
        context = create_context(content, "python")
        findings = rule.check(context)
        if findings:
            assert len(findings[0].remediation_hints) > 0
            assert any(
                "retry" in hint.lower() or "tenacity" in hint.lower()
                for hint in findings[0].remediation_hints
            )


# =============================================================================
# Cross-Rule Integration Tests
# =============================================================================


class TestResilienceRulesIntegration:
    """Integration tests for all resilience rules."""

    def test_all_rules_have_correct_category(self):
        """Test all resilience rules have correct category."""
        from claude_indexer.rules.resilience.missing_retry import MissingRetryRule
        from claude_indexer.rules.resilience.missing_timeout import MissingTimeoutRule
        from claude_indexer.rules.resilience.swallowed_exceptions import (
            SwallowedExceptionRule,
        )
        from claude_indexer.rules.resilience.unsafe_concurrency import (
            UnsafeConcurrencyRule,
        )
        from claude_indexer.rules.resilience.unsafe_loops import UnsafeLoopRule
        from claude_indexer.rules.resilience.unsafe_null import UnsafeNullRule
        from claude_indexer.rules.resilience.unsafe_resources import UnsafeResourceRule

        rules = [
            UnsafeNullRule(),
            UnsafeLoopRule(),
            UnsafeResourceRule(),
            UnsafeConcurrencyRule(),
            SwallowedExceptionRule(),
            MissingTimeoutRule(),
            MissingRetryRule(),
        ]

        for rule in rules:
            assert rule.category == "resilience"
            assert rule.rule_id.startswith("RESILIENCE.")

    def test_all_rules_support_common_languages(self):
        """Test all rules support Python, JavaScript, TypeScript."""
        from claude_indexer.rules.resilience.missing_retry import MissingRetryRule
        from claude_indexer.rules.resilience.missing_timeout import MissingTimeoutRule
        from claude_indexer.rules.resilience.swallowed_exceptions import (
            SwallowedExceptionRule,
        )
        from claude_indexer.rules.resilience.unsafe_concurrency import (
            UnsafeConcurrencyRule,
        )
        from claude_indexer.rules.resilience.unsafe_loops import UnsafeLoopRule
        from claude_indexer.rules.resilience.unsafe_null import UnsafeNullRule
        from claude_indexer.rules.resilience.unsafe_resources import UnsafeResourceRule

        rules = [
            UnsafeNullRule(),
            UnsafeLoopRule(),
            UnsafeResourceRule(),
            UnsafeConcurrencyRule(),
            SwallowedExceptionRule(),
            MissingTimeoutRule(),
            MissingRetryRule(),
        ]

        for rule in rules:
            langs = rule.supported_languages
            assert "python" in langs
            assert "javascript" in langs
            assert "typescript" in langs

    def test_all_rules_provide_remediation(self):
        """Test all rules provide remediation hints."""
        from claude_indexer.rules.resilience.missing_retry import MissingRetryRule
        from claude_indexer.rules.resilience.missing_timeout import MissingTimeoutRule
        from claude_indexer.rules.resilience.swallowed_exceptions import (
            SwallowedExceptionRule,
        )
        from claude_indexer.rules.resilience.unsafe_concurrency import (
            UnsafeConcurrencyRule,
        )
        from claude_indexer.rules.resilience.unsafe_loops import UnsafeLoopRule
        from claude_indexer.rules.resilience.unsafe_null import UnsafeNullRule
        from claude_indexer.rules.resilience.unsafe_resources import UnsafeResourceRule

        # Test cases that should trigger each rule
        test_cases = [
            (UnsafeNullRule(), "value = data.get('key').strip()", "python"),
            (UnsafeLoopRule(), "while True:\n    pass", "python"),
            (UnsafeResourceRule(), "f = open('file.txt')", "python"),
            (UnsafeConcurrencyRule(), "def f(x=[]):\n    pass", "python"),
            (SwallowedExceptionRule(), "try:\n    x()\nexcept:\n    pass", "python"),
            (MissingTimeoutRule(), "requests.get(url)", "python"),
            (MissingRetryRule(), "def f():\n    requests.get(url)", "python"),
        ]

        for rule, content, language in test_cases:
            context = create_context(content, language)
            findings = rule.check(context)
            if findings:
                assert (
                    len(findings[0].remediation_hints) > 0
                ), f"{rule.rule_id} should provide remediation hints"
