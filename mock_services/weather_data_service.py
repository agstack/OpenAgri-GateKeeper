# import jwt
# import requests
#
# from flask import Flask, jsonify, request
#
# from flasgger import Swagger
#
# JWT_SIGNING_KEY = "wToGB9hehaS+DdQRjbteK2QYrXOrzHQSYSGK8wrO/3k="
#
# # Flask App Setup
# app = Flask(__name__)
# app.url_map.strict_slashes = False
#
# # Add Swagger UI to the app
# swagger = Swagger(app)
#
# GATEKEEPER_URL = "http://127.0.0.1:8001/"
#
# # Mock Weather Data
# weather_data = {
#     "2024-11-17": {"min_temp": 10, "max_temp": 20},
#     "2024-11-18": {"min_temp": 12, "max_temp": 22},
#     "18-11-2024": {"min_temp": 12, "max_temp": 22}
# }
#
# # Global variables for tokens
# ACCESS_TOKEN = None
# REFRESH_TOKEN = None
#
#
# @app.route('/api/login/', methods=['POST'])
# def login():
#     """
#         Login via Gatekeeper and obtain JWT tokens.
#         ---
#         tags:
#           - Authentication
#         parameters:
#           - name: body
#             in: body
#             required: true
#             schema:
#               type: object
#               properties:
#                 username:
#                   type: string
#                   example: pranav
#                 password:
#                   type: string
#                   example: asdasdasd
#         responses:
#           200:
#             description: Login successful
#             schema:
#               type: object
#               properties:
#                 message:
#                   type: string
#                   example: Login successful
#                 access_token:
#                   type: string
#                   example: "<JWT_ACCESS_TOKEN>"
#                 refresh_token:
#                   type: string
#                   example: "<JWT_REFRESH_TOKEN>"
#           400:
#             description: Missing username or password
#           401:
#             description: Invalid credentials or no active account found
#           502:
#             description: Failed to connect to Gatekeeper
#         """
#
#     global ACCESS_TOKEN, REFRESH_TOKEN
#
#     # Parse request data
#     data = request.json
#     username = data.get("username")
#     password = data.get("password")
#
#     # Validate input parameters
#     if not username or not password:
#         return jsonify({"error": "username and password are required"}), 400
#
#     # Construct Gatekeeper login URL
#     login_url = f"{GATEKEEPER_URL}/api/login/"
#
#     # Send POST request to Gatekeeper
#     try:
#         response = requests.post(
#             login_url,
#             json={
#                 "username": username,
#                 "password": password
#             },
#             headers={"Content-Type": "application/json"}
#         )
#
#         # Return the response from Gatekeeper
#         if response.status_code == 200:
#             tokens = response.json()
#             ACCESS_TOKEN = tokens.get("access")
#             REFRESH_TOKEN = tokens.get("refresh")
#
#             # Check if tokens are present
#             if ACCESS_TOKEN and REFRESH_TOKEN:
#                 return jsonify({
#                     "message": "Login successful",
#                     "access_token": ACCESS_TOKEN,
#                     "refresh_token": REFRESH_TOKEN
#                 }), 200
#             return jsonify({"error": "Login successful but tokens are missing"}), 500
#         elif response.status_code == 401:
#             return jsonify({"error": "Invalid credentials or no active account found"}), 401
#         else:
#             return jsonify({"error": "Failed to log in", "details": response.json()}), response.status_code
#
#     except requests.RequestException as e:
#         return jsonify({"error": f"Failed to connect to Gatekeeper: {str(e)}"}), 502
#
#
# # Utility Functions
# def validate_jwt_token():
#     """
#     Validates the JWT token in the Authorization header.
#     """
#     token = request.headers.get("Authorization")
#     if not token:
#         return {"error": "Authorization header missing"}, 401
#
#     token = token.replace("Bearer ", "")  # Strip "Bearer" prefix
#     try:
#         decoded = jwt.decode(token, JWT_SIGNING_KEY, algorithms=["HS256"])
#         return decoded, 200
#     except jwt.ExpiredSignatureError:
#         return {"error": "Token expired"}, 401
#     except jwt.InvalidTokenError:
#         return {"error": "Invalid token"}, 401
#
#
# @app.route('/api/weather_data/v1/get_temperature/<date>', methods=['GET'])
# def get_temperature(date):
#     # Validate the token
#     decoded, status = validate_jwt_token()
#     if status != 200:
#         return jsonify(decoded), status
#
#     # Fetch the weather data
#     weather = weather_data.get(date)
#     if weather:
#         return jsonify(weather), 200
#     return jsonify({"error": "Weather data not available for the given date"}), 404
#
#
# @app.route('/api/weather_data/v1/get_farms', methods=['GET'])
# def get_farms():
#     """
#     Fetch farm details from the Farm Calendar service via Gatekeeper.
#     ---
#     tags:
#       - Farms
#     parameters:
#       - name: farm_id
#         in: query
#         required: false
#         type: integer
#         description: ID of the farm to fetch. If not provided, all farms are fetched.
#     responses:
#       200:
#         description: Farm data retrieved successfully
#         schema:
#           type: object
#           properties:
#             data:
#               type: array
#               items:
#                 type: object
#                 properties:
#                   farm_id:
#                     type: integer
#                     example: 1
#                   name:
#                     type: string
#                     example: "Green Acres"
#                   location:
#                     type: string
#                     example: "Countryside"
#       404:
#         description: Farm not found
#       502:
#         description: Failed to connect to Gatekeeper
#     """
#
#     farm_id = request.args.get("farm_id")
#
#     # Construct the reverse proxy URL
#     if farm_id:
#         GK_PROXY_URL = f"{GATEKEEPER_URL}/api/proxy/farm_calendar/get_all_farms/{farm_id}"
#     else:
#         GK_PROXY_URL = f"{GATEKEEPER_URL}/api/proxy/farm_calendar/get_all_farms"
#
#     headers = {
#         "Authorization": f"Bearer {ACCESS_TOKEN}"  # Use the global access token
#     }
#
#     try:
#         # Make the GET request to Gatekeeper
#         response = requests.get(GK_PROXY_URL, headers=headers)
#
#         # Handle the response
#         if response.status_code == 200:
#             return jsonify({"data": response.json()}), 200
#         elif response.status_code == 404:
#             return jsonify({"error": "Farm not found"}), 404
#         else:
#             return jsonify({"error": "Failed to fetch farms", "details": response.json()}), response.status_code
#
#     except requests.RequestException as e:
#         # Handle connection errors
#         return jsonify({"error": f"Failed to connect to Gatekeeper: {str(e)}"}), 502
#
#
#
# # Main Execution
# if __name__ == '__main__':
#     app.run(port=8003, debug=True)
