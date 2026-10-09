#!/usr/bin/env sh
set -eu

: "${DATABASE_URL:?DATABASE_URL must be set through an approved secret/config channel}"
BACKUP_PATH="${1:-nfcore-postgres.dump}"
CHECKSUM_PATH="${BACKUP_PATH}.sha256"

if [ ! -f "$BACKUP_PATH" ] || [ ! -f "$CHECKSUM_PATH" ]; then
  echo "backup or checksum file missing" >&2
  exit 2
fi

sha256sum --check "$CHECKSUM_PATH"
pg_restore --dbname="$DATABASE_URL" --no-owner --no-acl --exit-on-error "$BACKUP_PATH"
printf 'restore_completed=%s\n' "$BACKUP_PATH"
