#!/bin/sh
set -eu

command="${1:-}"

blocked() {
  echo "railway staging driver: BLOCKED_EXTERNAL ${1}"
  exit 42
}

require_value() {
  name="$1"
  eval "value=\${$name:-}"
  [ -n "$value" ] || blocked "missing=$name"
}

case "$command" in
  contract)
    echo "nfcore-staging-driver-v1"
    ;;
  provider)
    echo "railway"
    ;;
  preflight)
    require_value NFCORE_RAILWAY_PROJECT_ID
    require_value NFCORE_RAILWAY_ENVIRONMENT_ID
    require_value NFCORE_RAILWAY_API_SERVICE
    require_value NFCORE_RAILWAY_WORKER_SERVICE
    require_value NFCORE_RAILWAY_PORTAL_SERVICE

    if [ "${NFCORE_RAILWAY_REAL_EXECUTION_ENABLED:-false}" != "true" ]; then
      blocked "real execution is disabled while the repository remains public"
    fi

    require_value RAILWAY_API_TOKEN
    command -v railway >/dev/null 2>&1 || blocked "railway CLI is not installed"

    echo "railway staging driver: PREFLIGHT_READY"
    ;;
  backup|deploy|verify-worker|rollback)
    blocked "CL-15A certifies provider readiness only; real staging execution remains disabled"
    ;;
  *)
    echo "railway staging driver: FAIL unsupported command"
    exit 1
    ;;
esac
