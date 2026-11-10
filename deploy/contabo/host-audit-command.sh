#!/usr/bin/env bash
# NFCore: immutable read-only audit entry point for a dedicated forced SSH key.
# Must be installed root-owned at /opt/fm/nfcore/audit/host-audit-command.sh.
# Does not accept arbitrary shell, paths, scripts or environment overrides.
set -Eeuo pipefail
umask 077

parse_audit_request() {
  local request="${1:-}"
  # A single fixed verb and two immutable digests, no shell metacharacters.
  if [[ "$request" =~ ^nfcore-audit[[:space:]]([0-9a-f]{40})[[:space:]]([0-9a-f]{64})$ ]]; then
    AUDIT_PRODUCTION_SHA="${BASH_REMATCH[1]}"
    AUDIT_SCRIPT_SHA256="${BASH_REMATCH[2]}"
    return 0
  fi
  return 1
}

main() {
  if ! parse_audit_request "${SSH_ORIGINAL_COMMAND:-}"; then
    printf '%s\n' 'NO_GO_INVALID_AUDIT_REQUEST' >&2
    exit 42
  fi

  local audit_script=/opt/fm/nfcore/audit/bling-operational-host-audit.sh
  if [[ ! -f "$audit_script" || -L "$audit_script" || ! -r "$audit_script" ]]; then
    printf '%s\n' 'NO_GO_AUDIT_SCRIPT_UNAVAILABLE' >&2
    exit 42
  fi
  # The account holding the audit key must not be able to replace the script.
  if [[ "$(stat -c '%u' "$audit_script")" != "0" ]] || 
     [[ -n "$(find "$audit_script" -maxdepth 0 -perm /022 -print)" ]]; then
    printf '%s\n' 'NO_GO_AUDIT_SCRIPT_PERMISSIONS' >&2
    exit 42
  fi
  local installed_digest
  installed_digest=$(sha256sum "$audit_script")
  installed_digest="${installed_digest%% *}"
  if [[ "$installed_digest" != "$AUDIT_SCRIPT_SHA256" ]]; then
    printf '%s\n' 'NO_GO_AUDIT_SCRIPT_DIGEST' >&2
    exit 42
  fi

  # Only trusted script/arguments; never execute the caller supplied string.
  # Clean environment, no stdin (no scripts or commands from SSH client).
  exec /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C HOME=/nonexistent \
    /bin/bash "$audit_script" "$AUDIT_PRODUCTION_SHA" </dev/null
}

# Tests source the parser; executing the wrapper always requires forced SSH.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
