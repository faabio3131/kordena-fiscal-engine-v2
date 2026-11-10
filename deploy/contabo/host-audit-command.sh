#!/usr/bin/env bash
# NFCore dedicated SSH authorized_keys forced command, WITHOUT docker privilege.
# Install root-owned at /usr/local/libexec/nfcore-audit/ssh-gate.sh.
# The only escalation is sudoers' zero-argument pinned read-only root-audit.sh.
set -Eeuo pipefail
umask 077

parse_audit_request() {
  local request="${1:-}"
  # Only exact ASCII-space-separated immutable digests. No shell metacharacters.
  if [[ "$request" =~ ^nfcore-audit[\ ]([0-9a-f]{40})[\ ]([0-9a-f]{64})$ ]]; then
    AUDIT_PRODUCTION_SHA="${BASH_REMATCH[1]}"
    AUDIT_SCRIPT_SHA256="${BASH_REMATCH[2]}"
    return 0
  fi
  return 1
}

main() {
  if ! parse_audit_request "${SSH_ORIGINAL_COMMAND:-}"; then
    echo 'NO_GO_INVALID_AUDIT_REQUEST' >&2
    exit 42
  fi
  # No Docker socket permissions are granted to this user. The privileged
  # entry point validates the whole root-controlled path and script digest.
  # Sudoers must allow only this exact root-owned program with NO arguments.
  # A single prevalidated hash pair is forwarded on stdin, never as shell code.
  printf '%s %s\n' "$AUDIT_PRODUCTION_SHA" "$AUDIT_SCRIPT_SHA256" |
    /usr/bin/sudo -n -- /usr/local/libexec/nfcore-audit/root-audit.sh
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
