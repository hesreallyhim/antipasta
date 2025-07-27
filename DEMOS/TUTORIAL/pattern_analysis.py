#!/usr/bin/env python3
"""
Analyze code patterns that contribute to complexity.
This tool helps identify refactoring opportunities.
"""

import ast
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple


class ComplexityPatternAnalyzer(ast.NodeVisitor):
    """Analyze AST to find complexity patterns."""

    def __init__(self):
        self.patterns = defaultdict(list)
        self.current_function = None
        self.nesting_level = 0

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Track function context."""
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function

    def visit_If(self, node: ast.If):
        """Analyze if statements for patterns."""
        self.nesting_level += 1

        # Pattern 1: Nested if-else that could be early returns
        if self.nesting_level > 1 and node.orelse:
            self.patterns["nested_if_else"].append(
                {
                    "function": self.current_function,
                    "line": node.lineno,
                    "depth": self.nesting_level,
                }
            )

        # Pattern 2: If-elif chains (could be dictionary dispatch)
        if self._is_elif_chain(node):
            chain_length = self._count_elif_chain(node)
            if chain_length > 3:
                self.patterns["long_elif_chain"].append(
                    {"function": self.current_function, "line": node.lineno, "length": chain_length}
                )

        # Pattern 3: Boolean flag setting
        if self._is_boolean_flag_pattern(node):
            self.patterns["boolean_flag"].append(
                {"function": self.current_function, "line": node.lineno}
            )

        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_For(self, node: ast.For):
        """Analyze for loops for patterns."""
        # Pattern 4: Accumulator pattern
        if self._is_accumulator_pattern(node):
            self.patterns["accumulator_loop"].append(
                {"function": self.current_function, "line": node.lineno}
            )

        # Pattern 5: Boolean search pattern
        if self._is_boolean_search_pattern(node):
            self.patterns["boolean_search"].append(
                {"function": self.current_function, "line": node.lineno}
            )

        self.generic_visit(node)

    def visit_Try(self, node: ast.Try):
        """Analyze try-except blocks."""
        self.nesting_level += 1

        # Pattern 6: Nested try-except
        if self.nesting_level > 1:
            self.patterns["nested_try"].append(
                {
                    "function": self.current_function,
                    "line": node.lineno,
                    "depth": self.nesting_level,
                }
            )

        self.generic_visit(node)
        self.nesting_level -= 1

    def _is_elif_chain(self, node: ast.If) -> bool:
        """Check if this is the start of an elif chain."""
        if not node.orelse:
            return False
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            return True
        return False

    def _count_elif_chain(self, node: ast.If) -> int:
        """Count the length of an elif chain."""
        count = 1
        current = node
        while current.orelse:
            if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                count += 1
                current = current.orelse[0]
            else:
                break
        return count

    def _is_boolean_flag_pattern(self, node: ast.If) -> bool:
        """Check if this is a boolean flag setting pattern."""
        # Look for: if condition: flag = True
        if not node.body or len(node.body) != 1:
            return False

        stmt = node.body[0]
        if isinstance(stmt, ast.Assign):
            # Check if assigning True/False
            if isinstance(stmt.value, ast.Constant):
                return isinstance(stmt.value.value, bool)

        return False

    def _is_accumulator_pattern(self, node: ast.For) -> bool:
        """Check if this is an accumulator pattern."""
        # Look for: for x in y: result.append(...)
        for stmt in node.body:
            if isinstance(stmt, ast.Expr):
                if isinstance(stmt.value, ast.Call):
                    if isinstance(stmt.value.func, ast.Attribute):
                        if stmt.value.func.attr == "append":
                            return True
        return False

    def _is_boolean_search_pattern(self, node: ast.For) -> bool:
        """Check if this is a boolean search pattern."""
        # Look for: for x in y: if condition: found = True; break
        has_break = any(isinstance(stmt, ast.Break) for stmt in ast.walk(node))
        has_boolean_assign = False

        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Assign):
                if isinstance(stmt.value, ast.Constant):
                    if isinstance(stmt.value.value, bool):
                        has_boolean_assign = True

        return has_break and has_boolean_assign


def analyze_file(filepath: Path) -> Dict[str, List]:
    """Analyze a single Python file for complexity patterns."""
    try:
        with open(filepath) as f:
            source = f.read()

        tree = ast.parse(source)
        analyzer = ComplexityPatternAnalyzer()
        analyzer.visit(tree)

        return dict(analyzer.patterns)
    except Exception as e:
        print(f"Error analyzing {filepath}: {e}")
        return {}


def generate_report(patterns: Dict[str, List]) -> None:
    """Generate a report of found patterns."""
    print("\n" + "=" * 60)
    print("COMPLEXITY PATTERN ANALYSIS REPORT")
    print("=" * 60 + "\n")

    if not patterns:
        print("No complexity patterns found!")
        return

    # Summary
    print("SUMMARY:")
    total = sum(len(instances) for instances in patterns.values())
    print(f"Total patterns found: {total}")
    print(f"Pattern types: {len(patterns)}\n")

    # Details by pattern
    print("PATTERNS FOUND:\n")

    pattern_descriptions = {
        "nested_if_else": "Nested if-else structures (can use early returns)",
        "long_elif_chain": "Long if-elif chains (can use dictionary dispatch)",
        "boolean_flag": "Boolean flag assignments (can use any/all)",
        "accumulator_loop": "Accumulator loops (can use comprehensions)",
        "boolean_search": "Boolean search loops (can use any/next)",
        "nested_try": "Nested try-except blocks (can flatten)",
    }

    for pattern_type, instances in patterns.items():
        print(f"{pattern_descriptions.get(pattern_type, pattern_type)}:")
        print(f"  Found: {len(instances)} instances")

        # Show top 3 examples
        for i, instance in enumerate(instances[:3]):
            func = instance.get("function", "module-level")
            line = instance.get("line", "?")
            extra = ""

            if "depth" in instance:
                extra = f" (depth: {instance['depth']})"
            elif "length" in instance:
                extra = f" (length: {instance['length']})"

            print(f"    - {func}:{line}{extra}")

        if len(instances) > 3:
            print(f"    ... and {len(instances) - 3} more")
        print()

    # Recommendations
    print("\nRECOMMENDATIONS:")
    print("1. Start with nested if-else patterns - biggest complexity reduction")
    print("2. Convert long elif chains to dictionary dispatch")
    print("3. Replace accumulator loops with comprehensions")
    print("4. Use any()/all() for boolean searches")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python pattern_analysis.py <file.py>")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"File not found: {filepath}")
        sys.exit(1)

    patterns = analyze_file(filepath)
    generate_report(patterns)


if __name__ == "__main__":
    main()
