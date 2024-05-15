from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status, views
from rest_framework.response import Response
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model

User = get_user_model()


class TokenObtainPairView(views.APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'uuid': str(user.id),
            }, status=status.HTTP_200_OK)
        return Response({'error': 'Invalid Credentials'}, status=status.HTTP_401_UNAUTHORIZED)
