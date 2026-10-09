"""Real OS signals/processes; PostgreSQL cases require the real CI database."""

import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from threading import Event

import pytest

from kordena_fiscal.runtime.observability import WorkerHealth
from kordena_fiscal.runtime.worker_health import WorkerHealthPublisher, check_worker_health

FIXTURE = Path(__file__).parents[1] / "support" / "p04_worker_process.py"


def record(path, **changes):
    values = {
        "version": 1,
        "pid": os.getpid(),
        "sampled_at": time.monotonic(),
        "ready": True,
        "stopped": False,
    }
    values.update(changes)
    path.write_text(json.dumps(values))
    path.chmod(0o600)


@pytest.mark.parametrize(
    "changes",
    [
        {"ready": False},
        {"stopped": True},
        {"version": 2},
        {"version": True},
        {"pid": 0},
        {"pid": True},
        {"ready": 1},
        {"stopped": 0},
        {"sampled_at": True},
        {"sampled_at": float("nan")},
        {"sampled_at": float("inf")},
        {"private_payload": "synthetic"},
    ],
)
def test_invalid_or_unready_sample_fails_closed(tmp_path, changes):
    path = tmp_path / "health"
    record(path, **changes)
    assert not check_worker_health(path=path)


def test_sample_age_is_monotonic_bounded_and_not_future(tmp_path, monkeypatch):
    import kordena_fiscal.runtime.worker_health as module

    path = tmp_path / "health"
    record(path, sampled_at=100.0)
    monkeypatch.setattr(module, "monotonic", lambda: 104.99)
    assert check_worker_health(path=path)
    monkeypatch.setattr(module, "monotonic", lambda: 105.0)
    assert not check_worker_health(path=path)
    monkeypatch.setattr(module, "monotonic", lambda: 99.0)
    assert not check_worker_health(path=path)


def test_missing_malformed_large_public_and_symlink_samples_rejected(tmp_path):
    path = tmp_path / "health"
    assert not check_worker_health(path=path)
    path.write_text("not-json")
    path.chmod(0o600)
    assert not check_worker_health(path=path)
    path.write_text("x" * 1025)
    assert not check_worker_health(path=path)
    record(path)
    path.chmod(0o644)
    assert not check_worker_health(path=path)
    path.chmod(0o600)
    alias = tmp_path / "alias"
    alias.symlink_to(path)
    assert not check_worker_health(path=alias)
    assert not check_worker_health(path=tmp_path)


def test_dead_process_cannot_be_ready(tmp_path, monkeypatch):
    import kordena_fiscal.runtime.worker_health as module

    path = tmp_path / "health"
    record(path)

    def dead(*_args):
        raise ProcessLookupError()

    monkeypatch.setattr(module.os, "kill", dead)
    assert not check_worker_health(path=path)


def test_large_integer_timestamp_fails_closed(tmp_path):
    path = tmp_path / "health"
    record(path, sampled_at=10**400)
    assert not check_worker_health(path=path)


def test_periodic_publication_failure_does_not_terminate_publisher(tmp_path, monkeypatch):
    import kordena_fiscal.runtime.worker_health as module

    monkeypatch.setattr(module, "PUBLISH_INTERVAL_SECONDS", 0.001)
    publisher = WorkerHealthPublisher(Event(), path=tmp_path / "health")
    calls = []

    def denied():
        calls.append(True)
        if len(calls) == 2:
            publisher._closed.set()
        raise PermissionError("synthetic-private-error")

    monkeypatch.setattr(publisher, "publish", denied)
    publisher._loop()
    assert len(calls) == 2


