import jwt

from flask import Flask, jsonify, request


JWT_SIGNING_KEY = "wToGB9hehaS+DdQRjbteK2QYrXOrzHQSYSGK8wrO/3k="

# Flask App Setup
app = Flask(__name__)
app.url_map.strict_slashes = False

# Mock Weather Data
weather_data = {
    "2024-11-17": {"min_temp": 10, "max_temp": 20},
    "2024-11-18": {"min_temp": 12, "max_temp": 22}
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


@app.route('/api/weather_data/v1/get_weather/<date>', methods=['GET'])
def get_weather(date):
    """
    Fetch weather data for a specific date.
    """
    # Validate the token
    decoded, status = validate_jwt_token()
    if status != 200:
        return jsonify(decoded), status

    # Fetch the weather data
    weather = weather_data.get(date)
    if weather:
        return jsonify(weather), 200
    return jsonify({"error": "Weather data not available for the given date"}), 404

@app.route('/api/weather_data/v1/add_weather/', methods=['POST'])
def add_weather():
    """
    Add mock weather data.
    """
    # Validate the token
    decoded, status = validate_jwt_token()
    if status != 200:
        return jsonify(decoded), status

    # Parse and validate request data
    data = request.json
    date = data.get('date')
    min_temp = data.get('min_temp')
    max_temp = data.get('max_temp')

    if not date or min_temp is None or max_temp is None:
        return jsonify({"error": "Date, min_temp, and max_temp are required"}), 400

    # Add the weather data
    weather_data[date] = {"min_temp": min_temp, "max_temp": max_temp}
    return jsonify({"message": f"Weather data added for {date}"}), 201

# Main Execution
if __name__ == '__main__':
    app.run(port=8003, debug=True)
