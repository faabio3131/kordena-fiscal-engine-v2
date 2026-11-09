"""G0 contracts are pure values and cannot impersonate fiscal authority."""
from datetime import UTC, datetime

import pytest

from kordena_fiscal.domain import FiscalEnvironment
from kordena_fiscal.integrations.bling_contracts import (
    BlingInstallationState,
    BlingInstallationView,
    BlingOrderPage,
    BlingRecoveryOutcome,
    BlingRecoveryResult,
)


def test_installed_state_is_explicit_and_safe() -> None:
    assert {state.value for state in BlingInstallationState} == {
        "not_configured", "connected", "needs_reauth", "paused", "error"
    }
    view = BlingInstallationView(
        installation_id="i-1", company_id="c-1", tenant_id="t-1", unit_id="u-1",
        environment=FiscalEnvironment.HOMOLOGATION,
        state=BlingInstallationState.NEEDS_REAUTH, health_code="token_expired",
        credential_status="unavailable", updated_at=datetime.now(UTC), revision=2,
    )
    assert not any("token" in field for field in view.__dataclass_fields__)
    assert view.state is BlingInstallationState.NEEDS_REAUTH


def test_invalid_contracts_refuse_mutations() -> None:
    with pytest.raises(ValueError):
        BlingInstallationView(
            installation_id="", company_id="c", tenant_id="t", unit_id="u",
            environment=FiscalEnvironment.HOMOLOGATION,
            state=BlingInstallationState.CONNECTED, health_code="ready",
            credential_status="available", updated_at=datetime.now(UTC), revision=1,
        )
    with pytest.raises(ValueError):
        BlingOrderPage(rows=(), next_cursor=None, limit=101)
    with pytest.raises(ValueError):
        BlingRecoveryResult(
            operation_id="x", installation_id="i", order_id=0,
            outcome=BlingRecoveryOutcome.BLOCKED, correlation_id="c",
        )
