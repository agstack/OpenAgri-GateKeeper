import requests

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


class WeatherDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Forward request to the weather data service
        weather_service_url = "http://weather_data_service/api/data"
        headers = {'Authorization': f"Bearer {request.auth}"}

        response = requests.get(weather_service_url, headers=headers)
        return Response(response.json(), status=response.status_code)