#!/usr/bin/env bash
# NFCore Bling: auditoria de host somente leitura. Nunca imprime .env ou segredos.
# Uso (no host): bash /opt/fm/nfcore/src/deploy/contabo/bling-operational-host-audit.sh SHA_COMPLETO_PRODUCTION
set -uo pipefail
umask 077
root=${NFCORE_ROOT:-/opt/fm/nfcore}
expected=${1:-}
errors=0
operational=0
report() { printf '%s=%s\n' "$1" "$2"; }
block() { report "$1" BLOCKED; errors=$((errors + 1)); }
pending() { report "$1" PENDING; operational=$((operational + 1)); }
if [[ ! $expected =~ ^[[:xdigit:]]{40}$ ]]; then
  printf '%s\n' 'Uso: bling-operational-host-audit.sh SHA_COMPLETO_DA_PRODUCTION' >&2
  exit 2
fi
expected=${expected,,}
report EXPECTED_SHA "${expected:0:12}"

# Nao executa git fetch, compose up, schema --apply nem le logs completos.
installed=''
if [[ -f "$root/.deployed" ]]; then
  installed=$(sed -n 's/^SHA=\([[:xdigit:]]\{40\}\)$/\1/p' "$root/.deployed" | head -n 1)
fi
if [[ ${installed,,} == "$expected" ]]; then report DEPLOY_SHA_EXACT PASS; else block DEPLOY_SHA_EXACT; fi
if [[ -f "$root/.failed-sha" ]] && grep -Fqx "$expected" "$root/.failed-sha"; then
  block DEPLOY_FAILED_SHA
else
  report DEPLOY_FAILED_SHA CLEAR
fi
if [[ -f "$root/deploy.log" ]] && grep -Fq "DEPLOY OK ${expected:0:7}" "$root/deploy.log"; then
  report DEPLOY_LOG_SUCCESS PASS
else
  pending DEPLOY_LOG_SUCCESS
fi

# Validacao do backup existente sem gerar dump ou modificar banco.
backup_dir=${NFCORE_BACKUP_DIR:-/opt/fm/backups/nfcore-diario}
recent_dump=''
if [[ -d "$backup_dir" ]]; then
  recent_dump=$(find "$backup_dir" -maxdepth 1 -type f -name 'nfcore-*.dump' -mmin -1440 \
    -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-)
fi
if [[ -n $recent_dump && -f "$recent_dump.sha256" ]] && \
  (cd "$(dirname "$recent_dump")" && sha256sum -c "$(basename "$recent_dump").sha256" >/dev/null 2>&1); then
  report RECENT_BACKUP_INTEGRITY PASS
else
  pending RECENT_BACKUP_INTEGRITY
fi

if ! command -v docker >/dev/null 2>&1; then
  block DOCKER_ACCESS
  report RESULT NO_GO_MISSING_HOST_EVIDENCE
  report REAL_OAUTH UNVERIFIED_EXTERNAL
  report SEFAZ_A1 UNVERIFIED_EXTERNAL
  exit 1
