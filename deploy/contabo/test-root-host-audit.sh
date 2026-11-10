#!/usr/bin/env bash
# Synthetic unprivileged tests; no SSH, Docker, sudo, live host or secrets.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=deploy/contabo/root-host-audit.sh
source "$here/root-host-audit.sh"

owner=$(id -u)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -m 700 "$work/secure"
printf 'test fixture\n' > "$work/secure/script"
chmod 644 "$work/secure/script"

trust_path "$work/secure" "$owner"
trust_path "$work/secure/script" "$owner"
chmod g+w "$work/secure"
if trust_path "$work/secure" "$owner"; then
  echo 'FAIL: writable ancestor was accepted' >&2
  exit 1
fi
chmod g-w "$work/secure"
chmod o+w "$work/secure/script"
if trust_path "$work/secure/script" "$owner"; then
  echo 'FAIL: writable script was accepted' >&2
  exit 1
fi
chmod o-w "$work/secure/script"
ln -s "$work/secure/script" "$work/secure/link"
if trust_path "$work/secure/link" "$owner"; then
  echo 'FAIL: symlink accepted' >&2
  exit 1
fi
if [[ "$owner" -ne 0 ]] && trust_path "$work/secure" 0; then
  echo 'FAIL: wrong UID accepted' >&2
  exit 1
fi

sha=61015a837be8b2e5e3b0f1cdb5fb14c5c875fb91
digest=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
parse_root_audit_request < <(printf '%s %s\n' "$sha" "$digest")
[[ "$ROOT_AUDIT_SHA" == "$sha" && "$ROOT_AUDIT_DIGEST" == "$digest" ]]

for invalid in \
  "not-an-audit" \
  "$sha" \
  "$sha $digest extra" \
  "$sha $digest; id" \
  "${sha^^} $digest"; do
  if parse_root_audit_request < <(printf '%s\n' "$invalid"); then
    echo 'FAIL: invalid privileged request accepted' >&2
    exit 1
  fi
done
if parse_root_audit_request < <(printf '%s %s\nwhoami\n' "$sha" "$digest"); then
  echo 'FAIL: extra line accepted' >&2
  exit 1
fi
if parse_root_audit_request < <(printf '%s %s\n\n' "$sha" "$digest"); then
  echo 'FAIL: trailing newline accepted' >&2
  exit 1
fi
if parse_root_audit_request < <(printf '%s %s' "$sha" "$digest"); then
  echo 'FAIL: unterminated request accepted' >&2
  exit 1
fi
if parse_root_audit_request < <(printf 'A%.0s' {1..256}); then
  echo 'FAIL: oversized request accepted' >&2
  exit 1
fi
echo 'PASS: root-owned audit chain and bounded no-argument sudo input'
