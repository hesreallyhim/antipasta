"""
Tutorial: Code Complexity Reduction - Version 3 (Extract Validation Functions)

IMPROVEMENT FOCUS: Extract validation logic into separate functions
TECHNIQUE: Single Responsibility Principle - each function does one thing

By extracting validation logic:
- Each function becomes testable in isolation
- The main function becomes a coordinator
- Cyclomatic complexity is distributed across multiple functions
- Code becomes more reusable

Expected improvements:
- Cyclomatic complexity per function should drop dramatically
- Maintainability index should improve
- Overall structure becomes clearer
"""


def validate_username(username):
    """Validate username according to business rules."""
    if username is None or username == "":
        return False, "Username is required"

    if len(username) < 3:
        return False, "Username must be at least 3 characters"

    if len(username) > 20:
        return False, "Username must be 20 characters or less"

    # Check if username contains only valid characters
    for char in username:
        if not (char.isalnum() or char in "_-."):
            return False, "Username can only contain letters, numbers, underscore, dash, or dot"

    # Check if username is not taken
    existing_users = ["admin", "root", "test", "user", "demo"]
    if username.lower() in existing_users:
        return False, "Username is already taken"

    return True, None


def validate_password(password):
    """Validate password strength."""
    if password is None or password == "":
        return False, "Password is required"

    if len(password) < 8:
        return False, "Password must be at least 8 characters"

    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)

    if not all([has_upper, has_lower, has_digit, has_special]):
        return False, "Password must contain uppercase, lowercase, digit and special character"

    return True, None


def validate_email(email):
    """Validate email format."""
    if email is None or email == "":
        return False, "Email is required"

    if "@" not in email:
        return False, "Email must contain @"

    parts = email.split("@")
    if len(parts) != 2:
        return False, "Invalid email format"

    local, domain = parts

    if "." not in domain:
        return False, "Email must contain domain"

    domain_parts = domain.split(".")
    if len(domain_parts) < 2 or len(domain_parts[-1]) < 2:
        return False, "Invalid email domain"

    return True, None


def validate_age(age):
    """Validate user age."""
    if age is None:
        return False, "Age is required"

    try:
        age_int = int(age)
    except (ValueError, TypeError):
        return False, "Age must be a number"

    if age_int < 13:
        return False, "You must be at least 13 years old"

    if age_int > 120:
        return False, "Age must be 120 or less"

    return True, age_int


def validate_country(country):
    """Validate country code."""
    valid_countries = ["US", "UK", "CA", "AU", "DE", "FR", "IT", "ES", "JP", "CN"]
    if country not in valid_countries:
        return False, "Country not supported"
    return True, None


def validate_terms(terms_accepted):
    """Validate terms acceptance."""
    accepted_values = [True, "true", "1", "yes"]
    if terms_accepted not in accepted_values:
        return False, "You must accept the terms and conditions"
    return True, None


def process_referral_code(referral_code):
    """Process referral code and return bonus credits."""
    if not referral_code:
        return 0

    if len(referral_code) != 8 or not referral_code.startswith("REF"):
        return 0

    # Valid referral codes get different bonuses
    premium_codes = ["REF12345", "REF67890", "REF11111"]
    return 100 if referral_code in premium_codes else 50


def format_phone_number(phone):
    """Format phone number to standard format."""
    if not phone:
        return None

    # Extract digits only
    digits = "".join(c for c in phone if c.isdigit())

    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == "1":
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"

    return None


def verify_address(address, city, state, zipcode):
    """Verify if complete address is provided."""
    if not address:
        return True  # Address is optional

    # If address is provided, all fields must be filled
    if not all([city, state, zipcode]):
        return False

    # Validate zipcode format
    return len(zipcode) == 5 or (len(zipcode) == 10 and zipcode[5] == "-")


def normalize_boolean(value):
    """Convert various boolean representations to boolean."""
    return value in [True, "true", "1", "yes"]


def process_user_registration(
    username,
    password,
    email,
    age,
    country,
    referral_code,
    newsletter,
    terms_accepted,
    marketing_consent,
    phone,
    address,
    city,
    state,
    zipcode,
    backup_email,
    security_question,
    security_answer,
    preferred_language,
    timezone,
):
    """Process user registration with all validations and business logic."""

    # Validate all required fields
    valid, error = validate_username(username)
    if not valid:
        return {"success": False, "error": error}

    valid, error = validate_password(password)
    if not valid:
        return {"success": False, "error": error}

    valid, error = validate_email(email)
    if not valid:
        return {"success": False, "error": error}

    valid, age_int = validate_age(age)
    if not valid:
        return {"success": False, "error": age_int}  # age_int contains error message

    valid, error = validate_country(country)
    if not valid:
        return {"success": False, "error": error}

    valid, error = validate_terms(terms_accepted)
    if not valid:
        return {"success": False, "error": error}

    # Process optional fields
    bonus_credits = process_referral_code(referral_code)
    formatted_phone = format_phone_number(phone)
    address_verified = verify_address(address, city, state, zipcode)

    # Prepare user data
    user_data = {
        "username": username,
        "email": email,
        "age": age_int,
        "country": country,
        "newsletter": normalize_boolean(newsletter),
        "marketing": normalize_boolean(marketing_consent),
        "credits": 1000 + bonus_credits,
        "phone": formatted_phone,
        "address_verified": address_verified,
        "language": preferred_language if preferred_language in ["en", "es", "fr", "de"] else "en",
        "timezone": timezone or "UTC",
    }

    # Save to database (simulated)
    print(f"User created: {user_data}")
    return {"success": True, "user_id": 12345, "data": user_data}
