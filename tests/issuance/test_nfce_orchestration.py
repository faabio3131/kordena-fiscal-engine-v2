import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from kordena_fiscal.documents import CanonicalFiscalDocument, FiscalLineSnapshot
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    CnaeCode,
    Cnpj,
    ElectronicInvoiceModel,
    ExecutionScope,
    FiscalAddress,
    FiscalDocumentKind,
    FiscalEnvironment,
    FiscalProductProfile,
    FiscalProfile,
    FiscalUnitCode,
    FiscalValidationError,
    Gtin,
    Money,
    NcmCode,
    ProductOrigin,
    SourceReference,
    StateRegistration,
    TaxRegimeCode,
)
from kordena_fiscal.gateway import FakeFiscalGateway, FakeGatewayMode, FiscalGatewayClient
from kordena_fiscal.issuance import (
    NfceIssuanceCommand,
    NfceIssuanceContractError,
    NfceIssuanceOrchestrator,
)
from kordena_fiscal.lifecycle import (
    FiscalDocumentState,
    IdempotencyCoordinator,
    InMemoryIdempotencyStore,
    IssuanceAttemptStatus,
)
from kordena_fiscal.numbering import FiscalSequenceManager, InMemoryFiscalSequenceStore
from kordena_fiscal.security import (
    CertificateReference,
    FiscalSignerKind,
    FiscalSigningService,
    SignatureEnvelope,
    SigningRequest,
)
from kordena_fiscal.tax import TaxDecision, TaxRuleOutcome
from kordena_fiscal.xml import (
    NfceXmlPayload,
    NfeAccessKey,
    SchemaResource,
    SchemaSet,
    XmlSchemaValidator,
)

_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"
_SCHEMA = f"""<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
           targetNamespace="{_NAMESPACE}"
           xmlns="{_NAMESPACE}"
           elementFormDefault="qualified">
  <xs:element name="NFe">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="infNFe">
          <xs:complexType>
            <xs:sequence>
              <xs:element name="synthetic" type="xs:string"/>
            </xs:sequence>
            <xs:attribute name="Id" type="xs:string" use="required"/>
          </xs:complexType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
""".encode()


def _instant() -> datetime:
    return datetime(2026, 9, 10, 22, 0, tzinfo=UTC)


def _scope(*, unit: str = "unit-a") -> ExecutionScope:
    return ExecutionScope(
        tenant_id="tenant-a",
        unit_id=unit,
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-nfce-1",
    )


