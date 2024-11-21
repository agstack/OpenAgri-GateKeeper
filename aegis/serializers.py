# serializers.py

from django.contrib.auth import get_user_model
from django.db.models import Q

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
        # token["service_name"] = user.service_name
        token["uuid"] = str(user.uuid)
        return token

    def validate(self, attrs):
        # Extract username/email and service_name from the request data
        login_identifier = attrs.get("username")  # Can be either username or email
        # service_name = self.context["request"].data.get("service_name")

        # if not service_name:
        #     raise AuthenticationFailed("Service name is required.")

        # Get the user model
        user_model = get_user_model()

        # Retrieve the user by username or email and active status in one query
        try:
            user = user_model.objects.filter(
                Q(username=login_identifier) | Q(email=login_identifier),
                status=1,  # Ensure user is active
                # service_name=service_name
            ).first()
        except user_model.DoesNotExist:
            raise AuthenticationFailed("No active account found with the given credentials")

        if not user:
            raise AuthenticationFailed("No active account found with the given credentials.")

        attrs["username"] = user.username

        # Call the parent validate method to get the token if user is active
        data = super().validate(attrs)

        # Customize response
        return {
            "success": True,
            "access": data["access"],
            "refresh": data["refresh"]
        }
