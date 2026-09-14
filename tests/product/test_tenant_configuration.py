from decimal import Decimal

import pytest

from kordena_fiscal.product import (
    CommercialGatewayConfiguration,
    CommercialOfferConfiguration,
    DocumentKind,
    ExternalDependencyState,
    ExternalReference,
    FiscalChannelConfiguration,
    FiscalEnvironment,
    PricingMode,
    TenantConfigurationError,
    TenantConfigurationRegistry,
    TenantExternalConfiguration,
)


def missing() -> ExternalReference:
    return ExternalReference(None, ExternalDependencyState.MISSING)


def verified(name: str) -> ExternalReference:
    return ExternalReference(
        f"vault://{name}",
        ExternalDependencyState.VERIFIED,
        f"evidence://{name}",
    )


def configured(name: str) -> ExternalReference:
    return ExternalReference(f"vault://{name}", ExternalDependencyState.CONFIGURED)


def nfe_channel(*, homologation_verified: bool = True) -> FiscalChannelConfiguration:
    return FiscalChannelConfiguration(
        channel_id="sp-nfe-prod",
        document_kind=DocumentKind.NFE,
        environment=FiscalEnvironment.PRODUCTION,
        provider_profile_id="sefaz-sp-direct-v1",
        uf="sp",
        municipality_code=None,
        certificate=verified("cert/client-a"),
        csc_identifier=missing(),
        csc_token=missing(),
        provider_credentials=verified("provider/client-a"),
        official_homologation=(
            verified("homologation/sp-nfe")
            if homologation_verified
            else configured("homologation/sp-nfe")
        ),
    )


def tenant_config(
    *,
    version: int = 1,
    homologation_verified: bool = True,
    production_verified: bool = True,
) -> TenantExternalConfiguration:
    activation = (
        verified("activation/client-a")
        if production_verified
        else configured("activation/client-a")
    )
    return TenantExternalConfiguration(
        configuration_id=f"tenant-a-v{version}",
        version=version,
        tenant_id="tenant-a",
        company_id="company-a",
        unit_id="unit-a",
        channels=(nfe_channel(homologation_verified=homologation_verified),),
        gateway=CommercialGatewayConfiguration(
            gateway_profile_id="gateway-neutral-v1",
            account_reference=configured("billing/account-a"),
            webhook_secret_reference=configured("billing/webhook-a"),
        ),
        offer=CommercialOfferConfiguration(
            offer_id="growth-brl",
            edition_id="growth",
            pricing_mode=PricingMode.PER_DOCUMENT,
            currency="brl",
            base_amount=Decimal("149.90"),
            per_document_amount=Decimal("0.08"),
            external_price_reference="pricing://growth-brl-v1",
        ),
        legal_approval=verified("legal/terms-v1"),
        pilot_approval=verified("pilot/client-a"),
        production_activation=activation,
    )


def test_supported_customer_onboarding_requires_no_code_change() -> None:
    configuration = tenant_config()

    assert configuration.requires_code_change is False
    assert configuration.production_ready is True
    assert configuration.channels[0].uf == "SP"
    assert configuration.offer is not None
    assert configuration.offer.currency == "BRL"


def test_configuration_does_not_fake_external_readiness() -> None:
    configuration = tenant_config(homologation_verified=False)

    assert configuration.production_ready is False
    assert configuration.channels[0].externally_ready is False


def test_production_activation_is_an_explicit_external_gate() -> None:
    configuration = tenant_config(production_verified=False)

    assert configuration.production_ready is False


def test_verified_reference_requires_evidence() -> None:
    with pytest.raises(TenantConfigurationError, match="evidence_reference"):
        ExternalReference("vault://cert/client-a", ExternalDependencyState.VERIFIED)


def test_nfce_requires_csc_references_for_external_readiness() -> None:
    channel = FiscalChannelConfiguration(
        channel_id="sp-nfce-prod",
        document_kind=DocumentKind.NFCE,
        environment=FiscalEnvironment.PRODUCTION,
        provider_profile_id="sefaz-sp-direct-v1",
        uf="SP",
        municipality_code=None,
        certificate=verified("cert/client-a"),
        csc_identifier=configured("csc/id/client-a"),
        csc_token=configured("csc/token/client-a"),
        provider_credentials=verified("provider/client-a"),
        official_homologation=verified("homologation/sp-nfce"),
    )

    assert channel.externally_ready is False


def test_non_nfce_channel_rejects_csc_configuration() -> None:
    with pytest.raises(TenantConfigurationError, match="CSC identifier"):
        FiscalChannelConfiguration(
            channel_id="sp-nfe-prod",
            document_kind=DocumentKind.NFE,
            environment=FiscalEnvironment.PRODUCTION,
            provider_profile_id="sefaz-sp-direct-v1",
            uf="SP",
            municipality_code=None,
            certificate=verified("cert/client-a"),
            csc_identifier=configured("csc/id/client-a"),
            csc_token=missing(),
            provider_credentials=verified("provider/client-a"),
            official_homologation=verified("homologation/sp-nfe"),
        )


def test_registry_is_versioned_and_conflict_safe() -> None:
    registry = TenantConfigurationRegistry()
    first = tenant_config(version=1)
    registry.upsert(first, expected_version=None)

    second = tenant_config(version=2)
    registry.upsert(second, expected_version=1)

    assert registry.get("tenant-a", "unit-a") == second
    with pytest.raises(TenantConfigurationError, match="version conflict"):
        registry.upsert(tenant_config(version=3), expected_version=1)


def test_price_is_configuration_not_source_code_decision() -> None:
    offer = tenant_config().offer

    assert offer is not None
    assert offer.base_amount == Decimal("149.90")
    assert offer.per_document_amount == Decimal("0.08")
    assert offer.external_price_reference == "pricing://growth-brl-v1"


def test_from_mapping_supports_customer_specific_external_configuration() -> None:
    payload = {
        "configuration_id": "tenant-b-v1",
        "version": 1,
        "tenant_id": "tenant-b",
        "company_id": "company-b",
        "unit_id": "unit-b",
        "channels": [
            {
                "channel_id": "nfse-city-prod",
                "document_kind": "nfse",
                "environment": "production",
                "provider_profile_id": "nfse-national-v1",
                "uf": "SP",
                "municipality_code": "3550308",
                "certificate": {
                    "state": "configured",
                    "reference_id": "vault://cert/client-b",
                },
                "csc_identifier": {"state": "missing"},
                "csc_token": {"state": "missing"},
                "provider_credentials": {
                    "state": "configured",
                    "reference_id": "vault://provider/client-b",
                },
                "official_homologation": {"state": "missing"},
            }
        ],
        "gateway": None,
        "offer": {
            "offer_id": "enterprise-custom",
            "edition_id": "enterprise",
            "pricing_mode": "custom",
            "currency": "BRL",
            "external_price_reference": "crm://proposal/client-b",
        },
        "legal_approval": {"state": "missing"},
        "pilot_approval": {"state": "missing"},
        "production_activation": {"state": "missing"},
    }

    configuration = TenantExternalConfiguration.from_mapping(payload)

    assert configuration.requires_code_change is False
    assert configuration.production_ready is False
    assert configuration.channels[0].municipality_code == "3550308"
