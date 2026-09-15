#!/bin/sh
set -eu

base_url="${1:-${NFCORE_STAGING_BASE_URL:-}}"
case "$base_url" in
  https://*) ;;
  *)
    echo "staging smoke: FAIL HTTPS base URL required"
    exit 1
    ;;
esac

base_url="${base_url%/}"
curl --fail --silent --show-error --max-time 20 "$base_url/health/live" >/dev/null
curl --fail --silent --show-error --max-time 20 "$base_url/health/ready" >/dev/null

echo "staging smoke: PASS"
