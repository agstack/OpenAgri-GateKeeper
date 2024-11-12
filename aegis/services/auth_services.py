# services/auth_service.py

from django.db import IntegrityError
from django.core.exceptions import ValidationError

from rest_framework_simplejwt.tokens import RefreshToken

from aegis.utils.auth_utils import hash_password, verify_password
from aegis.models import DefaultAuthUserExtend


def register_user(username, email, password, first_name='', last_name=''):
    try:
        hashed_password = hash_password(password)
        user = DefaultAuthUserExtend.objects.create(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            password=hashed_password,
            # contact_no=contact_no
        )
        return {"message": "User created successfully", "user_id": user.uuid}
    except IntegrityError:
        raise ValidationError("Username or email already exists")


def authenticate_user(username: str, password: str):
    try:
        user = DefaultAuthUserExtend.objects.get(username=username, status=1)
    except DefaultAuthUserExtend.DoesNotExist:
        try:
            user = DefaultAuthUserExtend.objects.get(email=username, status=1)
        except DefaultAuthUserExtend.DoesNotExist:
            return None, None, None

    if not verify_password(password, user.password):
        return None, None, None

    # Use SimpleJWT to generate access and refresh tokens
    refresh = RefreshToken.for_user(user)

    # Add custom claims to the access token
    refresh["username"] = user.username
    refresh["email"] = user.email
    refresh["first_name"] = user.first_name
    refresh["last_name"] = user.last_name
    refresh["uuid"] = str(user.uuid)

    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    return user, access_token, refresh_token
