"""P09-T02: HTTP metrics must remain bounded and non-authoritative."""

from fastapi.testclient import TestClient

from kordena_fiscal.runtime.observability import MetricsRegistry
from kordena_fiscal.web.app import _metric_http_method, create_app


def test_metric_http_method_is_bounded() -> None:
    assert _metric_http_method("GET") == "GET"
    assert _metric_http_method("TENANT_PRIVATE") == "OTHER"


def test_http_metrics_count_latency_and_status_without_identifiers() -> None:
    metrics = MetricsRegistry()
    with TestClient(create_app(runtime_metrics=metrics)) as client:
        response = client.get("/health/live", headers={"Authorization": "Bearer private-token"})
        missing = client.get("/private-tenant-unknown")
    assert response.status_code == 200
    assert missing.status_code == 404
    samples = metrics.as_dicts()
    assert any(
        item["name"] == "nfcore_http_requests_total"
        and item["labels"] == {"method": "GET", "status_class": "2xx"}
        and item["value"] == 1
        for item in samples
    )
    assert any(
        item["name"] == "nfcore_http_requests_total"
        and item["labels"] == {"method": "GET", "status_class": "4xx"}
        and item["value"] == 1
        for item in samples
    )
    assert any(
        item["name"] == "nfcore_http_request_count" and item["value"] == 1
        for item in samples
    )
    assert all(item["value"] >= 0 for item in samples)
    assert "private" not in str(samples)
    assert "token" not in str(samples)


def test_http_telemetry_failure_does_not_change_response() -> None:
    class BrokenMetrics(MetricsRegistry):
        def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
            raise RuntimeError("telemetry unavailable")

    with TestClient(create_app(runtime_metrics=BrokenMetrics())) as client:
        assert client.get("/health/live").status_code == 200
