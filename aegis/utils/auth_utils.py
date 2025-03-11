# utils/auth_utils.py

import jwt

from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password, check_password


def decode_jwt_token(token: str):
    try:
        return jwt.decode(token, settings.JWT_SIGNING_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ValidationError("Token expired")
    except jwt.InvalidTokenError:
        raise ValidationError("Invalid token")


def hash_password(password: str) -> str:
    return make_password(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return check_password(password, hashed_password)
