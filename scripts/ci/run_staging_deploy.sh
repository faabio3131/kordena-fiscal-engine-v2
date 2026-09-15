#!/bin/sh
set -eu

sh scripts/ci/staging_preflight.sh

export NFCORE_SCHEMA_MIGRATION_APPROVED=true
python scripts/ci/migration_guard.py --apply

# The provider-specific driver is deliberately outside the Core contract.
# Required interface: deploy <immutable revision> and rollback <failed revision>.
revision="${NFCORE_DEPLOY_REVISION:-${GITHUB_SHA:-}}"
if [ -z "$revision" ]; then
  echo "staging deploy: FAIL immutable revision is required"
  exit 1
fi

sh "$NFCORE_STAGING_DEPLOY_DRIVER" deploy "$revision"
if ! sh scripts/ci/staging_smoke.sh "$NFCORE_STAGING_BASE_URL"; then
  echo "staging deploy: post-deploy smoke failed; invoking provider rollback"
  sh "$NFCORE_STAGING_DEPLOY_DRIVER" rollback "$revision"
  exit 1
fi

echo "staging deploy: PASS revision=$revision"