def test_publisher_uses_poll_health_and_stop_without_db_or_identity(tmp_path):
    path = tmp_path / "health"
    stop = Event()
    publisher = WorkerHealthPublisher(stop, path=path)
    publisher.start()
    try:
        assert not check_worker_health(path=path)
        publisher.attach(lambda: WorkerHealth(True, False, True, 0.0))
        publisher.publish()
        assert check_worker_health(path=path)
        assert path.stat().st_mode & 0o777 == 0o600
        assert set(json.loads(path.read_text())) == {
            "version",
            "pid",
            "sampled_at",
            "ready",
            "stopped",
        }
        # Publisher activity alone must not override stale/failed poll health.
        publisher.attach(lambda: WorkerHealth(False, False, False, 60.0))
        publisher.publish()
        assert not check_worker_health(path=path)
        publisher.attach(lambda: WorkerHealth(True, False, True, 0.0))
        stop.set()
        publisher.publish()
        assert not check_worker_health(path=path)
    finally:
        publisher.close()
    assert json.loads(path.read_text())["stopped"] is True


def test_health_source_exception_and_publication_failure_do_not_escape_loop(tmp_path, monkeypatch):
    publisher = WorkerHealthPublisher(Event(), path=tmp_path / "health")

    def broken():
        raise RuntimeError("synthetic-private-error")

    publisher.attach(broken)
    publisher.start()
    assert not check_worker_health(path=tmp_path / "health")

    def denied():
        raise PermissionError("synthetic-private-error")

    monkeypatch.setattr(publisher, "publish", denied)
    publisher.close()


def test_sigterm_during_bootstrap_is_not_lost_and_signals_restored(tmp_path, monkeypatch):
    import kordena_fiscal.runtime.worker_main as module
    from kordena_fiscal.persistence import SqliteFiscalDatabase

    original = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    db = SqliteFiscalDatabase(tmp_path / "bootstrap.sqlite")
    closed = []

    class BootstrapDatabase:
        def __init__(self, _dsn):
            pass

        def initialize(self):
            db.initialize()
            os.kill(os.getpid(), signal.SIGTERM)

        def connection(self):
            return sqlite3.connect(tmp_path / "bootstrap.sqlite")

        def close(self):
            closed.append(True)

    settings = type(
        "Settings", (), {"persistence_backend": "postgres", "database_url": "synthetic"}
    )()
    monkeypatch.setattr(module.RuntimeSettings, "from_environ", lambda: settings)
    monkeypatch.setattr(module, "PostgresFiscalDatabase", BootstrapDatabase)
    monkeypatch.delenv("NFCORE_WORKER_ONESHOT", raising=False)

    def forbidden(*_args):
        raise AssertionError("signal during bootstrap must prevent composition/claims")

    assert module.run(handler_factory=forbidden, health_path=tmp_path / "health") == 0
    assert closed == [True]
    assert {sig: signal.getsignal(sig) for sig in original} == original
    assert not check_worker_health(path=tmp_path / "health")


def test_configuration_failure_restores_signals_and_invalidates_old_sample(tmp_path, monkeypatch):
    import kordena_fiscal.runtime.worker_main as module

    original = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    path = tmp_path / "health"
    record(path)
    assert check_worker_health(path=path)

    def broken():
        raise module.RuntimeConfigurationError("synthetic configuration failure")

    monkeypatch.setattr(module.RuntimeSettings, "from_environ", broken)
    with pytest.raises(module.RuntimeConfigurationError):
        module.run(health_path=path)
    assert not check_worker_health(path=path)
    assert {sig: signal.getsignal(sig) for sig in original} == original


@pytest.mark.parametrize("failure", ["initialize", "connection", "close"])
def test_database_failure_closes_pool_and_restores_signals(tmp_path, monkeypatch, failure):
    import kordena_fiscal.runtime.worker_main as module

    original = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    closed = []

    class BrokenDatabase:
        def __init__(self, _dsn):
            pass

        def initialize(self):
            if failure == "initialize":
                raise RuntimeError("synthetic DB failure")

        def connection(self):
            if failure == "connection":
                raise RuntimeError("synthetic DB failure")
            return sqlite3.connect(":memory:")

        def close(self):
            closed.append(True)
            if failure == "close":
                raise RuntimeError("synthetic DB failure")

    settings = type(
        "Settings", (), {"persistence_backend": "postgres", "database_url": "synthetic"}
    )()
    monkeypatch.setattr(module.RuntimeSettings, "from_environ", lambda: settings)
    monkeypatch.setattr(module, "PostgresFiscalDatabase", BrokenDatabase)
    monkeypatch.setenv("NFCORE_WORKER_ONESHOT", "true")
    with pytest.raises(RuntimeError, match="synthetic DB failure"):
        module.run(health_path=tmp_path / "health")
    assert closed == [True]
    assert not check_worker_health(path=tmp_path / "health")
    assert {sig: signal.getsignal(sig) for sig in original} == original


