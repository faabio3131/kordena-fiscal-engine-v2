from concurrent.futures import ThreadPoolExecutor

import pytest

from kordena_fiscal.domain import (
    ElectronicInvoiceModel,
    ExecutionScope,
    FiscalEnvironment,
    FiscalValidationError,
)
from kordena_fiscal.numbering import (
    FiscalSequenceKey,
    FiscalSequenceManager,
    FiscalSequencePolicy,
    InMemoryFiscalSequenceStore,
    SequenceExhaustedError,
    SequenceStateError,
)


def _scope(
    *,
    tenant: str = "tenant-a",
    unit: str = "unit-a",
    environment: FiscalEnvironment = FiscalEnvironment.HOMOLOGATION,
    correlation: str = "corr-a",
) -> ExecutionScope:
    return ExecutionScope(
        tenant_id=tenant,
        unit_id=unit,
        environment=environment,
        correlation_id=correlation,
    )


def test_sequence_starts_at_one_and_advances_contiguously() -> None:
    store = InMemoryFiscalSequenceStore()
    manager = FiscalSequenceManager(store)

    first = manager.reserve(_scope(), model=ElectronicInvoiceModel.NFCE, series=1)
    second = manager.reserve(_scope(), model=ElectronicInvoiceModel.NFCE, series=1)

    assert first.number == 1
    assert second.number == 2
    assert first.reservation_token != second.reservation_token
    assert manager.last_reserved(
        _scope(), model=ElectronicInvoiceModel.NFCE, series=1
    ) == 2


def test_correlation_id_does_not_split_legal_sequence() -> None:
    store = InMemoryFiscalSequenceStore()
    manager = FiscalSequenceManager(store)

    first = manager.reserve(
        _scope(correlation="retry-1"),
        model=ElectronicInvoiceModel.NFCE,
        series=7,
    )
    second = manager.reserve(
        _scope(correlation="retry-2"),
        model=ElectronicInvoiceModel.NFCE,
        series=7,
    )

    assert (first.number, second.number) == (1, 2)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (_scope(tenant="tenant-a"), _scope(tenant="tenant-b")),
        (_scope(unit="unit-a"), _scope(unit="unit-b")),
        (
            _scope(environment=FiscalEnvironment.HOMOLOGATION),
            _scope(environment=FiscalEnvironment.PRODUCTION),
        ),
    ],
)
def test_sequence_is_isolated_by_scope(left: ExecutionScope, right: ExecutionScope) -> None:
    store = InMemoryFiscalSequenceStore()
    manager = FiscalSequenceManager(store)

    assert manager.reserve(left, model=ElectronicInvoiceModel.NFCE, series=1).number == 1
    assert manager.reserve(right, model=ElectronicInvoiceModel.NFCE, series=1).number == 1


def test_sequence_is_isolated_by_model_and_series() -> None:
    store = InMemoryFiscalSequenceStore()
    manager = FiscalSequenceManager(store)
    scope = _scope()

    assert manager.reserve(scope, model=ElectronicInvoiceModel.NFCE, series=1).number == 1
    assert manager.reserve(scope, model=ElectronicInvoiceModel.NFCE, series=2).number == 1
    assert manager.reserve(scope, model=ElectronicInvoiceModel.NFE, series=1).number == 1


def test_custom_policy_and_exhaustion_fail_closed() -> None:
    store = InMemoryFiscalSequenceStore()
    manager = FiscalSequenceManager(
        store,
        policy=FiscalSequencePolicy(first_number=100, max_number=101),
    )

    assert manager.reserve(_scope(), model=ElectronicInvoiceModel.NFCE, series=1).number == 100
    assert manager.reserve(_scope(), model=ElectronicInvoiceModel.NFCE, series=1).number == 101
    with pytest.raises(SequenceExhaustedError):
        manager.reserve(_scope(), model=ElectronicInvoiceModel.NFCE, series=1)


def test_policy_cannot_change_after_sequence_has_started() -> None:
    store = InMemoryFiscalSequenceStore()
    key = FiscalSequenceKey.from_scope(
        _scope(), model=ElectronicInvoiceModel.NFCE, series=1
    )

    store.reserve_next(key, FiscalSequencePolicy(first_number=10))
    with pytest.raises(SequenceStateError, match="cannot change"):
        store.reserve_next(key, FiscalSequencePolicy(first_number=11))


def test_128_concurrent_reservations_are_unique_and_contiguous() -> None:
    store = InMemoryFiscalSequenceStore()
    manager = FiscalSequenceManager(store)
    scope = _scope()

    def reserve_one(_: int) -> int:
        return manager.reserve(
            scope,
            model=ElectronicInvoiceModel.NFCE,
            series=42,
        ).number

    with ThreadPoolExecutor(max_workers=32) as executor:
        numbers = list(executor.map(reserve_one, range(128)))

    assert len(numbers) == 128
    assert len(set(numbers)) == 128
    assert sorted(numbers) == list(range(1, 129))


def test_reservation_token_is_deterministic_for_key_and_number() -> None:
    key = FiscalSequenceKey.from_scope(
        _scope(), model=ElectronicInvoiceModel.NFCE, series=1
    )
    first_store = InMemoryFiscalSequenceStore()
    second_store = InMemoryFiscalSequenceStore()

    first = first_store.reserve_next(key, FiscalSequencePolicy())
    second = second_store.reserve_next(key, FiscalSequencePolicy())

    assert first.number == second.number == 1
    assert first.reservation_token == second.reservation_token


def test_invalid_series_and_policy_are_rejected() -> None:
    with pytest.raises(FiscalValidationError, match="series"):
        FiscalSequenceKey.from_scope(
            _scope(), model=ElectronicInvoiceModel.NFCE, series=-1
        )
    with pytest.raises(FiscalValidationError, match="first_number"):
        FiscalSequencePolicy(first_number=0)
    with pytest.raises(FiscalValidationError, match="max_number"):
        FiscalSequencePolicy(first_number=10, max_number=9)
