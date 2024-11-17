# serializers.py

from django.contrib.auth import get_user_model

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["email"] = user.email
        token["first_name"] = user.first_name
        token["last_name"] = user.last_name
        token["service_name"] = user.service_name
        token["uuid"] = str(user.uuid)
        return token

    def validate(self, attrs):
        # Get the user model
        user = get_user_model()

        # Retrieve the user by username
        try:
            user = user.objects.get(username=attrs['username'])
        except user.DoesNotExist:
            raise AuthenticationFailed("No active account found with the given credentials")

        # Check if user status is active
        if user.status != 1:
            raise AuthenticationFailed("No active account found with the given credentials")

        # Call the parent validate method to get the token if user is active
        data = super().validate(attrs)

        # Customize response
        return {
            "success": True,
            "access": data["access"],
            "refresh": data["refresh"]
        }
