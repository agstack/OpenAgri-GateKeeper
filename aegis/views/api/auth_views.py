# views/api_views.py

import logging

from django import forms
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from rest_framework import status, permissions
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from datetime import datetime, timezone

from aegis.forms import UserRegistrationForm
from aegis.services.auth_services import register_user
from aegis.serializers import CustomTokenObtainPairSerializer

logging.basicConfig(level=logging.ERROR)


@method_decorator(never_cache, name='dispatch')
class LoginAPIView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@method_decorator(never_cache, name='dispatch')
class RegisterAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        form = UserRegistrationForm(request.data)

        if form.is_valid():
            try:
                register_user(
                    username=form.cleaned_data["username"],
                    email=form.cleaned_data["email"],
                    # service_name=form.cleaned_data["service_name"],
                    password=form.cleaned_data["password"],
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"]
                )
                return Response({
                    "success": True,
                    "message": "User registered successfully. Please log in."
                }, status=status.HTTP_201_CREATED)

            except forms.ValidationError as e:
                return Response({
                    "success": False,
                    "error": str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                logging.error(f"An unexpected error occurred: {str(e)}", exc_info=True)
                return Response({
                    "success": False,
                    # "error": f"An unexpected error occurred: {str(e)}"
                    "error": "An unexpected error occurred. Please try again later."
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Return validation errors
        return Response({
            "success": False,
            "errors": form.errors
        }, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(never_cache, name='dispatch')
class LogoutAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"success": "Logged out successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)


class TokenValidationAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        token_type = request.data.get("token_type", "access")
        token = request.data.get("token")

        if not token:
            return Response({"error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if token_type == "access":
                token_instance = AccessToken(token)
            elif token_type == "refresh":
                token_instance = RefreshToken(token)
            else:
                return Response({"error": "Invalid token type. Must be 'access' or 'refresh'."},
                                status=status.HTTP_400_BAD_REQUEST)

            # Get expiration time
            expiration_time = token_instance["exp"]

        except TokenError as e:
            # Check if the error is due to an expired token
            if "token is expired" in str(e).lower():
                return Response({"error": f"{token_type.capitalize()} token has expired"},
                                status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"error": f"Invalid {token_type} token"},
                                status=status.HTTP_400_BAD_REQUEST)

        # Calculate remaining time (in seconds)
        current_time = datetime.now(timezone.utc)
        remaining_time = expiration_time - current_time.timestamp()

        if remaining_time > 0:
            return Response({
                "success": True,
                "remaining_time_in_seconds": remaining_time
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "error": "Token has already expired"
            }, status=status.HTTP_400_BAD_REQUEST)
