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

**Status Codes:**
- `200 OK` - Login successful
- `400 BAD REQUEST` - Missing fields (username or password)
- `401 UNAUTHORIZED` - Invalid username/password or inactive account

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
**Status Codes:**
- `200 OK` - Logout successful
- `400 BAD REQUEST` - Missing, invalid, or expired refresh token

---

## Notes
- Ensure that authentication tokens are handled securely.
- The access token should be used in API requests requiring authentication.
- Refresh tokens should be stored securely and never exposed in frontend applications.

---
