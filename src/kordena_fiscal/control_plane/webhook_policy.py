"""Approved egress policy on the canonical configuration and outbox scope."""

from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from kordena_fiscal.domain import ExecutionScope, FiscalValidationError
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory

# Explicit special-use networks make denial stable on supported Python versions.
# IPv6 must also be native global unicast (no NAT64/translation/tunnel prefixes).
_FORBIDDEN_V4 = tuple(
    ipaddress.ip_network(value)
    for value in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.0.2.0/24",
        "192.88.99.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "198.51.100.0/24",
        "203.0.113.0/24",
        "224.0.0.0/4",
        "240.0.0.0/4",
    )
)
_NATIVE_V6 = ipaddress.ip_network("2000::/3")
_FORBIDDEN_V6 = tuple(
    ipaddress.ip_network(value)
    for value in (
        "2001::/23",
        "2001:db8::/32",
        "2002::/16",
        "3fff::/20",
    )
)


class WebhookPolicyDenied(FiscalValidationError):
    """Deliberately has no URL, response, DNS address or credential in its message."""


def normalize_webhook_url(value: str) -> tuple[str, str, str]:
    try:
        if not isinstance(value, str) or len(value) > 2048 or value != value.strip():
            raise ValueError
        if any(ord(char) <= 32 or ord(char) == 127 for char in value) or "\\" in value:
            raise ValueError
        parsed = urlsplit(value)
        host = (parsed.hostname or "").encode("idna").decode("ascii").lower()
        if parsed.scheme.lower() != "https" or parsed.port not in (None, 443):
            raise ValueError
        if parsed.username is not None or parsed.password is not None:
            raise ValueError
        if "?" in value or "#" in value or not parsed.path.startswith("/"):
            raise ValueError
        if not host or len(host) > 253 or "." not in host or host.endswith("."):
            raise ValueError
        if host.endswith((".localhost", ".local", ".internal", ".lan", ".home", ".arpa")):
            raise ValueError
        if host == "localhost" or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in host.split(".")
        ):
            raise ValueError
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError
        if re.search(r"%(?:0[0-9a-f]|1[0-9a-f]|7f|5c)", parsed.path, re.I):
            raise ValueError
        canonical = urlunsplit(("https", host, parsed.path, "", ""))
        return canonical, host, parsed.path
    except (ValueError, UnicodeError) as exc:
        raise WebhookPolicyDenied("WEBHOOK_DESTINATION_DENIED") from exc


class WebhookDnsResolver(Protocol):
    def addresses(self, hostname: str) -> tuple[str, ...]: ...


class SystemWebhookDnsResolver:
    def addresses(self, hostname: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    str(item[4][0])
                    for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
                }
            )
        )


@dataclass(frozen=True, slots=True)
class ApprovedWebhookConnection:
    canonical_url: str
    hostname: str
    path: str
    address: str
    version: int


class WebhookDispatchPolicy(Protocol):
    def authorize(
        self, scope: ExecutionScope, destination_id: str, url: str, now: datetime
    ) -> ApprovedWebhookConnection: ...


class DurableWebhookEgressPolicy:
    def __init__(
        self, unit_of_work_factory: FiscalUnitOfWorkFactory, dns: WebhookDnsResolver | None = None
    ) -> None:
        self._factory = unit_of_work_factory
        self._dns = dns or SystemWebhookDnsResolver()

    def authorize(
        self, scope: ExecutionScope, destination_id: str, url: str, now: datetime
    ) -> ApprovedWebhookConnection:
        canonical, hostname, path = normalize_webhook_url(url)
        if now.tzinfo is None:
            raise WebhookPolicyDenied("WEBHOOK_APPROVAL_DENIED")
        with self._factory() as uow:
            record = uow.commercial.webhook_approval(scope, destination_id)
            version = uow.commercial.configuration_version(scope, "webhooks", destination_id)
        try:
            if record is None or not record["enabled"] or record["approval_status"] != "approved":
                raise ValueError
            expires = datetime.fromisoformat(str(record["approved_until"]))
            if expires.tzinfo is None or expires <= now.astimezone(UTC):
                raise ValueError
            if version < 1 or record["approved_version"] != version or record["url"] != canonical:
                raise ValueError
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            if record["approved_url_sha256"] != digest or not record["approved_by"]:
                raise ValueError
            addresses = self._dns.addresses(hostname)
            if not addresses:
                raise ValueError
            for raw in addresses:
                if not isinstance(raw, str) or "%" in raw:
                    raise ValueError
                ip = ipaddress.ip_address(raw)
                if (
                    (
                        isinstance(ip, ipaddress.IPv4Address)
                        and any(ip in network for network in _FORBIDDEN_V4)
                    )
                    or (
                        isinstance(ip, ipaddress.IPv6Address)
                        and (
                            ip not in _NATIVE_V6 or any(ip in network for network in _FORBIDDEN_V6)
                        )
                    )
                    or not ip.is_global
                    or ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_multicast
                    or ip.is_reserved
                    or ip.is_unspecified
                    or (
                        isinstance(ip, ipaddress.IPv6Address)
                        and (
                            ip.ipv4_mapped is not None
                            or ip.sixtofour is not None
                            or ip.teredo is not None
                        )
                    )
                ):
                    raise ValueError
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise WebhookPolicyDenied("WEBHOOK_APPROVAL_OR_DNS_DENIED") from exc
        # DNS resolution is untrusted work. Detect revocation/reconfiguration that
        # happened while resolving, before publishing a connection target.
        with self._factory() as uow:
            latest = uow.commercial.webhook_approval(scope, destination_id)
            current = uow.commercial.configuration_version(scope, "webhooks", destination_id)
        if latest != record or current != version or expires <= datetime.now(UTC):
            raise WebhookPolicyDenied("WEBHOOK_APPROVAL_CHANGED_OR_EXPIRED")
        return ApprovedWebhookConnection(canonical, hostname, path, addresses[0], version)
