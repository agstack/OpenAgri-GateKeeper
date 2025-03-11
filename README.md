# GateKeeper

GateKeeper is a Django-based microservice designed to act as a central point for validation and authentication for 
all of the following OpenAgri microservices. 
This application is dockerised, making it easy to deploy and manage using Docker and Docker Compose.
- **Irrigation Management (IRM)**
- **Weather Data (WD)**
- **Farm Calendar (FC)**
- **Reporting (RP)**
- **Pest and Disease Management (PDM)**

## Features

- **Centralised Authentication:** Manage authentication across multiple microservices.
- **Validation Services:** Provides validation mechanisms to ensure data integrity.
- **Dockerised Deployment:** Utilise Docker for simplified deployment and management.
- **MySQL Database:** Utilises MySQL as the database backend, with phpMyAdmin for database management.
- GateKeeper is responsible solely for authentication and does not provide any additional features.

## Prerequisites

- Docker
- Docker Compose

## Getting Started

### Clone the Repository

```bash
git clone https://github.com/openagri-eu/GateKeeper.git
```

## Integration with Gatekeeper

Integrating with Gatekeeper is simple. It just means that your service can communicate with GK, use its endpoints, and handle authentication.

### What integration with GK really means:

- **Call GK’s API** – Your service should be able to send requests to GK’s endpoints.
- **Log in** – If a user provides valid credentials, GK will return an `access_token` and `refresh_token`.
- **Validate tokens** – If your service needs to check if a token is still valid, you can ask GK.
- **Refresh tokens** – If an `access_token` expires, your service can use the `refresh_token` to get a new one.
- **Log out** – If a user wants to log out, your service can call GK’s `/logout/` endpoint to invalidate their session.

That’s it! No complex setup. No extra steps. Just make sure your service can send requests to GK and handle the tokens properly. If you can do that, you’re fully integrated with GK.

## Sample Integration Flow

1. Services authenticate using the API endpoints provided by GK.
2. If the login is successful, the response contains:

    ```json
    {
        "success": true,
        "access": "access_token",
        "refresh": "refresh_token"
    }
    ```

3. Token validity is predefined, and each service must handle token expiration by refreshing the access token.
4. A service is considered successfully integrated with GK once it can log in via `/api/login/` and receive authentication tokens.

## Further Documentation

