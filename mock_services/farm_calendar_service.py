import jwt
import requests

from datetime import datetime, timedelta

from flask import Flask, jsonify, request

JWT_SIGNING_KEY = "wToGB9hehaS+DdQRjbteK2QYrXOrzHQSYSGK8wrO/3k="


GATEKEEPER_URL = "http://127.0.0.1:8001"

# Flask App Setup
app = Flask(__name__)
app.url_map.strict_slashes = False

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
    Fetch weather data for tomorrow via Gatekeeper.
    """
    # Validate the token
    decoded, status = validate_jwt_token()
    if status != 200:
        return jsonify(decoded), status

    # Get tomorrow's date
    tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # Construct Gatekeeper URL
    gatekeeper_url = f"{GATEKEEPER_URL}/api/weather_data/v1/get_weather/{tomorrow_date}"

    # Call Gatekeeper
    try:
        response = requests.get(gatekeeper_url, headers={"Authorization": request.headers.get("Authorization")})
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


@app.route('/farm_calendar/v2/get_all_farms/<int:farm_id>', methods=['GET'])
def get_all_farms(farm_id):
    """
    Fetch farm details by ID.
    """
    farm = farms.get(farm_id)
    if farm:
        return jsonify(farm), 200
    return jsonify({"error": "Farm not found"}), 404


@app.route('/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint to verify service availability.
    """
    return jsonify({"status": "healthy"}), 200


# Main Execution
if __name__ == '__main__':
    app.run(port=8002, debug=True)
