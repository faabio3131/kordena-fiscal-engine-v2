#!/usr/bin/env python3
"""Read-only audit of Railway API pre-deploy migration configuration.

Consumes the *non-secret* JSON returned by Railway describe-service.
Does not call Railway, inspect variable values, apply migrations or trigger deploys.
This only certifies the preDeployCommand field; it cannot certify staging as a whole.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def check_snapshot(snapshot: object, *, expected_environment: str) -> tuple[int, str]:
    if not isinstance(snapshot, dict):
        return (1, "FAIL malformed Railway configuration snapshot")
    service = snapshot.get("service")
    environment = snapshot.get("environment")
    config = snapshot.get("config")
    if (
        not isinstance(service, dict)
        or service.get("name") != "nfcore-api"
        or not isinstance(environment, dict)
        or environment.get("id") != expected_environment
        or not isinstance(config, dict)
        or not isinstance(config.get("deploy"), dict)
    ):
        return (1, "FAIL wrong Railway service/environment or incomplete snapshot")
    command = config["deploy"].get("preDeployCommand")
    if command not in (None, []):
        # Never echo arbitrary commands, which might contain credentials.
        return (42, "BLOCKED_EXTERNAL API preDeployCommand must be absent")
    return (0, "PASS API preDeployCommand absent; other P05-T01 gates remain unverified")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path, help="non-secret Railway describe-service JSON")
    parser.add_argument("--environment-id", required=True)
    args = parser.parse_args()
    try:
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        print("FAIL Railway configuration snapshot unreadable")
        return 1
    status, message = check_snapshot(snapshot, expected_environment=args.environment_id)
    print(message)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
