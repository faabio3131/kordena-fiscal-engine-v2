"""Certify the built worker image using a read-only, CI-only synthetic dispatch fixture.

Real PostgreSQL, PID1/non-root, idle continuity, Docker HEALTHCHECK, SIGTERM while
dispatching, drained durable batch, restart without replay. No external delivery.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

IMAGE = "nfcore-worker:test"
FIXTURE = Path("tests/support/p04_worker_process.py").resolve()
ENVIRONMENT = [
    "-e",
    "NFCORE_ENVIRONMENT=staging",
    "-e",
    "NFCORE_PERSISTENCE_BACKEND=postgres",
    "-e",
    "NFCORE_SECRET_BACKEND=external",
    "-e",
    "NFCORE_REQUIRE_HTTPS=true",
    "-e",
    "DATABASE_URL",
]


def docker(*args: str, check: bool = True, timeout: float = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        check=check,
        timeout=timeout,
        capture_output=True,
        text=True,
    )


def until(predicate, *, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.2)
    raise AssertionError("worker container proof deadline exceeded")


def main() -> None:
    os.environ["DATABASE_URL"] = os.environ["NFCORE_TEST_POSTGRES_DSN"]
    mounts = ["-v", f"{FIXTURE}:/proof/worker.py:ro"]
    names = ["nfcore-p04-idle", "nfcore-p04-drain", "nfcore-p04-restart"]

    def fixture(mode: str) -> None:
        docker(
            "run",
            "--rm",
            "--network",
            "host",
            *ENVIRONMENT,
            *mounts,
            "--entrypoint",
            "python",
            IMAGE,
            "/proof/worker.py",
            mode,
        )

    def ready(name: str) -> bool:
        return (
            docker(
                "exec",
                name,
                "python",
                "-m",
                "kordena_fiscal.runtime.worker_health",
                check=False,
                timeout=5,
            ).returncode
            == 0
        )

    def running(name: str) -> bool:
        return docker("inspect", "--format", "{{.State.Running}}", name).stdout.strip() == "true"

    def stop(name: str) -> None:
        docker("kill", "--signal", "SIGTERM", name)
        assert docker("wait", name, timeout=20).stdout.strip() == "0"
        assert not running(name)

    try:
        fixture("reset")
        # Keep the image's unconfigured production CMD fail-closed. This fixture does
        # not introduce an env-selected factory or ship a synthetic handler in src.
        rejected = docker("run", "--rm", "--network", "host", *ENVIRONMENT, IMAGE, check=False)
        assert rejected.returncode != 0, "unconfigured CMD must fail before consuming work"
        assert (
            "continuous worker requires an explicitly configured handler factory" in rejected.stderr
        )

        with tempfile.TemporaryDirectory(prefix="nfcore-worker-proof-") as directory:
            state = Path(directory)
            state.chmod(0o777)  # Disposable synthetic CI files, writable by container UID10001.

            def start(name: str, mode: str) -> None:
                docker(
                    "run",
                    "-d",
                    "--name",
                    name,
                    "--network",
                    "host",
                    *ENVIRONMENT,
                    *mounts,
                    "-v",
                    f"{state}:/proof/state",
                    "--entrypoint",
                    "python",
                    IMAGE,
                    "/proof/worker.py",
                    mode,
                )
                until(lambda: ready(name))
                assert running(name)
                assert docker("exec", name, "id", "-u").stdout.strip() == "10001"
                docker(
                    "exec",
                    name,
                    "python",
                    "-c",
                    "import json; from kordena_fiscal.runtime.worker_health import HEALTH_PATH; "
                    "assert json.loads(HEALTH_PATH.read_text())['pid'] == 1",
                )
                until(
                    lambda: (
                        docker(
                            "inspect", "--format", "{{.State.Health.Status}}", name
                        ).stdout.strip()
                        == "healthy"
                    )
                )

            start(names[0], "idle")
            time.sleep(2)
            assert running(names[0]) and ready(names[0]), "idle worker must remain continuous"
            stop(names[0])
            print("PASS: non-root PID1, continuous idle, Docker health, SIGTERM exit0")

            start(names[1], "drain")
            fixture("seed")
            until(lambda: (state / "dispatch_started").exists())
            docker("kill", "--signal", "SIGTERM", names[1])
            until(lambda: not ready(names[1]), timeout=5)
            assert running(names[1]), "worker must drain already-claimed batch before exit"
            (state / "release").touch()
            assert docker("wait", names[1], timeout=20).stdout.strip() == "0"
            fixture("verify_drained")
            print("PASS: SIGTERM invalidates readiness;10 claimed jobs drained,3 pending")

            start(names[2], "restart")
            fixture("verify_finished")
            stop(names[2])
            print("PASS: restart completes13/13;one attempt/audit per job;no terminal replay")
    finally:
        for name in names:
            docker("rm", "-f", name, check=False)


if __name__ == "__main__":
    main()
