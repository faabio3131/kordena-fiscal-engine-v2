#!/bin/sh
set -eu

sh scripts/ci/staging_preflight.sh

revision="${NFCORE_DEPLOY_REVISION:-${GITHUB_SHA:-}}"
case "$revision" in
  [0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]) ;;
  *)
    echo "staging deploy: FAIL immutable 40-hex revision is required"
    exit 1
    ;;
esac

# Back up the provisioned staging database through the provider driver before any
# schema mutation. The driver owns external storage; no backup material enters Git.
sh "$NFCORE_STAGING_DEPLOY_DRIVER" backup "$revision"

export NFCORE_SCHEMA_MIGRATION_APPROVED=true
python scripts/ci/migration_guard.py --apply

# Provider-specific driver contract v1:
#   contract                       -> prints nfcore-staging-driver-v1
#   backup <revision>              -> durable pre-deploy backup
#   deploy <revision>              -> deploy API + worker + portal at immutable revision
#   verify-worker <revision>       -> verify the worker process is healthy/running
#   rollback <failed-revision>     -> restore the previous application revision
sh "$NFCORE_STAGING_DEPLOY_DRIVER" deploy "$revision"

if ! sh "$NFCORE_STAGING_DEPLOY_DRIVER" verify-worker "$revision"; then
  echo "staging deploy: worker verification failed; invoking provider rollback"
  sh "$NFCORE_STAGING_DEPLOY_DRIVER" rollback "$revision"
  exit 1
fi

if ! sh scripts/ci/staging_smoke.sh "$NFCORE_STAGING_BASE_URL" "$NFCORE_STAGING_PORTAL_URL"; then
  echo "staging deploy: post-deploy smoke failed; invoking provider rollback"
  sh "$NFCORE_STAGING_DEPLOY_DRIVER" rollback "$revision"
  exit 1
fi

echo "staging deploy: PASS revision=$revision"
