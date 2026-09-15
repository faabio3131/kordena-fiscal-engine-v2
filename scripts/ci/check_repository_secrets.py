"""Fail closed when strong secret signatures are found in tracked repository files."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_MAX_TEXT_BYTES = 2_000_000
_FORBIDDEN_SUFFIXES = {".p12", ".pfx", ".jks", ".keystore"}
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private-key-pem",
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
            re.IGNORECASE,
        ),
    ),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("nvidia-api-key", re.compile(r"\bnvapi-[A-Za-z0-9_-]{24,}\b")),
)


def _tracked_files() -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return tuple(Path(item.decode()) for item in result.stdout.split(b"\0") if item)


def _read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) > _MAX_TEXT_BYTES or b"\0" in data:
        return None
    return data.decode("utf-8", errors="ignore")


def main() -> int:
    findings: list[tuple[str, str]] = []
    for path in _tracked_files():
        if path.suffix.casefold() in _FORBIDDEN_SUFFIXES:
            findings.append((path.as_posix(), "forbidden-secret-container"))
            continue
        text = _read_text(path)
        if text is None:
            continue
        for rule_name, pattern in _PATTERNS:
            if pattern.search(text):
                findings.append((path.as_posix(), rule_name))

    if findings:
        print("repository secret scan: FAIL")
        for path, rule_name in findings:
            print(f"- {path}: {rule_name}")
        return 1

    print("repository secret scan: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
