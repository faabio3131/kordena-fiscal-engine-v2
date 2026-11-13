"""Native National NFS-e preparation without ERP, A1, external transport or mock issuance."""
from __future__ import annotations

import base64
import gzip
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID, ObjectIdentifier
from fastapi.testclient import TestClient
from lxml import etree

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.archive import RetentionPolicyMetadata
from kordena_fiscal.compliance.nfse_preaudit import nfse_preaudit
from kordena_fiscal.control_plane import FiscalOrganization, FiscalUnitRegistration
from kordena_fiscal.control_plane.commercial import (
    ConfiguredFiscalOperation,
    ProviderBinding,
)
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    CnaeCode,
    Cnpj,
    ExecutionScope,
    FiscalAddress,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalProfile,
    StateRegistration,
    TaxRegimeCode,
)
from kordena_fiscal.gateway.nfse_nacional_homologation import (
    NACIONAL_HOMOLOGATION_PROVIDER_ID,
    NfseNacionalHomologationGateway,
)
from kordena_fiscal.issuance import NfseGatewayClient
from kordena_fiscal.issuance.nfse_dps_builder import build_signed_dps
from kordena_fiscal.lifecycle import FiscalDocumentState
from kordena_fiscal.operations import FakeFiscalOperationsGateway, FiscalOperationsClient
from kordena_fiscal.persistence import SqliteFiscalDatabase
from kordena_fiscal.runtime.canonical_fiscal_composition import _GovernedNationalNfseGateway
from kordena_fiscal.runtime.fiscal_runtime import (
    CanonicalFiscalOperationPath,
    CanonicalPortalOperationExecutor,
)
from kordena_fiscal.runtime.provider_operation_wiring import build_provider_operation_handlers
from kordena_fiscal.security.human_identity import (
    HumanAccount,
    HumanIdentityService,
    InMemoryHumanAccountRepository,
    InMemoryWebSessionRepository,
    PortalRole,
    ScryptPasswordHasher,
)
from kordena_fiscal.vault import EphemeralCertificateMaterial
from kordena_fiscal.web import create_app
from kordena_fiscal.web.human_auth import CSRF_COOKIE, CSRF_HEADER
from kordena_fiscal.web.portal_runtime import DurableHumanPortalExecutor
from kordena_fiscal.xml.nfse_nacional_schema import national_dps_validator

TENANT = "tenant-native"
UNIT = "unit-cajamar"
IBGE = "3509205"
ROUTE = "/v1/portal/operations/prepareNativeNfse"


def _database(path: Path, *, with_binding: bool = True) -> SqliteFiscalDatabase:
    db = SqliteFiscalDatabase(path)
    db.initialize()
    jurisdiction = BrazilianJurisdiction("SP", IBGE)
    scope = ExecutionScope(
        TENANT, UNIT, FiscalEnvironment.HOMOLOGATION, "setup", "fm-nfcore"
    )
    with db() as uow:
        uow.control_plane.add_organization(
            FiscalOrganization(tenant_id=TENANT, legal_name="Emissor Sintetico")
        )
        uow.control_plane.add_unit(FiscalUnitRegistration(
            tenant_id=TENANT, unit_id=UNIT, display_name="Cajamar",
            enabled_environments=frozenset({FiscalEnvironment.HOMOLOGATION}),
        ))
        uow.control_plane.add_profile(FiscalProfile(
            profile_id="issuer-native", scope=scope,
            cnpj=Cnpj("11222333000181"), legal_name="Emissor Sintetico Ltda",
            tax_regime=TaxRegimeCode.SIMPLES_NACIONAL,
            state_registration=StateRegistration("SP", "123456789"),
            primary_cnae=CnaeCode("6201501"),
            address=FiscalAddress(
                street="Rua de Homologacao", number="10", district="Centro",
                municipality_name="Cajamar", jurisdiction=jurisdiction,
                postal_code="07750000",
            ),
            effective_from=datetime.now(UTC) - timedelta(days=1),
        ))
        if with_binding:
            uow.commercial.put_provider_binding(ProviderBinding(
                binding_id="native-national-nfse-binding", tenant_id=TENANT,
                unit_id=UNIT, environment=FiscalEnvironment.HOMOLOGATION,
                document_kind=FiscalDocumentKind.NFSE,
                jurisdiction=jurisdiction,
                operation=ConfiguredFiscalOperation.AUTHORIZE,
                provider_id=NACIONAL_HOMOLOGATION_PROVIDER_ID,
            ))
        uow.commit()
    return db


def _client(
    db: SqliteFiscalDatabase,
    role: PortalRole = PortalRole.OWNER,
    *,
    operation_executor: CanonicalPortalOperationExecutor | None = None,
) -> TestClient:
    password = "only-for-synthetic-fixtures-2026"
    hasher = ScryptPasswordHasher()
    accounts = InMemoryHumanAccountRepository((HumanAccount(
        account_id="native-" + role.value, email=role.value + "@example.com",
        password_hash=hasher.hash(password), tenant_id=TENANT, role=role,
        unit_ids=frozenset({UNIT}),
    ),))
    identity = HumanIdentityService(
        accounts=accounts, sessions=InMemoryWebSessionRepository(),
        password_hasher=hasher,
    )
    web = TestClient(
        create_app(
            human_identity=identity,
            portal_executor=DurableHumanPortalExecutor(db, operation_executor=operation_executor),
        ),
        base_url="https://nfcore.test",
    )
    response = web.post("/v1/auth/login", json={
        "email": role.value + "@example.com", "password": password,
    })
    assert response.status_code == 200
    return web