@pytest.fixture
def process_env():
    dsn = os.environ.get("NFCORE_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("NFCORE_TEST_POSTGRES_DSN required for real process PostgreSQL proof")
    env = dict(os.environ)
    env.update(
        NFCORE_ENVIRONMENT="staging",
        NFCORE_PERSISTENCE_BACKEND="postgres",
        DATABASE_URL=dsn,
        NFCORE_SECRET_BACKEND="external",
        NFCORE_REQUIRE_HTTPS="true",
    )
    env.pop("NFCORE_WORKER_ONESHOT", None)
    subprocess.run([sys.executable, str(FIXTURE), "reset"], env=env, check=True, timeout=20)
    return env


def until(predicate, process=None, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        if process is not None:
            assert process.poll() is None, "worker exited before proof completed"
        time.sleep(0.05)
    raise AssertionError("process proof deadline exceeded")


def command(mode, path, state):
    return [sys.executable, str(FIXTURE), mode, str(path), str(state)]


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_real_continuous_idle_process_signal_exit_and_restart(process_env, tmp_path, sig):
    path = tmp_path / "health"
    for _ in range(2):
        process = subprocess.Popen(
            command("idle", path, tmp_path),
            env=process_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            until(lambda: check_worker_health(path=path), process)
            first = json.loads(path.read_text())["sampled_at"]
            until(
                lambda first=first: json.loads(path.read_text())["sampled_at"] > first + 1,
                process,
            )
            assert process.poll() is None
            process.send_signal(sig)
            assert process.wait(timeout=10) == 0
            assert not check_worker_health(path=path)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


@pytest.mark.parametrize("mode", ["oneshot", "unconfigured"])
def test_probe_or_missing_handlers_never_publish_continuous_ready(process_env, tmp_path, mode):
    path = tmp_path / "health"
    result = subprocess.run(
        command(mode, path, tmp_path),
        env=process_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=20,
    )
    assert (result.returncode == 0) is (mode == "oneshot")
    assert not check_worker_health(path=path)


def test_sigterm_during_real_dispatch_drains_batch_then_restart_finishes_without_replay(
    process_env, tmp_path
):
    path = tmp_path / "health"
    process = subprocess.Popen(
        command("drain", path, tmp_path),
        env=process_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        until(lambda: check_worker_health(path=path), process)
        subprocess.run(command("seed", path, tmp_path), env=process_env, check=True, timeout=20)
        until(lambda: (tmp_path / "dispatch_started").exists(), process)
        process.send_signal(signal.SIGTERM)
        until(lambda: not check_worker_health(path=path), process)
        assert process.poll() is None, "claimed batch must finish before graceful exit"
        (tmp_path / "release").touch()
        assert process.wait(timeout=15) == 0
        subprocess.run(
            command("verify_drained", path, tmp_path), env=process_env, check=True, timeout=20
        )
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    restarted = subprocess.Popen(
        command("restart", path, tmp_path),
        env=process_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        until(lambda: check_worker_health(path=path), restarted)
        subprocess.run(
            command("verify_finished", path, tmp_path), env=process_env, check=True, timeout=20
        )
        restarted.send_signal(signal.SIGTERM)
        assert restarted.wait(timeout=10) == 0
    finally:
        if restarted.poll() is None:
            restarted.kill()
            restarted.wait(timeout=5)
