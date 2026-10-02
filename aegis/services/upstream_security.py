import ipaddress
import socket

from functools import lru_cache
from urllib.parse import urlsplit

from django.conf import settings


class UpstreamPolicyError(ValueError):
    """Raised when an upstream URL violates GateKeeper's proxy policy."""


def normalize_upstream_base_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UpstreamPolicyError("Base URL must be a non-empty string.")

    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError as exc:
        raise UpstreamPolicyError("Base URL contains an invalid port.") from exc

    if parsed.scheme not in {"http", "https"}:
        raise UpstreamPolicyError("Base URL must use HTTP or HTTPS.")
    if not parsed.hostname or port is None:
        raise UpstreamPolicyError("Base URL must contain a hostname and explicit port.")
    if parsed.username or parsed.password:
        raise UpstreamPolicyError("Base URL must not contain credentials.")
    if parsed.path != "/" or parsed.query or parsed.fragment:
        raise UpstreamPolicyError("Base URL must end at the origin root with a trailing slash.")

    hostname = parsed.hostname.lower()
    rendered_hostname = f"[{hostname}]" if ":" in hostname else hostname
    return f"{parsed.scheme.lower()}://{rendered_hostname}:{port}/"


@lru_cache(maxsize=256)
def _resolved_addresses(hostname: str, port: int) -> tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]:
    try:
        return (ipaddress.ip_address(hostname),)
    except ValueError:
        pass

    try:
        results = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UpstreamPolicyError("Allowlisted upstream host could not be resolved.") from exc

    addresses = tuple({ipaddress.ip_address(result[4][0]) for result in results})
    if not addresses:
        raise UpstreamPolicyError("Allowlisted upstream host did not resolve to an address.")
    return addresses


def validate_allowed_upstream(value: str) -> str:
    canonical_url = normalize_upstream_base_url(value)

    try:
        allowed_urls = {
            normalize_upstream_base_url(entry)
            for entry in getattr(settings, "GATEKEEPER_ALLOWED_UPSTREAMS", ())
        }
    except UpstreamPolicyError as exc:
        raise UpstreamPolicyError("GateKeeper's upstream allowlist is invalid.") from exc

    if canonical_url not in allowed_urls:
        raise UpstreamPolicyError("Base URL is not in GateKeeper's upstream allowlist.")

    parsed = urlsplit(canonical_url)
    if parsed.scheme == "http" and not settings.GATEKEEPER_ALLOW_HTTP_UPSTREAMS:
        raise UpstreamPolicyError("HTTP upstreams are disabled; use HTTPS.")

    if not settings.GATEKEEPER_ALLOW_PRIVATE_UPSTREAMS:
        addresses = _resolved_addresses(parsed.hostname, parsed.port)
        if any(not address.is_global for address in addresses):
            raise UpstreamPolicyError(
                "Private, loopback, link-local, and reserved upstream addresses are disabled."
            )

    return canonical_url