def _payload() -> dict[str, object]:
    return {
        "unit_id": UNIT, "environment": "homologation",
        "source_id": "service-order-native-1",
        "competence_date": datetime.now(UTC).date().isoformat(),
        "service_state_code": "SP", "service_municipality_ibge": IBGE,
        "national_taxation_code": "010701",
        "municipal_service_code": "0107",
        "description": "Servico sintetico revisado pelo escritorio",
        "gross_amount": "100.00", "deduction_amount": "0.00",
        "iss_amount": "3.00", "iss_withheld": False,
        "taker_document": "12345678000195",
        "taker_name": "Tomador Sintetico Ltda",
        "source_normative": "urn:nfcore:synthetic:rule:2026",
        "rule_version": 1, "fiscal_review_approved": True,
    }


def _post(web: TestClient, payload: dict[str, object], key: str = "first-review"):
    csrf = web.cookies.get(CSRF_COOKIE)
    assert csrf
    return web.post(
        ROUTE, json=payload,
        headers={CSRF_HEADER: csrf, "Idempotency-Key": key},
    )


def test_owner_prepares_native_nfse_and_replay_keeps_immutable_document(tmp_path: Path) -> None:
    db = _database(tmp_path / "native.sqlite")
    web = _client(db)
    first = _post(web, _payload())
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["status"] == FiscalDocumentState.READY_TO_TRANSMIT.value
    assert result["fiscal_authorization"] == "not_inferred_from_preparation"
    assert result["transmitted"] is False
    assert result["dps_numbering"] == "pending_durable_authority"
    replay = _post(web, _payload(), key="second-review")
    assert replay.status_code == 200, replay.text
    assert replay.json()["replay"] is True
    assert replay.json()["document_id"] == result["document_id"]
    scope = ExecutionScope(TENANT, UNIT, FiscalEnvironment.HOMOLOGATION, "check", "fm-nfcore")
    prepared = FiscalApplicationService(db).load_prepared_nfse_authorization(
        scope, result["document_id"]
    )
    assert prepared.document.issuer.cnpj.value == "11222333000181"
    assert prepared.document.service_taker is not None
    assert prepared.document.service_taker.tax_id.value == "12345678000195"
    assert prepared.document.services[0].iss_amount.amount == 3
    with db() as uow:
        assert len(uow.archive.list_for_document(scope, result["document_id"])) == 1


def test_native_mutation_replay_cannot_change_reviewed_fiscal_facts(tmp_path: Path) -> None:
    db = _database(tmp_path / "conflict.sqlite")
    web = _client(db)
    assert _post(web, _payload()).status_code == 200
    changed = _post(web, _payload() | {"iss_amount": "4.00"}, "different-http-key")
    assert changed.status_code == 409
    assert changed.json()["detail"]["code"] == "NATIVE_NFSE_CONTENT_CONFLICT"
    assert _post(web, _payload(), "third-http-key").json()["replay"] is True


def test_native_nfse_enforces_owner_csrf_unit_and_explicit_review(tmp_path: Path) -> None:
    db = _database(tmp_path / "security.sqlite")
    operator = _client(db, PortalRole.OPERATOR)
    assert _post(operator, _payload()).status_code == 403
    owner = _client(db)
    assert owner.post(ROUTE, json=_payload()).status_code == 403
    csrf = owner.cookies.get(CSRF_COOKIE)
    assert csrf
    assert owner.post(ROUTE, json=_payload(), headers={CSRF_HEADER: csrf}).status_code == 400
    assert _post(owner, _payload() | {"tenant_id": "other"}).status_code == 400
    assert _post(owner, _payload() | {"unit_id": "other"}).status_code == 403
    assert _post(owner, _payload() | {"environment": "production"}).status_code == 400
    assert _post(owner, _payload() | {"fiscal_review_approved": False}).status_code == 403


def test_native_nfse_requires_real_binding_and_effective_profile(tmp_path: Path) -> None:
    db = _database(tmp_path / "unbound.sqlite", with_binding=False)
    web = _client(db)
    result = _post(web, _payload())
    assert result.status_code == 409
    assert result.json()["detail"]["code"] == "NATIVE_NFSE_PROVIDER_NOT_CONFIGURED"


def test_unmodeled_untaxed_iss_and_malformed_money_fail_before_preparation(tmp_path: Path) -> None:
    db = _database(tmp_path / "tax.sqlite")
    web = _client(db)
    assert _post(web, _payload() | {"iss_amount": "0.00"}).status_code == 400
    assert _post(web, _payload() | {"gross_amount": "100.001"}).status_code == 400
    assert _post(web, _payload() | {"national_taxation_code": "bad"}).status_code == 400
    assert _post(web, _payload()).status_code == 200



