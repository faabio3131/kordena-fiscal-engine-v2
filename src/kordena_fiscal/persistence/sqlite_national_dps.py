"""National DPS numbering isolated from fiscal model 55/65 and municipal RPS.

The unique legal sequence is shared by all authorized units using the same
issuer CNPJ within the same host and fiscal environment, so changing a unit
never recycles a DPS number for that legal issuer and series. Caller tenant/
unit still belong to the reservation token and durable fiscal document.
"""
from __future__ import annotations

import hashlib
import sqlite3

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.numbering import (
    FiscalNumberReservation,
    FiscalSequenceKey,
    FiscalSequencePolicy,
    InternalFiscalSequenceStream,
    SequenceExhaustedError,
    SequenceStateError,
)

from ._sqlite_common import host_key, integer, one_row


class SqliteNationalDpsSequenceStore:
    """One atomic DPS counter per host, environment, CNPJ and series."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @staticmethod
    def identity(key: FiscalSequenceKey) -> tuple[str, str, str, int]:
        if (
            not isinstance(key, FiscalSequenceKey)
            or key.model is not InternalFiscalSequenceStream.NFSE_DPS
            or key.issuer_cnpj is None
            or key.host_namespace is None
            or not 0 <= key.series <= 99999
        ):
            raise FiscalValidationError("Dedicated DPS sequence requires exact issuer key")
        return (
            host_key(key.host_namespace),
            key.environment.value,
            key.issuer_cnpj,
            key.series,
        )

    def reserve_next(
        self, key: FiscalSequenceKey, policy: FiscalSequencePolicy,
    ) -> FiscalNumberReservation:
        if not isinstance(policy, FiscalSequencePolicy):
            raise FiscalValidationError("DPS requires a valid sequence policy")
        identity = self.identity(key)
        row = one_row(self._connection.execute(
            """SELECT first_number, max_number, last_reserved
               FROM fm_nfse_dps_sequences
               WHERE host_namespace = ? AND environment = ?
                 AND issuer_cnpj = ? AND series = ?""",
            identity,
        ))
        if row is None:
            number = policy.first_number
            if policy.max_number is not None and number > policy.max_number:
                raise SequenceExhaustedError("National DPS sequence exhausted")
            self._connection.execute(
                """INSERT INTO fm_nfse_dps_sequences (
                     host_namespace, environment, issuer_cnpj, series,
                     first_number, max_number, last_reserved
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (*identity, policy.first_number, policy.max_number, number),
            )
        else:
            first = integer(row[0], "first_number")
            maximum = None if row[1] is None else integer(row[1], "max_number")
            if first != policy.first_number or maximum != policy.max_number:
                raise SequenceStateError("National DPS sequence policy changed")
            number = integer(row[2], "last_reserved") + 1
            if policy.max_number is not None and number > policy.max_number:
                raise SequenceExhaustedError("National DPS sequence exhausted")
            self._connection.execute(
                """UPDATE fm_nfse_dps_sequences SET last_reserved = ?
                   WHERE host_namespace = ? AND environment = ?
                     AND issuer_cnpj = ? AND series = ?""",
                (number, *identity),
            )
        token = hashlib.sha256(
            f"{key.canonical_material}|{number}".encode()
        ).hexdigest()
        return FiscalNumberReservation(key=key, number=number, reservation_token=token)

    def last_reserved(self, key: FiscalSequenceKey) -> int | None:
        identity = self.identity(key)
        row = one_row(self._connection.execute(
            """SELECT last_reserved FROM fm_nfse_dps_sequences
               WHERE host_namespace = ? AND environment = ?
                 AND issuer_cnpj = ? AND series = ?""",
            identity,
        ))
        return None if row is None else integer(row[0], "last_reserved")
