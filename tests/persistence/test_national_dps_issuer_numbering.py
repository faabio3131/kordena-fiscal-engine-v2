"""Isolated, issuer-keyed National DPS numbering and rollback regression."""
from __future__ import annotations

from dataclasses import replace

import pytest

from kordena_fiscal.domain import ExecutionScope, FiscalEnvironment, FiscalValidationError
from kordena_fiscal.numbering import (
    FiscalSequenceKey,
    FiscalSequencePolicy,
    InternalFiscalSequenceStream,
    SequenceExhaustedError,
)
from kordena_fiscal.persistence import SqliteFiscalDatabase

_CNPJ_A = "11222333000181"
_CNPJ_B = "12345678000195"


def _key(
    *, unit: str = "unit-a", tenant: str = "tenant-a",
    cnpj: str | None = _CNPJ_A, series: int = 1,
    environment: FiscalEnvironment = FiscalEnvironment.HOMOLOGATION,
) -> FiscalSequenceKey:
    return FiscalSequenceKey.from_scope(
        ExecutionScope(
            tenant, unit, environment, "corr-dps", "fm-nfcore",
        ),
        model=InternalFiscalSequenceStream.NFSE_DPS,
        series=series,
        issuer_cnpj=cnpj,
    )


def test_dps_counter_is_shared_by_same_issuer_across_units_not_other_issuer(tmp_path) -> None:
    db = SqliteFiscalDatabase(tmp_path / "numbering.sqlite")
    assert 6 in db.initialize()
    policy = FiscalSequencePolicy(max_number=1000)
    with db() as uow:
        one = uow.dps_sequences.reserve_next(_key(), policy)
        two = uow.dps_sequences.reserve_next(_key(unit="unit-b"), policy)
        three = uow.dps_sequences.reserve_next(_key(tenant="tenant-b"), policy)
        four = uow.dps_sequences.reserve_next(_key(cnpj=_CNPJ_B), policy)
        other_series = uow.dps_sequences.reserve_next(_key(series=2), policy)
        other_environment = uow.dps_sequences.reserve_next(
            _key(environment=FiscalEnvironment.PRODUCTION), policy,
        )
        uow.commit()
    assert [one.number, two.number, three.number, four.number] == [1, 2, 3, 1]
    assert other_series.number == 1
    assert other_environment.number == 1
    assert len({one.reservation_token, two.reservation_token, three.reservation_token}) == 3
    reopened = SqliteFiscalDatabase(db.path)
    with reopened() as uow:
        assert uow.dps_sequences.last_reserved(_key(unit="new-unit")) == 3
        assert uow.dps_sequences.last_reserved(_key(cnpj=_CNPJ_B)) == 1
        assert uow.sequences.last_reserved(
            FiscalSequenceKey.from_scope(
                ExecutionScope(
                    "tenant-a", "unit-a", FiscalEnvironment.HOMOLOGATION, "corr", "fm-nfcore"
                ), model=InternalFiscalSequenceStream.NFSE_RPS, series=1,
            )
        ) is None


def test_dps_rollback_does_not_consume_number(tmp_path) -> None:
    db = SqliteFiscalDatabase(tmp_path / "rollback.sqlite")
    db.initialize()
    with db() as uow:
        first = uow.dps_sequences.reserve_next(
            _key(), FiscalSequencePolicy(max_number=2),
        )
        assert first.number == 1
        # No commit: atomic rollback of the attempted reservation.
    with db() as uow:
        first = uow.dps_sequences.reserve_next(
            _key(), FiscalSequencePolicy(max_number=2),
        )
        assert first.number == 1
        uow.commit()
    with db() as uow:
        second = uow.dps_sequences.reserve_next(
            _key(), FiscalSequencePolicy(max_number=2),
        )
        assert second.number == 2
        uow.commit()
    with db() as uow:
        with pytest.raises(SequenceExhaustedError):
            uow.dps_sequences.reserve_next(
                _key(), FiscalSequencePolicy(max_number=2),
            )


def test_generic_nfse_dps_sequence_is_rejected_and_legacy_stream_is_unchanged(tmp_path) -> None:
    db = SqliteFiscalDatabase(tmp_path / "legacy.sqlite")
    db.initialize()
    key = _key()
    with db() as uow:
        with pytest.raises(FiscalValidationError, match="dedicated CNPJ"):
            uow.sequences.reserve_next(key, FiscalSequencePolicy())
        old_key = FiscalSequenceKey.from_scope(
            ExecutionScope(
                "tenant-a", "unit-a", FiscalEnvironment.HOMOLOGATION,
                "corr", "fm-nfcore",
            ), model=InternalFiscalSequenceStream.NFSE_RPS, series=1,
        )
        assert uow.sequences.reserve_next(
            old_key, FiscalSequencePolicy(),
        ).number == 1
        uow.commit()


@pytest.mark.parametrize("cnpj", [None, "", "123", "ABCDEFGHIJKLMN"])
def test_dps_key_rejects_invalid_issuer(cnpj: str | None) -> None:
    with pytest.raises(FiscalValidationError, match="issuer CNPJ"):
        _key(cnpj=cnpj)


def test_issuer_field_cannot_be_added_to_nfse_rps() -> None:
    with pytest.raises(FiscalValidationError, match="only allowed"):
        replace(_key(), model=InternalFiscalSequenceStream.NFSE_RPS)
