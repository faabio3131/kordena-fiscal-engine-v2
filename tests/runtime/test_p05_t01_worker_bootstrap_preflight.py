"""Fail-closed preflight for the actual continuous Worker entrypoint.

This is internal synthetic certification: no Railway process, Google Cloud account,
real secret, schema mutation or transport is exercised by these tests.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from kordena_fiscal.runtime import worker_main
from kordena_fiscal.runtime.worker_health import check_worker_health
from kordena_fiscal.runtime.config import RuntimeConfigurationError
from kordena_fiscal.runtime.worker_composition import WorkerWebhookDependencies
from kordena_fiscal.security import InMemoryWebhookKeyRing, WebhookSecurity


def _valid_webhook() -> WorkerWebhookDependencies:
    ring = InMemoryWebhookKeyRing(
        active_key_id="synthetic",
        keys={"synthetic": b"synthetic-only-never-a-cloud-credential" * 2},
    )
    return WorkerWebhookDependencies(
        security=WebhookSecurity(key_resolver=ring, signing_key_id="synthetic"),
        destination_id="events",
    )


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        ("absent", "explicitly configured handler factory"),
        ("ambiguous", "one handler composition source"),
        ("invalid_factory", "handler factory is invalid"),
        ("invalid_webhook", "webhook signing dependencies are invalid"),
    ],
)
def test_unconfigured_worker_rejects_before_database_open(
    tmp_path, monkeypatch, kind: str, message: str
) -> None:
    settings = SimpleNamespace(
        persistence_backend="postgres",
        database_url="postgresql://synthetic.invalid/not-used",
        is_production_like=True,
    )
    monkeypatch.setattr(worker_main.RuntimeSettings, "from_environ", lambda: settings)
    monkeypatch.delenv("NFCORE_WORKER_ONESHOT", raising=False)
    database_calls: list[str] = []

    class ForbiddenDatabase:
        def __init__(self, _dsn: str) -> None:
            database_calls.append("opened")
            raise AssertionError("a rejected Worker must not open PostgreSQL")

    monkeypatch.setattr(worker_main, "PostgresFiscalDatabase", ForbiddenDatabase)
    def factory(_db, _settings):
        return {}
    if kind == "ambiguous":
        kwargs = {"handler_factory": factory, "webhook": _valid_webhook()}
    elif kind == "invalid_factory":
        kwargs = {"handler_factory": object()}
    elif kind == "invalid_webhook":
        kwargs = {"webhook": object()}
    else:
        kwargs = {}

    with pytest.raises(RuntimeConfigurationError, match=message):
        worker_main.run(health_path=tmp_path / "worker-health", **kwargs)
    assert database_calls == []
    assert not (tmp_path / "worker-health").exists() or (
        not check_worker_health(path=tmp_path / "worker-health")
    )


def test_explicit_continuous_handler_factory_reaches_database_gate(
    tmp_path, monkeypatch
) -> None:
    settings = SimpleNamespace(
        persistence_backend="postgres",
        database_url="postgresql://synthetic.invalid/not-used",
        is_production_like=True,
    )
    monkeypatch.setattr(worker_main.RuntimeSettings, "from_environ", lambda: settings)
    monkeypatch.delenv("NFCORE_WORKER_ONESHOT", raising=False)
    calls: list[str] = []

    class DatabaseSentinel:
        def __init__(self, _dsn: str) -> None:
            calls.append("entered")
            raise LookupError("synthetic database sentinel")

    monkeypatch.setattr(worker_main, "PostgresFiscalDatabase", DatabaseSentinel)
    with pytest.raises(LookupError, match="synthetic database sentinel"):
        worker_main.run(
            handler_factory=lambda _db, _settings: {},
            health_path=tmp_path / "worker-health",
        )
    assert calls == ["entered"]
