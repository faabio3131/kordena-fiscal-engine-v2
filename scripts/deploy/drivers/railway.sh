#!/bin/sh
set -eu

command="${1:-}"

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
  eval "value=\${$name:-}"
  [ -n "$value" ] || blocked "missing=$name"
}

require_revision() {
  revision="${1:-}"
  [ "${#revision}" -eq 40 ] || fail "immutable 40-hex revision is required"
  case "$revision" in
    *[!0-9a-fA-F]*) fail "immutable 40-hex revision is required" ;;
    *) ;;
  esac
}

preflight_checks() {
  require_value NFCORE_RAILWAY_PROJECT_ID
  require_value NFCORE_RAILWAY_ENVIRONMENT_ID
  require_value NFCORE_RAILWAY_API_SERVICE
  require_value NFCORE_RAILWAY_WORKER_SERVICE
  require_value NFCORE_RAILWAY_PORTAL_SERVICE
  require_value NFCORE_RAILWAY_POSTGRES_SERVICE

  if [ "${NFCORE_RAILWAY_REAL_EXECUTION_ENABLED:-false}" != "true" ]; then
    blocked "real execution is disabled by the governance flag"
  fi

  require_value RAILWAY_API_TOKEN
  command -v railway >/dev/null 2>&1 || blocked "railway CLI is not installed"

  railway link \
    --project "$NFCORE_RAILWAY_PROJECT_ID" \
    --environment "$NFCORE_RAILWAY_ENVIRONMENT_ID" \
    --json >/dev/null 2>&1 || fail "unable to select Railway project/environment"
}

evidence() {
  helper="scripts/deploy/railway_evidence.py"
  [ -f "$helper" ] || fail "Railway evidence verifier is missing"
  python "$helper" "$@"
}

deployment_list() {
  railway deployment list \
    --service "$1" \
    --environment "$NFCORE_RAILWAY_ENVIRONMENT_ID" \
    --limit 1 --json
}

runtime_status() {
  railway status \
    --project "$NFCORE_RAILWAY_PROJECT_ID" \
    --environment "$NFCORE_RAILWAY_ENVIRONMENT_ID" --json
}

require_running() {
  service="$1"
  deployment_id="$2"
  observed="$(runtime_status)" || fail "provider runtime status unavailable"
  printf '%s' "$observed" | evidence runtime \
    "$NFCORE_RAILWAY_PROJECT_ID" "$NFCORE_RAILWAY_ENVIRONMENT_ID" \
    "$service" "$deployment_id" >/dev/null ||
    fail "service=$service running replica/current deployment unverified"
}

latest_baseline() {
  observed="$(deployment_list "$1")" || fail "provider deployment listing unavailable"
  printf '%s' "$observed" | evidence baseline ||
    fail "service=$1 immutable baseline unavailable"
}

latest_deployment_identity() {
  observed="$(deployment_list "$1")" || fail "provider deployment listing unavailable"
  printf '%s' "$observed" | evidence latest-id ||
    fail "service=$1 latest deployment identity unavailable"
}

rollback_baseline_file() {
  printf '%s' "${NFCORE_RAILWAY_ROLLBACK_BASELINE_FILE:-.artifacts/railway-rollback-baseline.tsv}"
}

capture_rollback_baseline() {
  file="$(rollback_baseline_file)"
  directory="$(dirname "$file")"
  mkdir -p "$directory"
  # Capture only a proven healthy pre-migration baseline. Worker 0/1 blocks.
  temp_file="$file.pending"
  : > "$temp_file"

  for service in \
    "$NFCORE_RAILWAY_API_SERVICE" \
    "$NFCORE_RAILWAY_WORKER_SERVICE" \
    "$NFCORE_RAILWAY_PORTAL_SERVICE"
  do
    baseline="$(latest_baseline "$service")"
    deployment_id="$(printf '%s' "$baseline" | cut -f1)"
    baseline_revision="$(printf '%s' "$baseline" | cut -f2)"
    [ -n "$deployment_id" ] && [ "${#baseline_revision}" -eq 40 ] ||
      fail "service=$service baseline incomplete"
    require_running "$service" "$deployment_id"
    printf '%s\t%s\t%s\n' "$service" "$deployment_id" "$baseline_revision" >> "$temp_file"
  done
  mv "$temp_file" "$file"
  echo "railway staging driver: ROLLBACK_BASELINE_CAPTURED"
}

