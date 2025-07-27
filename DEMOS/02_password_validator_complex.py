"""Demo 2: Password Validator - High Complexity (Bad Example)

Metrics:
- Cyclomatic Complexity: 15+ (very high)
- Cognitive Complexity: 20+ (very high)
- Maintainability Index: ~45 (poor)
- Halstead Volume: High

This demonstrates overly complex nested logic that should be refactored.
"""


def validate_password(
    password: str, username: str = "", old_passwords: list[str] | None = None
) -> tuple[bool, str]:
    """Validate password with multiple rules (overly complex version)."""
    if password is None or password == "":
        return False, "Password cannot be empty"
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    has_upper = False
    has_lower = False
    has_digit = False
    has_special = False
    consecutive_chars = 0
    prev_char = ""

    for i, char in enumerate(password):
        if char.isupper():
            has_upper = True
            if i > 0 and password[i - 1].isupper():
                consecutive_chars += 1
                if consecutive_chars > 2:
                    return False, "Too many consecutive uppercase letters"
        elif char.islower():
            has_lower = True
            if i > 0 and password[i - 1].islower():
                consecutive_chars += 1
                if consecutive_chars > 3:
                    return False, "Too many consecutive lowercase letters"
        elif char.isdigit():
            has_digit = True
            if i > 0 and password[i - 1].isdigit():
                consecutive_chars += 1
                if consecutive_chars > 2:
                    return False, "Too many consecutive digits"
        elif char in "!@#$%^&*()_+-=[]{}|;:,.<>?":
            has_special = True
        else:
            return False, f"Invalid character: {char}"

        if char != prev_char:
            consecutive_chars = 0
        prev_char = char

    if not has_upper:
        return False, "Password must contain uppercase letter"
    if not has_lower:
        return False, "Password must contain lowercase letter"
    if not has_digit:
        return False, "Password must contain digit"
    if not has_special:
        return False, "Password must contain special character"
    if username is not None:
        if username.lower() in password.lower():
            return False, "Password cannot contain username"
        username_reversed = username[::-1].lower()
        if username_reversed in password.lower():
            return False, "Password cannot contain username (reversed)"

    if old_passwords is not None:
        for old_password in old_passwords:
            if old_password == password:
                return False, "Password was used recently"
            similarity = 0
            for i in range(min(len(password), len(old_password))):
                if password[i] == old_password[i]:
                    similarity += 1
            if similarity / len(password) > 0.8:
                return False, "Password too similar to recent password"

    common_passwords = [
        "password",
        "12345678",
        "qwerty",
        "abc123",
        "password123",
    ]
    for common in common_passwords:
        if common in password.lower():
            return False, "Password contains common pattern"

    return True, "Password is valid"
