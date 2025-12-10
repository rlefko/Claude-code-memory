"""Unit tests for UI guard reporters."""

import json
from io import StringIO

import pytest

from claude_indexer.ui.cli.reporter import CLIReporter, JSONReporter
from claude_indexer.ui.models import (
    Evidence,
    EvidenceType,
    Finding,
    Severity,
    SymbolKind,
    SymbolRef,
    UIAnalysisResult,
    Visibility,
)


class TestCLIReporter:
    """Tests for CLIReporter."""

    @pytest.fixture
    def reporter(self):
        """Create a CLIReporter without colors for testing."""
        stream = StringIO()
        return CLIReporter(stream=stream, use_color=False)

    @pytest.fixture
    def sample_finding(self):
        """Create a sample finding for testing."""
        return Finding(
            rule_id="COLOR.NON_TOKEN",
            severity=Severity.FAIL,
            confidence=0.95,
            summary="Hardcoded color #ff6b6b not in design tokens",
            evidence=[
                Evidence(
                    evidence_type=EvidenceType.STATIC,
                    description="Found in property 'background-color'",
                    data={"property": "background-color", "value": "#ff6b6b"},
                )
            ],
            remediation_hints=["Use token: --color-error-500 (#ef4444)"],
            source_ref=SymbolRef(
                file_path="src/Button.tsx",
                start_line=42,
                end_line=42,
                kind=SymbolKind.CSS,
                visibility=Visibility.LOCAL,
            ),
        )

    def test_empty_result(self, reporter):
        """Empty result should show no issues message."""
        result = UIAnalysisResult(
            findings=[],
            files_analyzed=["test.css"],
            analysis_time_ms=50.0,
            tier=0,
        )

        reporter.report(result)
        output = reporter.stream.getvalue()

        assert "No issues found" in output
        assert "50ms" in output

    def test_single_finding(self, reporter, sample_finding):
        """Single finding should be formatted correctly."""
        result = UIAnalysisResult(
            findings=[sample_finding],
            files_analyzed=["src/Button.tsx"],
            analysis_time_ms=100.0,
            tier=0,
        )

        reporter.report(result)
        output = reporter.stream.getvalue()

        assert "src/Button.tsx:42" in output
        assert "COLOR.NON_TOKEN" in output
        assert "#ff6b6b" in output
        assert "-> Use token:" in output
        assert "1 issue(s)" in output
        assert "100ms" in output
        assert "(1 blocking)" in output

    def test_multiple_findings(self, reporter):
        """Multiple findings should all be reported."""
        findings = [
            Finding(
                rule_id="COLOR.NON_TOKEN",
                severity=Severity.FAIL,
                confidence=0.95,
                summary="Hardcoded color",
                evidence=[
                    Evidence(evidence_type=EvidenceType.STATIC, description="test")
                ],
                source_ref=SymbolRef("test.css", 10, 10, SymbolKind.CSS),
            ),
            Finding(
                rule_id="SPACING.OFF_SCALE",
                severity=Severity.WARN,
                confidence=0.85,
                summary="Off-scale spacing",
                evidence=[
                    Evidence(evidence_type=EvidenceType.STATIC, description="test")
                ],
                source_ref=SymbolRef("test.css", 20, 20, SymbolKind.CSS),
            ),
        ]

        result = UIAnalysisResult(
            findings=findings,
            files_analyzed=["test.css"],
            analysis_time_ms=150.0,
            tier=0,
        )

        reporter.report(result)
        output = reporter.stream.getvalue()

        assert "test.css:10" in output
        assert "test.css:20" in output
        assert "COLOR.NON_TOKEN" in output
        assert "SPACING.OFF_SCALE" in output
        assert "2 issue(s)" in output

    def test_remediation_hints(self, reporter, sample_finding):
        """Remediation hints should be displayed."""
        result = UIAnalysisResult(
            findings=[sample_finding],
            files_analyzed=["src/Button.tsx"],
            analysis_time_ms=100.0,
            tier=0,
        )

        reporter.report(result)
        output = reporter.stream.getvalue()

        assert "-> Use token: --color-error-500" in output


