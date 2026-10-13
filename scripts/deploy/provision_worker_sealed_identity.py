#!/usr/bin/env python3
"""Operator-only Windows transfer; no deploy, no schema mutation, no secret output.

Requires a PRE-SEALED Railway placeholder, encrypted owner-only local directory,
Google-enforced key expiry <=30 days and explicit operator approval. No ADC export.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT = "fm-nfcore-staging"
SA = f"nfcore-stg-worker@{PROJECT}.iam.gserviceaccount.com"
SECRET = "nfcore-stg-pilot-webhook-signing"
RAILWAY_PROJECT = "b84b290d-f3b4-46a1-9023-0b761cb96b0d"
ENVIRONMENT = "c9878b9b-62b2-4a97-b8ba-743c8a3e99ec"
SERVICE = "b3bde804-fa29-4c67-841d-7cda050c40e7"
VARIABLE = "NFCORE_WORKER_GSM_CREDENTIAL_JSON"
API = "https://backboard.railway.app/graphql/v2"


class Blocked(Exception):
    pass


def command(args):
    env = dict(os.environ, CLOUDSDK_CORE_LOG_HTTP="false",
               CLOUDSDK_CORE_DISABLE_FILE_LOGGING="true")
    result = subprocess.run(args, capture_output=True, text=True, timeout=60, env=env)
    if result.returncode:
        # Never propagate CLI stderr/stdout which could contain credential data.
        raise Blocked("Official CLI operation failed; inspect permissions locally, no secret logs.")
    return result.stdout


def google(*args):
    executable = shutil.which("gcloud.cmd") or shutil.which("gcloud")
    if not executable:
        raise Blocked("Official gcloud CLI missing.")
    return command([executable, *args, f"--project={PROJECT}", "--quiet",
                    "--verbosity=none", "--format=json"])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Blocked("Unexpected API redirect; transfer aborted.")


def railway(token, query, variables):
    request = urllib.request.Request(API, data=json.dumps({
        "query": query, "variables": variables,
    }).encode(), headers={"Content-Type": "application/json", "Project-Access-Token": token})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
            result = json.load(response)
        if result.get("errors") or not result.get("data"):
            raise Blocked("Railway API rejected operation; response suppressed.")
        return result["data"]
    except Exception:
        raise Blocked("Railway HTTPS operation failed; response suppressed.") from None


def sealed(token):
    result = railway(token, '''query($project: String!, $environment: String!) {
      environment(id: $environment, projectId: $project) {
        variables(first: 10000) { edges { node { name serviceId isSealed } }
          pageInfo { hasNextPage } }
      }
    }''', {"project": RAILWAY_PROJECT, "environment": ENVIRONMENT})
    connection = result["environment"]["variables"]
    if connection["pageInfo"]["hasNextPage"]:
        raise Blocked("Variable metadata pagination requires review.")
    matches = [e["node"] for e in connection["edges"]
               if e["node"]["name"] == VARIABLE and e["node"]["serviceId"] == SERVICE]
    if len(matches) != 1 or matches[0]["isSealed"] is not True:
        raise Blocked("Worker credential placeholder must already be SEALED; no key created.")


def expiry_limit(policy):
    values = policy.get("listPolicy", {}).get("allowedValues", [])
    if not values or policy.get("listPolicy", {}).get("allValues"):
        raise Blocked("Effective Google key-expiry policy not confirmed; no key created.")
    hours = []
    for value in values:
        match = re.fullmatch(r"(\d+)h", value)
        if not match or not 1 <= int(match[1]) <= 720:
            raise Blocked("Google key expiry must be finite and <=720h; no key created.")
        hours.append(int(match[1]))
    return max(hours)


def rotation_metadata(key, key_id, now):
    start = datetime.fromisoformat(key["validAfterTime"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(key["validBeforeTime"].replace("Z", "+00:00"))
    if (key["name"].rsplit("/", 1)[-1] != key_id or key.get("disabled", False)
            or start.utcoffset() is None or end.utcoffset() is None
            or not start <= now < end <= start + timedelta(days=30)):
        raise Blocked("Actual IAM key identity/expiry invalid; newly created key must be revoked.")
    return {
        "NFCORE_WORKER_GSM_KEY_ID": key_id,
        "NFCORE_WORKER_GSM_KEY_CREATED_AT": start.isoformat(),
        "NFCORE_WORKER_GSM_KEY_NOT_AFTER": end.isoformat(),
    }


def private_directory(root):
    # Windows BitLocker + current SID-only ACL before gcloud writes anything.
    if os.name != "nt" or not root.is_absolute() or not re.fullmatch(r"[A-Za-z]:", root.drive):
        raise Blocked("Windows absolute local drive required.")
    if not root.is_dir() or root.is_symlink():
        raise Blocked("Existing local directory required outside Git/OneDrive/Dropbox.")
    if any((parent / ".git").exists() for parent in (root, *root.parents)):
        raise Blocked("Protected directory cannot be inside a Git checkout.")
    if any(name in str(root).lower() for name in ("onedrive", "dropbox")):
        raise Blocked("Protected directory cannot be inside a sync directory.")
    drive = root.drive  # validated; never interpolate caller text into PowerShell
    proof = command(["powershell.exe", "-NoProfile", "-Command",
                     f"Get-BitLockerVolume -MountPoint '{drive}' | "
                     "Select-Object EncryptionPercentage,ProtectionStatus | ConvertTo-Json"])
    proof = json.loads(proof)
    if proof["EncryptionPercentage"] != 100 or str(proof["ProtectionStatus"]) not in {"On", "1"}:
        raise Blocked("BitLocker fully encrypted + protection ON required.")
    directory = Path(tempfile.mkdtemp(prefix="nfcore-identity-", dir=root))
    try:
        sid = json.loads(command(["powershell.exe", "-NoProfile", "-Command",
                         "[Security.Principal.WindowsIdentity]::GetCurrent().User.Value "
                         "| ConvertTo-Json"]))
        if not re.fullmatch(r"S-1-[0-9-]+", sid):
            raise Blocked("Windows owner SID unavailable.")
        command(["icacls.exe", str(directory), "/inheritance:r", "/grant:r",
                 f"*{sid}:(OI)(CI)F"])
        return directory
    except Exception:
        directory.rmdir()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-directory", type=Path, required=True)
    parser.add_argument("--rotation-owner", required=True, help="Nonsecret internal owner ID")
    parser.add_argument("--approve-key-creation", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", args.rotation_owner):
        raise Blocked("Nonsecret rotation owner ID required.")
    if os.name != "nt" or not sys.stdin.isatty():
        raise Blocked("Interactive Windows terminal required for hidden token input.")
    token = getpass.getpass("Railway project token (hidden, never shared): ")
    sealed(token)  # no variable VALUES queried
    expiry_limit(json.loads(google("resource-manager", "org-policies", "describe",
                                  "iam.serviceAccountKeyExpiryHours", "--effective")))
    version = json.loads(google("secrets", "versions", "describe", "1", f"--secret={SECRET}"))
    if version.get("state") != "ENABLED":
        raise Blocked("Expected secret version 1 is not enabled.")
    if not args.approve_key_creation:
        print("READ_ONLY_PREFLIGHT_PASS; no key/config/deploy created. Review approval gate.")
        return
    directory = private_directory(args.protected_directory)
    key_file = directory / "identity.json"
    key_id = None
    transferred = False
    try:
        google("iam", "service-accounts", "keys", "create", str(key_file),
               f"--iam-account={SA}", "--key-file-type=json")
        raw = key_file.read_text(encoding="utf-8")
        info = json.loads(raw)
        key_id = info.get("private_key_id")
        if (info.get("type") != "service_account" or info.get("project_id") != PROJECT
                or info.get("client_email") != SA or not isinstance(key_id, str)
                or not re.fullmatch(r"[a-f0-9]{40}", key_id)):
            raise Blocked("Created credential identity invalid.")
        keys = json.loads(google("iam", "service-accounts", "keys", "list",
                                 f"--iam-account={SA}", "--managed-by=user"))
        matches = [key for key in keys if key["name"].rsplit("/", 1)[-1] == key_id]
        if len(matches) != 1:
            raise Blocked("Created key not independently reconciled in IAM.")
        metadata = rotation_metadata(matches[0], key_id, datetime.now(UTC))
        sealed(token)  # revalidate just before transfer
        result = railway(token, '''mutation($input: VariableCollectionUpsertInput!) {
          variableCollectionUpsert(input: $input)
        }''', {"input": {"projectId": RAILWAY_PROJECT, "environmentId": ENVIRONMENT,
                         "serviceId": SERVICE, "skipDeploys": True, "replace": False,
                         "variables": {VARIABLE: raw, **metadata}}})
        if result.get("variableCollectionUpsert") is not True:
            raise Blocked("Railway write acknowledgement missing.")
        sealed(token)  # receipt verifies seal only, never secret read-back
        transferred = True
        print(json.dumps({"status": "SEALED_CONFIGURED_NO_DEPLOY", "rotation_owner":
                          args.rotation_owner, "rotation_due": metadata[
                              "NFCORE_WORKER_GSM_KEY_NOT_AFTER"], "metadata": metadata}))
    finally:
        if key_id and not transferred:
            try:
                google("iam", "service-accounts", "keys", "delete", key_id,
                       f"--iam-account={SA}")
                print("ABORTED: newly created key revoked; Railway readiness not certified.")
            except Exception:
                print("URGENT: revoke newly created Worker key locally in IAM; cleanup failed.",
                      file=sys.stderr)
                raise Blocked("IAM revocation requires operator intervention.") from None
        if key_file.exists():
            key_file.unlink()  # encrypted volume: deletion is not a secure-erase claim
        directory.rmdir()


if __name__ == "__main__":
    try:
        main()
    except Blocked as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("BLOCKED: inspect runbook prerequisites locally; no raw errors/credentials printed.",
              file=sys.stderr)
        sys.exit(1)
