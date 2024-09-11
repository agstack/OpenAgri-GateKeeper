# aegis/tests/test_farm_calendar.py

import logging
import requests_mock
from datetime import datetime, timedelta
from uuid import uuid4
import jwt

from django.test import TestCase
from django.conf import settings

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from aegis.models import DefaultAuthUserExtend

logger = logging.getLogger('aegis')


class FarmCalendarTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = DefaultAuthUserExtend.objects.create_user(username='testuser', password='testpass')

        # Manually generate a JWT token with custom claims
        payload = {
            'user_id': self.user.id,
            'exp': datetime.utcnow() + timedelta(days=1),
            'token_type': 'access',
            'jti': str(uuid4()),
        }

        self.token = jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm=settings.JWT_ALG)

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

        # Set the authorization header with the manually generated JWT token
        headers = {
            'Authorization': f'Bearer {self.token}',
        }
        self.client.credentials(HTTP_AUTHORIZATION=headers['Authorization'])

        # Send a GET request to the farm_calendar API
        logger.info('Farm Calendar sending GET request to gatekeeper')

        response = self.client.get('/api/farm_calendar/')

        # Log the response
        logger.info(f'Farm Calendar received response: {response.status_code} {response.json()}')

        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertIn('message', response.json())

        # # Mock the gatekeeper service to call weather_data service
        # def gatekeeper_callback(request, context):
        #     logger.info('Gatekeeper received request from farm_calendar and calling weather_data service')
        #     weather_response = requests_mock.Mocker().get(weather_data_url, json={"data": "mocked weather data"})
        #     logger.info(f'Weather data service responded with: {weather_response.json()}')
        #     return {"data": "mocked weather data from gatekeeper"}
        #
        # mock.get(gatekeeper_url, json=gatekeeper_callback)
        #
        # # Log the call from farm_calendar to gatekeeper
        # self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.token)
        # logger.info('Farm Calendar sending GET request to gatekeeper')
        #
        # response = self.client.get('/api/farm_calendar/')
        #
        # logger.info(f'Farm Calendar received response: {response.status_code} {response.json()}')
        #
        # self.assertEqual(response.status_code, 200)
        # self.assertIn('message', response.json())