fi
status_of() { docker inspect --format '{{.State.Status}}' "$1" 2>/dev/null || true; }
health_of() { docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' "$1" 2>/dev/null || true; }
for service in nfcore-db nfcore-api nfcore-portal; do
  if [[ $(status_of "$service") == running ]]; then
    report "CONTAINER_$service" PASS
  else
    block "CONTAINER_$service"
  fi
done
readiness() {
  docker exec "$1" python -c "import urllib.request as r; r.urlopen('http://127.0.0.1:$2/$3', timeout=3).read()" >/dev/null 2>&1
}
if readiness nfcore-api 8080 health/ready; then report API_READY PASS; else block API_READY; fi
if readiness nfcore-portal 8081 ''; then report PORTAL_READY PASS; else block PORTAL_READY; fi

# Guard oficial fiscal + Cakto; nunca chama --apply.
if docker exec nfcore-api python scripts/ci/migration_guard.py --assert-current-production >/dev/null 2>&1; then
  report SCHEMA_PRODUCTION_GUARD PASS
else
  block SCHEMA_PRODUCTION_GUARD
fi
versions=$(docker exec nfcore-db psql -U nfcore -d nfcore -AtX -v ON_ERROR_STOP=1 \
  -c "SELECT COALESCE(string_agg(version::text, ',' ORDER BY version), '') FROM fm_schema_migrations" 2>/dev/null || true)
if [[ $versions =~ ^([0-9]+,)*[0-9]+$ ]]; then
  if [[ $versions == "$(seq -s, 1 21)" ]]; then
    report BLING_SCHEMA_20_21 PASS
  elif [[ $versions == "$(seq -s, 1 19)" ]]; then
    pending BLING_SCHEMA_20_21
  else
    block BLING_SCHEMA_20_21
  fi
else
  block BLING_SCHEMA_20_21
fi
api_flag=$(docker exec nfcore-api python -c \
  'import os; print("ENABLED" if os.getenv("NFCORE_BLING_INSTALLATIONS_ENABLED") == "true" else "DISABLED")' 2>/dev/null || true)
if [[ $api_flag == ENABLED ]]; then report BLING_API_FLAG PASS; else pending BLING_API_FLAG; fi

# Checa apenas booleanos, sem imprimir valor de env ou conteudo dos arquivos.
secret_ready=$(docker exec nfcore-api python -c '
import os
from pathlib import Path
keys=("NFCORE_BLING_CLIENT_ID", "NFCORE_BLING_APPROVED_SCOPES")
files=("NFCORE_BLING_CLIENT_SECRET_FILE", "NFCORE_BLING_TOKEN_MASTER_KEY_FILE")
ready=(all(os.getenv(k) for k in keys) and
       all(os.getenv(k) and Path(os.environ[k]).is_file() and os.access(os.environ[k], os.R_OK) for k in files))
print("READY" if ready else "UNAVAILABLE")
' 2>/dev/null || true)
if [[ $secret_ready == READY ]]; then report BLING_SECRET_MOUNTS PASS; else pending BLING_SECRET_MOUNTS; fi

# Read-only proof that the scoped fiscal-policy runtime from PR #418 is mounted
# RO and that present artifacts pass the CANONICAL preparer validation. This
# does not prove every Bling installation has a policy: tenant-specific onboarding
# still requires its own policy and authenticated end-to-end rehearsal.
if [[ $api_flag == ENABLED ]]; then
  policy_mount=$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/run/nfcore/bling-policies"}}{{if .RW}}RW{{else}}RO{{end}}{{end}}{{end}}' nfcore-api 2>/dev/null || true)
  if [[ $policy_mount == RO ]]; then
    report BLING_POLICY_MOUNT PASS
  else
    block BLING_POLICY_MOUNT
  fi
  policy_state=$(docker exec nfcore-api python -c '
import json
import os
from pathlib import Path
from types import SimpleNamespace
from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment
from kordena_fiscal.runtime.bling_preparation import BlingSalePreparer

root_path = os.environ.get("NFCORE_BLING_FISCAL_POLICY_ROOT", "")
root = Path(root_path)
if root_path != "/run/nfcore/bling-policies" or root.is_symlink() or not root.is_dir():
    print("UNAVAILABLE")
else:
    try:
        artifacts = sorted(root.glob("*.json"))
        if not artifacts:
            print("EMPTY")
        else:
            # Validate against the actual API environment: forbidden global settings
            # legacy global policy must not be masked by synthetic audit settings.
            preparer = BlingSalePreparer(os.environ)
            for artifact in artifacts:
                if artifact.is_symlink():
                    raise ValueError("symlink")
                with artifact.open("rb") as stream:
                    raw = stream.read(1_048_577)
                if len(raw) > 1_048_576:
                    raise ValueError("oversized")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("not a policy")
                company_id = data["company_id"]
                if not isinstance(company_id, str):
                    raise ValueError("company")
                scope = ExecutionScope(
                    tenant_id=data["tenant_id"],
                    unit_id=data["unit_id"],
                    environment=FiscalEnvironment(data["environment"]),
                    correlation_id="host-audit",
                    host_namespace="bling",
                )
                name = preparer.policy_scope_digest(scope, company_id)
                if artifact.name != name + ".json":
                    raise ValueError("wrong scope slot")
                preparer.policy(SimpleNamespace(scope=scope, company_id=company_id))
            print("READY")
    except Exception:
        # Do not reveal tenant names, policy JSON, secret paths or exception text.
        print("INVALID")
' 2>/dev/null || true)
  case "$policy_state" in
    READY) report BLING_POLICY_ARTIFACTS PASS ;;
    EMPTY) pending BLING_POLICY_ARTIFACTS ;;
    *) block BLING_POLICY_ARTIFACTS ;;
  esac
else
  pending BLING_POLICY_MOUNT
  pending BLING_POLICY_ARTIFACTS
fi
if [[ $(status_of nfcore-bling-worker) == running ]]; then
  report BLING_WORKER_RUNNING PASS
  if [[ $(health_of nfcore-bling-worker) == healthy ]]; then
    report BLING_WORKER_HEALTH PASS
  else
    block BLING_WORKER_HEALTH
  fi
else
  pending BLING_WORKER_RUNNING
fi

report REAL_OAUTH UNVERIFIED_EXTERNAL
report REAL_BLING_ORDER UNVERIFIED_EXTERNAL
report SEFAZ_A1 UNVERIFIED_EXTERNAL
if (( errors != 0 )); then
  report RESULT NO_GO_HOST_GATES
elif (( operational != 0 )); then
  report RESULT CODE_READY_BUT_BLING_NOT_ACTIVE
else
  report RESULT HOST_GATES_PASS_EXTERNAL_STILL_UNVERIFIED
fi
exit "$(( errors != 0 || operational != 0 ))"
