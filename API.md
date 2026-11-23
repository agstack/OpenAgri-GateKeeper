# API Documentation

This document describes the currently implemented GateKeeper API endpoints that matter for login, entitlement discovery, FarmCalendar scope discovery, catalog lookup, logout, and token lifecycle.

## Base URLs

Local default:

```text
http://localhost:8001/
```

API root:

```text
http://localhost:8001/api/
```

## Authentication Endpoints

### Temporary Event Registration

**Endpoint**

```text
POST /api/register/
```

Creates an active staff user who is the administrator of a new isolated
`sip-temp-<12 hex characters>` tenant. When temporary farm provisioning is
enabled, GateKeeper also creates one synthetic farm and one parcel in
FarmCalendar and stamps both resources with the new tenant in its local catalog.

**Request Body**

```json
{
  "username": "event-user",
  "email": "event-user@example.com",
  "first_name": "Event",
  "last_name": "User",
  "password": "temporary-password",
  "confirm_password": "temporary-password"
}
```

**Success Response**

```json
{
  "success": true,
  "message": "User registered successfully. Please log in.",
  "user_id": "user-uuid",
  "tenant_code": "sip-temp-12hexchars",
  "farm_provisioning": {
    "success": true,
    "skipped": false,
    "farm_id": "farm-uuid",
    "parcel_id": "parcel-uuid"
  }
}
```

Registration remains successful if FarmCalendar is unavailable. In that case,
`farm_provisioning.success` is `false`; no FarmCalendar error details are exposed
to the anonymous caller.

### 1. Login

**Endpoint**

```text
POST /api/login/
```

**Description**

Obtain JWT access and refresh tokens.

Login accepts either:

- username
- email

**Headers**

```text
Content-Type: application/json
```

**Request Body**

```json
{
  "username": "string",
  "password": "string"
}
```

**Success Response**

```json
{
  "success": true,
  "access": "jwt-access-token",
  "refresh": "jwt-refresh-token"
}
```

**Error Response**

```json
{
  "detail": "No active account found with the given credentials."
}
```

### 2. Logout

**Endpoint**

```text
POST /api/logout/
```

**Description**

Blacklists the submitted refresh token. If an access token is supplied in the `Authorization` header, GK also records that access token JTI in the access blacklist.

**Headers**

```text
Content-Type: application/json
Authorization: Bearer <access_token>   # optional
```

**Request Body**

```json
{
  "refresh": "jwt-refresh-token"
}
```

**Success Response**

```json
{
  "success": "Logged out successfully"
}
```

**Error Response**

```json
{
  "error": "Refresh token is required"
}
```

### 3. Token Refresh

**Endpoint**

```text
POST /api/token/refresh/
```

**Request Body**

```json
{
  "refresh": "jwt-refresh-token"
}
```

**Success Response**

```json
{
  "access": "new-jwt-access-token"
}
```

### 4. Token Validation

**Endpoint**

```text
POST /api/validate_token/
```

**Request Body**

```json
{
  "token": "jwt-token",
  "token_type": "access"
}
```

`token_type` may be:

- `access`
- `refresh`

**Success Response**

```json
{
  "success": true,
  "remaining_time_in_seconds": 1234.56
}
```

**Error Response**

```json
{
  "error": "Invalid access token"
}
```

## Identity And Entitlements

### 5. Current User

**Endpoint**

```text
GET /api/me/
```

**Description**

Returns:

- the authenticated user's identity
- tenant context
- platform-admin / tenant-admin flags
- normalized service entitlements

**Headers**

```text
Authorization: Bearer <access_token>
```

**Success Response**

```json
{
  "user": {
    "uuid": "string",
    "username": "string",
    "email": "string",
    "first_name": "string",
    "last_name": "string",
    "groups": [],
    "tenant_id": "uuid-or-null",
    "tenant_code": "sip06",
    "tenant_name": "Precise Olive Irrigation Solution",
    "is_platform_admin": false,
    "is_tenant_admin": true,
    "is_read_only": false
  },
  "services": [
    {
      "code": "FC",
      "name": "Farm Calendar",
      "roles": ["Viewer"],
      "actions": ["view"],
      "scopes": {
        "farm": ["farm-uuid"],
        "parcel": ["parcel-uuid"]
      },
      "assignments": [
        {
          "role": "Viewer",
          "actions": ["view"],
          "scope_type": "farm",
          "scope_id": "farm-uuid",
          "source": "user"
        }
      ],
      "unrestricted": false
    }
  ]
}
```

