"""SQLite implementation of the certified issuance-idempotency contract."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from typing import cast

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.lifecycle import (
    IdempotencyConflictError,
    IdempotencyKey,
    IdempotencyReservation,
    IdempotencyStateError,
    IssuanceAttempt,
    IssuanceAttemptStatus,
)

from ._sqlite_common import integer, one_row, optional_text, text


class SqliteIdempotencyStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @staticmethod
    def _attempt(row: tuple[object, ...]) -> IssuanceAttempt:
        return IssuanceAttempt(
            key=IdempotencyKey(text(row[0], "key")),
            generation=integer(row[1], "generation"),
            request_fingerprint=text(row[2], "request_fingerprint"),
            document_id=text(row[3], "document_id"),
            status=IssuanceAttemptStatus(text(row[4], "status")),
            result_reference=optional_text(row[5], "result_reference"),
            rejection_reason=optional_text(row[6], "rejection_reason"),
        )

    def _latest(self, key: IdempotencyKey) -> IssuanceAttempt | None:
        row = one_row(
            self._connection.execute(
                """
                SELECT key, generation, request_fingerprint, document_id, status,
                       result_reference, rejection_reason
                FROM fm_idempotency_attempts
                WHERE key = ?
                ORDER BY generation DESC
                LIMIT 1
                """,
                (key.value,),
            )
        )
        return None if row is None else self._attempt(row)

    def reserve(
        self,
        key: IdempotencyKey,
        request_fingerprint: str,
        document_id: str,
    ) -> IdempotencyReservation:
        if not isinstance(key, IdempotencyKey):
            raise FiscalValidationError("key must be IdempotencyKey")
        latest = self._latest(key)
        if latest is None:
            attempt = IssuanceAttempt(
                key=key,
                generation=1,
                request_fingerprint=request_fingerprint,
                document_id=document_id,
            )
            self._insert(attempt)
            return IdempotencyReservation(attempt=attempt, replay=False)
        if latest.request_fingerprint == request_fingerprint:
            return IdempotencyReservation(attempt=latest, replay=True)
        if latest.status is not IssuanceAttemptStatus.REJECTED:
            raise IdempotencyConflictError(
                "issuance intent already exists with different content and is not safely rejected"
            )
        attempt = IssuanceAttempt(
            key=key,
            generation=latest.generation + 1,
            request_fingerprint=request_fingerprint,
            document_id=document_id,
        )
        self._insert(attempt)
        return IdempotencyReservation(attempt=attempt, replay=False)

    def _insert(self, attempt: IssuanceAttempt) -> None:
        self._connection.execute(
            """
            INSERT INTO fm_idempotency_attempts (
                key, generation, request_fingerprint, document_id, status,
                result_reference, rejection_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt.key.value,
                attempt.generation,
                attempt.request_fingerprint,
                attempt.document_id,
                attempt.status.value,
                attempt.result_reference,
                attempt.rejection_reason,
            ),
        )

    def mark_authorized(
        self,
        key: IdempotencyKey,
        generation: int,
        result_reference: str,
    ) -> IssuanceAttempt:
        reference = result_reference.strip()
        if not reference:
            raise FiscalValidationError("result_reference must not be blank")
        latest = self._latest_for_update(key, generation)
        if latest.status is IssuanceAttemptStatus.AUTHORIZED:
            if latest.result_reference != reference:
                raise IdempotencyStateError("authorized attempt cannot change result_reference")
            return latest
        if latest.status is not IssuanceAttemptStatus.RESERVED:
            raise IdempotencyStateError("only reserved attempt can become authorized")
        updated = replace(
            latest,
            status=IssuanceAttemptStatus.AUTHORIZED,
            result_reference=reference,
        )
        self._connection.execute(
            """
            UPDATE fm_idempotency_attempts
            SET status = ?, result_reference = ?, rejection_reason = NULL
            WHERE key = ? AND generation = ?
            """,
            (updated.status.value, reference, key.value, generation),
        )
        return updated

    def mark_rejected(
        self,
        key: IdempotencyKey,
        generation: int,
        rejection_reason: str,
    ) -> IssuanceAttempt:
        reason = rejection_reason.strip()
        if not reason:
            raise FiscalValidationError("rejection_reason must not be blank")
        latest = self._latest_for_update(key, generation)
        if latest.status is IssuanceAttemptStatus.REJECTED:
            if latest.rejection_reason != reason:
                raise IdempotencyStateError("rejected attempt cannot change rejection_reason")
            return latest
        if latest.status is not IssuanceAttemptStatus.RESERVED:
            raise IdempotencyStateError("only reserved attempt can become rejected")
        updated = replace(
            latest,
            status=IssuanceAttemptStatus.REJECTED,
            rejection_reason=reason,
        )
        self._connection.execute(
            """
            UPDATE fm_idempotency_attempts
            SET status = ?, rejection_reason = ?, result_reference = NULL
            WHERE key = ? AND generation = ?
            """,
            (updated.status.value, reason, key.value, generation),
        )
        return updated

    def attempts(self, key: IdempotencyKey) -> tuple[IssuanceAttempt, ...]:
        rows = self._connection.execute(
            """
            SELECT key, generation, request_fingerprint, document_id, status,
                   result_reference, rejection_reason
            FROM fm_idempotency_attempts
            WHERE key = ?
            ORDER BY generation
            """,
            (key.value,),
        ).fetchall()
        return tuple(self._attempt(cast(tuple[object, ...], row)) for row in rows)

    def _latest_for_update(self, key: IdempotencyKey, generation: int) -> IssuanceAttempt:
        latest = self._latest(key)
        if latest is None:
            raise IdempotencyStateError("idempotency key has no reserved attempt")
        if latest.generation != generation:
            raise IdempotencyStateError("only the latest generation can be updated")
        return latest
