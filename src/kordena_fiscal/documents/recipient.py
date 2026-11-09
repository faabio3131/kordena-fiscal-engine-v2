"""Immutable Brazilian recipient facts, distinct from fiscal classification rules."""

from dataclasses import dataclass

from kordena_fiscal.domain import Cnpj, Cpf, FiscalAddress, FiscalValidationError, StateRegistration


@dataclass(frozen=True, slots=True)
class FiscalRecipientSnapshot:
    document: Cnpj | Cpf
    name: str
    address: FiscalAddress
    ie_indicator: int
    final_consumer: bool
    state_registration: StateRegistration | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.document, (Cnpj, Cpf)):
            raise FiscalValidationError("recipient requires a validated CPF or CNPJ")
        if not isinstance(self.name, str) or not 2 <= len(self.name.strip()) <= 60:
            raise FiscalValidationError("recipient name requires 2 to 60 characters")
        object.__setattr__(self, "name", self.name.strip())
        if not isinstance(self.address, FiscalAddress):
            raise FiscalValidationError("recipient requires a complete fiscal address")
        if type(self.ie_indicator) is not int or self.ie_indicator not in {1, 2, 9}:
            raise FiscalValidationError("recipient IE indicator must be explicit: 1, 2 or 9")
        if type(self.final_consumer) is not bool:
            raise FiscalValidationError("recipient final consumer fact must be explicit")
        registration = self.state_registration
        if registration is not None and not isinstance(registration, StateRegistration):
            raise FiscalValidationError("recipient state registration has invalid type")
        if self.ie_indicator == 1 and (registration is None or registration.exempt):
            raise FiscalValidationError("taxpayer recipient requires a state registration")
        if registration is not None:
            if not isinstance(registration, StateRegistration):
                raise FiscalValidationError("recipient state registration has invalid type")
            if registration.state_code != self.address.jurisdiction.state_code:
                raise FiscalValidationError("recipient registration and address states differ")
            if self.ie_indicator == 2 and not registration.exempt:
                raise FiscalValidationError("exempt recipient cannot have a registration number")
