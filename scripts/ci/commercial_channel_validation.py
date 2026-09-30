#!/usr/bin/env python3
"""Fail-closed operational contract for real commercial-channel validation.

This script never authenticates to a sales provider and never accepts secret material.
It validates only the non-secret staging/channel prerequisites and sanitized evidence
references required before a channel can be reviewed for COMMERCIAL_CHANNEL_READY.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

CONTRACT = "nfcore-commercial-channel-validation-v1"
READY_STAGING = "STAGING_DEPLOYED_AND_E2E_VALIDATED"
_PROVIDER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_EVIDENCE = re.compile(r"^evidence:[A-Za-z0-9][A-Za-z0-9._:/-]{2,255}$")
_REQUIRED_EVIDENCE = (
    "account_kyc",
    "product_plan_configuration",
    "checkout",
    "webhook_registration",
    "authenticated_event",
    "controlled_purchase",
    "refund_or_cancel",
    "reconciliation",
)


def _blocked(reason: str) -> int:
    print(f"commercial channel validation: BLOCKED_EXTERNAL reason={reason}")
    return 42


def _fail(reason: str) -> int:
    print(f"commercial channel validation: FAIL reason={reason}")
    return 1


def _https_url(value: str, field: str) -> str:
    normalized = value.strip()
    parsed = urlparse(normalized)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError(f"{field} must be an absolute HTTPS URL without credentials/fragment")
    return normalized


def _preflight() -> int:
    staging = os.environ.get("NFCORE_STAGING_STATE", "").strip()
    if staging != READY_STAGING:
        return _blocked("staging_not_validated")

    enabled = os.environ.get(
        "NFCORE_COMMERCIAL_CHANNEL_REAL_VALIDATION_ENABLED", ""
    ).strip().lower()
    if enabled != "true":
        return _blocked("real_validation_not_enabled")

    provider = os.environ.get("NFCORE_COMMERCIAL_CHANNEL_PROVIDER", "").strip().lower()
    if not provider:
        return _blocked("provider_not_selected")
    if _PROVIDER.fullmatch(provider) is None:
        return _fail("invalid_provider_id")

    callback = os.environ.get("NFCORE_COMMERCIAL_CHANNEL_CALLBACK_URL", "").strip()
    checkout = os.environ.get("NFCORE_COMMERCIAL_CHANNEL_CHECKOUT_URL", "").strip()
    if not callback:
        return _blocked("callback_url_missing")
    if not checkout:
        return _blocked("checkout_url_missing")
    try:
        _https_url(callback, "callback_url")
        _https_url(checkout, "checkout_url")
    except ValueError as exc:
        return _fail(str(exc).replace(" ", "_"))

    print(
        "commercial channel validation: READY_FOR_REAL_VALIDATION "
        f"provider={provider} contract={CONTRACT}"
    )
    return 0


def _validate_evidence(path: Path) -> int:
    if not path.is_file():
        return _blocked("evidence_file_missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _fail("evidence_file_invalid")
    if not isinstance(payload, dict):
        return _fail("evidence_root_invalid")

    provider = payload.get("provider_id")
    environment = payload.get("environment")
    if not isinstance(provider, str) or _PROVIDER.fullmatch(provider) is None:
        return _fail("evidence_provider_invalid")
    if environment != "staging":
        return _fail("evidence_environment_must_be_staging")

    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        return _fail("evidence_mapping_invalid")

    for field in _REQUIRED_EVIDENCE:
        value = evidence.get(field)
        if value is None:
            return _blocked(f"missing_evidence_{field}")
        if not isinstance(value, str) or _EVIDENCE.fullmatch(value) is None:
            return _fail(f"invalid_evidence_{field}")

    extra = set(evidence) - set(_REQUIRED_EVIDENCE)
    if extra:
        return _fail("unexpected_evidence_fields")

    print(
        "commercial channel validation: EVIDENCE_SET_COMPLETE "
        f"provider={provider} environment=staging contract={CONTRACT}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", action="store_true")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    if args.contract:
        print(CONTRACT)
        return 0
    if args.evidence is not None:
        return _validate_evidence(args.evidence)
    return _preflight()


if __name__ == "__main__":
    sys.exit(main())
