"""Verify Bling order notifications before passing them to the fiscal inbox."""

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime


class BlingWebhookError(ValueError):
    """A notification failed authentication or the supported envelope contract."""


@dataclass(frozen=True, slots=True)
class BlingOrderNotification:
    event_id: str
    company_id: str
    order_id: int
    event: str
    occurred_at: datetime
    body_sha256: str


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate webhook member")
        result[key] = value
    return result


def verify_order_notification(
    body: bytes,
    signature: str,
    *,
    client_secret: bytes,
    expected_company_id: str,
) -> BlingOrderNotification:
    """Authenticate the raw UTF-8 body and bind the event to the configured company."""
    if not client_secret or len(body) > 1_048_576 or len(signature) != 71:
        raise BlingWebhookError("Bling notification refused")
    expected = b"sha256=" + hmac.new(client_secret, body, hashlib.sha256).hexdigest().encode()
    if not hmac.compare_digest(signature.encode("utf-8"), expected):
        raise BlingWebhookError("Bling signature is invalid")

    try:
        payload = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
        event_id = payload["eventId"]
        company_id = payload["companyId"]
        order_id = payload["data"]["id"]
        event = payload["event"]
        occurred_at = datetime.fromisoformat(payload["date"])
        version = payload["version"]
    except (KeyError, TypeError, ValueError, RecursionError):
        raise BlingWebhookError("Bling notification envelope is invalid") from None

    if (
        not isinstance(event_id, str)
        or not event_id.strip()
        or len(event_id) > 128
        or not isinstance(company_id, str)
        or not company_id
        or len(company_id) > 96
        or company_id != expected_company_id
        or type(order_id) is not int
        or order_id <= 0
        or event not in ("order.created", "order.updated", "order.deleted")
        or occurred_at.utcoffset() is None
        or type(version) is not str
        or version != "v1"
    ):
        raise BlingWebhookError("Bling notification envelope is unsupported")

    return BlingOrderNotification(
        event_id, company_id, order_id, event, occurred_at, hashlib.sha256(body).hexdigest()
    )
