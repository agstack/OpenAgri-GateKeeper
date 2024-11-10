# services/auth_service.py

from django.db import IntegrityError
from django.core.exceptions import ValidationError

from rest_framework_simplejwt.tokens import RefreshToken

from aegis.utils.auth_utils import hash_password, verify_password, create_jwt_token, decode_jwt_token
from aegis.models import DefaultAuthUserExtend


def register_user(username, email, password, contact_no, first_name='', last_name=''):
    try:
        hashed_password = hash_password(password)
        user = DefaultAuthUserExtend.objects.create(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            password=hashed_password,
            contact_no=contact_no
        )
        return {"message": "User created successfully", "user_id": user.uuid}
    except IntegrityError:
        raise ValidationError("Username or email already exists")

def authenticate_user(login: str, password: str):
    try:
        user = DefaultAuthUserExtend.objects.get(username=login, status=1)
    except DefaultAuthUserExtend.DoesNotExist:
        try:
            user = DefaultAuthUserExtend.objects.get(email=login, status=1)
        except DefaultAuthUserExtend.DoesNotExist:
            return None, None, None

    if not verify_password(password, user.password):
        return None, None, None

    # token_data = {"user_id": user.id, "username": user.username, "email": user.email}
    # access_token = create_jwt_token(token_data, token_type="access")
    # refresh_token = create_jwt_token(token_data, token_type="refresh")

    # Use SimpleJWT to generate access and refresh tokens
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    return user, access_token, refresh_token
