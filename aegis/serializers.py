# serializers.py

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["email"] = user.email
        token["first_name"] = user.first_name
        token["last_name"] = user.last_name
        token["uuid"] = str(user.uuid)
        return token

    def validate(self, attrs):
        # Call the parent validate method to get the token
        data = super().validate(attrs)

        # Customize response
        return {
            "success": True,
            "access_token": data["access"],
            "refresh_token": data["refresh"]
        }