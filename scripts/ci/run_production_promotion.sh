#!/bin/sh
set -eu

sh scripts/ci/production_preflight.sh

export NFCORE_SCHEMA_MIGRATION_APPROVED=true
python scripts/ci/migration_guard.py --apply

revision="$NFCORE_DEPLOY_REVISION"
sh "$NFCORE_PRODUCTION_DEPLOY_DRIVER" deploy "$revision"
if ! sh scripts/ci/production_smoke.sh "$NFCORE_PRODUCTION_BASE_URL"; then
  echo "production promotion: post-deploy smoke failed; invoking provider rollback"
  sh "$NFCORE_PRODUCTION_DEPLOY_DRIVER" rollback "$revision"
  exit 1
fi

echo "production promotion: PASS revision=$revision"
