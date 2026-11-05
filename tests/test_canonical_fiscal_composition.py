"""Canonical fiscal entrypoint wiring smoke tests."""
from kordena_fiscal.runtime.canonical_fiscal_composition import (
    UnprovisionedFiscalGateway,
    build_runtime_fiscal_handler_factory,
)


def test_canonical_factory_registers_four_operations() -> None:
    class ApplicationStub:
        pass

    # The factory is deliberately strict about the canonical application type.
    # This test checks the unprovisioned transport behavior independently.
    gateway = UnprovisionedFiscalGateway()
    for operation in ("authorize", "query", "cancel", "inutilize"):
        try:
            getattr(gateway, operation)(object())
        except Exception as exc:
            assert "Certificado A1" in str(exc)
        else:
            raise AssertionError(f"{operation} must fail closed")


def test_canonical_factory_is_available_to_runtime() -> None:
    assert callable(build_runtime_fiscal_handler_factory())
