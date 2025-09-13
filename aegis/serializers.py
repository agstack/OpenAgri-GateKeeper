# serializers.py

from typing import cast, TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db.models import Q

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

if TYPE_CHECKING:
    from aegis.models import DefaultAuthUserExtend


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        user = cast("DefaultAuthUserExtend", user)

        token = super().get_token(user)
        token["username"] = user.username
        token["first_name"] = user.first_name
        token["last_name"] = user.last_name
        # token["service_name"] = user.service_name
        token["uuid"] = str(getattr(user, "uuid", ""))
        return token

    def validate(self, attrs):
        # Extract username/email and service_name from the request data
        login_identifier = (attrs.get("username") or "").strip()  # Can be either username or email

        # Get the user model
        user_model = get_user_model()

        if not login_identifier:
            raise AuthenticationFailed("No active account found with the given credentials.")

        user = user_model.objects.filter(
            Q(username__iexact=login_identifier) | Q(email__iexact=login_identifier),
            status=1,
        ).first()

        if not user:
            raise AuthenticationFailed("No active account found with the given credentials.")

        attrs["username"] = user.username

        # Authenticate first (sets self.user if credentials are valid)
        super().validate(attrs)

        # Mint a fresh pair so we can safely add rjti and avoid re-parsing strings
        # Note: get_token actually returns a RefreshToken; we cast to satisfy PyCharm.
        refresh = cast(RefreshToken, self.get_token(self.user))
        access = refresh.access_token  # AccessToken instance

        # Tag access with the refresh's JTI so we can revoke all access minted from this refresh
        access["rjti"] = str(refresh["jti"])

        # Return strings as usual
        return {
            "success": True,
            "access": str(access),
            "refresh": str(refresh),
        }
