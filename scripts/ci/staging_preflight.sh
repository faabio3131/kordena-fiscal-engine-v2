#!/bin/sh
set -eu

require_value() {
  name="$1"
  eval "value=\${$name:-}"
  if [ -z "$value" ]; then
    echo "staging preflight: BLOCKED_EXTERNAL missing=$name"
    exit 42
  fi
}

require_value NFCORE_STAGING_BASE_URL
require_value NFCORE_STAGING_PORTAL_URL
require_value NFCORE_STAGING_DEPLOY_DRIVER
require_value DATABASE_URL

for url in "$NFCORE_STAGING_BASE_URL" "$NFCORE_STAGING_PORTAL_URL"; do
  case "$url" in
    https://*) ;;
    *)
      echo "staging preflight: FAIL public staging URLs must use HTTPS"
      exit 1
      ;;
  esac
done

case "$NFCORE_STAGING_DEPLOY_DRIVER" in
  scripts/deploy/drivers/*.sh) ;;
  *)
    echo "staging preflight: FAIL deploy driver must live under scripts/deploy/drivers"
    exit 1
    ;;
esac

if [ ! -f "$NFCORE_STAGING_DEPLOY_DRIVER" ]; then
  echo "staging preflight: BLOCKED_EXTERNAL deploy driver is not provisioned"
  exit 42
fi

contract="$(sh "$NFCORE_STAGING_DEPLOY_DRIVER" contract 2>/dev/null || true)"
[ "$contract" = "nfcore-staging-driver-v1" ] || {
  echo "staging preflight: FAIL incompatible deploy driver contract"
  exit 1
}

[ "${NFCORE_ENVIRONMENT:-}" = "staging" ] || {
  echo "staging preflight: FAIL NFCORE_ENVIRONMENT must be staging"
  exit 1
}
[ "${NFCORE_PERSISTENCE_BACKEND:-}" = "postgres" ] || {
  echo "staging preflight: FAIL PostgreSQL is mandatory"
  exit 1
}
[ "${NFCORE_SECRET_BACKEND:-}" = "external" ] || {
  echo "staging preflight: FAIL external secret backend is mandatory"
  exit 1
}
[ "${NFCORE_REQUIRE_HTTPS:-}" = "true" ] || {
  echo "staging preflight: FAIL HTTPS policy is mandatory"
  exit 1
}

echo "staging preflight: PASS"
