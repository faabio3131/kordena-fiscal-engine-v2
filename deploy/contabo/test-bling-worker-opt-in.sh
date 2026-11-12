#!/usr/bin/env bash
# Bling Worker Compose acceptance: config-only; no host access, Docker start or real secrets.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp "$here/compose.prod.yml" "$here/compose.bling.worker.opt-in.yml" "$work/"
mkdir -p "$work/src" "$work/synthetic-credentials"
printf 'POSTGRES_PASSWORD=synthetic-ci-only\n' > "$work/.env"
printf 'NFCORE_BLING_CLIENT_ID=synthetic-ci-only\nNFCORE_BLING_APPROVED_SCOPES=synthetic\n' \
  > "$work/.env.bling.worker"
export POSTGRES_PASSWORD=synthetic-ci-only
export NFCORE_BLING_SECRETS_HOST_DIR="$work/synthetic-credentials"

base=(docker compose -f "$work/compose.prod.yml")
worker=(docker compose -f "$work/compose.prod.yml" -f "$work/compose.bling.worker.opt-in.yml")
if "${base[@]}" config --services | grep -Fxq nfcore-bling-worker; then
  echo 'FAIL: Bling worker included in routine production compose' >&2
  exit 1
fi
if "${worker[@]}" config --services | grep -Fxq nfcore-bling-worker; then
  echo 'FAIL: Bling worker starts without the authorized profile' >&2
  exit 1
fi
"${worker[@]}" --profile bling-worker-authorized config --format json > "$work/config.json"
python3 - "$work/config.json" <<'PY'
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
worker = config["services"]["nfcore-bling-worker"]
assert worker["profiles"] == ["bling-worker-authorized"]
assert worker["read_only"] is True
assert worker["user"] == "10001:10001"
assert worker["restart"] == "no"
assert worker["cap_drop"] == ["ALL"]
assert "no-new-privileges:true" in worker["security_opt"]
assert "ports" not in worker and "expose" not in worker
assert set(worker["networks"]) == {"internal"}
assert set(worker["depends_on"]) == {"nfcore-db"}
assert worker["environment"]["NFCORE_WORKER_CONNECTOR"] == "bling-multi"
assert worker["environment"]["NFCORE_BLING_INSTALLATIONS_ENABLED"] == "true"
assert worker["environment"]["NFCORE_ENVIRONMENT"] == "production"
assert worker["environment"]["NFCORE_PERSISTENCE_BACKEND"] == "postgres"
assert worker["environment"]["NFCORE_SECRET_BACKEND"] == "external"
assert worker["environment"]["NFCORE_BLING_CLIENT_ID"] == "synthetic-ci-only"
mounts = worker["volumes"]
assert len(mounts) == 1
mount = mounts[0]
assert mount["type"] == "bind" and mount["read_only"] is True
assert mount["target"] == "/run/nfcore/bling"
assert mount.get("bind", {}).get("create_host_path") is False
assert "nfcore-api" in config["services"] and "nfcore-db" in config["services"]
PY

rm "$work/.env.bling.worker"
if "${worker[@]}" --profile bling-worker-authorized config --quiet >/dev/null 2>&1; then
  echo 'FAIL: worker accepted missing env file' >&2
  exit 1
fi
printf 'NFCORE_BLING_CLIENT_ID=synthetic-ci-only\n' > "$work/.env.bling.worker"
if (unset NFCORE_BLING_SECRETS_HOST_DIR; \
    "${worker[@]}" --profile bling-worker-authorized config --quiet) >/dev/null 2>&1; then
  echo 'FAIL: worker accepted missing secrets mount' >&2
  exit 1
fi
echo 'PASS: Bling Worker opt-in isolated, read-only, no ingress and fail-closed'
