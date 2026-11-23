from collections import defaultdict

from django.db.models import Q

from aegis.models import (
    FarmCalendarResourceCache,
    PermissionMaster,
    ServiceMaster,
    ServiceScopeAssignment,
)


FC_SERVICE_IDENTIFIERS = {"farmcalendar", "fc"}
READ_ONLY_ROLE = "read_only"
READ_ONLY_ACTIONS = frozenset({"view"})


def _normalize_service_key(value):
    return (value or "").strip().lower()


def _is_fc_service(service_code, service_name):
    return (
        _normalize_service_key(service_code) in FC_SERVICE_IDENTIFIERS
        or _normalize_service_key(service_name) in FC_SERVICE_IDENTIFIERS
        or _normalize_service_key(service_name) == "farm calendar"
    )


def fc_service_queryset(base_qs=None):
    """Filter a ServiceMaster queryset (default: all rows) down to FC."""
    if base_qs is None:
        base_qs = ServiceMaster.objects.all()
    return base_qs.filter(
        Q(service_code__iexact="FC")
        | Q(service_code__iexact="farmcalendar")
        | Q(service_name__iexact="Farm Calendar")
        | Q(service_name__iexact="FarmCalendar")
    )


def _empty_service_entry(service_code, service_name):
    return {
        "code": service_code,
        "name": service_name or service_code,
        "roles": set(),
        "actions": set(),
        "scopes": defaultdict(set),
        "assignments": [],
        "unrestricted": False,
    }


def _ensure_service_entry(container, service_code, service_name):
    if service_code not in container:
        container[service_code] = _empty_service_entry(service_code, service_name)
    return container[service_code]


def _append_assignment(entry, *, role, actions, scope_type, scope_id, source):
    normalized_actions = sorted(
        {
            action
            for action in (actions or [])
            if isinstance(action, str) and action
        }
    )
    assignment = {
        "role": role or "",
        "actions": normalized_actions,
        "scope_type": scope_type or "",
        "scope_id": str(scope_id) if scope_id else "",
        "source": source,
    }
    entry["assignments"].append(assignment)

    if role:
        entry["roles"].add(role)
    for action in normalized_actions:
        entry["actions"].add(action)
    if scope_type and scope_id:
        entry["scopes"][scope_type].add(str(scope_id))


def _apply_superuser_entitlements():
    services = {}
    active_services = ServiceMaster.objects.filter(status=1).values_list("service_code", "service_name")

    for service_code, service_name in active_services:
        entry = _ensure_service_entry(services, service_code, service_name)
        entry["unrestricted"] = True

        permission_actions = PermissionMaster.objects.filter(
            status=1,
            service__status=1,
            service__service_code=service_code,
        ).values_list("action", flat=True)
        for action in permission_actions:
            if action:
                entry["actions"].add(action)

        if _is_fc_service(service_code, service_name):
            fc_rows = FarmCalendarResourceCache.objects.filter(
                status=1,
                resource_type__in=("farm", "parcel"),
            ).values_list("resource_type", "resource_id")
            for scope_type, scope_id in fc_rows:
                _append_assignment(
                    entry,
                    role="admin",
                    actions=["view", "add", "edit", "delete"],
                    scope_type=scope_type,
                    scope_id=scope_id,
                    source="superuser",
                )

    return services


def _apply_tenant_user_entitlements(user, services):
    """Policy:
    - Every user that belongs to a tenant gets all non-FC services tenant-wide
      (unrestricted, all actions).
    - Tenant admins additionally get FC enumerated to every farm/parcel in
      their tenant. Non-admin users get FC only via explicit Role Grants.
    - Read-only users get FC enumerated like tenant admins; all their actions
      are later capped to ``view`` by ``_cap_to_read_only``.
    """
    tenant_id = getattr(user, "tenant_id", None)
    if not tenant_id:
        return services
    if getattr(user, "is_superuser", False):
        return services

    is_tenant_admin = bool(getattr(user, "is_tenant_admin", False))
    is_read_only = bool(getattr(user, "is_read_only", False))
    tenant_wide_role = READ_ONLY_ROLE if is_read_only else "tenant_admin"

    active_services = ServiceMaster.objects.filter(status=1).values_list("service_code", "service_name")
    for service_code, service_name in active_services:
        is_fc = _is_fc_service(service_code, service_name)
        if is_fc and not (is_tenant_admin or is_read_only):
            continue

        entry = _ensure_service_entry(services, service_code, service_name)
        if is_tenant_admin or is_read_only:
            entry["roles"].add(tenant_wide_role)

        permission_actions = PermissionMaster.objects.filter(
            status=1,
            service__status=1,
            service__service_code=service_code,
        ).values_list("action", flat=True)
        for action in permission_actions:
            if action:
                entry["actions"].add(action)

        if is_fc:
            fc_rows = FarmCalendarResourceCache.objects.filter(
                status=1,
                tenant_id=tenant_id,
                resource_type__in=("farm", "parcel"),
            ).values_list("resource_type", "resource_id")
            for scope_type, scope_id in fc_rows:
                _append_assignment(
                    entry,
                    role=tenant_wide_role,
                    actions=sorted(entry["actions"]),
                    scope_type=scope_type,
                    scope_id=scope_id,
                    source=tenant_wide_role,
                )
        else:
            entry["unrestricted"] = True

    return services


