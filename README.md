# GateKeeper

GateKeeper is a Django-based microservice designed to act as a central point for validation and authentication for all OpenAgri microservices. This application is dockerised, making it easy to deploy and manage using Docker and Docker Compose.

## Features

- **Centralised Authentication:** Manage authentication across multiple microservices.
- **Validation Services:** Provides validation mechanisms to ensure data integrity.
- **Dockerised Deployment:** Utilise Docker for simplified deployment and management.
- **Nginx Proxy:** Serves as a reverse proxy for the Django application.
- **MySQL Database:** Utilises MySQL as the database backend, with phpMyAdmin for database management.

## Prerequisites

- Docker
- Docker Compose

## Getting Started

### Clone the Repository

```bash
git clone https://github.com/openagri-eu/GateKeeper.git
```

### Configure Environement Variables

Copy the `.env.sample` file into a new file called `.env`. Then change its content accordingly. Here is a list of the most important configuration variables and their use:

* DB_<USER|PASS|HOST|PORT>= used to set the database configuration for user, password, the ip address hosting the database, and the port used.
* DATABASE_URL= this is an alternative configuration that can be used instead of the previous one, by representing all the database configs as a single url.
* JWT_SECRET= The secret used to encript/decript the authentication tokens.
* APP_<HOST|PORT>= the web service host (i.e., 0.0.0.0) and port (8001 by default).
* SUPERUSER_<USERNAME|EMAIL|PASSWORD>= Used to create admin user on initial data setup of the system.
* FARM_CALENDAR_API=API endpoit for the farmcalendar. \*
* FARM_CALENDAR_POST_AUTH=Farmcalendar post  authentication url. \*


\* In the future this information will be provided by each service uppon registration, instead of being set in the gatekeeper config.

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
