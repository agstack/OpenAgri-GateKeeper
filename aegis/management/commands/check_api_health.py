# aegis/management/commands/check_api_health.py

from django.core.management.base import BaseCommand
import requests
import logging

logger = logging.getLogger('aegis')

class Command(BaseCommand):
    help = 'Check health status of services'

    def handle(self, *args, **kwargs):
        services = {
            'Weather Data': "http://weather_data_service/api/health",
            'Farm Calendar': "http://farm_calendar_service/api/health"
        }

        for service_name, url in services.items():
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    logger.info(f"{service_name} is healthy")
                else:
                    logger.warning(f"{service_name} is not healthy: {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"{service_name} health check failed: {e}")