def _cap_to_read_only(services):
    """Strip every action except ``view`` from a read-only user's entitlements,
    including actions that came from explicit Role Grants."""
    for entry in services.values():
        entry["actions"] &= READ_ONLY_ACTIONS
        kept = []
        for assignment in entry["assignments"]:
            assignment["actions"] = [a for a in assignment["actions"] if a in READ_ONLY_ACTIONS]
            if assignment["actions"]:
                kept.append(assignment)
        entry["assignments"] = kept
        entry["roles"] = {READ_ONLY_ROLE} | {a["role"] for a in kept if a["role"]}
        entry["scopes"] = defaultdict(set)
        for assignment in kept:
            if assignment["scope_type"] and assignment["scope_id"]:
                entry["scopes"][assignment["scope_type"]].add(assignment["scope_id"])


def resolve_service_entitlements_for_user(user):
    """
    Build normalized per-service entitlements for a user by combining:
    1) Tenant-wide auto-grants (non-FC) + tenant-admin FC scope
    2) Scoped assignments (ServiceScopeAssignment / Role Grants)

    Output keeps both:
    - flattened compatibility fields (`roles`, `actions`, `scopes`)
    - exact per-scope `assignments`
    """
    if getattr(user, "is_superuser", False):
        services = _apply_superuser_entitlements()
    else:
        services = {}

    services = _apply_tenant_user_entitlements(user, services)

    group_ids = list(user.groups.values_list("id", flat=True))

    # Scoped assignments via group or user.
    scope_assignments = (
        ServiceScopeAssignment.objects
        .filter(
            status=1,
            service__status=1,
        )
        .filter(Q(user=user) | Q(group_id__in=group_ids))
    )
    if getattr(user, "tenant_id", None):
        scope_assignments = scope_assignments.filter(tenant_id=user.tenant_id)
    else:
        scope_assignments = scope_assignments.filter(tenant__isnull=True)

    scope_rows = scope_assignments.values_list(
        "service__service_code",
        "service__service_name",
        "role_ref__role_name",
        "role",
        "role_ref__permissions__action",
        "actions",
        "scope_type",
        "scope_id",
        "user_id",
        "group_id",
    )
    grouped_scope_rows = defaultdict(lambda: {"actions": set()})
    for service_code, service_name, role_name, role_code, permission_action, actions, scope_type, scope_id, user_id, group_id in scope_rows:
        if not service_code:
            continue
        key = (service_code, service_name, role_name or role_code or "", scope_type, scope_id, user_id, group_id)
        grouped_scope_rows[key]["actions"].update(
            action for action in (([permission_action] if permission_action else []) or []) if action
        )
        if not permission_action and isinstance(actions, list):
            grouped_scope_rows[key]["actions"].update(
                action for action in actions if isinstance(action, str) and action
            )

    for (service_code, service_name, role_name, scope_type, scope_id, user_id, group_id), payload in grouped_scope_rows.items():
        entry = _ensure_service_entry(services, service_code, service_name)
        _append_assignment(
            entry,
            role=role_name,
            actions=sorted(payload["actions"]),
            scope_type=scope_type,
            scope_id=scope_id,
            source="user" if user_id else ("group" if group_id else "unknown"),
        )

    if getattr(user, "is_read_only", False):
        _cap_to_read_only(services)

    normalized = []
    for _, data in sorted(services.items()):
        scopes = {
            scope_key: sorted(scope_values)
            for scope_key, scope_values in sorted(data["scopes"].items())
        }
        normalized.append({
            "code": data["code"],
            "name": data["name"],
            "roles": sorted(data["roles"]),
            "actions": sorted(data["actions"]),
            "scopes": scopes,
            "assignments": sorted(
                data["assignments"],
                key=lambda item: (
                    item.get("scope_type", ""),
                    item.get("scope_id", ""),
                    item.get("role", ""),
                ),
            ),
            "unrestricted": bool(data["unrestricted"]),
        })

    return normalized
