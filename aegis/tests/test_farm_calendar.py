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

        # Generate the JWT token using Django's AccessToken class
        self.token = str(AccessToken.for_user(self.user))

        # Log the generated token
        logger.info(f'Generated JWT Token for test user: {self.token}')

    @requests_mock.Mocker()
    def test_farm_calendar_access(self, mock):
        # Mocking the gatekeeper's response which in turn calls the weather_data service
        gatekeeper_url = "http://gatekeeper_service/api/weather_data/"
        weather_data_url = "http://weather_data_service/api/data"

        # Mock the weather data service response
        mock.get(weather_data_url, json={"data": "mocked weather data"})

        # Mock the gatekeeper service response
        mock.get(gatekeeper_url, json={"data": "mocked weather data from gatekeeper"})

        # Set the authorization header with the generated JWT token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

        # Send a GET request to the farm_calendar API
        logger.info('Farm Calendar sending GET request to gatekeeper')

        response = self.client.get('/api/farm_calendar/')

        # Log the response
        logger.info(f'Farm Calendar received response: {response.status_code} {response.json()}')

        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertIn('message', response.json())
