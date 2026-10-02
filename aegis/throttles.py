import hashlib

from django.conf import settings
from django.core.cache import cache


def _login_attempt_limit():
    return max(1, int(getattr(settings, "LOGIN_THROTTLE_ATTEMPTS", 5)))


def _login_attempt_window_seconds():
    return max(60, int(getattr(settings, "LOGIN_THROTTLE_WINDOW_SECONDS", 600)))


def _cache_key(kind, value):
    digest = hashlib.sha256((value or "").encode("utf-8")).hexdigest()
    return f"gk:login_throttle:{kind}:{digest}"


def _get_client_ip(request):
    forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip() or "unknown"


def _normalize_identifier(identifier):
    return (identifier or "").strip().lower()


def _read_counter(key):
    payload = cache.get(key)
    if not isinstance(payload, dict):
        return 0
    return int(payload.get("count", 0))


def _bump_counter(key):
    window = _login_attempt_window_seconds()
    payload = cache.get(key)
    count = 1
    if isinstance(payload, dict):
        count = int(payload.get("count", 0)) + 1
    cache.set(key, {"count": count}, timeout=window)
    return count


def _clear_counter(key):
    cache.delete(key)


def _retry_after_seconds(key):
    remaining = cache.ttl(key)
    if remaining is None:
        return _login_attempt_window_seconds()
    return max(1, int(remaining))


def check_login_allowed(request, identifier=""):
    limit = _login_attempt_limit()
    ip_key = _cache_key("ip", _get_client_ip(request))
    keys = [ip_key]

    normalized_identifier = _normalize_identifier(identifier)
    if normalized_identifier:
        keys.append(_cache_key("identifier", normalized_identifier))

    blocked_key = next((key for key in keys if _read_counter(key) >= limit), None)
    if blocked_key:
        return False, _retry_after_seconds(blocked_key)
    return True, None


def register_login_failure(request, identifier=""):
    ip_key = _cache_key("ip", _get_client_ip(request))
    _bump_counter(ip_key)

    normalized_identifier = _normalize_identifier(identifier)
    if normalized_identifier:
        identifier_key = _cache_key("identifier", normalized_identifier)
        _bump_counter(identifier_key)


def clear_login_failures(request, identifier=""):
    ip_key = _cache_key("ip", _get_client_ip(request))
    _clear_counter(ip_key)

    normalized_identifier = _normalize_identifier(identifier)
    if normalized_identifier:
        identifier_key = _cache_key("identifier", normalized_identifier)
        _clear_counter(identifier_key)
