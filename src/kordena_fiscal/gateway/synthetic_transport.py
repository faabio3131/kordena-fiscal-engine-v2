"""Network-free provider transport used only for contracts and deterministic tests."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from kordena_fiscal.vault import EphemeralCscMaterial, EphemeralProviderCredentialsMaterial

from .provider import (
    ProviderRequest,
    ProviderResponseStatus,
    ProviderTransportError,
    ProviderTransportResponse,
)


@dataclass(frozen=True, slots=True)
class SyntheticTransportObservation:
    """Non-secret evidence captured by the synthetic transport."""

    provider_id: str
    operation: str
    tenant_id: str
    unit_id: str
    environment: str
    credentials_reference_id: str
    csc_reference_id: str | None
    payload_sha256: str


class SyntheticProviderTransport:
    """Deterministic transport with no socket or external endpoint access."""

    def __init__(self) -> None:
        self._responses: list[ProviderTransportResponse] = []
        self._errors: list[ProviderTransportError] = []
        self.observations: list[SyntheticTransportObservation] = []

    def queue_response(self, response: ProviderTransportResponse) -> None:
        self._responses.append(response)

    def queue_error(self, error: ProviderTransportError) -> None:
        self._errors.append(error)

    def exchange(
        self,
        *,
        provider_id: str,
        request: ProviderRequest,
        credentials: EphemeralProviderCredentialsMaterial,
        csc: EphemeralCscMaterial | None,
    ) -> ProviderTransportResponse:
        self.observations.append(
            SyntheticTransportObservation(
                provider_id=provider_id,
                operation=request.operation.value,
                tenant_id=request.scope.tenant_id,
                unit_id=request.scope.unit_id,
                environment=request.scope.environment.value,
                credentials_reference_id=credentials.reference_id,
                csc_reference_id=csc.reference_id if csc is not None else None,
                payload_sha256=sha256(request.payload).hexdigest(),
            )
        )
        if self._errors:
            raise self._errors.pop(0)
        if self._responses:
            return self._responses.pop(0)
        return ProviderTransportResponse(
            status=ProviderResponseStatus.ACCEPTED,
            provider_request_id="synthetic-request",
            external_reference="synthetic-reference",
        )
