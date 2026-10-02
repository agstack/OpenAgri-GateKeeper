# GateKeeper
🇪🇺
*"This service was created in the context of OpenAgri project (https://horizon-openagri.eu/). OpenAgri has received funding from the EU’s Horizon Europe research and innovation programme under Grant Agreement no. 101134083."*

GateKeeper (GK) is the central authentication, authorization, and service-proxy component for shared OpenAgri deployments.

It is responsible for:

- authenticating users and issuing JWT tokens
- returning the caller's tenant and service entitlements
- enforcing tenant- and scope-aware access for downstream services
- mirroring FarmCalendar farms and parcels into GK cache for RBAC assignment
- providing a Django admin for platform admins and tenant admins

## Services In Scope

GK is used in front of:

- Farm Calendar (`FC`)
- Irrigation Management (`IRM`)
- Weather Data (`WD`)
- Pest and Disease Management (`PDM`)
- Reporting (`RP`)

## Current Authorization Model

GK now uses a tenant-scoped RBAC model.

Core objects:

- `Tenant`
- `User Master`
- `Service`
- `Permission`
- `Service Role`
- `Role Grant`
- `FarmCalendar Resource Cache`

Access is modeled as:

- permissions belong to service roles
- service roles are tenant-scoped
- role grants assign a role to a user on a farm or parcel scope

Admin types:

- `platform_admin`
  - Django `is_superuser=True`
  - unrestricted across all tenants
- `tenant_admin`
  - `is_tenant_admin=True`
  - tenant-scoped admin access inside GK
- normal tenant user
  - tenant-bound, non-admin user

## Main API Surface

GK exposes:

- `POST /api/login/`
- `POST /api/logout/`
- `POST /api/token/refresh/`
- `POST /api/validate_token/`
- `GET /api/me/`
- `GET /api/farmcalendar-scopes/`
- `GET /api/farmcalendar-catalog/`
- `POST /api/register_service/`
- `GET /api/service_directory/`
- `POST /api/delete_service/`
- `GET|POST|PATCH|DELETE /api/proxy/<path>`

See:

- [API.md](/home/pranav/PyCharm/OpenAgri/GateKeeper/API.md)

## Management Commands

### Create one tenant admin

```bash
python manage.py create_tenant_admin sip06 sip06_admin sip06_admin@example.com 'replace-me'
```

### Bootstrap many tenant admins from CSV

```bash
python manage.py bootstrap_tenant_admins --csv /path/to/tenant_admins.csv
```

Dry run:

```bash
python manage.py bootstrap_tenant_admins --csv /path/to/tenant_admins.csv --dry-run
```

### Sync FarmCalendar catalog into GK cache

```bash
python manage.py sync_farmcalendar_catalog
```

Watch mode:

```bash
python manage.py sync_farmcalendar_catalog --watch --interval 30
```

## Important Environment Variables

Database and runtime:

- `DATABASE_URL`
- `APP_HOST`
- `APP_PORT`
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_STATIC_ROOT`

Superuser bootstrap:

- `SUPERUSER_USERNAME`
- `SUPERUSER_EMAIL`
- `SUPERUSER_PASSWORD`

JWT:

- `JWT_SIGNING_KEY`
- `JWT_ALG`
- `JWT_ACCESS_TOKEN_MINUTES`
- `JWT_REFRESH_TOKEN_DAYS`

Proxy upstream policy:

- `GK_ALLOWED_UPSTREAMS` — comma-separated exact service origins, including ports and trailing slashes
- `GK_ALLOW_PRIVATE_UPSTREAMS` — explicitly permit allowlisted private/Docker-network addresses
- `GK_ALLOW_HTTP_UPSTREAMS` — explicitly permit allowlisted plain-HTTP origins

Temporary registration provisioning:

- `GK_PROVISION_SAMPLE_FARM_ON_REGISTRATION` — create one sample farm and parcel for each new temporary tenant
- `GK_FARM_PROVISION_TIMEOUT_SECONDS` — connect/read timeout for each FarmCalendar request

The sample data is selected from 100 synthetic profiles in
`aegis/data/temporary_farm_profiles.json`. Creation is best-effort: registration
is retained if FarmCalendar is temporarily unavailable.

FarmCalendar / proxy integration:

- `FARM_CALENDAR_API`
- `FARM_CALENDAR_POST_AUTH`
- `INTERNAL_GK_URL`

FC catalog sync credentials:

- `FC_SYNC_USERNAME`
- `FC_SYNC_PASSWORD`

Fallback sync credentials if dedicated sync credentials are not set:

- `GATEKEEPER_SUPERUSER_USERNAME`
- `GATEKEEPER_SUPERUSER_PASSWORD`
- `SUPERUSER_USERNAME`
- `SUPERUSER_PASSWORD`

## Running Locally

Create your env file and configure the required values first.

Then run:

```bash
docker compose up -d
```

Access:

- site login: `http://localhost:8001/login/`
- Django admin: `http://localhost:8001/admin/`

## Production Notes

GK is configured to serve static files with WhiteNoise when `DEBUG=False`.

Required deployment behavior:

1. set `DJANGO_DEBUG=False`
2. set `DJANGO_STATIC_ROOT` consistently
3. run `collectstatic`
4. proxy traffic through Traefik or another reverse proxy

If you use a persisted static volume, make sure stale collected assets do not prevent fresh `collectstatic` runs after image updates.

## Admin Behavior

Tenant admins use the same GK admin panel but only see tenant-local data.

Tenant admins can:

- create users inside their own tenant
- create tenant-local service roles
- create role grants for tenant users

Tenant admins cannot:

- create superusers
- see global platform configuration
- see or modify another tenant's data

## Further Documentation

- [API.md](/home/pranav/PyCharm/OpenAgri/GateKeeper/API.md)
- [GK_DASHBOARD_AUTHZ_GUIDE.md](/home/pranav/PyCharm/OpenAgri/GateKeeper/docs/GK_DASHBOARD_AUTHZ_GUIDE.md)
- [GK_PROXY_PENETRATION_TESTING.md](/home/pranav/PyCharm/OpenAgri/GateKeeper/docs/GK_PROXY_PENETRATION_TESTING.md)

# License

This project is distributed with the EUPL 1.2v. See the `LICENSE` file for details.
