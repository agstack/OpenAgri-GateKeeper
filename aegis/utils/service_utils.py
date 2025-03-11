import re
import requests
import logging

logger = logging.getLogger(__name__)


def match_endpoint(requested_endpoint, stored_endpoint):
    """
    Matches the requested endpoint against a registered endpoint with dynamic path variables.
    """
    # Strip leading and trailing slashes for consistent matching
    requested_endpoint = requested_endpoint.strip("/")
    stored_endpoint = stored_endpoint.strip("/")

    # Replace path variables like {id} with regex patterns (e.g., [^/]+ for non-slash values)
    pattern = re.sub(r"{[^}]+}", r"[^/]+", stored_endpoint)

    # Add ^ and $ to ensure the entire path matches
    pattern = f"^{pattern}$"

    is_match = re.fullmatch(pattern, requested_endpoint) is not None

    logger.info(f"Matching '{requested_endpoint}' with stored endpoint '{stored_endpoint}' -> Match: {is_match}")

    return is_match


def check_service_health(base_url):
    """
    Pings a service's health endpoint to check if it's operational.
    If no health endpoint is available or the request fails, assume the service is reachable.
    """
    health_url = f"{base_url}/health"
    logger.info(f"Checking service health at: {health_url}")

    try:
        response = requests.get(health_url, timeout=5)
        logger.info(f"Health check response code: {response.status_code}")
        return response.status_code == 200  # Return True if the service responds with HTTP 200
    except requests.HTTPError as e:
        logger.error(f"Service returned an error for health check: {str(e)}")
        return False
    except requests.RequestException as e:
        logger.warning(f"No health endpoint or service unreachable: {str(e)}. Assuming service is up.")
        return True