Notes:

- platform admins are returned with unrestricted service access
- tenant admins receive implicit FC entitlement for their tenant
- read-only users (`is_read_only: true`) receive implicit FC entitlement for their tenant, and every service is reduced to the `view` action with the `read_only` role
- `assignments` reflects the exact entitlement rows used to derive the flattened `roles`, `actions`, and `scopes`

### 6. FarmCalendar Scopes

**Endpoint**

```text
GET /api/farmcalendar-scopes/
```

**Description**

Returns a UI-oriented FC scope block for the authenticated user.

**Headers**

```text
Authorization: Bearer <access_token>
```

**Success Response**

```json
{
  "service": {
    "code": "FC",
    "name": "Farm Calendar"
  },
  "tenant": {
    "id": "uuid-or-null",
    "code": "sip06",
    "name": "Precise Olive Irrigation Solution"
  },
  "roles": ["Viewer"],
  "actions": ["view"],
  "assignments": [],
  "unrestricted": false,
  "scopes": {
    "farm": ["farm-uuid"],
    "parcel": ["parcel-uuid"]
  },
  "summary": {
    "farm_count": 1,
    "parcel_count": 1
  }
}
```

If the user has no FC entitlement, GK returns an empty FC-shaped response instead of omitting the object entirely.

### 7. FarmCalendar Catalog Mirror

**Endpoint**

```text
GET /api/farmcalendar-catalog/
```

**Description**

Returns GK's cached FarmCalendar farm and parcel mirror. For non-platform users the response is tenant-filtered.

**Headers**

```text
Authorization: Bearer <access_token>
```

**Success Response**

```json
{
  "summary": {
    "farm_count": 1,
    "parcel_count": 2
  },
  "farms": [
    {
      "id": "farm-uuid",
      "name": "Farm A",
      "payload": {},
      "synced_at": "2026-04-22T05:12:21+00:00"
    }
  ],
  "parcels": [
    {
      "id": "parcel-uuid",
      "name": "Parcel 1",
      "farm_id": "farm-uuid",
      "payload": {},
      "synced_at": "2026-04-22T05:12:21+00:00"
    }
  ]
}
```

## Service Registry And Proxy

### 8. Register Service

**Endpoint**

```text
POST /api/register_service/
```

Registers a downstream service definition in GK.

Requires an active GateKeeper platform superuser. The submitted `base_url`
must be present in `GK_ALLOWED_UPSTREAMS`; HTTP and private-network destinations
also require their explicit environment flags.

### 9. Service Directory

**Endpoint**

```text
GET /api/service_directory/
```

Returns the registered service directory.

Requires an active GateKeeper platform superuser because directory entries
contain internal upstream routing information.

### 10. Delete Service

**Endpoint**

```text
DELETE /api/delete_service/
```

Deletes a registered service definition.

Requires an active GateKeeper platform superuser.

### 11. Reverse Proxy

**Endpoint**

```text
/api/proxy/<path>
```

GK proxies authenticated requests to downstream services and applies entitlement checks before forwarding.
The selected service origin must also remain in `GK_ALLOWED_UPSTREAMS`; legacy
or manually inserted routes outside the allowlist are rejected before a network
request is made.

In practice this is used heavily for FarmCalendar:

- `GET /api/proxy/farmcalendar/api/v1/Farm/`
- `GET /api/proxy/farmcalendar/api/v1/Farm/<uuid>/`
- `GET /api/proxy/farmcalendar/api/v1/FarmParcels/`
- `PATCH /api/proxy/farmcalendar/api/v1/Farm/<uuid>/?format=json`

The proxy layer is where tenant, action, and scope enforcement is applied for protected service requests.

For read-only users the proxy forwards `GET`, `HEAD` and `OPTIONS` to every service,
and `POST` only to the routes in `GK_READ_ONLY_POST_ALLOWLIST`. Any other request is
refused before it reaches the service:

```json
{
  "error": "This account is read-only."
}
```

with status `403`.

## Admin Login Behavior

These are browser endpoints, not JSON API endpoints, but they matter operationally:

- site login:
  - `/login/`
- admin login:
  - `/admin/login/?next=/admin/`

Django admin login accepts either:

- username
- email
