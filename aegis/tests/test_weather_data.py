# aegis/tests/test_weather_data.py

import logging
import requests_mock
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from aegis.models import DefaultAuthUserExtend

logger = logging.getLogger('aegis')

class WeatherDataTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = DefaultAuthUserExtend.objects.create_user(username='testuser', password='testpass')
        self.token = str(AccessToken.for_user(self.user))

        # Print token details
        logger.info(f'Generated JWT Token for test user: {self.token}')

        # Print token lifetime details
        logger.info(f'Token Lifetime: 60 minutes')

    @requests_mock.Mocker()
    def test_weather_data_proxy(self, mock):
        weather_data_url = "http://weather_data_service/api/data"
        mock.get(weather_data_url, json={"data": "mocked weather data"})

        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        logger.info('Gatekeeper sending GET request to weather_data')

        response = self.client.get('/api/weather_data/')

        logger.info(f'Gatekeeper received response: {response.status_code} {response.json()}')

        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.json())
