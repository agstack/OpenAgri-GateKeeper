from rest_framework.decorators import api_view
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from rest_framework.response import Response
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model

User = get_user_model()


@api_view(['POST'])
def login(request):
    try:
        username = request.data.get('username')
        password = request.data.get('password')

        # Basic validation
        if not username or not password:
            return Response({'status': 'error', 'message': 'Username and password are required fields.',
                             'data': {}}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)

        if user is not None:
            refresh = RefreshToken.for_user(user)
            return Response({'status': 'success', 'message': 'Authentication successful.',
                             'data': {'refresh_token': str(refresh), 'access_token': str(refresh.access_token),
                                      'uuid': str(user.uuid)}
                             }, status=status.HTTP_200_OK)
        else:
            return Response({'status': 'error', 'message': 'Invalid username or password', 'data': {}},
                            status=status.HTTP_401_UNAUTHORIZED)

    except Exception as e:
        return Response({'status': 'error', 'message': str(e), 'data': {}},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
