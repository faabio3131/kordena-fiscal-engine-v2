"""Railway GraphQL helper for governed staging deployment recovery.

This script intentionally implements only the small provider operation needed by the
NFCore staging driver. Authentication material is read from the environment and is
never printed.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_DEFAULT_ENDPOINT = "https://backboard.railway.com/graphql/v2"
_ROLLBACK_MUTATION = """
mutation deploymentRollback($id: String!) {
  deploymentRollback(id: $id) {
    id
    status
  }
}
"""


class RailwayGraphQLError(RuntimeError):
    """Raised when Railway GraphQL recovery cannot be proven."""


def _endpoint() -> str:
    value = os.environ.get("NFCORE_RAILWAY_GRAPHQL_ENDPOINT", "").strip()
    return value or _DEFAULT_ENDPOINT


def _token() -> str:
    token = os.environ.get("RAILWAY_API_TOKEN", "").strip()
    if not token:
        raise RailwayGraphQLError("RAILWAY_API_TOKEN is required")
    return token


def _request(query: str, variables: dict[str, str]) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = Request(
        _endpoint(),
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {_token()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read()
    except HTTPError as exc:
        raise RailwayGraphQLError(
            f"Railway GraphQL HTTP failure status={exc.code}"
        ) from None
    except URLError:
        raise RailwayGraphQLError("Railway GraphQL network failure") from None

    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RailwayGraphQLError("Railway GraphQL returned an invalid response") from None
    if not isinstance(decoded, dict):
        raise RailwayGraphQLError("Railway GraphQL returned an invalid response")
    if decoded.get("errors"):
        raise RailwayGraphQLError("Railway GraphQL mutation failed")
    data = decoded.get("data")
    if not isinstance(data, dict):
        raise RailwayGraphQLError("Railway GraphQL response is missing data")
    return data


def rollback_deployment(deployment_id: str) -> tuple[str, str]:
    normalized = deployment_id.strip()
    if not normalized:
        raise RailwayGraphQLError("deployment id is required")
    data = _request(_ROLLBACK_MUTATION, {"id": normalized})
    result = data.get("deploymentRollback")
    if not isinstance(result, dict):
        raise RailwayGraphQLError("Railway rollback response is missing deployment")
    rollback_id = str(result.get("id", "")).strip()
    status = str(result.get("status", "")).strip()
    if not rollback_id or not status:
        raise RailwayGraphQLError("Railway rollback response is incomplete")
    return rollback_id, status


def main() -> int:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    rollback = subcommands.add_parser("rollback")
    rollback.add_argument("deployment_id")
    args = parser.parse_args()

    try:
        rollback_id, status = rollback_deployment(args.deployment_id)
    except RailwayGraphQLError as exc:
        print(f"railway graphql: FAIL {exc}")
        return 1

    print(
        "railway graphql: ROLLBACK_REQUESTED "
        f"deployment={rollback_id} status={status}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
