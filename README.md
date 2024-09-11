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