def _issuer(scope: ExecutionScope) -> FiscalProfile:
    return FiscalProfile(
        profile_id="issuer-1",
        scope=scope,
        cnpj=Cnpj("12.345.678/0001-95"),
        legal_name="Empresa Fiscal Sintetica Ltda",
        tax_regime=TaxRegimeCode.SIMPLES_NACIONAL,
        state_registration=StateRegistration("SP", "123456789"),
        primary_cnae=CnaeCode("5611-2/01"),
        address=FiscalAddress(
            street="Rua Sintetica",
            number="100",
            district="Centro",
            municipality_name="Sao Paulo",
            jurisdiction=BrazilianJurisdiction("SP", "3550308"),
            postal_code="01001000",
        ),
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _product(scope: ExecutionScope) -> FiscalProductProfile:
    return FiscalProductProfile(
        profile_id="product-profile-1",
        product_id="product-1",
        scope=scope,
        commercial_code="SKU-001",
        description="Produto fiscal sintetico",
        ncm=NcmCode("21069090"),
        commercial_unit=FiscalUnitCode("UN"),
        taxable_unit=FiscalUnitCode("UN"),
        origin=ProductOrigin.NATIONAL,
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        gtin=Gtin("SEM GTIN"),
    )


def _tax_decision() -> TaxDecision:
    return TaxDecision(
        rule_id="rule-synthetic-1",
        rule_version=1,
        source_normative="NORMA-SINTETICA",
        outcome=TaxRuleOutcome(
            cfop="5102",
            icms_code="102",
            pis_cst="49",
            cofins_cst="49",
            ibs_cbs_classification_code="000001",
        ),
        rank=(1, 1, 1),
    )


def _document(**overrides: object) -> CanonicalFiscalDocument:
    scope = _scope()
    values: dict[str, object] = {
        "document_id": "doc-nfce-1",
        "scope": scope,
        "source": SourceReference("sale", "sale-100"),
        "document_kind": FiscalDocumentKind.NFCE,
        "issued_at": _instant(),
        "issuer": _issuer(scope),
        "items": (
            FiscalLineSnapshot(
                line_number=1,
                product=_product(scope),
                quantity=Decimal("1.000"),
                unit_price=Money(Decimal("10.00")),
                gross_amount=Money(Decimal("10.00")),
                tax_decision=_tax_decision(),
            ),
        ),
    }
    values.update(overrides)
    return CanonicalFiscalDocument(**values)  # type: ignore[arg-type]


def _certificate(scope: ExecutionScope | None = None) -> CertificateReference:
    target = scope or _scope()
    return CertificateReference(
        tenant_id=target.tenant_id,
        unit_id=target.unit_id,
        reference_id="vault://synthetic/certificate-1",
        signer_kind=FiscalSignerKind.A1_PFX,
        not_before=_instant() - timedelta(days=30),
        expires_at=_instant() + timedelta(days=300),
        subject_identifier="synthetic-certificate",
    )


class _FixedNumericCodeProvider:
    def __init__(self, code: int = 12345678) -> None:
        self.code = code
        self.calls = 0

    def code_for(self, document, attempt, number) -> int:  # type: ignore[no-untyped-def]
        del document, attempt, number
        self.calls += 1
        return self.code


class _SyntheticXmlBuilder:
    def build(
        self,
        document: CanonicalFiscalDocument,
        access_key: NfeAccessKey,
    ) -> NfceXmlPayload:
        del document
        xml = (
            f'<NFe xmlns="{_NAMESPACE}"><infNFe Id="NFe{access_key.value}">'
            "<synthetic>ok</synthetic></infNFe></NFe>"
        ).encode()
        return NfceXmlPayload(access_key=access_key, xml=xml)


class _FakeSigner:
    def sign(self, request: SigningRequest) -> SignatureEnvelope:
        return SignatureEnvelope(
            certificate_reference_id=request.certificate.reference_id,
            signer_kind=request.certificate.signer_kind,
            algorithm=request.algorithm,
            signature_value=hashlib.sha256(b"signature:" + request.payload).digest(),
            payload_sha256=request.payload_sha256,
            signed_at=request.signing_time,
        )


class _SyntheticSignedXmlAssembler:
    def assemble(
        self,
        payload: NfceXmlPayload,
        signature: SignatureEnvelope,
    ) -> bytes:
        marker = (
            '<Signature xmlns="urn:kordena:synthetic">'
            f"{signature.signature_value.hex()}"
            "</Signature></NFe>"
        )
        return payload.xml.replace(b"</NFe>", marker.encode())


class _UnsafePassthroughAssembler:
    def assemble(
        self,
        payload: NfceXmlPayload,
        signature: SignatureEnvelope,
    ) -> bytes:
        del signature
        return payload.xml


def _validator() -> XmlSchemaValidator:
    resource = SchemaResource.from_bytes("synthetic-nfce.xsd", _SCHEMA)
    return XmlSchemaValidator(
        SchemaSet(
            version="synthetic-fisc-12-v1",
            root_schema=resource.name,
            resources=(resource,),
            source_uri="https://example.invalid/fisc-12-synthetic-schema",
        )
    )


def _system(
    mode: FakeGatewayMode,
    *,
    assembler=None,  # type: ignore[no-untyped-def]
):
    idempotency_store = InMemoryIdempotencyStore()
    numbering_store = InMemoryFiscalSequenceStore()
    numbering = FiscalSequenceManager(numbering_store)
    gateway_adapter = FakeFiscalGateway(mode)
    numeric_code_provider = _FixedNumericCodeProvider()
    orchestrator = NfceIssuanceOrchestrator(
        idempotency=IdempotencyCoordinator(idempotency_store),
        numbering=numbering,
        numeric_code_provider=numeric_code_provider,
        xml_builder=_SyntheticXmlBuilder(),
        xml_validator=_validator(),
        signing=FiscalSigningService(_FakeSigner()),
        signed_xml_assembler=assembler or _SyntheticSignedXmlAssembler(),
        gateway=FiscalGatewayClient(gateway_adapter),
    )
    return orchestrator, gateway_adapter, numbering, numeric_code_provider


def _command(document: CanonicalFiscalDocument | None = None) -> NfceIssuanceCommand:
    target = document or _document()
    return NfceIssuanceCommand(
        document=target,
        series=3,
        certificate=_certificate(target.scope),
        signing_algorithm="synthetic-signature-v1",
    )


def test_authorized_nfce_composes_all_previous_boundaries_once() -> None:
    orchestrator, gateway, numbering, numeric_codes = _system(FakeGatewayMode.AUTHORIZE)
    document = _document()

    result = orchestrator.issue(_command(document))

    assert result.replay is False
    assert result.number_reservation is not None
    assert result.number_reservation.number == 1
    assert result.access_key is not None
    assert result.access_key.model is ElectronicInvoiceModel.NFCE
    assert result.access_key.series == 3
    assert result.access_key.invoice_number == 1
    assert result.access_key.value.startswith("35260912345678000195")
    assert result.attempt.status is IssuanceAttemptStatus.AUTHORIZED
    assert result.attempt.result_reference == "SYNTHETIC-PROTOCOL-1"
    assert result.lifecycle is not None
    assert result.lifecycle.state is FiscalDocumentState.AUTHORIZED
    assert result.lifecycle.version == 6
    assert len(gateway.calls) == 1
    assert numeric_codes.calls == 1
    assert numbering.last_reserved(
        document.scope,
        model=ElectronicInvoiceModel.NFCE,
        series=3,
    ) == 1


def test_rejected_nfce_closes_attempt_and_lifecycle_as_rejected() -> None:
    orchestrator, gateway, _, _ = _system(FakeGatewayMode.REJECT)

    result = orchestrator.issue(_command())

    assert result.attempt.status is IssuanceAttemptStatus.REJECTED
    assert result.attempt.rejection_reason == (
        "SYNTHETIC-REJECTION: synthetic rejection for contract test"
    )
    assert result.lifecycle is not None
    assert result.lifecycle.state is FiscalDocumentState.REJECTED
    assert result.authorization is not None
    assert result.authorization.rejection_code == "SYNTHETIC-REJECTION"
    assert len(gateway.calls) == 1


def test_pending_nfce_is_not_retransmitted_by_plain_retry() -> None:
    orchestrator, gateway, numbering, numeric_codes = _system(FakeGatewayMode.PENDING)
    command = _command()

    first = orchestrator.issue(command)
    replay = orchestrator.issue(command)

    assert first.attempt.status is IssuanceAttemptStatus.RESERVED
    assert first.lifecycle is not None
    assert first.lifecycle.state is FiscalDocumentState.TRANSMITTING
    assert replay.replay is True
    assert replay.attempt.status is IssuanceAttemptStatus.RESERVED
    assert replay.authorization is None
    assert len(gateway.calls) == 1
    assert numeric_codes.calls == 1
    assert numbering.last_reserved(
        command.document.scope,
        model=ElectronicInvoiceModel.NFCE,
        series=3,
    ) == 1


def test_authorized_retry_is_replay_without_new_number_or_gateway_call() -> None:
    orchestrator, gateway, numbering, _ = _system(FakeGatewayMode.AUTHORIZE)
    command = _command()

    first = orchestrator.issue(command)
    replay = orchestrator.issue(command)

    assert first.attempt.status is IssuanceAttemptStatus.AUTHORIZED
    assert replay.replay is True
    assert replay.attempt.status is IssuanceAttemptStatus.AUTHORIZED
    assert replay.attempt.result_reference == "SYNTHETIC-PROTOCOL-1"
    assert len(gateway.calls) == 1
    assert numbering.last_reserved(
        command.document.scope,
        model=ElectronicInvoiceModel.NFCE,
        series=3,
    ) == 1


def test_changed_content_after_safe_rejection_opens_new_generation_and_number() -> None:
    orchestrator, gateway, numbering, _ = _system(FakeGatewayMode.REJECT)
    first_document = _document()
    second_document = replace(first_document, document_id="doc-nfce-2", schema_version=2)

    first = orchestrator.issue(_command(first_document))
    second = orchestrator.issue(_command(second_document))

    assert first.attempt.generation == 1
    assert second.attempt.generation == 2
    assert second.replay is False
    assert second.number_reservation is not None
    assert second.number_reservation.number == 2
    assert len(gateway.calls) == 2
    assert numbering.last_reserved(
        first_document.scope,
        model=ElectronicInvoiceModel.NFCE,
        series=3,
    ) == 2


def test_unsigned_passthrough_is_blocked_before_gateway() -> None:
    orchestrator, gateway, _, _ = _system(
        FakeGatewayMode.AUTHORIZE,
        assembler=_UnsafePassthroughAssembler(),
    )

    with pytest.raises(NfceIssuanceContractError, match="unsigned payload"):
        orchestrator.issue(_command())

    assert gateway.calls == ()


def test_command_blocks_non_nfce_and_cross_scope_certificate_before_execution() -> None:
    document = replace(_document(), document_kind=FiscalDocumentKind.NFE)
    with pytest.raises(FiscalValidationError, match="only NFCE"):
        NfceIssuanceCommand(
            document=document,
            series=1,
            certificate=_certificate(document.scope),
            signing_algorithm="synthetic",
        )

    nfce_document = _document()
    with pytest.raises(Exception, match="does not belong to scope"):
        NfceIssuanceCommand(
            document=nfce_document,
            series=1,
            certificate=_certificate(_scope(unit="unit-b")),
            signing_algorithm="synthetic",
        )
