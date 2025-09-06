"""Tests for violation detection."""

from pathlib import Path

from antipasta.core.config import ComparisonOperator, MetricConfig
from antipasta.core.metrics import MetricResult, MetricType
from antipasta.core.violations import FileReport, Violation, check_metric_violation


class TestViolation:
    """Tests for Violation class."""

    def test_violation_creation(self) -> None:
        """Test creating a violation."""
        violation = Violation(
            file_path=Path("test.py"),
            metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
            value=15.0,
            threshold=10.0,
            comparison=ComparisonOperator.LE,
            line_number=42,
            function_name="complex_function",
        )

        assert violation.file_path == Path("test.py")
        assert violation.metric_type == MetricType.CYCLOMATIC_COMPLEXITY
        assert violation.value == 15.0
        assert violation.threshold == 10.0
        assert violation.line_number == 42
        assert violation.function_name == "complex_function"

    def test_violation_message_generation(self) -> None:
        """Test automatic message generation."""
        violation = Violation(
            file_path=Path("test.py"),
            metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
            value=15.0,
            threshold=10.0,
            comparison=ComparisonOperator.LE,
            line_number=42,
            function_name="complex_function",
        )

        expected = (
            "test.py:42 (complex_function): Cyclomatic Complexity is 15.00 (threshold: <= 10.0)"
        )
        assert violation.message == expected

    def test_violation_message_without_location(self) -> None:
        """Test message generation without line number or function."""
        violation = Violation(
            file_path=Path("test.py"),
            metric_type=MetricType.MAINTAINABILITY_INDEX,
            value=45.0,
            threshold=50.0,
            comparison=ComparisonOperator.GE,
        )

        expected = "test.py: Maintainability Index is 45.00 (threshold: >= 50.0)"
        assert violation.message == expected


class TestFileReport:
    """Tests for FileReport class."""

    def test_file_report_creation(self) -> None:
        """Test creating a file report."""
        metrics = [
            MetricResult(
                file_path=Path("test.py"),
                metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
                value=5.0,
            )
        ]
        violations: list[Violation] = []

        report = FileReport(
            file_path=Path("test.py"),
            language="python",
            metrics=metrics,
            violations=violations,
        )

        assert report.file_path == Path("test.py")
        assert report.language == "python"
        assert len(report.metrics) == 1
        assert not report.has_violations
        assert report.violation_count == 0

    def test_file_report_with_violations(self) -> None:
        """Test file report with violations."""
        violations = [
            Violation(
                file_path=Path("test.py"),
                metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
                value=15.0,
                threshold=10.0,
                comparison=ComparisonOperator.LE,
            ),
            Violation(
                file_path=Path("test.py"),
                metric_type=MetricType.MAINTAINABILITY_INDEX,
                value=40.0,
                threshold=50.0,
                comparison=ComparisonOperator.GE,
            ),
        ]

        report = FileReport(
            file_path=Path("test.py"),
            language="python",
            metrics=[],
            violations=violations,
        )

        assert report.has_violations
        assert report.violation_count == 2

    def test_file_report_with_error(self) -> None:
        """Test file report with error."""
        report = FileReport(
            file_path=Path("test.py"),
            language="python",
            metrics=[],
            violations=[],
            error="Syntax error in file",
        )

        assert report.error == "Syntax error in file"
        assert not report.has_violations


class TestCheckMetricViolation:
    """Tests for check_metric_violation function."""

    def test_check_violation_le_operator(self) -> None:
        """Test <= operator violation checking."""
        metric = MetricResult(
            file_path=Path("test.py"),
            metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
            value=15.0,
        )
        config = MetricConfig(
            type=MetricType.CYCLOMATIC_COMPLEXITY,
            threshold=10.0,
            comparison=ComparisonOperator.LE,
        )

        violation = check_metric_violation(metric, config)
        assert violation is not None
        assert violation.value == 15.0
        assert violation.threshold == 10.0

        # Test non-violation
        metric.value = 10.0
        violation = check_metric_violation(metric, config)
        assert violation is None

    def test_check_violation_ge_operator(self) -> None:
        """Test >= operator violation checking."""
        metric = MetricResult(
            file_path=Path("test.py"),
            metric_type=MetricType.MAINTAINABILITY_INDEX,
            value=40.0,
        )
        config = MetricConfig(
            type=MetricType.MAINTAINABILITY_INDEX,
            threshold=50.0,
            comparison=ComparisonOperator.GE,
        )

        violation = check_metric_violation(metric, config)
        assert violation is not None
        assert violation.value == 40.0
        assert violation.threshold == 50.0

        # Test non-violation
        metric.value = 50.0
        violation = check_metric_violation(metric, config)
        assert violation is None

    def test_check_violation_all_operators(self) -> None:
        """Test all comparison operators."""
        metric = MetricResult(
            file_path=Path("test.py"),
            metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
            value=10.0,
        )

        # Test < operator
        config = MetricConfig(
            type=MetricType.CYCLOMATIC_COMPLEXITY,
            threshold=10.0,
            comparison=ComparisonOperator.LT,
        )
        assert check_metric_violation(metric, config) is not None  # 10 is not < 10

        # Test > operator
        config.comparison = ComparisonOperator.GT
        assert check_metric_violation(metric, config) is not None  # 10 is not > 10

        # Test == operator
        config.comparison = ComparisonOperator.EQ
        assert check_metric_violation(metric, config) is None  # 10 == 10

        # Test != operator
        config.comparison = ComparisonOperator.NE
        assert check_metric_violation(metric, config) is not None  # 10 != 10 is false

    def test_check_violation_disabled_metric(self) -> None:
        """Test that disabled metrics don't create violations."""
        metric = MetricResult(
            file_path=Path("test.py"),
            metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
            value=100.0,  # Very high value
        )
        config = MetricConfig(
            type=MetricType.CYCLOMATIC_COMPLEXITY,
            threshold=10.0,
            comparison=ComparisonOperator.LE,
            enabled=False,
        )

        violation = check_metric_violation(metric, config)
        assert violation is None  # Disabled metrics never violate

    def test_check_violation_preserves_metadata(self) -> None:
        """Test that violation preserves metric metadata."""
        metric = MetricResult(
            file_path=Path("test.py"),
            metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
            value=15.0,
            line_number=42,
            function_name="complex_function",
        )
        config = MetricConfig(
            type=MetricType.CYCLOMATIC_COMPLEXITY,
            threshold=10.0,
            comparison=ComparisonOperator.LE,
        )

        violation = check_metric_violation(metric, config)
        assert violation is not None
        assert violation.line_number == 42
        assert violation.function_name == "complex_function"
