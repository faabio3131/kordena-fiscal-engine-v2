#!/bin/sh
set -eu

sh scripts/ci/staging_preflight.sh

export NFCORE_SCHEMA_MIGRATION_APPROVED=true
python scripts/ci/migration_guard.py --apply

# The provider-specific driver is deliberately outside the Core contract.
# It must accept: deploy <immutable revision>.
revision="${NFCORE_DEPLOY_REVISION:-${GITHUB_SHA:-}}"
if [ -z "$revision" ]; then
  echo "staging deploy: FAIL immutable revision is required"
  exit 1
fi

sh "$NFCORE_STAGING_DEPLOY_DRIVER" deploy "$revision"
sh scripts/ci/staging_smoke.sh "$NFCORE_STAGING_BASE_URL"

echo "staging deploy: PASS revision=$revision"
