#!/usr/bin/env python3
"""
Proof of Concept: Automated Early Return Refactoring

This demonstrates how we could automatically refactor nested if-else
structures into early returns, which can reduce cognitive complexity
by up to 90%.
"""

import ast
import astor
from typing import List, Optional


class EarlyReturnRefactorer(ast.NodeTransformer):
    """Transform nested if-else patterns to early returns."""

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Visit function definitions and transform their bodies."""
        # Process the function body
        new_body = self._transform_body(node.body)
        if new_body != node.body:
            node.body = new_body
            print(f"Refactored function: {node.name}")

        return self.generic_visit(node)

    def _transform_body(self, body: List[ast.stmt]) -> List[ast.stmt]:
        """Transform a function body to use early returns."""
        new_body = []

        for stmt in body:
            if isinstance(stmt, ast.If) and self._can_convert_to_early_return(stmt):
                # Convert nested if-else to early returns
                early_returns = self._extract_early_returns(stmt)
                new_body.extend(early_returns)
            else:
                new_body.append(stmt)

        return new_body

    def _can_convert_to_early_return(self, if_stmt: ast.If) -> bool:
        """Check if an if statement can be converted to early returns."""
        # Look for patterns where all branches end in returns
        if not if_stmt.orelse:
            return False

        # Check if all branches have returns
        has_if_return = self._branch_ends_with_return(if_stmt.body)
        has_else_return = self._branch_ends_with_return(if_stmt.orelse)

        return has_if_return and has_else_return

    def _branch_ends_with_return(self, body: List[ast.stmt]) -> bool:
        """Check if a branch ends with a return statement."""
        if not body:
            return False

        last_stmt = body[-1]

        # Direct return
        if isinstance(last_stmt, ast.Return):
            return True

        # Nested if-else where all branches return
        if isinstance(last_stmt, ast.If):
            return self._branch_ends_with_return(last_stmt.body) and self._branch_ends_with_return(
                last_stmt.orelse
            )

        return False

    def _extract_early_returns(self, if_stmt: ast.If) -> List[ast.stmt]:
        """Extract early returns from nested if-else structure."""
        early_returns = []

        # Process the current if statement
        if self._is_simple_condition_with_return(if_stmt):
            # Invert condition for early return
            inverted = self._invert_condition(if_stmt.test)
            else_returns = self._get_return_statements(if_stmt.orelse)

            # Create early return with inverted condition
            early_if = ast.If(test=inverted, body=else_returns, orelse=[])
            early_returns.append(early_if)

            # Add the original if body (without the else)
            early_returns.extend(if_stmt.body)
        else:
            # Recursively process nested structures
            early_returns.append(if_stmt)

        return early_returns

    def _is_simple_condition_with_return(self, if_stmt: ast.If) -> bool:
        """Check if this is a simple if-else with returns."""
        if not if_stmt.orelse:
            return False

        # Both branches should end with returns
        if_has_return = any(isinstance(stmt, ast.Return) for stmt in if_stmt.body)
        else_has_return = any(isinstance(stmt, ast.Return) for stmt in if_stmt.orelse)

        return if_has_return and else_has_return

    def _invert_condition(self, condition: ast.expr) -> ast.expr:
        """Invert a boolean condition."""
        # Simple inversion using UnaryOp(Not)
        return ast.UnaryOp(op=ast.Not(), operand=condition)

    def _get_return_statements(self, body: List[ast.stmt]) -> List[ast.stmt]:
        """Extract return statements from a body."""
        returns = []
        for stmt in body:
            if isinstance(stmt, ast.Return):
                returns.append(stmt)
            elif isinstance(stmt, ast.If) and stmt.orelse:
                # Get returns from nested if-else
                returns.extend(self._get_return_statements(stmt.orelse))
        return returns


def refactor_code(source_code: str) -> str:
    """Refactor Python source code to use early returns."""
    # Parse the source code
    tree = ast.parse(source_code)

    # Apply transformations
    refactorer = EarlyReturnRefactorer()
    new_tree = refactorer.visit(tree)

    # Convert back to source code
    return astor.to_source(new_tree)


# Example usage
if __name__ == "__main__":
    # Example 1: Simple nested if-else
    example1 = """
def validate_age(age):
    if age is not None:
        if age >= 0:
            if age <= 120:
                return True
            else:
                return False
        else:
            return False
    else:
        return False
"""

    # Example 2: More complex validation
    example2 = """
def process_user(user):
    if user is not None:
        if user.active:
            if user.verified:
                # Process the user
                result = do_processing(user)
                return {"success": True, "data": result}
            else:
                return {"success": False, "error": "User not verified"}
        else:
            return {"success": False, "error": "User not active"}
    else:
        return {"success": False, "error": "User is None"}
"""

    print("Example 1 - Before:")
    print(example1)

    refactored1 = refactor_code(example1)
    print("\nExample 1 - After:")
    print(refactored1)

    print("\n" + "=" * 60 + "\n")

    print("Example 2 - Before:")
    print(example2)

    refactored2 = refactor_code(example2)
    print("\nExample 2 - After:")
    print(refactored2)


# More advanced implementation would handle:
# 1. Multiple return points in branches
# 2. Complex conditions (AND/OR)
# 3. Try-except blocks
# 4. Preserving comments
# 5. Maintaining code style
# 6. Side effects in conditions