def _synthetic_a1_for_native_issuer() -> EphemeralCertificateMaterial:
    """Ephemeral PKCS#12 fixture; never a real customer A1 or trusted authority."""
    password = b"synthetic-native-e2e-only"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(UTC)
    issuer = Cnpj("11222333000181")
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic A1 fixture")])
    encoded = issuer.value.encode("ascii")
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False,
        ), critical=True)
        .add_extension(x509.SubjectAlternativeName([
            x509.OtherName(ObjectIdentifier("2.16.76.1.3.3"),
                           bytes([0x04, len(encoded)]) + encoded),
        ]), critical=False)
        .sign(key, hashes.SHA256())
    )
    return EphemeralCertificateMaterial(
        reference_id="synthetic-only-native-e2e",
        pkcs12_bytes=pkcs12.serialize_key_and_certificates(
            name=b"synthetic-native", key=key, cert=certificate, cas=None,
            encryption_algorithm=serialization.BestAvailableEncryption(password),
        ),
        password=password,
    )


def test_web_native_nfse_preparation_to_signed_gateway_and_authorized_xml(
    tmp_path: Path,
) -> None:
    """HTTP Portal -> durable preparation -> DPS 1.01 -> fake SEFIN -> archive HTTP.

    This uses one canonical runtime path and an ephemeral synthetic A1; no
    external gateway, municipality authorization or customer cert is contacted.
    """
    db = _database(tmp_path / "native-e2e.sqlite")
    application = FiscalApplicationService(db)
    captured: list[bytes] = []
    key = "35" + "0" * 48
    official_xml = (
        '<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse">'
        f'<infNFSe Id="NFS{key}"/></NFSe>'
    ).encode()

    def fake_sefin(payload: bytes, *_args: object) -> bytes:
        request = json.loads(payload)
        signed = gzip.decompress(base64.b64decode(request["dpsXmlGZipB64"]))
        national_dps_validator("1.01").validate_document(signed)
        root = etree.fromstring(signed)
        signature = root.find("{http://www.w3.org/2000/09/xmldsig#}Signature")
        assert signature is not None
        assert root.findtext(
            "{http://www.sped.fazenda.gov.br/nfse}infDPS/"
            "{http://www.sped.fazenda.gov.br/nfse}prest/"
            "{http://www.sped.fazenda.gov.br/nfse}CNPJ"
        ) == "11222333000181"
        captured.append(signed)
        return json.dumps({
            "tipoAmbiente": 2, "chaveAcesso": key, "idDps": "synthetic-native-e2e",
            "nfseXmlGZipB64": base64.b64encode(
                gzip.compress(official_xml, mtime=0)
            ).decode("ascii"),
        }).encode()

    a1 = _synthetic_a1_for_native_issuer()
    national = NfseNacionalHomologationGateway(
        resolve_certificate=lambda _scope, _cnpj: a1,
        build_signed_dps=build_signed_dps,
        exchange=fake_sefin,
    )
    governed = _GovernedNationalNfseGateway(
        application=application, preaudit=nfse_preaudit, gateway=national,
    )
    handlers = build_provider_operation_handlers(
        FiscalOperationsClient(FakeFiscalOperationsGateway()),
        application=application, prepared_nfse_gateway=NfseGatewayClient(governed),
        archive_retention=RetentionPolicyMetadata("nfcore-fiscal-archive", 1),
    )
    operation_executor = CanonicalPortalOperationExecutor(
        unit_of_work_factory=db,
        path=CanonicalFiscalOperationPath(application, handlers=handlers),
    )
    browser = _client(db, operation_executor=operation_executor)
    prepared = _post(browser, _payload())
    assert prepared.status_code == 200, prepared.text
    document_id = prepared.json()["document_id"]

    csrf = browser.cookies.get(CSRF_COOKIE)
    assert csrf
    issue_body = {
        "unit_id": UNIT, "environment": "homologation", "document_id": document_id,
    }
    issued = browser.post(
        "/v1/portal/operations/issueFiscalDocument",
        json=issue_body,
        headers={CSRF_HEADER: csrf, "Idempotency-Key": "native-issue-1"},
    )
    assert issued.status_code == 200, issued.text
    assert issued.json()["status"] == FiscalDocumentState.AUTHORIZED.value
    assert len(captured) == 1

    downloaded = browser.get(
        f"/v1/portal/documents/{document_id}/artifacts/authorized_xml",
        params={"unit_id": UNIT, "environment": "homologation"},
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == official_xml
    assert downloaded.headers["Cache-Control"] == "no-store"
    assert downloaded.headers["X-Content-Type-Options"] == "nosniff"

    again = browser.post(
        "/v1/portal/operations/issueFiscalDocument",
        json=issue_body,
        headers={CSRF_HEADER: csrf, "Idempotency-Key": "native-issue-1"},
    )
    assert again.status_code == 200, again.text
    assert len(captured) == 1, "Replay must not retransmit the signed DPS"
    assert _post(browser, _payload(), "native-after-authorization").status_code == 200
