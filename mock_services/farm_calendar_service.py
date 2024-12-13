import jwt
import requests

from datetime import datetime, timedelta

from flask import Flask, jsonify, request

JWT_SIGNING_KEY = "wToGB9hehaS+DdQRjbteK2QYrXOrzHQSYSGK8wrO/3k="


GATEKEEPER_URL = "http://127.0.0.1:8001"
SERVICE_CACHE = {}
CACHE_EXPIRY = datetime.now()
ACCESS_TOKEN = None

# Flask App Setup
app = Flask(__name__)
app.url_map.strict_slashes = False


# Utility Functions
def login_and_get_token(username, password):
    global ACCESS_TOKEN

    login_url = f"{GATEKEEPER_URL}/api/login/"
    try:
        response = requests.post(
            login_url,
            json={
                "username": username,
                "password": password
            },
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            tokens = response.json()
            ACCESS_TOKEN = tokens["access"]
            print("Login successful. Access token acquired.")
            print(ACCESS_TOKEN)
        else:
            print(f"Login failed: {response.json()}")
    except requests.RequestException as e:
        print(f"Error during login: {str(e)}")


# Utility Functions
def refresh_service_cache():
    """
    Fetch and cache the list of registered services from Gatekeeper.
    """
    global SERVICE_CACHE, CACHE_EXPIRY

    try:
        # Call GK's service directory API
        response = requests.get(
            f"{GATEKEEPER_URL}/api/service_directory/",
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}
        )
        if response.status_code == 200:
            services = response.json()  # Parse the JSON response

            # Populate SERVICE_CACHE using "service_name" as the key
            SERVICE_CACHE = {
                service["service_name"]: {
                    "base_url": service["base_url"],
                    "endpoint": service["endpoint"],
                    "methods": service["methods"],
                    "service_url": service["service_url"],
                }
                for service in services
            }

            # Update cache expiry
            CACHE_EXPIRY = datetime.now() + timedelta(minutes=5)
            print("Service cache updated successfully.")
            print(SERVICE_CACHE)
        else:
            print(f"Failed to refresh service cache: {response.status_code}, {response.json()}")
    except requests.RequestException as e:
        print(f"Error fetching service directory: {str(e)}")


def get_service_url(service_name, method):
    """
    Retrieve the service URL from the cached service directory.
    Args:
        service_name (str): The name of the service (e.g., "weather_data").
        method (str): The HTTP method (e.g., "GET").
    Returns:
        str: The service URL if found and valid, None otherwise.
    """
    global SERVICE_CACHE, CACHE_EXPIRY

    # Refresh the cache if it has expired
    if datetime.now() > CACHE_EXPIRY:
        refresh_service_cache()

    # Look up the service in the cache
    service = SERVICE_CACHE.get(service_name)
    if not service:
        print(f"Service '{service_name}' not found in cache.")
        return None

    # Validate the method
    if method not in service["methods"]:
        print(f"Method '{method}' not supported for service '{service_name}'.")
        return None

    return service["service_url"]


# Mock Farm Data
farms = {
    1: {"farm_id": 1, "name": "Green Acres", "location": "Countryside"},
    2: {"farm_id": 2, "name": "Sunny Fields", "location": "Uplands"}
}

# Utility Functions
def validate_jwt_token():
    """
    Validates the JWT token in the Authorization header.
    """
    token = request.headers.get("Authorization")
    if not token:
        return {"error": "Authorization header missing"}, 401

    token = token.replace("Bearer ", "")  # Strip "Bearer" prefix
    try:
        decoded = jwt.decode(token, JWT_SIGNING_KEY, algorithms=["HS256"])
        return decoded, 200
    except jwt.ExpiredSignatureError:
        return {"error": "Token expired"}, 401
    except jwt.InvalidTokenError:
        return {"error": "Invalid token"}, 401