baseline_deployment_for_service() {
  service="$1"
  file="$(rollback_baseline_file)"
  [ -f "$file" ] || fail "rollback baseline file is missing"
  awk -F '\t' -v service="$service" '$1 == service { print $2; exit }' "$file"
}

baseline_revision_for_service() {
  service="$1"
  file="$(rollback_baseline_file)"
  [ -f "$file" ] || fail "rollback baseline file is missing"
  awk -F '\t' -v service="$service" '$1 == service { print $3; exit }' "$file"
}

request_rollback() {
  deployment_id="$1"
  helper="${NFCORE_RAILWAY_GRAPHQL_HELPER:-scripts/deploy/railway_graphql.py}"
  [ -f "$helper" ] || fail "Railway GraphQL rollback helper is missing"
  python "$helper" rollback "$deployment_id" ||
    fail "Railway rollback request failed"
}

wait_for_success() {
  service="$1"
  revision="$2"
  previous_id="$3"
  attempts="${NFCORE_RAILWAY_WAIT_ATTEMPTS:-60}"
  delay="${NFCORE_RAILWAY_WAIT_SECONDS:-5}"
  count=0

  while [ "$count" -lt "$attempts" ]; do
    observed="$(deployment_list "$service")" ||
      fail "service=$service deployment listing unavailable"
    deployment_id="$(printf '%s' "$observed" |
      evidence deployment "$revision" "$previous_id" 2>/dev/null)" || deployment_id=""
    if [ -n "$deployment_id" ]; then
      live="$(runtime_status)" ||
        fail "service=$service runtime status unavailable"
      if printf '%s' "$live" | evidence runtime \
        "$NFCORE_RAILWAY_PROJECT_ID" "$NFCORE_RAILWAY_ENVIRONMENT_ID" \
        "$service" "$deployment_id" >/dev/null 2>&1; then
        echo "railway staging driver: SERVICE_READY service=$service revision=$revision"
        return 0
      fi
    fi
    count=$((count + 1))
    if [ "$count" -lt "$attempts" ] && [ "$delay" -gt 0 ] 2>/dev/null; then
      sleep "$delay"
    fi
  done
  fail "service=$service immutable revision or running replicas unverified"
}

assert_local_revision() {
  revision="$1"
  command -v git >/dev/null 2>&1 || fail "git is required for immutable deploy verification"
  actual="$(git rev-parse HEAD 2>/dev/null || true)"
  [ "$actual" = "$revision" ] || fail "checkout revision mismatch"
}

