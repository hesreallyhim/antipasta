"""Tests for Python metric runners."""

from pathlib import Path

from antipasta.core.metrics import MetricType
from antipasta.runners.python.radon import RadonRunner


class TestRadonRunner:
    """Tests for RadonRunner."""

    def test_is_available(self) -> None:
        """Test that Radon is available in test environment."""
        runner = RadonRunner()
        assert runner.is_available() is True

    def test_supported_metrics(self) -> None:
        """Test that runner reports correct supported metrics."""
        runner = RadonRunner()
        supported = runner.supported_metrics

        expected_metrics = [
            MetricType.CYCLOMATIC_COMPLEXITY.value,
            MetricType.MAINTAINABILITY_INDEX.value,
            MetricType.HALSTEAD_VOLUME.value,
            MetricType.HALSTEAD_DIFFICULTY.value,
            MetricType.HALSTEAD_EFFORT.value,
            MetricType.HALSTEAD_TIME.value,
            MetricType.HALSTEAD_BUGS.value,
            MetricType.LINES_OF_CODE.value,
            MetricType.LOGICAL_LINES_OF_CODE.value,
            MetricType.SOURCE_LINES_OF_CODE.value,
            MetricType.COMMENT_LINES.value,
            MetricType.BLANK_LINES.value,
        ]

        assert set(supported) == set(expected_metrics)

    def test_analyze_simple_file(self, tmp_path: Path) -> None:
        """Test analyzing a simple Python file."""
        # Create a simple Python file
        file_path = tmp_path / "simple.py"
        file_path.write_text(
            """
def hello():
    \"\"\"Say hello.\"\"\"
    print("Hello, World!")

def add(a, b):
    \"\"\"Add two numbers.\"\"\"
    return a + b
"""
        )

        runner = RadonRunner()
        result = runner.analyze(file_path)

        assert result.file_path == file_path
        assert result.language == "python"
        assert result.error is None
        assert len(result.metrics) > 0

        # Check cyclomatic complexity
        cc_metrics = [
            m for m in result.metrics if m.metric_type == MetricType.CYCLOMATIC_COMPLEXITY
        ]
        assert len(cc_metrics) >= 2  # At least 2 functions
        for m in cc_metrics:
            if m.function_name in ["hello", "add"]:
                assert m.value == 1  # Simple functions have CC of 1

        # Check maintainability index
        mi_metric = result.get_metric(MetricType.MAINTAINABILITY_INDEX)
        assert mi_metric is not None
        assert mi_metric.value > 50  # Simple code should have high MI

        # Check LOC metrics
        loc_metric = result.get_metric(MetricType.LINES_OF_CODE)
        assert loc_metric is not None
        assert loc_metric.value == 8  # Total lines in file

    def test_analyze_complex_file(self, tmp_path: Path) -> None:
        """Test analyzing a file with complex functions."""
        file_path = tmp_path / "complex.py"
        file_path.write_text(
            """
def complex_function(x, y, z):
    \"\"\"A function with higher complexity.\"\"\"
    result = 0
    if x > 0:
        if y > 0:
            result = x + y
        else:
            result = x - y
    elif z > 0:
        if x == 0:
            result = z
        else:
            result = z * 2
    else:
        for i in range(10):
            if i % 2 == 0:
                result += i
    return result
"""
        )

        runner = RadonRunner()
        result = runner.analyze(file_path)

        # Find the complex function's CC
        cc_metrics = [
            m
            for m in result.metrics
            if m.metric_type == MetricType.CYCLOMATIC_COMPLEXITY
            and m.function_name == "complex_function"
        ]
        assert len(cc_metrics) == 1
        assert cc_metrics[0].value > 5  # Should have higher complexity

        # MI should be lower for complex code
        mi_metric = result.get_metric(MetricType.MAINTAINABILITY_INDEX)
        assert mi_metric is not None
        assert mi_metric.value < 100  # Complex code has lower MI

    def test_analyze_with_content(self, tmp_path: Path) -> None:
        """Test analyzing with content provided."""
        file_path = tmp_path / "test.py"
        content = """
def test():
    return 42
"""

        runner = RadonRunner()
        # Note: we still need the file to exist for radon commands
        file_path.write_text(content)
        result = runner.analyze(file_path, content=content)

        assert result.error is None
        assert len(result.metrics) > 0

    def test_analyze_nonexistent_file(self) -> None:
        """Test analyzing a file that doesn't exist."""
        runner = RadonRunner()
        result = runner.analyze(Path("/nonexistent/file.py"))

        assert result.error is not None
        assert "Failed to read file" in result.error
        assert len(result.metrics) == 0

    def test_analyze_syntax_error(self, tmp_path: Path) -> None:
        """Test analyzing a file with syntax errors."""
        file_path = tmp_path / "syntax_error.py"
        file_path.write_text(
            """
def broken(:
    pass
"""
        )

        runner = RadonRunner()
        result = runner.analyze(file_path)

        # Radon might still return some metrics even with syntax errors
        # but certain metrics like CC might be missing
        assert result.file_path == file_path

    def test_halstead_metrics(self, tmp_path: Path) -> None:
        """Test that Halstead metrics are calculated correctly."""
        file_path = tmp_path / "halstead.py"
        file_path.write_text(
            """
def calculate(a, b, c):
    x = a + b
    y = b * c
    z = x / y
    return z if z > 0 else -z
"""
        )

        runner = RadonRunner()
        result = runner.analyze(file_path)

        # Check all Halstead metrics are present
        halstead_types = [
            MetricType.HALSTEAD_VOLUME,
            MetricType.HALSTEAD_DIFFICULTY,
            MetricType.HALSTEAD_EFFORT,
            MetricType.HALSTEAD_TIME,
            MetricType.HALSTEAD_BUGS,
        ]

        for metric_type in halstead_types:
            metric = result.get_metric(metric_type)
            assert metric is not None
            assert metric.value >= 0

    def test_class_methods(self, tmp_path: Path) -> None:
        """Test analyzing a file with class methods."""
        file_path = tmp_path / "class_example.py"
        file_path.write_text(
            """
class Calculator:
    def add(self, a, b):
        return a + b

    def multiply(self, a, b):
        return a * b

    def divide(self, a, b):
        if b != 0:
            return a / b
        else:
            raise ValueError("Division by zero")
"""
        )

        runner = RadonRunner()
        result = runner.analyze(file_path)

        # Check that methods are detected
        cc_metrics = [
            m
            for m in result.metrics
            if m.metric_type == MetricType.CYCLOMATIC_COMPLEXITY and m.function_name
        ]

        method_names = {m.function_name for m in cc_metrics}
        assert "add" in method_names
        assert "multiply" in method_names
        assert "divide" in method_names

        # divide method should have higher CC due to if statement
        divide_metric = next(m for m in cc_metrics if m.function_name == "divide")
        assert divide_metric.value > 1
