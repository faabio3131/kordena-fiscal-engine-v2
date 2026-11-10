#!/usr/bin/env bash
# Run without SSH, secrets, Contabo credentials, Docker or external network.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=deploy/contabo/host-audit-command.sh
source "$here/host-audit-command.sh"
sha=61015a837be8b2e5e3b0f1cdb5fb14c5c875fb91
digest=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

parse_audit_request "nfcore-audit $sha $digest"
[[ "$AUDIT_PRODUCTION_SHA" == "$sha" && "$AUDIT_SCRIPT_SHA256" == "$digest" ]]

for invalid in \
    "" \
    "id" \
    "nfcore-audit $sha" \
    "nfcore-audit $sha $digest extra" \
    "nfcore-audit $sha $digest;id" \
    "nfcore-audit ${sha^^} $digest" \
    "nfcore-audit $sha ${digest:0:63}" \
    "nfcore-audit $sha $digest\nwhoami"; do
  if parse_audit_request "$invalid"; then
    printf 'FAIL: accepted invalid SSH audit command\n' >&2
    exit 1
  fi
done

# The entrypoint must fail closed on untrusted commands without probing host.
if SSH_ORIGINAL_COMMAND='cat /etc/shadow' bash "$here/host-audit-command.sh" >/dev/null 2>&1; then
  echo 'FAIL: accepted arbitrary command' >&2
  exit 1
fi
if SSH_ORIGINAL_COMMAND="nfcore-audit $sha $digest; id" \
   bash "$here/host-audit-command.sh" >/dev/null 2>&1; then
  echo 'FAIL: accepted shell injection' >&2
  exit 1
fi
echo 'PASS: forced SSH audit entry rejects arbitrary commands'
