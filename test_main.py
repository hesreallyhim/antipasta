#!/usr/bin/env python3
"""Unit tests for main.py (code_cop)"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch
from main import (
    load_config,
    detect_language,
    heuristic_metrics,
    radon_metrics,
    compute_diff,
    evaluate_operation,
    Metrics,
    RADON_AVAILABLE
)


class TestLoadConfig(unittest.TestCase):
    """Test cases for load_config function"""

    def test_load_config_defaults(self) -> None:
        """Test that load_config returns defaults when no config file exists"""
        with patch.dict(
            os.environ,
            {'CLAUDE_PROJECT_DIR': '/nonexistent/path'}
        ):
            config = load_config()
            self.assertEqual(config['max_cyclomatic_increase'], 0.0)
            self.assertEqual(config['max_halstead_volume_increase'], 0.0)
            self.assertEqual(config['min_maintainability_index'], 50.0)
            self.assertEqual(config['max_loc_increase'], 0.0)
            self.assertEqual(config['max_class_count'], 9999999.0)

    def test_load_config_from_file(self) -> None:
        """Test that load_config loads custom values from config file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, '.code_cop.config.json')
            config_data = {
                'thresholds': {
                    'max_cyclomatic_increase': 5.0,
                    'max_halstead_volume_increase': 100.0,
                    'min_maintainability_index': 65.0,
                    'max_loc_increase': 50.0,
                    'max_class_count': 10.0
                }
            }
            with open(config_path, 'w') as f:
                json.dump(config_data, f)

            with patch.dict(os.environ, {'CLAUDE_PROJECT_DIR': tmpdir}):
                config = load_config()
                self.assertEqual(config['max_cyclomatic_increase'], 5.0)
                self.assertEqual(config['max_halstead_volume_increase'],
                                 100.0)
                self.assertEqual(config['min_maintainability_index'], 65.0)
                self.assertEqual(config['max_loc_increase'], 50.0)
                self.assertEqual(config['max_class_count'], 10.0)


class TestDetectLanguage(unittest.TestCase):
    """Test cases for detect_language function"""

    def test_detect_python(self) -> None:
        """Test detection of Python files"""
        self.assertEqual(detect_language('test.py'), 'python')
        self.assertEqual(detect_language('/path/to/script.py'), 'python')
        self.assertEqual(detect_language('test.PY'), 'python')

    def test_detect_typescript(self) -> None:
        """Test detection of TypeScript files"""
        self.assertEqual(detect_language('test.ts'), 'typescript')
        self.assertEqual(detect_language('component.tsx'), 'typescript')
        self.assertEqual(detect_language('/src/app.TS'), 'typescript')

    def test_detect_javascript(self) -> None:
        """Test detection of JavaScript files"""
        self.assertEqual(detect_language('script.js'), 'javascript')
        self.assertEqual(detect_language('component.jsx'), 'javascript')
        self.assertEqual(detect_language('app.JS'), 'javascript')

    def test_detect_unknown(self) -> None:
        """Test detection of unknown file types"""
        self.assertEqual(detect_language('file.txt'), 'unknown')
        self.assertEqual(detect_language('README.md'), 'unknown')
        self.assertEqual(detect_language(None), 'unknown')
        self.assertEqual(detect_language(''), 'unknown')


