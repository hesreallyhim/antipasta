"""
Tutorial: Code Complexity Reduction - Version 4 (Data Classes & Configuration)

IMPROVEMENT FOCUS: Reduce parameter count and improve data organization
TECHNIQUE: Use data classes and configuration objects

Too many parameters increase complexity:
- Hard to remember parameter order
- Functions become unwieldy
- Increases Halstead volume

Solution:
- Group related parameters into data classes
- Use configuration for validation rules
- This improves both maintainability and reduces volume

Expected improvements:
- Halstead volume should decrease
- Maintainability index should improve
- Code becomes more organized
"""

from dataclasses import dataclass
from typing import Any

# Configuration constants
VALID_COUNTRIES = ["US", "UK", "CA", "AU", "DE", "FR", "IT", "ES", "JP", "CN"]
VALID_LANGUAGES = ["en", "es", "fr", "de"]
PREMIUM_REFERRAL_CODES = ["REF12345", "REF67890", "REF11111"]
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 20
MIN_PASSWORD_LENGTH = 8
MIN_AGE = 13
MAX_AGE = 120
INITIAL_CREDITS = 1000
PREMIUM_REFERRAL_BONUS = 100
STANDARD_REFERRAL_BONUS = 50


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
    preferred_language: str | None = "en"
    timezone: str | None = "UTC"


@dataclass
class AddressData:
    """User address information."""

    address: str | None = None
    city: str | None = None
    state: str | None = None
    zipcode: str | None = None


class ValidationError(Exception):
    """Custom exception for validation errors."""

    pass


def validate_username(username: str) -> None:
    """Validate username. Raises ValidationError if invalid."""
    if not username:
        raise ValidationError("Username is required")

    if not MIN_USERNAME_LENGTH <= len(username) <= MAX_USERNAME_LENGTH:
        raise ValidationError(
            f"Username must be {MIN_USERNAME_LENGTH}-{MAX_USERNAME_LENGTH} characters"
        )

    if not all(c.isalnum() or c in "_-." for c in username):
        raise ValidationError(
            "Username can only contain letters, numbers, underscore, dash, or dot"
        )

    # In real app, this would check database
    if username.lower() in ["admin", "root", "test", "user", "demo"]:
        raise ValidationError("Username is already taken")


def validate_password(password: str) -> None:
    """Validate password strength. Raises ValidationError if invalid."""
    if not password:
        raise ValidationError("Password is required")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        )

    checks = {
        "uppercase": any(c.isupper() for c in password),
        "lowercase": any(c.islower() for c in password),
        "digit": any(c.isdigit() for c in password),
        "special": any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password),
    }

    if not all(checks.values()):
        raise ValidationError(
            "Password must contain uppercase, lowercase, digit and special character"
        )


def validate_email(email: str) -> None:
    """Validate email format. Raises ValidationError if invalid."""
    if not email:
        raise ValidationError("Email is required")

    if email.count("@") != 1:
        raise ValidationError("Invalid email format")

    local, domain = email.split("@")

    if not local or not domain:
        raise ValidationError("Invalid email format")

    if "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValidationError("Invalid email domain")


def validate_registration_data(data: UserRegistrationData) -> None:
    """Validate all registration data. Raises ValidationError if invalid."""
    validate_username(data.username)
    validate_password(data.password)
    validate_email(data.email)

    if data.age < MIN_AGE:
        raise ValidationError(f"You must be at least {MIN_AGE} years old")

    if data.age > MAX_AGE:
        raise ValidationError(f"Age must be {MAX_AGE} or less")

    if data.country not in VALID_COUNTRIES:
        raise ValidationError("Country not supported")

    if not data.terms_accepted:
        raise ValidationError("You must accept the terms and conditions")


def calculate_bonus_credits(referral_code: str | None) -> int:
    """Calculate bonus credits from referral code."""
    if (
        not referral_code
        or len(referral_code) != 8
        or not referral_code.startswith("REF")
    ):
        return 0

    return (
        PREMIUM_REFERRAL_BONUS
        if referral_code in PREMIUM_REFERRAL_CODES
        else STANDARD_REFERRAL_BONUS
    )


def format_phone_number(phone: str | None) -> str | None:
    """Format phone number to standard format."""
    if not phone:
        return None

    digits = "".join(c for c in phone if c.isdigit())

    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    if len(digits) == 11 and digits[0] == "1":
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"

    return None


def is_address_complete(address: AddressData) -> bool:
    """Check if address information is complete."""
    if not address.address:
        return True  # Address is optional

    # If address is provided, all fields must be filled
    if not all([address.city, address.state, address.zipcode]):
        return False
    assert address.zipcode is not None, "Zipcode should not be None"

    # Validate zipcode format
    zip_str = address.zipcode
    return len(zip_str) == 5 or (len(zip_str) == 10 and zip_str[5] == "-")


def create_user_account(
    data: UserRegistrationData, address: AddressData
) -> dict[str, Any]:
    """Create user account after validation."""
    return {
        "username": data.username,
        "email": data.email,
        "age": data.age,
        "country": data.country,
        "newsletter": bool(data.newsletter),
        "marketing": bool(data.marketing_consent),
        "credits": INITIAL_CREDITS
        + calculate_bonus_credits(data.referral_code),
        "phone": format_phone_number(data.phone),
        "address_verified": is_address_complete(address),
        "language": data.preferred_language
        if data.preferred_language in VALID_LANGUAGES
        else "en",
        "timezone": data.timezone or "UTC",
    }


def process_user_registration(
    registration_data: UserRegistrationData, address_data: AddressData
) -> dict[str, Any]:
    """Process user registration with all validations and business logic."""
    try:
        # Validate all data
        validate_registration_data(registration_data)

        # Create user account
        user_data = create_user_account(registration_data, address_data)

        # Save to database (simulated)
        print(f"User created: {user_data}")

        return {"success": True, "user_id": 12345, "data": user_data}

    except ValidationError as e:
        return {"success": False, "error": str(e)}
