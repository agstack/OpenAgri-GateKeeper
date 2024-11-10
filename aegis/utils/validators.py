# utils/validators.py

import re

from django.core.exceptions import ValidationError


ALLOWED_NAME_REGEX = r"^[a-zA-Z0-9\-_.,()\[\]{}@#&]*$"


def validate_email(email: str) -> str:
    email_regex = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
    if not re.match(email_regex, email):
        raise ValidationError("Invalid email format")
    return email

def validate_username(username: str) -> str:
    if len(username) < 3:
        raise ValidationError("Username must be at least 3 characters long")
    return username

def validate_password(password: str) -> str:
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long")
    return password