class TestCLIReporterColors:
    """Tests for CLIReporter color output."""

    def test_color_codes_enabled(self):
        """Color codes should be included when enabled."""
        stream = StringIO()
        reporter = CLIReporter(stream=stream, use_color=True)

        finding = Finding(
            rule_id="COLOR.NON_TOKEN",
            severity=Severity.FAIL,
            confidence=0.95,
            summary="test",
            evidence=[Evidence(evidence_type=EvidenceType.STATIC, description="test")],
            source_ref=SymbolRef("test.css", 1, 1, SymbolKind.CSS),
        )

        result = UIAnalysisResult(
            findings=[finding],
            files_analyzed=["test.css"],
            analysis_time_ms=50.0,
            tier=0,
        )

        reporter.report(result)
        output = stream.getvalue()

        # Should contain ANSI escape codes
        assert "\033[" in output

    def test_color_codes_disabled(self):
        """Color codes should not be included when disabled."""
        stream = StringIO()
        reporter = CLIReporter(stream=stream, use_color=False)

        finding = Finding(
            rule_id="COLOR.NON_TOKEN",
            severity=Severity.FAIL,
            confidence=0.95,
            summary="test",
            evidence=[Evidence(evidence_type=EvidenceType.STATIC, description="test")],
            source_ref=SymbolRef("test.css", 1, 1, SymbolKind.CSS),
        )

        result = UIAnalysisResult(
            findings=[finding],
            files_analyzed=["test.css"],
            analysis_time_ms=50.0,
            tier=0,
        )

        reporter.report(result)
        output = stream.getvalue()

        # Should not contain ANSI escape codes
        assert "\033[" not in output