class TestHeuristicMetrics(unittest.TestCase):
    """Test cases for heuristic_metrics function"""

    def test_heuristic_metrics_simple_code(self) -> None:
        """Test heuristic metrics for simple code without control flow"""
        source = '''
def add(a, b):
    return a + b
'''
        metrics = heuristic_metrics(source)
        self.assertEqual(metrics.cyclomatic, 1.0)  # No decision points
        self.assertEqual(metrics.loc, 2)  # Two non-empty lines
        self.assertGreater(metrics.halstead_volume, 0)
        self.assertGreater(metrics.maintainability_index, 0)
        self.assertEqual(metrics.classes, 0)

    def test_heuristic_metrics_complex_code(self) -> None:
        """Test heuristic metrics for code with control flow"""
        source = '''
def process_data(data):
    if data is None:
        return None

    result = []
    for item in data:
        if item > 0:
            result.append(item)
        elif item < 0:
            result.append(-item)

    return result
'''
        metrics = heuristic_metrics(source)
        self.assertGreater(metrics.cyclomatic, 1.0)  # Has if, for, elif
        self.assertEqual(metrics.loc, 10)  # Ten non-empty lines
        self.assertGreater(metrics.halstead_volume, 0)
        self.assertLess(metrics.maintainability_index, 100)
        self.assertEqual(metrics.classes, 0)

    def test_heuristic_metrics_with_classes(self) -> None:
        """Test heuristic metrics correctly counts classes"""
        source = '''
class Calculator:
    def add(self, a, b):
        return a + b

class AdvancedCalculator(Calculator):
    def multiply(self, a, b):
        return a * b
'''
        metrics = heuristic_metrics(source)
        self.assertEqual(metrics.classes, 2)


class TestComputeDiff(unittest.TestCase):
    """Test cases for compute_diff function"""

    def test_compute_diff_all_increases(self) -> None:
        """Test diff computation when all metrics increase"""
        old = Metrics(
            cyclomatic=5.0,
            halstead_volume=100.0,
            halstead_difficulty=10.0,
            halstead_effort=1000.0,
            maintainability_index=70.0,
            loc=50,
            classes=1
        )
        new = Metrics(
            cyclomatic=8.0,
            halstead_volume=150.0,
            halstead_difficulty=12.0,
            halstead_effort=1800.0,
            maintainability_index=65.0,
            loc=70,
            classes=2
        )
        diff = compute_diff(old, new)
        self.assertEqual(diff['cyclomatic'], 3.0)
        self.assertEqual(diff['halstead_volume'], 50.0)
        self.assertEqual(diff['maintainability_index'], -5.0)
        self.assertEqual(diff['loc'], 20)
        self.assertEqual(diff['class_count'], 1)

    def test_compute_diff_all_decreases(self) -> None:
        """Test diff computation when metrics decrease"""
        old = Metrics(
            cyclomatic=10.0,
            halstead_volume=200.0,
            halstead_difficulty=15.0,
            halstead_effort=3000.0,
            maintainability_index=50.0,
            loc=100,
            classes=3
        )
        new = Metrics(
            cyclomatic=5.0,
            halstead_volume=100.0,
            halstead_difficulty=10.0,
            halstead_effort=1000.0,
            maintainability_index=70.0,
            loc=50,
            classes=1
        )
        diff = compute_diff(old, new)
        self.assertEqual(diff['cyclomatic'], -5.0)
        self.assertEqual(diff['halstead_volume'], -100.0)
        self.assertEqual(diff['maintainability_index'], 20.0)
        self.assertEqual(diff['loc'], -50)
        self.assertEqual(diff['class_count'], -2)


