#!/bin/sh
set -eu

command="\${1:-}"

blocked() {
  echo "railway staging driver: BLOCKED_EXTERNAL $1"
  exit 42
}

fail() {
  echo "railway staging driver: FAIL $1"
  exit 1
}

require_value() {
  name="$1"
  eval "value=\\\${$name:-}"
  [ -n "$value" ] || blocked "missing=$name"
}

require_revision() {
  revision="\${1:-}"
  case "$revision" in
    [0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]) ;;
    *) fail "immutable 40-hex revision is required" ;;
  esac
}

preflight_checks() {
  require_value NFCORE_RAILWAY_PROJECT_ID
  require_value NFCORE_RAILWAY_ENVIRONMENT_ID
  require_value NFCORE_RAILWAY_API_SERVICE
  require_value NFCORE_RAILWAY_WORKER_SERVICE
  require_value NFCORE_RAILWAY_PORTAL_SERVICE
  require_value NFCORE_RAILWAY_POSTGRES_SERVICE

  if [ "\${NFCORE_RAILWAY_REAL_EXECUTION_ENABLED:-false}" != "true" ]; then
    blocked "real execution is disabled while the repository remains public"
  fi

  require_value RAILWAY_API_TOKEN
  command -v railway >/dev/null 2>&1 || blocked "railway CLI is not installed"

  railway link \
    --project "$NFCORE_RAILWAY_PROJECT_ID" \
    --environment "$NFCORE_RAILWAY_ENVIRONMENT_ID" \
    --json >/dev/null 2>&1 || fail "unable to select Railway project/environment"
}

latest_status() {
  service="$1"
  railway deployment list \
    --service "$service" \
    --environment "$NFCORE_RAILWAY_ENVIRONMENT_ID" \
    --limit 1 --json 2>/dev/null |
    python -c 'import json,sys
rows=json.load(sys.stdin)
row=rows[0] if isinstance(rows,list) and rows else {}
print(str(row.get("status","")))' 2>/dev/null || true
}

wait_for_success() {
  service="$1"
  attempts="\${NFCORE_RAILWAY_WAIT_ATTEMPTS:-60}"
  delay="\${NFCORE_RAILWAY_WAIT_SECONDS:-5}"
  count=0

  while [ "$count" -lt "$attempts" ]; do
    status="$(latest_status "$service")"
    case "$status" in
      SUCCESS)
        echo "railway staging driver: SERVICE_READY service=$service"
        return 0
        ;;
      FAILED|CRASHED|REMOVED|REMOVING)
        fail "service=$service status=$status"
        ;;
      *)
        count=$((count + 1))
        if [ "$count" -lt "$attempts" ] && [ "$delay" -gt 0 ] 2>/dev/null; then
          sleep "$delay"
        fi
        ;;
    esac
  done

  fail "service=$service status=timeout"
}

assert_local_revision() {
  revision="$1"
  command -v git >/dev/null 2>&1 || fail "git is required for immutable deploy verification"
  actual="$(git rev-parse HEAD 2>/dev/null || true)"
  [ "$actual" = "$revision" ] || fail "checkout revision mismatch"
}

deploy_service() {
  service="$1"
  railway up --ci \
    --project "$NFCORE_RAILWAY_PROJECT_ID" \
    --environment "$NFCORE_RAILWAY_ENVIRONMENT_ID" \
    --service "$service"
  wait_for_success "$service"
}

case "$command" in
  contract)
    echo "nfcore-staging-driver-v1"
    ;;
  provider)
    echo "railway"
    ;;
  preflight)
    preflight_checks
    echo "railway staging driver: PREFLIGHT_READY"
    ;;
  backup)
    revision="\${2:-}"
    require_revision "$revision"
    preflight_checks
    short_revision="$(printf '%s' "$revision" | cut -c1-12)"
    railway postgres pitr backup create \
      --project "$NFCORE_RAILWAY_PROJECT_ID" \
      --environment "$NFCORE_RAILWAY_ENVIRONMENT_ID" \
      --service "$NFCORE_RAILWAY_POSTGRES_SERVICE" \
      --name "nfcore-pre-$short_revision" \
      --json >/dev/null
    echo "railway staging driver: BACKUP_REQUESTED revision=$revision"
    ;;
  deploy)
    revision="\${2:-}"
    require_revision "$revision"
    preflight_checks
    assert_local_revision "$revision"
    deploy_service "$NFCORE_RAILWAY_API_SERVICE"
    deploy_service "$NFCORE_RAILWAY_WORKER_SERVICE"
    deploy_service "$NFCORE_RAILWAY_PORTAL_SERVICE"
    echo "railway staging driver: DEPLOY_READY revision=$revision"
    ;;
  verify-worker)
    revision="\${2:-}"
    require_revision "$revision"
    preflight_checks
    wait_for_success "$NFCORE_RAILWAY_WORKER_SERVICE"
    echo "railway staging driver: WORKER_READY revision=$revision"
    ;;
  rollback)
    revision="\${2:-}"
    require_revision "$revision"
    blocked "exact Railway rollback remains pending external baseline certification"
    ;;
  *)
    echo "railway staging driver: FAIL unsupported command"
    exit 1
    ;;
esac
