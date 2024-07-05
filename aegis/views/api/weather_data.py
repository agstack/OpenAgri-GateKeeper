# aegis/views/api/weather_data.py

import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
import logging

logger = logging.getLogger('aegis')


class WeatherDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Forward request to weather data service
        weather_data_url = "http://weather_data_service/api/data"

        headers = {
            'Authorization': f'Bearer {request.auth}'
        }

        logger.info("Gatekeeper forwarding request from Farm Calendar to Weather Data service")

        try:
            weather_response = requests.get(weather_data_url, headers=headers)
            weather_response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)
        except requests.exceptions.RequestException as e:
            logger.error(f"Weather Data service request failed: {e}")
            return Response({"error": "Service Unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        logger.info(f"Weather Data service response: {weather_response.json()}")
        return Response(weather_response.json())
