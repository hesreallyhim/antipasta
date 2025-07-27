"""
Tutorial: Code Complexity Reduction - Version 1 (Initial Bad Code)

This is an intentionally poorly written user management system with:
- Very high cyclomatic complexity (nested conditions)
- Very high cognitive complexity (deeply nested logic)
- Low maintainability index (long, complex functions)
- High Halstead metrics (complex operations)

This represents typical legacy code that grew organically without refactoring.
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

    # This function has everything in one place - a common anti-pattern
    if username is not None and username != "":
        if len(username) >= 3:
            if len(username) <= 20:
                # Check if username contains only valid characters
                valid_chars = True
                for char in username:
                    if not (char.isalnum() or char in "_-."):
                        valid_chars = False
                        break

                if valid_chars:
                    # Check if username is not taken
                    existing_users = ["admin", "root", "test", "user", "demo"]
                    if username.lower() not in existing_users:
                        # Username is valid, now check password
                        if password is not None and password != "":
                            if len(password) >= 8:
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

                                if has_upper and has_lower and has_digit and has_special:
                                    # Password is strong, check email
                                    if email is not None and email != "":
                                        if "@" in email:
                                            parts = email.split("@")
                                            if len(parts) == 2:
                                                if "." in parts[1]:
                                                    domain_parts = parts[1].split(".")
                                                    if len(domain_parts) >= 2:
                                                        if len(domain_parts[-1]) >= 2:
                                                            # Email looks valid, check age
                                                            if age is not None:
                                                                if (
                                                                    isinstance(age, int)
                                                                    or age.isdigit()
                                                                ):
                                                                    age_int = int(age)
                                                                    if age_int >= 13:
                                                                        if age_int <= 120:
                                                                            # Age is valid, check country
                                                                            valid_countries = [
                                                                                "US",
                                                                                "UK",
                                                                                "CA",
                                                                                "AU",
                                                                                "DE",
                                                                                "FR",
                                                                                "IT",
                                                                                "ES",
                                                                                "JP",
                                                                                "CN",
                                                                            ]
                                                                            if (
                                                                                country
                                                                                in valid_countries
                                                                            ):
                                                                                # Check terms accepted
                                                                                if (
                                                                                    terms_accepted
                                                                                    == True
                                                                                    or terms_accepted
                                                                                    == "true"
                                                                                    or terms_accepted
                                                                                    == "1"
                                                                                    or terms_accepted
                                                                                    == "yes"
                                                                                ):
                                                                                    # Process referral code if provided
                                                                                    bonus_credits = 0
                                                                                    if (
                                                                                        referral_code
                                                                                        is not None
                                                                                        and referral_code
                                                                                        != ""
                                                                                    ):
                                                                                        if (
                                                                                            len(
                                                                                                referral_code
                                                                                            )
                                                                                            == 8
                                                                                        ):
                                                                                            if referral_code.startswith(
                                                                                                "REF"
                                                                                            ):
                                                                                                # Valid referral code format
                                                                                                if (
                                                                                                    referral_code
                                                                                                    in [
                                                                                                        "REF12345",
                                                                                                        "REF67890",
                                                                                                        "REF11111",
                                                                                                    ]
                                                                                                ):
                                                                                                    bonus_credits = 100
                                                                                                else:
                                                                                                    # Unknown referral code
                                                                                                    bonus_credits = 50

                                                                                    # Process phone number if provided
                                                                                    formatted_phone = None
                                                                                    if (
                                                                                        phone
                                                                                        is not None
                                                                                        and phone
                                                                                        != ""
                                                                                    ):
                                                                                        # Remove all non-digit characters
                                                                                        digits_only = ""
                                                                                        for (
                                                                                            char
                                                                                        ) in phone:
                                                                                            if char.isdigit():
                                                                                                digits_only += char

                                                                                        if (
                                                                                            len(
                                                                                                digits_only
                                                                                            )
                                                                                            == 10
                                                                                        ):
                                                                                            formatted_phone = f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:]}"
                                                                                        elif (
                                                                                            len(
                                                                                                digits_only
                                                                                            )
                                                                                            == 11
                                                                                            and digits_only[
                                                                                                0
                                                                                            ]
                                                                                            == "1"
                                                                                        ):
                                                                                            formatted_phone = f"+1 ({digits_only[1:4]}) {digits_only[4:7]}-{digits_only[7:]}"

                                                                                    # Validate address if provided
                                                                                    if (
                                                                                        address
                                                                                        is not None
                                                                                        and address
                                                                                        != ""
                                                                                    ):
                                                                                        if (
                                                                                            city
                                                                                            is not None
                                                                                            and city
                                                                                            != ""
                                                                                        ):
                                                                                            if (
                                                                                                state
                                                                                                is not None
                                                                                                and state
                                                                                                != ""
                                                                                            ):
                                                                                                if (
                                                                                                    zipcode
                                                                                                    is not None
                                                                                                    and zipcode
                                                                                                    != ""
                                                                                                ):
                                                                                                    # Check if zipcode is valid
                                                                                                    if (
                                                                                                        len(
                                                                                                            zipcode
                                                                                                        )
                                                                                                        == 5
                                                                                                        or (
                                                                                                            len(
                                                                                                                zipcode
                                                                                                            )
                                                                                                            == 10
                                                                                                            and zipcode[
                                                                                                                5
                                                                                                            ]
                                                                                                            == "-"
                                                                                                        )
                                                                                                    ):
                                                                                                        # Full address provided
                                                                                                        address_verified = True
                                                                                                    else:
                                                                                                        address_verified = False
                                                                                                else:
                                                                                                    address_verified = False
                                                                                            else:
                                                                                                address_verified = False
                                                                                        else:
                                                                                            address_verified = False
                                                                                    else:
                                                                                        address_verified = True  # Address is optional

                                                                                    # Create user account
                                                                                    user_data = {
                                                                                        "username": username,
                                                                                        "email": email,
                                                                                        "age": age_int,
                                                                                        "country": country,
                                                                                        "newsletter": newsletter
                                                                                        == True
                                                                                        or newsletter
                                                                                        == "true"
                                                                                        or newsletter
                                                                                        == "1",
                                                                                        "marketing": marketing_consent
                                                                                        == True
                                                                                        or marketing_consent
                                                                                        == "true"
                                                                                        or marketing_consent
                                                                                        == "1",
                                                                                        "credits": 1000
                                                                                        + bonus_credits,
                                                                                        "phone": formatted_phone,
                                                                                        "address_verified": address_verified,
                                                                                        "language": preferred_language
                                                                                        if preferred_language
                                                                                        in [
                                                                                            "en",
                                                                                            "es",
                                                                                            "fr",
                                                                                            "de",
                                                                                        ]
                                                                                        else "en",
                                                                                        "timezone": timezone
                                                                                        if timezone
                                                                                        is not None
                                                                                        else "UTC",
                                                                                    }

                                                                                    # Save to database (simulated)
                                                                                    print(
                                                                                        f"User created: {user_data}"
                                                                                    )
                                                                                    return {
                                                                                        "success": True,
                                                                                        "user_id": 12345,
                                                                                        "data": user_data,
                                                                                    }
                                                                                else:
                                                                                    return {
                                                                                        "success": False,
                                                                                        "error": "You must accept the terms and conditions",
                                                                                    }
                                                                            else:
                                                                                return {
                                                                                    "success": False,
                                                                                    "error": "Country not supported",
                                                                                }
                                                                        else:
                                                                            return {
                                                                                "success": False,
                                                                                "error": "Age must be 120 or less",
                                                                            }
                                                                    else:
                                                                        return {
                                                                            "success": False,
                                                                            "error": "You must be at least 13 years old",
                                                                        }
                                                                else:
                                                                    return {
                                                                        "success": False,
                                                                        "error": "Age must be a number",
                                                                    }
                                                            else:
                                                                return {
                                                                    "success": False,
                                                                    "error": "Age is required",
                                                                }
                                                        else:
                                                            return {
                                                                "success": False,
                                                                "error": "Invalid email domain",
                                                            }
                                                    else:
                                                        return {
                                                            "success": False,
                                                            "error": "Invalid email domain",
                                                        }
                                                else:
                                                    return {
                                                        "success": False,
                                                        "error": "Email must contain domain",
                                                    }
                                            else:
                                                return {
                                                    "success": False,
                                                    "error": "Invalid email format",
                                                }
                                        else:
                                            return {
                                                "success": False,
                                                "error": "Email must contain @",
                                            }
                                    else:
                                        return {"success": False, "error": "Email is required"}
                                else:
                                    return {
                                        "success": False,
                                        "error": "Password must contain uppercase, lowercase, digit and special character",
                                    }
                            else:
                                return {
                                    "success": False,
                                    "error": "Password must be at least 8 characters",
                                }
                        else:
                            return {"success": False, "error": "Password is required"}
                    else:
                        return {"success": False, "error": "Username is already taken"}
                else:
                    return {
                        "success": False,
                        "error": "Username can only contain letters, numbers, underscore, dash, or dot",
                    }
            else:
                return {"success": False, "error": "Username must be 20 characters or less"}
        else:
            return {"success": False, "error": "Username must be at least 3 characters"}
    else:
        return {"success": False, "error": "Username is required"}