deploy_service() {
  service="$1"
  revision="$2"
  # The captured baseline is immutable, not re-read from potentially partial deploys.
  previous_id="$(baseline_deployment_for_service "$service")"
  [ -n "$previous_id" ] || fail "service=$service baseline missing"
  railway up --ci \
    --project "$NFCORE_RAILWAY_PROJECT_ID" \
    --environment "$NFCORE_RAILWAY_ENVIRONMENT_ID" \
    --service "$service"
  wait_for_success "$service" "$revision" "$previous_id"
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
    revision="${2:-}"
    require_revision "$revision"
    preflight_checks
    short_revision="$(printf '%s' "$revision" | cut -c1-12)"
    backup_name="nfcore-pre-$short_revision-$(date -u +%Y%m%d%H%M%S)"
    request="$(railway postgres pitr backup create \
      --project "$NFCORE_RAILWAY_PROJECT_ID" \
      --environment "$NFCORE_RAILWAY_ENVIRONMENT_ID" \
      --service "$NFCORE_RAILWAY_POSTGRES_SERVICE" \
      --name "$backup_name" --json)" || fail "backup request failed"
    backup_id="$(printf '%s' "$request" | evidence backup-request "$backup_name")" ||
      fail "backup request id not proven"
    count=0
    attempts="${NFCORE_RAILWAY_BACKUP_WAIT_ATTEMPTS:-60}"
    delay="${NFCORE_RAILWAY_BACKUP_WAIT_SECONDS:-5}"
    while [ "$count" -lt "$attempts" ]; do
      listing="$(railway postgres pitr backup list \
        --project "$NFCORE_RAILWAY_PROJECT_ID" \
        --environment "$NFCORE_RAILWAY_ENVIRONMENT_ID" \
        --service "$NFCORE_RAILWAY_POSTGRES_SERVICE" --json)" ||
        fail "backup listing unavailable"
      if printf '%s' "$listing" |
        evidence backup-receipt "$backup_id" "$backup_name" >/dev/null 2>&1; then
        echo "railway staging driver: BACKUP_COMPLETED revision=$revision"
        exit 0
      fi
      count=$((count + 1))
      if [ "$count" -lt "$attempts" ] && [ "$delay" -gt 0 ] 2>/dev/null; then
        sleep "$delay"
      fi
    done
    fail "backup completion/retention unverified"
    ;;
  prepare-rollback)
    revision="${2:-}"
    require_revision "$revision"
    preflight_checks
    assert_local_revision "$revision"
    capture_rollback_baseline
    ;;
  deploy)
    revision="${2:-}"
    require_revision "$revision"
    preflight_checks
    assert_local_revision "$revision"
    # Never replace the pre-migration baseline during a retry or partial deploy.
    [ -f "$(rollback_baseline_file)" ] || fail "rollback baseline file is missing"
    for service in \
      "$NFCORE_RAILWAY_API_SERVICE" \
      "$NFCORE_RAILWAY_WORKER_SERVICE" \
      "$NFCORE_RAILWAY_PORTAL_SERVICE"
    do
      deployment_id="$(baseline_deployment_for_service "$service")"
      [ -n "$deployment_id" ] || fail "service=$service rollback baseline is missing"
    done
    deploy_service "$NFCORE_RAILWAY_API_SERVICE" "$revision"
    deploy_service "$NFCORE_RAILWAY_WORKER_SERVICE" "$revision"
    deploy_service "$NFCORE_RAILWAY_PORTAL_SERVICE" "$revision"
    echo "railway staging driver: DEPLOY_READY revision=$revision"
    ;;
  verify-worker)
    revision="${2:-}"
    require_revision "$revision"
    preflight_checks
    previous_id="$(baseline_deployment_for_service "$NFCORE_RAILWAY_WORKER_SERVICE")"
    [ -n "$previous_id" ] || fail "worker baseline missing"
    wait_for_success "$NFCORE_RAILWAY_WORKER_SERVICE" "$revision" "$previous_id"
    echo "railway staging driver: WORKER_READY revision=$revision"
    ;;
  rollback)
    revision="${2:-}"
    require_revision "$revision"
    preflight_checks
    for service in \
      "$NFCORE_RAILWAY_API_SERVICE" \
      "$NFCORE_RAILWAY_WORKER_SERVICE" \
      "$NFCORE_RAILWAY_PORTAL_SERVICE"
    do
      deployment_id="$(baseline_deployment_for_service "$service")"
      [ -n "$deployment_id" ] || fail "service=$service rollback baseline is missing"
      previous_id="$(latest_deployment_identity "$service")"
      restored_revision="$(baseline_revision_for_service "$service")"
      [ -n "$restored_revision" ] || fail "service=$service baseline revision missing"
      request_rollback "$deployment_id"
      wait_for_success "$service" "$restored_revision" "$previous_id"
    done
    echo "railway staging driver: ROLLBACK_READY failed_revision=$revision"
    ;;
  *)
    echo "railway staging driver: FAIL unsupported command"
    exit 1
    ;;
esac
