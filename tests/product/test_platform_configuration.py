import pytest

from kordena_fiscal.product import (
    ExternalDependencyState,
    ExternalReference,
    PlatformExternalConfiguration,
    TenantConfigurationError,
)


def missing() -> ExternalReference:
    return ExternalReference(None, ExternalDependencyState.MISSING)


def configured(name: str) -> ExternalReference:
    return ExternalReference(f"external://{name}", ExternalDependencyState.CONFIGURED)


def verified(name: str) -> ExternalReference:
    return ExternalReference(
        f"external://{name}",
        ExternalDependencyState.VERIFIED,
        f"evidence://{name}",
    )


def test_platform_external_items_are_configuration_driven() -> None:
    configuration = PlatformExternalConfiguration(
        configuration_id="fm-fiscal-prod-v1",
        version=1,
        deployment_profile_id="aws-managed-v1",
        public_base_url="https://fiscal.fmtecnologia.example",
        cloud_account=configured("cloud/account"),
        dns_control=configured("dns/fiscal"),
        secret_backend=configured("secrets/primary"),
        commercial_gateway_account=configured("gateway/account"),
        production_activation=missing(),
    )

    assert configuration.production_ready is False
    assert configuration.public_base_url == "https://fiscal.fmtecnologia.example"


def test_platform_production_ready_requires_verified_external_evidence() -> None:
    configuration = PlatformExternalConfiguration(
        configuration_id="fm-fiscal-prod-v2",
        version=2,
        deployment_profile_id="aws-managed-v1",
        public_base_url="https://fiscal.fmtecnologia.example/",
        cloud_account=verified("cloud/account"),
        dns_control=verified("dns/fiscal"),
        secret_backend=verified("secrets/primary"),
        commercial_gateway_account=verified("gateway/account"),
        production_activation=verified("activation/fm-fiscal"),
    )

    assert configuration.production_ready is True
    assert configuration.public_base_url == "https://fiscal.fmtecnologia.example"


def test_platform_rejects_non_https_public_endpoint() -> None:
    with pytest.raises(TenantConfigurationError, match="HTTPS"):
        PlatformExternalConfiguration(
            configuration_id="invalid",
            version=1,
            deployment_profile_id="local",
            public_base_url="http://fiscal.example",
            cloud_account=missing(),
            dns_control=missing(),
            secret_backend=missing(),
            commercial_gateway_account=missing(),
            production_activation=missing(),
        )


def test_platform_from_mapping_is_reference_only() -> None:
    configuration = PlatformExternalConfiguration.from_mapping(
        {
            "configuration_id": "fm-fiscal-prod-v1",
            "version": 1,
            "deployment_profile_id": "cloud-profile-v1",
            "public_base_url": "https://fiscal.example.com",
            "cloud_account": {
                "state": "configured",
                "reference_id": "cloud://account/fm-fiscal",
            },
            "dns_control": {
                "state": "configured",
                "reference_id": "dns://fm-fiscal",
            },
            "secret_backend": {
                "state": "configured",
                "reference_id": "vault://fm-fiscal",
            },
            "commercial_gateway_account": {"state": "missing"},
            "production_activation": {"state": "missing"},
        }
    )

    assert configuration.production_ready is False
    assert configuration.deployment_profile_id == "cloud-profile-v1"