@app.route('/api/farm_calendar/v1/get_tomorrow_weather', methods=['GET'])
def get_tomorrow_weather():
    """
    Fetch weather data for tomorrow via Gatekeeper's reverse proxy.
    """
    # Validate the token
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return jsonify({"error": "Authorization header missing"}), 401

    # Get tomorrow's date
    tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # Construct the reverse proxy URL
    reverse_proxy_url = f"{GATEKEEPER_URL}/api/proxy/weather_data/get_temperature/{tomorrow_date}"

    try:
        # Make the request to GK's reverse proxy
        response = requests.get(
            reverse_proxy_url,
            headers={"Authorization": request.headers.get("Authorization")}
        )
        if response.status_code == 200:
            return jsonify({"tomorrow_weather": response.json()}), 200
        return jsonify({"error": response.json().get("error", "Failed to fetch weather data")}), response.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to connect to Gatekeeper: {str(e)}"}), 502


# Routes
@app.route('/api/farm_calendar/v2/get_all_farm/<int:farm_id>', methods=['GET'])
def get_farm(farm_id):
    """
    Fetch farm details.
    """
    # Validate the token
    decoded, status = validate_jwt_token()
    if status != 200:
        return jsonify(decoded), status

    # Fetch the farm data
    farm = farms.get(farm_id)
    if farm:
        return jsonify(farm), 200
    return jsonify({"error": "Farm not found"}), 404

@app.route('/api/farm_calendar/v1/ask_weather/', methods=['POST'])
def ask_weather():
    """
    Request weather data via Gatekeeper.
    """
    # Validate the token
    decoded, status = validate_jwt_token()
    if status != 200:
        return jsonify(decoded), status

    # Parse request data
    data = request.json
    date = data.get('date')
    if not date:
        return jsonify({"error": "Date is required"}), 400

    # Call Gatekeeper to fetch weather data
    gatekeeper_url = f"{GATEKEEPER_URL}/api/weather_data/v1/get_weather/{date}"
    try:
        response = requests.get(gatekeeper_url, headers={"Authorization": request.headers.get("Authorization")})
        if response.status_code == 200:
            return jsonify({"weather_data": response.json()}), 200
        return jsonify({"error": response.json().get("error", "Failed to fetch weather data")}), response.status_code
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to connect to Gatekeeper: {str(e)}"}), 502


@app.route('/api/farm_calendar/v1/get_all_farms', defaults={'farm_id': None}, methods=['GET'])
@app.route('/api/farm_calendar/v1/get_all_farms/<int:farm_id>', methods=['GET'])
def get_all_farms(farm_id):
    """
    Fetch farm details by ID or return all farms if no ID is provided.
    """
    if farm_id is not None:
        # Fetch a specific farm
        farm = farms.get(farm_id)
        if farm:
            return jsonify(farm), 200
        return jsonify({"error": "Farm not found"}), 404

    # Return all farms if no ID is provided
    return jsonify(list(farms.values())), 200


@app.route('/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint to verify service availability.
    """
    return jsonify({"status": "healthy"}), 200


# Main Execution
if __name__ == '__main__':
    login_and_get_token(username="admin", password="admin")
    refresh_service_cache()

    print("\nCalling weather data through Gatekeeper...\n")

    # Construct the Gatekeeper reverse proxy URL
    # GK_PROXY_URL = f"{GATEKEEPER_URL}/api/proxy/weather_data/get_temperature/18-11-2024"
    GK_PROXY_URL = f"{GATEKEEPER_URL}/api/proxy/weather_data/api/data/thi/?lat=12.0&lon=12.0"
    print("GK_PROXY_URL: ", GK_PROXY_URL)

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    try:
        # Make the GET request to GK's proxy endpoint
        response = requests.get(GK_PROXY_URL, headers=headers)
        if response.status_code == 200:
            print("Weather Data from Gatekeeper:", response.json())
        else:
            print("Error from Gatekeeper:", response.status_code, response.json())
    except requests.RequestException as e:
        print("Request to Gatekeeper failed:", str(e))

    app.run(port=8002, debug=True)
