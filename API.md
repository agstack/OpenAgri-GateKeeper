# API Documentation

This document provides the authentication endpoints for logging in and logging out of the GateKeeper API.

## Base URL
```
http://localhost:8001/api/
```

## Authentication Endpoints

### 1. Login

**Endpoint:**
```
POST /api/login/
```

**Description:**
Obtain JWT tokens (access and refresh) for authentication.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```
{
    "username": "string", // required
    "password": "string" // required
}
```

**Success Response:**
```
{
    "success": true,
    "access": "string", // JWT access token
    "refresh": "string" // JWT refresh token
}
```

**Error Responses:**

**400 Bad Request - Missing required fields**
```
{
    "username": ["This field is required."],
    "password": ["This field is required."]
}
```


**401 Unauthorized - Invalid credentials or inactive/deleted account**
```
{
    "detail": "No active account found with the given credentials"
}
```

---

### 2. Logout

**Endpoint:**
```
POST /api/logout/
```

**Description:**  
Logs out a user by blacklisting the refresh token.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```
{ "refresh": "string" // required, JWT refresh token }
```

**Success Response:**
```
{ "success": "Logged out successfully" }
```

**Error Responses:**

**400 Bad Request - Missing token**
```
{ "error": "Refresh token is required" }
```

**400 Bad Request - Invalid or expired token**
```
{ "error": "Invalid or expired token" }
```

---

### 3. Register a Service

**Endpoint:**
```
POST /api/register_service/
```

**Description:**  
Register a new service endpoint or update an existing service with the provided data.
If a service with the same base url, service name, and endpoint exists:
- The service is updated with new methods, params, and comments.
- Existing methods are merged with the new ones provided.
- Existing params and comments are replaced with the new values.

If no matching service is found, a new service is created.

To remove method(s), use the Delete Service API.

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <access_token> (Required)
```

**Request Body:**
```
{
    // Required, base URL of the service (name of the docker service)
    "base_url": "string",
    
    // Required, name of the service
    "service_name": "string",
     
    // Required, endpoint of the service
    "endpoint": "string",
    
    // Optional, list of HTTP methods (default: ["GET", "POST"])
    "methods": ["string"],
    
    // Optional, additional parameters for the service
    "params": "string of query parameters"
    
    // Optional, comments for the service, if any
    "comments": "string"
}
```

**Success Response:**

**201 Created - Service registered successfully**
```
{
    "success": true,
    "message": "Service registered successfully", 
    "service_id": 9 // ID of the created service at GateKeeper
}
```

**200 OK - Existing service updated with new methods**
```
{
    "success": true,
    "message": "Service updated successfully.",
    "service_id": 9
}
```

**Error Responses:**

**400 Bad Request - Missing required fields**
```
{
    "error": "Missing required fields: endpoint"
}
```

**400 Bad Request - Invalid JSON input**
```
{
    "detail": "JSON parse error - Expecting ’,’ delimiter: line 3 column 3 (char 35)"
}
```

**400 Bad Request - Methods not in the correct format**
```
{
    "error": "Methods should be a list of strings."
}
```

**400 Bad Request - Service already exists with the same methods**
```
{
    "error": "A service with this endpoint and methods already exists."
}
```

**400 Bad Request - Base URL format invalid**
```
{
    "error": "Base URL must follow the format ’http://baseurl:port/’ or ’https://baseurl:port/’."
}
```

**400 Bad Request - Service Name invalid**
```
{
    "error": "Service name must only contain alphanumeric characters and underscores, and must be less than 30 characters."
}
```

**400 Bad Request - Endpoint format invalid**
```
{
    "error": "Endpoint must not start with a forward or backward slash and must end with ’/’."
}
```

**500 Internal Server Error - Database or unexpected error**
```
{
    "error": "Database error: <database_error_message>"
}
{
    "error": "Unexpected error: <error_message>"
}
```

---

### 4. Delete a Service

**Endpoint:**
```
POST /api/delete_service/
```

**Description:**  
Delete a service or specific method associated with a service. You can delete:
- A specific method by providing the method query parameter.
- The entire service if method is not provided.

**Headers:**
```
Authorization: Bearer <access token> (Required)
```

**Request Body:**
```
{
    base_url: string // Required, base URL of the service
    service_name: string // Required, name of the service
    endpoint: string // Required, endpoint of the service
    method: string // Optional, HTTP method to delete (e.g., "POST")
}
```

**Success Responses:**
**200 OK - Entire service deleted**
```
{
    "success": true,
    "message": "Base URL, service and endpoint deleted successfully."
}
```

**200 OK - Specific method removed from the service**
```
{
    "success": true,
    "message": "Method ’POST’ removed from the service."
}
```

**Error Responses:**
**400 Bad Request - Missing required parameters**
```
{
    "error": "Base URL, service name, and endpoint are required."
}
```

**400 Bad Request - Method not found for the service**
```
{
    "error": "Method ’POST’ does not exist for this endpoint."
}
```

**404 Not Found - Service not found or already deleted**
```
{
    "error": "Service with this base URL, name, and endpoint does not exist or is already deleted."
}
```

**500 Internal Server Error - Database or unexpected error**
```
{
    "error": "Database error: <database_error_message>"
}
{
    "error": "Unexpected error: <error_message>"
}
```

---

### 5. Service Directory
**Endpoint:**
```
GET /api/service directory/
```

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <access token> (Required)
```
**Description:**
Retrieve a list of all registered services. If no query parameters are provided, all available
services are returned. Optionally, you can filter the results based on service name, endpoint, or
method.

**Optional Query Parameters:**
```
{
    "service_name": "string", // Optional, partial or full match for the service name
    "endpoint": "string", // Optional, partial or full match for the endpoint
    "method": "string" // Optional, HTTP method supported by the service
}
```

**Success Response:**
```
[
    {
        "base_url": "http://127.0.0.1:8003",
        "service_name": "weather_data",
        "endpoint": "get_temperature/{dd-mm-yyyy}",
        "methods":[
            "POST",
            "DELETE",
            "GET"
        ],
        "params":{},
        "service_url": "http://127.0.0.1:8003/weather_data/get_temperature/{dd-mm-yyyy}"
    },
    {
        "base_url": "http://127.0.0.1:8002/",
        "service_name": "farm_calendar",
        "endpoint": "get_all_farms/{id}",
        "methods":[
            "DELETE",
            "POST",
            "GET"
        ],
        "params":{},
        "service_url": "http://127.0.0.1:8002/farm_calendar/get_all_farms/{id}"
    }
]
```


**Error Responses:**

**500 Internal Server Error - Unexpected error during query execution**
```
{
    "error": "Unexpected error: <error_message>"
}
```

**500 Internal Server Error - Database error**
```
{
    "error": "Database error: <database_error_message>"
}
```

---

## Notes
- Ensure that authentication tokens are handled securely.
- The access token should be used in API requests requiring authentication.
- Refresh tokens should be stored securely and never exposed in frontend applications.

---
