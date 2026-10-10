"""Validate Railway backup, deployment and live replica evidence fail-closed.

Only parses CLI JSON; never handles credentials or secrets. Unknown schemas are
blocked until an actual provider sample is reviewed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
import sys
from typing import Any

_SHA = re.compile(r"[0-9a-fA-F]{40}\Z")


class EvidenceError(ValueError):
    """Unverifiable, ambiguous, stale or inconsistent provider evidence."""


def _obj(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceError("expected JSON object")
    return value


def _str(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceError("expected nonempty string")
    return value


def _edges(value: Any) -> list[dict[str, Any]]:
    edges = _obj(value).get("edges")
    if not isinstance(edges, list):
        raise EvidenceError("GraphQL edges missing")
    return [_obj(_obj(item).get("node")) for item in edges]


def _time(value: Any) -> datetime:
    try:
        stamp = datetime.fromisoformat(_str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceError("invalid timestamp") from exc
    if stamp.tzinfo is None:
        raise EvidenceError("timezone missing")
    return stamp


def backup_request(payload: Any, expected_name: str) -> str:
    record = _obj(payload)
    if isinstance(record.get("backup"), dict):
        record = _obj(record["backup"])
    if record.get("name") != expected_name:
        raise EvidenceError("backup name mismatch")
    return _str(record.get("id"))


def backup_receipt(payload: Any, backup_id: str, expected_name: str) -> str:
    rows = payload if isinstance(payload, list) else _obj(payload).get("backups")
    if not isinstance(rows, list):
        raise EvidenceError("unknown backup listing schema")
    records = [_obj(item) for item in rows if isinstance(item, dict) and item.get("id") == backup_id]
    if len(records) != 1:
        raise EvidenceError("backup receipt absent or ambiguous")
    record = records[0]
    if record.get("name") != expected_name or record.get("status") != "COMPLETED":
        raise EvidenceError("backup not completed")
    if _time(record.get("completedAt")) > datetime.now(timezone.utc):
        raise EvidenceError("backup completion in future")
    if _time(record.get("expiresAt")) <= datetime.now(timezone.utc):
        raise EvidenceError("backup expired or retention unproven")
    return backup_id


def deployment(payload: Any, *, expected_sha: str | None, previous: str | None) -> str:
    if not isinstance(payload, list) or not payload:
        raise EvidenceError("deployment list missing")
    row = _obj(payload[0])
    deployment_id = _str(row.get("id"))
    if previous is not None and deployment_id == previous:
        raise EvidenceError("new deployment not observed")
    if row.get("status") != "SUCCESS":
        raise EvidenceError("newest deployment not successful")
    meta = _obj(row.get("meta"))
    revision = _str(meta.get("commitHash"))
    if not _SHA.fullmatch(revision):
        raise EvidenceError("provider revision invalid")
    if expected_sha is not None and revision.lower() != expected_sha.lower():
        raise EvidenceError("provider revision mismatch")
    return deployment_id


def runtime(
    payload: Any, *,
    project: str, environment: str, service: str, deployment_id: str,
) -> str:
    status = _obj(payload)
    if status.get("id") != project:
        raise EvidenceError("project mismatch")
    matches = [env for env in _edges(status.get("environments")) if env.get("id") == environment]
    if len(matches) != 1:
        raise EvidenceError("environment missing or ambiguous")
    services = [item for item in _edges(matches[0].get("serviceInstances"))
                if item.get("serviceId") == service or item.get("serviceName") == service]
    if len(services) != 1:
        raise EvidenceError("service missing or ambiguous")
    record = services[0]
    latest = _obj(record.get("latestDeployment"))
    if latest.get("id") != deployment_id or latest.get("status") != "SUCCESS":
        raise EvidenceError("latest deployment mismatch")
    active = record.get("activeDeployments")
    if not isinstance(active, list):
        raise EvidenceError("active deployments unavailable")
    serving = [_obj(x) for x in active if isinstance(x, dict) and x.get("id") == deployment_id]
    if len(serving) != 1:
        raise EvidenceError("new deployment not serving")
    live = serving[0]
    if live.get("status") != "SUCCESS" or live.get("deploymentStopped") is not False:
        raise EvidenceError("deployment is stopped")
    instances = live.get("instances")
    if not isinstance(instances, list) or not instances:
        raise EvidenceError("no replica observed")
    if not all(_obj(x).get("status") == "RUNNING" for x in instances):
        raise EvidenceError("replicas not all running")
    return deployment_id


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="check", required=True)
    item = sub.add_parser("backup-request")
    item.add_argument("name")
    item = sub.add_parser("backup-receipt")
    item.add_argument("id")
    item.add_argument("name")
    item = sub.add_parser("deployment")
    item.add_argument("revision")
    item.add_argument("previous")
    sub.add_parser("baseline")
    sub.add_parser("latest-id")
    item = sub.add_parser("runtime")
    for key in ("project", "environment", "service", "deployment_id"):
        item.add_argument(key)
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
        if args.check == "backup-request":
            proof = backup_request(payload, args.name)
        elif args.check == "backup-receipt":
            proof = backup_receipt(payload, args.id, args.name)
        elif args.check == "deployment":
            if not _SHA.fullmatch(args.revision):
                raise EvidenceError("invalid expected SHA")
            proof = deployment(payload, expected_sha=args.revision, previous=args.previous)
        elif args.check == "baseline":
            deployment_id = deployment(payload, expected_sha=None, previous=None)
            proof = deployment_id + "\\t" + _obj(payload[0]["meta"])["commitHash"]
        elif args.check == "latest-id":
            if not isinstance(payload, list) or not payload:
                raise EvidenceError("latest deployment unavailable")
            proof = _str(_obj(payload[0]).get("id"))
        else:
            proof = runtime(payload, project=args.project, environment=args.environment,
                            service=args.service, deployment_id=args.deployment_id)
    except (ValueError, TypeError, KeyError):
        # Never echo the provider payload, raw exception or credential.
        print("railway evidence: BLOCKED unverified provider receipt")
        return 1
    print(proof)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
