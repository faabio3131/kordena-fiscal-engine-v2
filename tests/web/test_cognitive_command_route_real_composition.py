"""Proves the Command cognitive metrics route survives the REAL app composition.

PR #380 fixed kordena_fiscal.cognitive.composition.build_cognitive_router so it
always returns a router containing the Command metrics sub-route, even without
human_identity/portal_executor or NFCORE_COGNITIVE_ENABLED. But kordena_fiscal.web
create_app() used to mount that whole router only inside `if human_identity is not
None:`, which silently dropped it again whenever human_identity ended up None in
the real application (e.g. no PostgreSQL composition) -- exactly the case that
produced the 404 Command observed. This test exercises create_app() itself, not
the isolated router, to certify the fix at the composition that actually runs in
production.
"""

from fastapi.testclient import TestClient

from kordena_fiscal.cognitive.composition import build_cognitive_router
from kordena_fiscal.web import create_app


def test_command_metrics_route_survives_real_app_composition_without_human_identity() -> None:
    cognitive_router = build_cognitive_router(None, None, {})
    assert cognitive_router is not None

    app = create_app(human_identity=None, cognitive_router=cognitive_router)
    client = TestClient(app)

    response = client.get("/v1/command/cognitive/metrics")

    # The route must exist in the real app (no 404). Auth/config failure (401/503)
    # is acceptable here since no Command token is configured in this test; what
    # matters is that the route is routable at all, matching what PR #380 fixed
    # inside build_cognitive_router and what this test additionally certifies at
    # the create_app() composition level.
    assert response.status_code != 404


def test_advisory_route_still_absent_from_real_app_without_human_identity() -> None:
    cognitive_router = build_cognitive_router(None, None, {})
    assert cognitive_router is not None

    app = create_app(human_identity=None, cognitive_router=cognitive_router)
    client = TestClient(app)

    response = client.post("/v1/portal/cognitive/advise", json={})

    assert response.status_code == 404
