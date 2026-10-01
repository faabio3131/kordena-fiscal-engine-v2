"""Password-recovery HTTP boundary for the NFCORE customer journey.

Reset delivery is injected explicitly. The public request endpoint always returns the same
accepted response for eligible and unknown accounts so account existence is not disclosed.
Raw reset tokens are handed only to the delivery adapter and are never returned to browsers.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any, Protocol, runtime_checkable

from fastapi import APIRouter, Body, HTTPException, status

from kordena_fiscal.security.human_identity import (
    HumanAuthenticationError,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    PasswordPolicyError,
)
from kordena_fiscal.security.human_recovery import (
    IssuedPasswordReset,
    PasswordRecoveryService,
)


@runtime_checkable
class PasswordResetDelivery(Protocol):
    """External delivery port; production implementations may enqueue email/SMS delivery."""

    def deliver(
        self,
        *,
        email: str,
        reset: IssuedPasswordReset,
    ) -> None: ...


def create_password_recovery_router(
    recovery: PasswordRecoveryService,
    *,
    delivery: PasswordResetDelivery | None,
    on_completed: Callable[[str, datetime], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> APIRouter:
    """Expose recovery without leaking account existence or reset tokens."""

    now_provider = now or (lambda: datetime.now(UTC))
    router = APIRouter(prefix="/v1/auth/password-reset", tags=["human-auth"])

    @router.post("/request", status_code=status.HTTP_202_ACCEPTED)
    async def request_reset(
        payload: Annotated[dict[str, Any], Body()],
    ) -> dict[str, str]:
        email = payload.get("email")
        if not isinstance(email, str) or not email.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_PASSWORD_RESET_REQUEST",
                    "message": "Email is required",
                },
            )

        # Do not create an undeliverable token when the external delivery adapter has
        # not been configured. The public response remains generic to avoid enumeration.
        if delivery is None:
            return {"status": "accepted"}

        reset = recovery.request_reset(email=email, now=now_provider())
        if reset is not None:
            try:
                delivery.deliver(email=email.strip().casefold(), reset=reset)
            except Exception:
                # Delivery health belongs to the external adapter/observability boundary.
                # Returning a different status only for real accounts would disclose
                # account existence, so the public response remains indistinguishable.
                pass
        return {"status": "accepted"}

    @router.post("/complete", status_code=status.HTTP_204_NO_CONTENT)
    async def complete_reset(
        payload: Annotated[dict[str, Any], Body()],
    ) -> None:
        reset_token = payload.get("reset_token")
        new_password = payload.get("new_password")
        if not isinstance(reset_token, str) or not isinstance(new_password, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_PASSWORD_RESET",
                    "message": "Reset token and new password are required",
                },
            )
        instant = now_provider()
        try:
            account_id = recovery.complete_reset(
                reset_token=reset_token,
                new_password=new_password,
                now=instant,
            )
        except PasswordPolicyError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "PASSWORD_POLICY_INVALID",
                    "message": (
                        "A senha deve ter entre "
                        f"{PASSWORD_MIN_LENGTH} e {PASSWORD_MAX_LENGTH} caracteres."
                    ),
                },
            ) from exc
        except HumanAuthenticationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "PASSWORD_RESET_NOT_USABLE",
                    "message": (
                        "Este link de recuperação não é mais válido. "
                        "Solicite um novo link e use somente o e-mail mais recente."
                    ),
                },
            ) from exc
        if on_completed is not None:
            try:
                on_completed(account_id, instant)
            except Exception:
                # Credential activation has already completed successfully. Commercial
                # projection can be reconciled/retried without making the password result
                # ambiguous to the human user.
                pass
        return None

    return router