class TestEvaluateOperation(unittest.TestCase):
    """Test cases for evaluate_operation function"""

    def test_evaluate_write_operation_approved(self) -> None:
        """Test Write operation that meets all thresholds"""
        thresholds = {
            'max_cyclomatic_increase': 10.0,
            'max_halstead_volume_increase': 500.0,
            'min_maintainability_index': 40.0,
            'max_loc_increase': 100.0,
            'max_class_count': 5.0
        }
        tool_input = {
            'file_path': 'test.py',
            'content': 'def hello():\n    print("Hello")\n'
        }
        decision, reason = evaluate_operation('Write', tool_input, thresholds)
        self.assertEqual(decision, 'approve')
        self.assertIn('approved', reason.lower())

    def test_evaluate_write_operation_blocked_complexity(self) -> None:
        """Test Write operation blocked due to complexity increase"""
        thresholds = {
            'max_cyclomatic_increase': 0.0,  # Very restrictive
            'max_halstead_volume_increase': 500.0,
            'min_maintainability_index': 40.0,
            'max_loc_increase': 100.0,
            'max_class_count': 5.0
        }
        tool_input = {
            'file_path': 'test.py',
            'content': '''
def complex_function(x):
    if x > 0:
        for i in range(x):
            if i % 2 == 0:
                print(i)
'''
        }
        decision, reason = evaluate_operation('Write', tool_input, thresholds)
        self.assertEqual(decision, 'block')
        self.assertIn('cyclomatic', reason.lower())

    def test_evaluate_edit_operation_approved(self) -> None:
        """Test Edit operation that improves code quality"""
        thresholds = {
            'max_cyclomatic_increase': 10.0,  # Allow some increase
            'max_halstead_volume_increase': 100.0,  # Allow some increase
            'min_maintainability_index': 50.0,
            'max_loc_increase': 10.0,  # Allow some increase
            'max_class_count': 5.0
        }
        tool_input = {
            'file_path': 'test.py',
            'old_string': '''
def complex_func(x):
    if x > 0:
        if x < 10:
            if x != 5:
                return x
''',
            'new_string': '''
def simple_func(x):
    return x if 0 < x < 10 and x != 5 else None
'''
        }
        decision, reason = evaluate_operation('Edit', tool_input, thresholds)
        # Should be approved as it simplifies the code
        self.assertEqual(decision, 'approve')

    def test_evaluate_multiedit_operation(self) -> None:
        """Test MultiEdit operation with multiple edits"""
        thresholds = {
            'max_cyclomatic_increase': 5.0,
            'max_halstead_volume_increase': 200.0,
            'min_maintainability_index': 50.0,
            'max_loc_increase': 20.0,
            'max_class_count': 2.0
        }
        tool_input = {
            'file_path': 'test.py',
            'edits': [
                {
                    'old_string': 'def func1():\n    pass',
                    'new_string': 'def func1():\n    return 1'
                },
                {
                    'old_string': 'def func2():\n    pass',
                    'new_string': (
                        'def func2():\n'
                        '    if True:\n'
                        '        return 2'
                    )
                }
            ]
        }
        decision, reason = evaluate_operation(
            'MultiEdit', tool_input, thresholds
        )
        self.assertIn(decision, ['approve', 'block'])
        self.assertIn('Metrics delta:', reason)


class TestRadonMetrics(unittest.TestCase):
    """Test cases for radon_metrics function"""

    @unittest.skipIf(not RADON_AVAILABLE, "Radon not available")
    def test_radon_metrics_simple_python(self) -> None:
        """Test radon metrics for simple Python code"""
        source = '''
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
'''
        metrics = radon_metrics(source)
        self.assertGreater(metrics.cyclomatic, 0)
        self.assertGreater(metrics.halstead_volume, 0)
        self.assertGreater(metrics.maintainability_index, 0)
        self.assertEqual(metrics.loc, 6)  # 6 lines including the blank line
        self.assertEqual(metrics.classes, 0)

    @unittest.skipIf(not RADON_AVAILABLE, "Radon not available")
    def test_radon_metrics_with_class(self) -> None:
        """Test radon metrics correctly counts Python classes"""
        source = '''
class Calculator:
    def __init__(self) -> None:
        self.result = 0

    def add(self, x):
        self.result += x
        return self.result
'''
        metrics = radon_metrics(source)
        self.assertEqual(metrics.classes, 1)
        self.assertGreater(metrics.loc, 0)

    def test_radon_metrics_fallback(self) -> None:
        """
        Test that radon_metrics falls back to heuristic when radon unavailable
        """
        with patch('main.RADON_AVAILABLE', False):
            source = 'def test():\n    pass'
            metrics = radon_metrics(source)
            # Should still return valid metrics using heuristic
            self.assertIsInstance(metrics, Metrics)
            self.assertEqual(metrics.loc, 2)


if __name__ == '__main__':
    unittest.main()
