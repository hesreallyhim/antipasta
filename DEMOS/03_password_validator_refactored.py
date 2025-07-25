"""Demo 3: Password Validator - Refactored Version

Metrics:
- Cyclomatic Complexity: 2-3 per function (much better)
- Cognitive Complexity: 1-2 per function
- Maintainability Index: ~75 (good)
- Halstead Volume: Moderate

This is a refactored version of Demo 2, showing how to reduce complexity
through decomposition and early returns.
"""

import re


class PasswordValidator:
    """Clean password validator with separated concerns."""

    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    COMMON_PASSWORDS = {"password", "12345678", "qwerty", "abc123", "password123"}

    def __init__(self, min_length: int = 8):
        self.min_length = min_length
        self.rules = [
            self._check_length,
            self._check_uppercase,
            self._check_lowercase,
            self._check_digit,
            self._check_special_char,
            self._check_valid_chars,
            self._check_consecutive_chars,
        ]

    def validate(
        self,
        password: str,
        username: str | None = None,
        old_passwords: list[str] | None = None,
    ) -> tuple[bool, str]:
        """Validate password against all rules."""
        if not password:
            return False, "Password cannot be empty"

        # Check basic rules
        for rule in self.rules:
            is_valid, message = rule(password)
            if not is_valid:
                return False, message

        # Check username-related rules
        if username:
            is_valid, message = self._check_username_similarity(password, username)
            if not is_valid:
                return False, message

        # Check password history
        if old_passwords:
            is_valid, message = self._check_password_history(password, old_passwords)
            if not is_valid:
                return False, message

        # Check common passwords
        is_valid, message = self._check_common_passwords(password)
        if not is_valid:
            return False, message

        return True, "Password is valid"

    def _check_length(self, password: str) -> tuple[bool, str]:
        """Check minimum length."""
        if len(password) < self.min_length:
            return False, f"Password must be at least {self.min_length} characters"
        return True, ""

    def _check_uppercase(self, password: str) -> tuple[bool, str]:
        """Check for uppercase letter."""
        if not re.search(r"[A-Z]", password):
            return False, "Password must contain uppercase letter"
        return True, ""

    def _check_lowercase(self, password: str) -> tuple[bool, str]:
        """Check for lowercase letter."""
        if not re.search(r"[a-z]", password):
            return False, "Password must contain lowercase letter"
        return True, ""

    def _check_digit(self, password: str) -> tuple[bool, str]:
        """Check for digit."""
        if not re.search(r"\d", password):
            return False, "Password must contain digit"
        return True, ""

    def _check_special_char(self, password: str) -> tuple[bool, str]:
        """Check for special character."""
        if not any(char in self.SPECIAL_CHARS for char in password):
            return False, "Password must contain special character"
        return True, ""

    def _check_valid_chars(self, password: str) -> tuple[bool, str]:
        """Check all characters are valid."""
        allowed = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" + self.SPECIAL_CHARS
        )
        for char in password:
            if char not in allowed:
                return False, f"Invalid character: {char}"
        return True, ""

    def _check_consecutive_chars(self, password: str) -> tuple[bool, str]:
        """Check for too many consecutive similar characters."""
        for pattern, max_count, name in [
            (r"[A-Z]{3,}", 2, "uppercase letters"),
            (r"[a-z]{4,}", 3, "lowercase letters"),
            (r"\d{3,}", 2, "digits"),
        ]:
            if re.search(pattern, password):
                return False, f"Too many consecutive {name}"
        return True, ""

    def _check_username_similarity(self, password: str, username: str) -> tuple[bool, str]:
        """Check password doesn't contain username."""
        username_lower = username.lower()
        password_lower = password.lower()

        if username_lower in password_lower:
            return False, "Password cannot contain username"

        if username_lower[::-1] in password_lower:
            return False, "Password cannot contain username (reversed)"

        return True, ""

    def _check_password_history(self, password: str, old_passwords: list[str]) -> tuple[bool, str]:
        """Check password against history."""
        if password in old_passwords:
            return False, "Password was used recently"

        for old_password in old_passwords:
            similarity = self._calculate_similarity(password, old_password)
            if similarity > 0.8:
                return False, "Password too similar to recent password"

        return True, ""

    def _calculate_similarity(self, password1: str, password2: str) -> float:
        """Calculate similarity ratio between two passwords."""
        if not password1 or not password2:
            return 0.0

        matches = sum(1 for a, b in zip(password1, password2, strict=False) if a == b)
        return matches / max(len(password1), len(password2))

    def _check_common_passwords(self, password: str) -> tuple[bool, str]:
        """Check against common passwords."""
        password_lower = password.lower()
        for common in self.COMMON_PASSWORDS:
            if common in password_lower:
                return False, "Password contains common pattern"
        return True, ""


# Simple function interface for backward compatibility
def validate_password(
    password: str, username: str | None = None, old_passwords: list[str] | None = None
) -> tuple[bool, str]:
    """Validate password using default validator."""
    validator = PasswordValidator()
    return validator.validate(password, username, old_passwords)
