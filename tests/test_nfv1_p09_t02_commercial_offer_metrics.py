"""P09-T02: observe public offer readiness without fabricating purchase events."""

import asyncio
from types import SimpleNamespace

from fastapi import Response

from kordena_fiscal.runtime.observability import MetricsRegistry
from kordena_fiscal.web.commercial_release import create_commercial_release_router


def test_blocked_commercial_offer_is_observed_without_purchase_event() -> None:
    metrics = MetricsRegistry()
    router = create_commercial_release_router(
        identity=SimpleNamespace(),
        pricing=SimpleNamespace(current=None),
        release=SimpleNamespace(current=None),
        runtime_metrics=metrics,
    )
    endpoint = next(
        route.endpoint for route in router.routes
        if route.path == "/v1/commercial/offer"
    )
    payload = asyncio.run(endpoint(Response()))
    assert payload["purchase_enabled"] is False
    values = metrics.as_dicts()
    assert any(
        item["name"] == "nfcore_commercial_offer_observed_total"
        and item["labels"] == {"outcome": "blocked"}
        and item["value"] == 1
        for item in values
    )
    assert not any("purchase_completed" in item["name"] for item in values)


def test_commercial_offer_metrics_failure_preserves_blocked_offer() -> None:
    class BrokenMetrics(MetricsRegistry):
        def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
            raise RuntimeError("metrics offline")

    router = create_commercial_release_router(
        identity=SimpleNamespace(),
        pricing=SimpleNamespace(current=None),
        release=SimpleNamespace(current=None),
        runtime_metrics=BrokenMetrics(),
    )
    endpoint = next(
        route.endpoint for route in router.routes
        if route.path == "/v1/commercial/offer"
    )
    assert asyncio.run(endpoint(Response()))["purchase_enabled"] is False
