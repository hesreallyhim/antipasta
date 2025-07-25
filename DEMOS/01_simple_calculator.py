"""Demo 1: Simple Calculator - Low Complexity Example

Metrics:
- Cyclomatic Complexity: 1-2 per function
- Cognitive Complexity: 0-1
- Maintainability Index: ~85
- Halstead Volume: Low

This demonstrates clean, simple functions with single responsibilities.
"""


def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b


def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


def calculate(operation: str, a: float, b: float) -> float:
    """Perform calculation based on operation."""
    operations = {
        "add": add,
        "subtract": subtract,
        "multiply": multiply,
        "divide": divide,
    }

    if operation not in operations:
        raise ValueError(f"Unknown operation: {operation}")

    return operations[operation](a, b)
