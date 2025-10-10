# GateKeeper
🇪🇺
*"This service was created in the context of OpenAgri project (https://horizon-openagri.eu/). OpenAgri has received funding from the EU’s Horizon Europe research and innovation programme under Grant Agreement no. 101134083."*

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

### Configure Environment Variables

Copy the `.env.sample` file into a new file called `.env`.  
Then change its content accordingly. Below is the full list of configuration variables and their purposes.

| Variable | Description | Example / Default |
|-----------|--------------|------------------|
| `DB_USER` | Database username. | `root` |
| `DB_PASS` | Database password. | `mypassword` |
| `DB_HOST` | Database host address. | `localhost` |
| `DB_PORT` | Database port number. | `3306` |
| `DB_NAME` | Database name. | `gatekeeper_db` |
| `DATABASE_URL` | Alternative database connection string (used instead of separate DB variables). | `mysql://user:password@host:port/dbname` |
| `DJANGO_SECRET_KEY` | Django’s secret key used for cryptographic signing. **Must be set in production.** | `your-secret-key` |
| `DJANGO_DEBUG` | Enables or disables Django debug mode. | `True` or `False` (default: `False`) |
| `DJANGO_PORT` | Port Django runs on locally. | `8001` |
| `EXTRA_ALLOWED_HOSTS` | Comma-separated list of additional allowed hosts. | `example.com,api.example.com` |
| `JWT_SIGNING_KEY` | Key used for signing JWT tokens for authentication. | `your-jwt-signing-key` |
| `JWT_ALG` | Algorithm used for JWT signing. | `HS256` |
| `JWT_ACCESS_TOKEN_MINUTES` | Access token expiration time (in minutes). | `60` |
| `JWT_REFRESH_TOKEN_DAYS` | Refresh token expiration time (in days). | `30` |
| `FARM_CALENDAR_API` | Base API URL for the Farm Calendar service. | `http://127.0.0.1:8002/api/` |
| `FARM_CALENDAR_POST_AUTH` | Post-authentication endpoint for the Farm Calendar service. | `http://127.0.0.1:8002/post_auth/` |
| `IRM_API` | Base API URL for the Irrigation Management service. | `http://127.0.0.1:5173/api/` |
| `IRM_POST_AUTH` | Post-authentication endpoint for the Irrigation Management service. | `http://127.0.0.1:5173/post_auth/` |
| `INTERNAL_GK_URL` | Internal Gatekeeper URL used by internal services. | `http://gatekeeper:8001/` |
| `GATEKEEPER_URL` | External/public URL for the Gatekeeper service. | `https://example.com/gatekeeper/` |
| `FARM_CALENDAR` | Optional reference or identifier for the Farm Calendar service. | `FarmCalendar` |
| `IRM` | Optional reference or identifier for the Irrigation Management service. | `IrrigationManagement` |
| `SUPERUSER_USERNAME` | Used to create the admin username during initial setup. | `admin` |
| `SUPERUSER_EMAIL` | Email address of the admin user during initial setup. | `admin@example.com` |
| `SUPERUSER_PASSWORD` | Password for the admin user during initial setup. | `admin123` |

> **Note:**  
> - Variables marked with `*` in older versions (like `FARM_CALENDAR_API` and `FARM_CALENDAR_POST_AUTH`) are still manually configured but may later be automatically provided by each registered service.  
> - Always keep `DJANGO_SECRET_KEY` and `JWT_SIGNING_KEY` private and never commit them to source control.

### Running
To start up the container with the OpenAgri Gatekeeper service, you can run the command:

```
$ docker compose up -d
```
this will start both the DB (postgres) and the Gatekeeper service containers.

To access the service on the web, you can go to:
`http://localhost:8001/login/`
Where you'll be able to login using you admin account (as defined in you .env configurations).

### Stopping
To stop the containers running, run the command:
```
$ docker compose stop
```
Afterwards you may resume them using:
```
$ docker compose start
```

### Removing containers
To stop, and remove existing containers, **including any data stored in the database** in can run:
```
$ docker compose down
```

# License
This project is distributed with the EUPL 1.2v. See the LICENSE file for more details.
