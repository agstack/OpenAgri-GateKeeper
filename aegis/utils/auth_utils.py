# utils/auth_utils.py

import jwt

from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password, check_password


def create_jwt_token(data: dict, token_type: str = "access") -> str:
    if token_type == "access":
        expires_delta = timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    elif token_type == "refresh":
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    elif token_type == "auth":
        expires_delta = timedelta(minutes=settings.AUTH_TOKEN_EXPIRE_MINUTES)
    else:
        raise ValueError("Invalid token type specified.")

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, settings.JWT_SIGNING_KEY, algorithm="HS256")


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
