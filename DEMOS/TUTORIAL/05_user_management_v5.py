"""
Tutorial: Code Complexity Reduction - Version 5 (Final Best Practices)

IMPROVEMENT FOCUS: Professional patterns and testability
TECHNIQUE: Dependency injection, validators as classes, proper separation

This final version shows enterprise-level patterns:
- Validator classes for reusability
- Repository pattern for data access
- Service layer for business logic
- Easy to test each component
- Easy to extend with new validators

This version maintains low complexity while being production-ready.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class UserRegistrationData:
    """User registration input data."""

    username: str
    password: str
    email: str
    age: int
    country: str
    terms_accepted: bool
    referral_code: str | None = None
    newsletter: bool | None = False
    marketing_consent: bool | None = False
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zipcode: str | None = None
    preferred_language: str | None = "en"
    timezone: str | None = "UTC"


class ValidationResult:
    """Result of a validation check."""

    def __init__(self, is_valid: bool, error: str | None = None):
        self.is_valid = is_valid
        self.error = error


class Validator(ABC):
    """Base validator interface."""

    @abstractmethod
    def validate(self, value: Any) -> ValidationResult:
        pass


class UsernameValidator(Validator):
    """Validates usernames according to business rules."""

    def __init__(self, min_length: int = 3, max_length: int = 20):
        self.min_length = min_length
        self.max_length = max_length
        self.reserved_names = {"admin", "root", "test", "user", "demo"}
        self.valid_pattern = re.compile(r"^[a-zA-Z0-9._-]+$")

    def validate(self, username: str) -> ValidationResult:
        if not username:
            return ValidationResult(False, "Username is required")

        if not self.min_length <= len(username) <= self.max_length:
            return ValidationResult(
                False,
                f"Username must be {self.min_length}-"
                f"{self.max_length} characters",
            )

        if not self.valid_pattern.match(username):
            return ValidationResult(
                False, "Username can only contain letters, "
                "numbers, underscore, dash, or dot"
            )

        if username.lower() in self.reserved_names:
            return ValidationResult(False, "Username is already taken")

        return ValidationResult(True)


class PasswordValidator(Validator):
    """Validates password strength."""

    def __init__(self, min_length: int = 8):
        self.min_length = min_length

    def validate(self, password: str) -> ValidationResult:
        if not password:
            return ValidationResult(False, "Password is required")

        if len(password) < self.min_length:
            return ValidationResult(
                False,
                f"Password must be at least {self.min_length} characters",
            )

        requirements = [
            (r"[A-Z]", "uppercase letter"),
            (r"[a-z]", "lowercase letter"),
            (r"[0-9]", "digit"),
            (r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]", "special character"),
        ]

        missing = [
            desc
            for pattern, desc in requirements
            if not re.search(pattern, password)
        ]

        if missing:
            return ValidationResult(
                False, f"Password must contain: {', '.join(missing)}"
            )

        return ValidationResult(True)


class EmailValidator(Validator):
    """Validates email addresses."""

    def __init__(self) -> None:
        # Simple email regex - in production use a library
        self.email_pattern = re.compile(
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        )

    def validate(self, email: str) -> ValidationResult:
        if not email:
            return ValidationResult(False, "Email is required")

        if not self.email_pattern.match(email):
            return ValidationResult(False, "Invalid email format")

        return ValidationResult(True)


class UserRepository(Protocol):
    """Interface for user data access."""

    def save_user(self, user_data: dict[str, Any]) -> int:
        """Save user and return user ID."""
        ...

    def username_exists(self, username: str) -> bool:
        """Check if username already exists."""
        ...


class MockUserRepository:
    """Mock implementation for demo purposes."""

    def save_user(self, user_data: dict[str, Any]) -> int:
        print(f"Saving user: {user_data['username']}")
        return 12345

    def username_exists(self, username: str) -> bool:
        return username.lower() in {"admin", "root", "test", "user", "demo"}


class UserRegistrationService:
    """Service for handling user registration."""

    def __init__(self, repository: UserRepository):
        self.repository = repository
        self.username_validator = UsernameValidator()
        self.password_validator = PasswordValidator()
        self.email_validator = EmailValidator()

        # Configuration
        self.valid_countries = {
            "US", "UK", "CA", "AU", "DE", "FR", "IT", "ES", "JP", "CN"
        }
        self.valid_languages = {"en", "es", "fr", "de"}
        self.min_age = 13
        self.max_age = 120
        self.initial_credits = 1000
        self.referral_bonuses = {
            "REF12345": 100,
            "REF67890": 100,
            "REF11111": 100,
        }
        self.default_referral_bonus = 50

    def register_user(self, data: UserRegistrationData) -> dict[str, Any]:
        """Process user registration."""
        # Validate basic fields
        validations = [
            self.username_validator.validate(data.username),
            self.password_validator.validate(data.password),
            self.email_validator.validate(data.email),
        ]

        for result in validations:
            if not result.is_valid:
                return {"success": False, "error": result.error}

        # Validate age
        if not self.min_age <= data.age <= self.max_age:
            return {
                "success": False,
                "error": (
                    f"Age must be between {self.min_age} and {self.max_age}"
                ),
            }

        # Validate country
        if data.country not in self.valid_countries:
            return {"success": False, "error": "Country not supported"}

        # Validate terms
        if not data.terms_accepted:
            return {"success": False, "error": (
                "You must accept the terms and conditions"
            )}

        # Check username availability (in real app)
        if self.repository.username_exists(data.username):
            return {"success": False, "error": "Username is already taken"}

        # Build user data
        user_data = self._build_user_data(data)

        # Save user
        user_id = self.repository.save_user(user_data)

        return {"success": True, "user_id": user_id, "data": user_data}

    def _build_user_data(self, data: UserRegistrationData) -> dict[str, Any]:
        """Build user data dictionary from registration data."""
        return {
            "username": data.username,
            "email": data.email,
            "age": data.age,
            "country": data.country,
            "newsletter": bool(data.newsletter),
            "marketing": bool(data.marketing_consent),
            "credits": self._calculate_credits(data.referral_code),
            "phone": self._format_phone(data.phone),
            "address_verified": self._is_address_complete(data),
            "language": data.preferred_language
            if data.preferred_language in self.valid_languages
            else "en",
            "timezone": data.timezone or "UTC",
        }

    def _calculate_credits(self, referral_code: str | None) -> int:
        """Calculate total credits including referral bonus."""
        if not referral_code or not (
            self._is_valid_referral_format(referral_code)
        ):
            return self.initial_credits

        bonus = self.referral_bonuses.get(
            referral_code, self.default_referral_bonus
        )
        return self.initial_credits + bonus

    def _is_valid_referral_format(self, code: str) -> bool:
        """Check if referral code has valid format."""
        return len(code) == 8 and code.startswith("REF")

    def _format_phone(self, phone: str | None) -> str | None:
        """Format phone number."""
        if not phone:
            return None

        digits = "".join(c for c in phone if c.isdigit())

        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        if len(digits) == 11 and digits[0] == "1":
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"

        return None

    def _is_address_complete(self, data: UserRegistrationData) -> bool:
        """Check if address is complete."""
        if not data.address:
            return False

        has_all_fields = all([data.city, data.state, data.zipcode])
        if not has_all_fields:
            return False

        assert data.zipcode is not None, (
            "Zipcode should not be None"  # Ensure zipcode is not None
        )

        # Simple zipcode validation
        return bool(re.match(r"^\d{5}(-\d{4})?$", data.zipcode))


# Example usage
def main() -> None:
    """Example of how to use the registration service."""
    # Create repository and service
    repository = MockUserRepository()
    service = UserRegistrationService(repository)

    # Create registration data
    registration_data = UserRegistrationData(
        username="john_doe",
        password="SecurePass123!",
        email="john@example.com",
        age=25,
        country="US",
        terms_accepted=True,
        referral_code="REF12345",
        newsletter=True,
        phone="555-123-4567",
    )

    # Process registration
    result = service.register_user(registration_data)
    print(f"Registration result: {result}")


if __name__ == "__main__":
    main()
