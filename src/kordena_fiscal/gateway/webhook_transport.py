"""Pinned HTTPS implementation of the existing webhook transport port."""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from datetime import UTC, datetime

from kordena_fiscal.application.webhook_delivery import (
    WebhookDeliveryRequest,
    WebhookDeliveryResponse,
)
from kordena_fiscal.control_plane.webhook_policy import (
    ApprovedWebhookConnection,
    WebhookDispatchPolicy,
    WebhookPolicyDenied,
)


class _PinnedHttpsConnection(http.client.HTTPSConnection):
    def __init__(self, target: ApprovedWebhookConnection, timeout: float) -> None:
        self._tls = ssl.create_default_context()
        super().__init__(target.hostname, 443, timeout=timeout, context=self._tls)
        self._target = target

    def connect(self) -> None:
        # A numeric socket address never goes through a second hostname lookup.
        address = ipaddress.ip_address(self._target.address)
        family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
        raw = socket.socket(family, socket.SOCK_STREAM)
        try:
            raw.settimeout(self.timeout)
            raw.connect((str(address), 443))
            self.sock = self._tls.wrap_socket(raw, server_hostname=self._target.hostname)
        except BaseException:
            raw.close()
            raise


class PinnedWebhookTransport:
    def __init__(self, policy: WebhookDispatchPolicy, timeout_seconds: float = 10) -> None:
        if not 0 < timeout_seconds <= 300:
            raise ValueError("invalid webhook timeout")
        self._policy = policy
        self._timeout = timeout_seconds

    def deliver(self, request: WebhookDeliveryRequest) -> WebhookDeliveryResponse:
        if request.scope is None or request.approved_connection is None:
            raise WebhookPolicyDenied("WEBHOOK_APPROVED_CONNECTION_REQUIRED")
        target = self._policy.authorize(
            request.scope,
            request.destination.destination_id,
            request.destination.url,
            datetime.now(UTC),
        )
        if target.version != request.approved_connection.version:
            raise WebhookPolicyDenied("WEBHOOK_APPROVAL_CHANGED")
        # Headers are constructed by SignedWebhookOutboxHandler; callers cannot add
        # credential headers, a Host override, framing ambiguity, or a proxy.
        allowed = {
            "content-type",
            "x-fm-webhook-signature",
            "x-fm-correlation-id",
            "x-fm-causation-id",
            "x-fm-outbox-entry-id",
            "x-fm-delivery-attempt",
        }
        if any(name.lower() not in allowed for name, _value in request.headers):
            raise WebhookPolicyDenied("WEBHOOK_HEADERS_DENIED")
        connection = _PinnedHttpsConnection(target, self._timeout)
        try:
            connection.request(
                "POST", target.path, body=request.body, headers=dict(request.headers)
            )
            response = connection.getresponse()
            # No redirect traversal; no response body/Location is logged or persisted.
            return WebhookDeliveryResponse(response.status)
        finally:
            connection.close()
