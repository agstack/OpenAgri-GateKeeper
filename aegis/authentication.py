# aegis/authentication.py

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from aegis.models import BlacklistedRefresh, BlacklistedAccess

class JWTAuthenticationWithDenylist(JWTAuthentication):
    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)  # validates signature/exp etc.

        # Specific access token revoked?
        jti = token.get("jti")
        if jti and BlacklistedAccess.objects.filter(jti=jti).exists():
            raise InvalidToken("Access token has been revoked.")

        # Parent refresh revoked?
        rjti = token.get("rjti")
        if rjti and BlacklistedRefresh.objects.filter(rjti=rjti).exists():
            raise InvalidToken("Access token has been revoked (parent refresh blacklisted).")

        return token
