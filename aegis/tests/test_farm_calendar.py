# aegis/tests/test_farm_calendar.py

import logging
import requests_mock
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from aegis.models import DefaultAuthUserExtend

logger = logging.getLogger('aegis')


class FarmCalendarTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = DefaultAuthUserExtend.objects.create_user(username='testuser', password='testpass')
        self.token = str(AccessToken.for_user(self.user))

        # Print token details
        logger.info(f'Generated JWT Token for test user: {self.token}')

        # Print token lifetime details
        logger.info(f'Token Lifetime: 60 minutes')

    @requests_mock.Mocker()
    def test_farm_calendar_access(self, mock):
        # Mocking the gatekeeper's response which in turn calls the weather_data service
        gatekeeper_url = "http://gatekeeper_service/api/weather_data/"
        weather_data_url = "http://weather_data_service/api/data"

        # Mock the weather data service response
        mock.get(weather_data_url, json={"data": "mocked weather data"})

        # Mock the gatekeeper service to call weather_data service
        def gatekeeper_callback(request, context):
            logger.info('Gatekeeper received request from farm_calendar and calling weather_data service')
            weather_response = requests_mock.Mocker().get(weather_data_url, json={"data": "mocked weather data"})
            logger.info(f'Weather data service responded with: {weather_response.json()}')
            return {"data": "mocked weather data from gatekeeper"}

        mock.get(gatekeeper_url, json=gatekeeper_callback)

        # Log the call from farm_calendar to gatekeeper
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        logger.info('Farm Calendar sending GET request to gatekeeper')

        response = self.client.get('/api/farm_calendar/')

        logger.info(f'Farm Calendar received response: {response.status_code} {response.json()}')

        self.assertEqual(response.status_code, 200)
        self.assertIn('message', response.json())
