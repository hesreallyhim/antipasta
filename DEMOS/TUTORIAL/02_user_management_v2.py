"""
Tutorial: Code Complexity Reduction - Version 2 (Early Returns)

IMPROVEMENT FOCUS: Reducing nesting depth with early returns
TECHNIQUE: Instead of nesting if-statements, return early when validation fails

This is one of the simplest and most effective ways to reduce complexity:
- Replace nested if-else chains with guard clauses
- Return immediately when a condition fails
- This "fails fast" approach makes code more readable

Expected improvements:
- Cognitive complexity should drop significantly (less nesting)
- Maintainability index should improve (more readable)
- Cyclomatic complexity will remain similar (same number of paths)
"""


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

    # Early return for username validation
    if username is None or username == "":
        return {"success": False, "error": "Username is required"}

    if len(username) < 3:
        return {"success": False, "error": "Username must be at least 3 characters"}

    if len(username) > 20:
        return {"success": False, "error": "Username must be 20 characters or less"}

    # Check if username contains only valid characters
    valid_chars = True
    for char in username:
        if not (char.isalnum() or char in "_-."):
            valid_chars = False
            break

    if not valid_chars:
        return {
            "success": False,
            "error": "Username can only contain letters, numbers, underscore, dash, or dot",
        }

    # Check if username is not taken
    existing_users = ["admin", "root", "test", "user", "demo"]
    if username.lower() in existing_users:
        return {"success": False, "error": "Username is already taken"}

    # Password validation with early returns
    if password is None or password == "":
        return {"success": False, "error": "Password is required"}

    if len(password) < 8:
        return {"success": False, "error": "Password must be at least 8 characters"}

    has_upper = False
    has_lower = False
    has_digit = False
    has_special = False

    for char in password:
        if char.isupper():
            has_upper = True
        elif char.islower():
            has_lower = True
        elif char.isdigit():
            has_digit = True
        elif char in "!@#$%^&*()_+-=[]{}|;:,.<>?":
            has_special = True

    if not (has_upper and has_lower and has_digit and has_special):
        return {
            "success": False,
            "error": "Password must contain uppercase, lowercase, digit and special character",
        }

    # Email validation with early returns
    if email is None or email == "":
        return {"success": False, "error": "Email is required"}

    if "@" not in email:
        return {"success": False, "error": "Email must contain @"}

    parts = email.split("@")
    if len(parts) != 2:
        return {"success": False, "error": "Invalid email format"}

    if "." not in parts[1]:
        return {"success": False, "error": "Email must contain domain"}

    domain_parts = parts[1].split(".")
    if len(domain_parts) < 2:
        return {"success": False, "error": "Invalid email domain"}

    if len(domain_parts[-1]) < 2:
        return {"success": False, "error": "Invalid email domain"}

    # Age validation with early returns
    if age is None:
        return {"success": False, "error": "Age is required"}

    if not (isinstance(age, int) or age.isdigit()):
        return {"success": False, "error": "Age must be a number"}

    age_int = int(age)
    if age_int < 13:
        return {"success": False, "error": "You must be at least 13 years old"}

    if age_int > 120:
        return {"success": False, "error": "Age must be 120 or less"}

    # Country validation
    valid_countries = ["US", "UK", "CA", "AU", "DE", "FR", "IT", "ES", "JP", "CN"]
    if country not in valid_countries:
        return {"success": False, "error": "Country not supported"}

    # Terms validation
    if not (
        terms_accepted == True
        or terms_accepted == "true"
        or terms_accepted == "1"
        or terms_accepted == "yes"
    ):
        return {"success": False, "error": "You must accept the terms and conditions"}

    # Process referral code if provided
    bonus_credits = 0
    if referral_code is not None and referral_code != "":
        if len(referral_code) == 8 and referral_code.startswith("REF"):
            # Valid referral code format
            if referral_code in ["REF12345", "REF67890", "REF11111"]:
                bonus_credits = 100
            else:
                # Unknown referral code
                bonus_credits = 50

    # Process phone number if provided
    formatted_phone = None
    if phone is not None and phone != "":
        # Remove all non-digit characters
        digits_only = ""
        for char in phone:
            if char.isdigit():
                digits_only += char

        if len(digits_only) == 10:
            formatted_phone = f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:]}"
        elif len(digits_only) == 11 and digits_only[0] == "1":
            formatted_phone = f"+1 ({digits_only[1:4]}) {digits_only[4:7]}-{digits_only[7:]}"

    # Validate address if provided
    address_verified = True  # Default to true since address is optional
    if address is not None and address != "":
        if (
            city is None
            or city == ""
            or state is None
            or state == ""
            or zipcode is None
            or zipcode == ""
        ):
            address_verified = False
        elif not (len(zipcode) == 5 or (len(zipcode) == 10 and zipcode[5] == "-")):
            address_verified = False

    # Create user account
    user_data = {
        "username": username,
        "email": email,
        "age": age_int,
        "country": country,
        "newsletter": newsletter == True or newsletter == "true" or newsletter == "1",
        "marketing": marketing_consent == True
        or marketing_consent == "true"
        or marketing_consent == "1",
        "credits": 1000 + bonus_credits,
        "phone": formatted_phone,
        "address_verified": address_verified,
        "language": preferred_language if preferred_language in ["en", "es", "fr", "de"] else "en",
        "timezone": timezone if timezone is not None else "UTC",
    }

    # Save to database (simulated)
    print(f"User created: {user_data}")
    return {"success": True, "user_id": 12345, "data": user_data}
