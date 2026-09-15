#!/usr/bin/env sh
set -eu

: "${DATABASE_URL:?DATABASE_URL must be set through an approved secret/config channel}"
BACKUP_PATH="${1:-nfcore-postgres.dump}"
CHECKSUM_PATH="${BACKUP_PATH}.sha256"

umask 077
pg_dump "$DATABASE_URL" --format=custom --no-owner --no-acl --file="$BACKUP_PATH"
sha256sum "$BACKUP_PATH" > "$CHECKSUM_PATH"
printf 'backup_created=%s\nchecksum=%s\n' "$BACKUP_PATH" "$CHECKSUM_PATH"