class TestJSONReporter:
    """Tests for JSONReporter."""

    @pytest.fixture
    def reporter(self):
        """Create a JSONReporter for testing."""
        stream = StringIO()
        return JSONReporter(stream=stream)

    def test_empty_result(self, reporter):
        """Empty result should produce valid JSON."""
        result = UIAnalysisResult(
            findings=[],
            files_analyzed=["test.css"],
            analysis_time_ms=50.0,
            tier=0,
        )

        output_dict = reporter.report(result)

        assert output_dict["decision"] == "approve"
        assert output_dict["reason"] == "UI checks passed"
        assert output_dict["findings"] == []
        assert output_dict["analysis_time_ms"] == 50.0
        assert output_dict["tier"] == 0

    def test_blocking_finding(self, reporter):
        """Blocking findings should set decision to 'block'."""
        finding = Finding(
            rule_id="COLOR.NON_TOKEN",
            severity=Severity.FAIL,
            confidence=0.95,
            summary="Hardcoded color",
            evidence=[Evidence(evidence_type=EvidenceType.STATIC, description="test")],
            source_ref=SymbolRef("test.css", 1, 1, SymbolKind.CSS),
        )

        result = UIAnalysisResult(
            findings=[finding],
            files_analyzed=["test.css"],
            analysis_time_ms=100.0,
            tier=0,
        )

        output_dict = reporter.report(result)

        assert output_dict["decision"] == "block"
        assert "COLOR.NON_TOKEN" in output_dict["reason"]

    def test_warning_finding(self, reporter):
        """Warning findings should set decision to 'approve'."""
        finding = Finding(
            rule_id="SPACING.OFF_SCALE",
            severity=Severity.WARN,
            confidence=0.85,
            summary="Off-scale spacing",
            evidence=[Evidence(evidence_type=EvidenceType.STATIC, description="test")],
            source_ref=SymbolRef("test.css", 1, 1, SymbolKind.CSS),
        )

        result = UIAnalysisResult(
            findings=[finding],
            files_analyzed=["test.css"],
            analysis_time_ms=100.0,
            tier=0,
        )

        output_dict = reporter.report(result)

        assert output_dict["decision"] == "approve"
        assert output_dict["counts"]["warn"] == 1

    def test_valid_json_output(self, reporter):
        """Output should be valid JSON."""
        finding = Finding(
            rule_id="COLOR.NON_TOKEN",
            severity=Severity.FAIL,
            confidence=0.95,
            summary="test",
            evidence=[Evidence(evidence_type=EvidenceType.STATIC, description="test")],
            remediation_hints=["Use token"],
            source_ref=SymbolRef("test.css", 1, 1, SymbolKind.CSS),
        )

        result = UIAnalysisResult(
            findings=[finding],
            files_analyzed=["test.css"],
            analysis_time_ms=100.0,
            tier=0,
        )

        reporter.report(result)
        output = reporter.stream.getvalue()

        # Should be valid JSON
        parsed = json.loads(output)
        assert "decision" in parsed
        assert "findings" in parsed
        assert len(parsed["findings"]) == 1

    def test_counts_included(self, reporter):
        """Output should include counts by severity."""
        findings = [
            Finding(
                rule_id="RULE1",
                severity=Severity.FAIL,
                confidence=0.9,
                summary="fail",
                evidence=[
                    Evidence(evidence_type=EvidenceType.STATIC, description="test")
                ],
            ),
            Finding(
                rule_id="RULE2",
                severity=Severity.WARN,
                confidence=0.8,
                summary="warn",
                evidence=[
                    Evidence(evidence_type=EvidenceType.STATIC, description="test")
                ],
            ),
            Finding(
                rule_id="RULE3",
                severity=Severity.INFO,
                confidence=0.7,
                summary="info",
                evidence=[
                    Evidence(evidence_type=EvidenceType.STATIC, description="test")
                ],
            ),
        ]

        result = UIAnalysisResult(
            findings=findings,
            files_analyzed=["test.css"],
            analysis_time_ms=100.0,
            tier=0,
        )

        output_dict = reporter.report(result)

        assert output_dict["counts"]["fail"] == 1
        assert output_dict["counts"]["warn"] == 1
        assert output_dict["counts"]["info"] == 1

    def test_multiple_blocking_rules(self, reporter):
        """Multiple blocking rules should be summarized in reason."""
        findings = [
            Finding(
                rule_id="RULE1",
                severity=Severity.FAIL,
                confidence=0.9,
                summary="fail1",
                evidence=[
                    Evidence(evidence_type=EvidenceType.STATIC, description="test")
                ],
            ),
            Finding(
                rule_id="RULE2",
                severity=Severity.FAIL,
                confidence=0.9,
                summary="fail2",
                evidence=[
                    Evidence(evidence_type=EvidenceType.STATIC, description="test")
                ],
            ),
        ]

        result = UIAnalysisResult(
            findings=findings,
            files_analyzed=["test.css"],
            analysis_time_ms=100.0,
            tier=0,
        )

        output_dict = reporter.report(result)

        assert output_dict["decision"] == "block"
        assert "2 rule violations" in output_dict["reason"]

    def test_finding_serialization(self, reporter):
        """Finding should be properly serialized to JSON."""
        finding = Finding(
            rule_id="COLOR.NON_TOKEN",
            severity=Severity.FAIL,
            confidence=0.95,
            summary="Hardcoded color",
            evidence=[
                Evidence(
                    evidence_type=EvidenceType.STATIC,
                    description="test",
                    data={"property": "color", "value": "#ff0000"},
                )
            ],
            remediation_hints=["Use token: --color-primary"],
            source_ref=SymbolRef("test.css", 10, 12, SymbolKind.CSS),
        )

        result = UIAnalysisResult(
            findings=[finding],
            files_analyzed=["test.css"],
            analysis_time_ms=100.0,
            tier=0,
        )

        output_dict = reporter.report(result)
        finding_dict = output_dict["findings"][0]

        assert finding_dict["rule_id"] == "COLOR.NON_TOKEN"
        assert finding_dict["severity"] == "fail"
        assert finding_dict["confidence"] == 0.95
        assert finding_dict["summary"] == "Hardcoded color"
        assert finding_dict["remediation_hints"] == ["Use token: --color-primary"]
        assert finding_dict["source_ref"]["file_path"] == "test.css"
        assert finding_dict["source_ref"]["start_line"] == 10
