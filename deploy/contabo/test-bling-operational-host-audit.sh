#!/usr/bin/env bash
# Tests sintéticos: nenhum container ou host real e nenhuma mutacao.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
sha=61015a837be8b2e5e3b0f1cdb5fb14c5c875fb91
if bash "$here/bling-operational-host-audit.sh" wrong > "$tmp/invalid" 2>&1; then
  echo 'FAIL: invalid SHA accepted'; exit 1
fi
grep -Fq SHA_COMPLETO "$tmp/invalid"
if NFCORE_ROOT="$tmp/missing" NFCORE_BACKUP_DIR="$tmp/missing" \
  bash "$here/bling-operational-host-audit.sh" "$sha" > "$tmp/missing.out" 2>&1; then
  echo 'FAIL: missing host accepted'; exit 1
fi
grep -Fxq 'DEPLOY_SHA_EXACT=BLOCKED' "$tmp/missing.out"
grep -Fq 'RESULT=NO_GO_' "$tmp/missing.out"

mkdir -p "$tmp/root" "$tmp/backups" "$tmp/bin"
printf 'SHA=%s\n' "$sha" > "$tmp/root/.deployed"
printf '== DEPLOY OK %s\n' "${sha:0:7}" > "$tmp/root/deploy.log"
printf 'synthetic backup\n' > "$tmp/backups/nfcore-test.dump"
(cd "$tmp/backups" && sha256sum nfcore-test.dump > nfcore-test.dump.sha256)
cat > "$tmp/bin/docker" <<'DOCKER'
#!/usr/bin/env bash
set -euo pipefail
case "$1" in
inspect)
  if [[ "$3" == *".Mounts"* ]]; then
    if [[ "${MOCK_POLICY_RW:-0}" == 1 ]]; then echo RW; else echo RO; fi
    exit 0
  fi
  if [[ "${MOCK_WORKER:-1}" == 0 && "$4" == nfcore-bling-worker ]]; then exit 1; fi
  if [[ "$3" == *Health* ]]; then echo healthy; else echo running; fi
  ;;
exec)
  if [[ "$3" == psql ]]; then
    if [[ "${MOCK_SCHEMA:-21}" == 21 ]]; then seq -s, 1 21; else seq -s, 1 19; fi
  elif [[ "$3" == python && "$4" == -c && "$5" == *NFCORE_BLING_FISCAL_POLICY_ROOT* ]]; then
    echo "${MOCK_POLICY_STATE:-READY}"
  elif [[ "$3" == python && "$4" == -c && "$5" == *NFCORE_BLING_INSTALLATIONS_ENABLED* ]]; then
    if [[ "${MOCK_BLING:-1}" == 1 ]]; then echo ENABLED; else echo DISABLED; fi
  elif [[ "$3" == python && "$4" == -c && "$5" == *NFCORE_BLING_CLIENT_ID* ]]; then
    if [[ "${MOCK_BLING:-1}" == 1 ]]; then echo READY; else echo UNAVAILABLE; fi
  fi
  ;;
*) exit 1;;
esac
DOCKER
chmod +x "$tmp/bin/docker"
NFCORE_ROOT="$tmp/root" NFCORE_BACKUP_DIR="$tmp/backups" PATH="$tmp/bin:$PATH" \
  bash "$here/bling-operational-host-audit.sh" "$sha" > "$tmp/ready.out"
for assertion in 'DEPLOY_SHA_EXACT=PASS' 'RECENT_BACKUP_INTEGRITY=PASS' \
  'BLING_SCHEMA_20_21=PASS' 'BLING_API_FLAG=PASS' 'BLING_SECRET_MOUNTS=PASS' \
  'BLING_POLICY_MOUNT=PASS' 'BLING_POLICY_ARTIFACTS=PASS' \
  'BLING_WORKER_HEALTH=PASS' 'RESULT=HOST_GATES_PASS_EXTERNAL_STILL_UNVERIFIED'; do
  grep -Fxq "$assertion" "$tmp/ready.out"
done
if NFCORE_ROOT="$tmp/root" NFCORE_BACKUP_DIR="$tmp/backups" PATH="$tmp/bin:$PATH" \
  MOCK_BLING=0 MOCK_SCHEMA=19 MOCK_WORKER=0 \
  bash "$here/bling-operational-host-audit.sh" "$sha" > "$tmp/off.out"; then
  echo 'FAIL: inactive Bling accepted'; exit 1
fi
for assertion in 'BLING_SCHEMA_20_21=PENDING' 'BLING_API_FLAG=PENDING' \
  'BLING_WORKER_RUNNING=PENDING' 'RESULT=CODE_READY_BUT_BLING_NOT_ACTIVE'; do
  grep -Fxq "$assertion" "$tmp/off.out"
done
# Scoped fiscal policies must be mounted read-only and valid, not just OAuth-ready.
if NFCORE_ROOT="$tmp/root" NFCORE_BACKUP_DIR="$tmp/backups" PATH="$tmp/bin:$PATH" \
  MOCK_POLICY_STATE=EMPTY \
  bash "$here/bling-operational-host-audit.sh" "$sha" > "$tmp/policy-empty.out"; then
  echo 'FAIL: empty scoped policy directory accepted'; exit 1
fi
grep -Fxq 'BLING_POLICY_ARTIFACTS=PENDING' "$tmp/policy-empty.out"
grep -Fxq 'RESULT=CODE_READY_BUT_BLING_NOT_ACTIVE' "$tmp/policy-empty.out"
if NFCORE_ROOT="$tmp/root" NFCORE_BACKUP_DIR="$tmp/backups" PATH="$tmp/bin:$PATH" \
  MOCK_POLICY_RW=1 \
  bash "$here/bling-operational-host-audit.sh" "$sha" > "$tmp/policy-rw.out"; then
  echo 'FAIL: writable scoped fiscal-policy mount accepted'; exit 1
fi
grep -Fxq 'BLING_POLICY_MOUNT=BLOCKED' "$tmp/policy-rw.out"
grep -Fxq 'RESULT=NO_GO_HOST_GATES' "$tmp/policy-rw.out"
if NFCORE_ROOT="$tmp/root" NFCORE_BACKUP_DIR="$tmp/backups" PATH="$tmp/bin:$PATH" \
  MOCK_POLICY_STATE=INVALID \
  bash "$here/bling-operational-host-audit.sh" "$sha" > "$tmp/policy-invalid.out"; then
  echo 'FAIL: invalid scoped fiscal-policy artifact accepted'; exit 1
fi
grep -Fxq 'BLING_POLICY_ARTIFACTS=BLOCKED' "$tmp/policy-invalid.out"
grep -Fxq 'RESULT=NO_GO_HOST_GATES' "$tmp/policy-invalid.out"
echo 'PASS: Bling host audit is read-only and fails closed'
