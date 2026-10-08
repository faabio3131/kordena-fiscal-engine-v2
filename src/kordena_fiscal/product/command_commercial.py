"""Strict, PII-free Command commercial contract; payload never grants authority."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime

from kordena_fiscal.product.commercial_fulfillment import (
    CommercialEventType,
    CommercialFulfillmentError,
)
from kordena_fiscal.security.secrets import SecretReference, SecretScope

_TOKEN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")


def token(value: str) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise CommercialFulfillmentError("invalid Command identifier")
    return value


@dataclass(frozen=True, slots=True)
class CommandBinding:
    key_id: str
    binding_id: str
    product_id: str
    environment: str
    secret_reference: str
    secret_version: int
    not_after: datetime
    enabled: bool = True
    contract_version: int = 1

    def __post_init__(self) -> None:
        for value in (self.key_id, self.binding_id, self.product_id):
            token(value)
        if self.environment not in {"test", "development", "staging", "production"}:
            raise CommercialFulfillmentError("invalid Command environment")
        SecretReference(self.secret_reference, self.secret_version)
        if self.not_after.tzinfo is None or self.not_after.utcoffset() is None:
            raise CommercialFulfillmentError("Command binding expiry must be aware")
        if type(self.enabled) is not bool or type(self.contract_version) is not int:
            raise CommercialFulfillmentError("invalid Command binding flags")
        if self.contract_version != 1:
            raise CommercialFulfillmentError("unknown Command contract version")

    @property
    def scope(self) -> SecretScope:
        identity = f"{self.binding_id}|{self.product_id}|{self.environment}|{self.contract_version}"
        namespace = "command-binding-" + hashlib.sha256(identity.encode()).hexdigest()
        return SecretScope(namespace, None, "commercial.command.webhook")


@dataclass(frozen=True, slots=True)
class CommandCommercialEvent:
    version: int
    event_id: str
    event_type: CommercialEventType
    occurred_at: datetime
    product_id: str
    environment: str
    command_customer_id: str
    command_subscription_id: str
    command_invoice_id: str
    acquisition_id: str
    plan_id: str
    price_id: str

    @classmethod
    def parse(cls, body: bytes) -> CommandCommercialEvent:
        def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise CommercialFulfillmentError("duplicate Command field")
                result[key] = value
            return result

        try:
            value = json.loads(body, object_pairs_hook=unique)
            fields = set(cls.__dataclass_fields__)
            if not isinstance(value, dict) or set(value) != fields:
                raise ValueError("schema")
            if type(value["version"]) is not int or value["version"] != 1:
                raise ValueError("version")
            for key in fields - {"version", "occurred_at"}:
                token(value[key])
            occurred = datetime.fromisoformat(value["occurred_at"])
            if occurred.tzinfo is None or occurred.utcoffset() is None:
                raise ValueError("time")
            return cls(
                **{
                    **value,
                    "event_type": CommercialEventType(value["event_type"]),
                    "occurred_at": occurred,
                }
            )
        except (ValueError, TypeError, UnicodeDecodeError, RecursionError) as exc:
            raise CommercialFulfillmentError("invalid Command commercial envelope") from exc

    @property
    def fingerprint(self) -> str:
        payload = {**asdict(self), "occurred_at": self.occurred_at.isoformat()}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
