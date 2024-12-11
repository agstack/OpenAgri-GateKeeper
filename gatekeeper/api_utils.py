import requests
import json

class APIUtils:
    BASE_URL = "http://127.0.0.1:8001"

    @staticmethod
    def login(username, password):
        """
        Logs in a user by obtaining JWT tokens.

        Parameters:
            username (str): The username for login.
            password (str): The password for login.

        Returns:
            dict: A dictionary containing success, tokens, or error message.
        """
        url = f"{APIUtils.BASE_URL}/api/login/"
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "username": username,
            "password": password
        }

        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))

            if response.status_code == 200:
                return {
                    "success": True,
                    "access": response.json().get("access"),
                    "refresh": response.json().get("refresh")
                }
            elif response.status_code == 400:
                return {
                    "success": False,
                    "error": response.json()
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "error": response.json().get("detail", "Unauthorized access.")
                }
            else:
                return {
                    "success": False,
                    "error": f"Unexpected status code: {response.status_code}"
                }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Request error: {str(e)}"
            }

    @staticmethod
    def logout(refresh_token):
        """
        Logs out a user by blacklisting the refresh token.

        Parameters:
            refresh_token (str): The JWT refresh token to blacklist.

        Returns:
            dict: A dictionary containing success message or error details.
        """
        url = f"{APIUtils.BASE_URL}/api/logout/"
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "refresh": refresh_token
        }

        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))

            if response.status_code == 200:
                return {
                    "success": True,
                    "message": response.json().get("success", "Logged out successfully")
                }
            elif response.status_code == 400:
                return {
                    "success": False,
                    "error": response.json().get("error", "Invalid or missing refresh token.")
                }
            else:
                return {
                    "success": False,
                    "error": f"Unexpected status code: {response.status_code}"
                }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Request error: {str(e)}"
            }
