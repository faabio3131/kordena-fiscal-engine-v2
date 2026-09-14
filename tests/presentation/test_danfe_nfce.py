import hashlib
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from kordena_fiscal.documents import (
    CanonicalFiscalDocument,
    FiscalLineSnapshot,
    FiscalPaymentSnapshot,
    PaymentMethodKind,
)
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
from kordena_fiscal.gateway import (
    AuthorizationResult,
    AuthorizationStatus,
    GatewayProviderMetadata,
)
from kordena_fiscal.lifecycle import IdempotencyKey
from kordena_fiscal.presentation import (
    DanfeNfceData,
    DanfeNfceLayout,
    NfcePrintContractError,
    NfcePrintReceipt,
    NfcePrintService,
    NfceQrCodeArtifact,
    NfceQrCodePayload,
)
from kordena_fiscal.tax import TaxDecision, TaxRuleOutcome
from kordena_fiscal.xml import AccessKeyInput, NfeAccessKey, build_access_key


def _instant() -> datetime:
    return datetime(2026, 9, 10, 22, 30, tzinfo=UTC)


def _scope(*, unit: str = "unit-a") -> ExecutionScope:
    return ExecutionScope(
        tenant_id="tenant-a",
        unit_id=unit,
        environment=FiscalEnvironment.HOMOLOGATION,
        correlation_id="corr-danfe-1",
    )


def _issuer(scope: ExecutionScope) -> FiscalProfile:
    return FiscalProfile(
        profile_id="issuer-1",
        scope=scope,
        cnpj=Cnpj("12.345.678/0001-95"),
        legal_name="Empresa Fiscal Sintetica & Filhos Ltda",
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
        description="Produto <sintetico>",
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


def _document(scope: ExecutionScope | None = None) -> CanonicalFiscalDocument:
    target = scope or _scope()
    return CanonicalFiscalDocument(
        document_id="doc-danfe-1",
        scope=target,
        source=SourceReference("sale", "sale-200"),
        document_kind=FiscalDocumentKind.NFCE,
        issued_at=_instant(),
        issuer=_issuer(target),
        items=(
            FiscalLineSnapshot(
                line_number=1,
                product=_product(target),
                quantity=Decimal("1.000"),
                unit_price=Money(Decimal("10.00")),
                gross_amount=Money(Decimal("10.00")),
                discount_amount=Money(Decimal("1.00")),
                tax_decision=_tax_decision(),
            ),
        ),
        payments=(
            FiscalPaymentSnapshot(
                method=PaymentMethodKind.PIX,
                amount=Money(Decimal("9.00")),
            ),
        ),
    )


def _access_key(document: CanonicalFiscalDocument | None = None) -> NfeAccessKey:
    target = document or _document()
    return build_access_key(
        AccessKeyInput(
            state_ibge_code="35",
            issued_at=target.issued_at,
            issuer_cnpj=target.issuer.cnpj,
            model=ElectronicInvoiceModel.NFCE,
            series=3,
            invoice_number=7,
            emission_type=1,
            numeric_code=12345678,
        )
    )


def _authorization(
    document: CanonicalFiscalDocument | None = None,
    *,
    status: AuthorizationStatus = AuthorizationStatus.AUTHORIZED,
) -> AuthorizationResult:
    target = document or _document()
    key = _access_key(target)
    common = {
        "scope": target.scope,
        "access_key": key,
        "idempotency_key": IdempotencyKey("1" * 64),
        "request_fingerprint": "2" * 64,
        "provider": GatewayProviderMetadata("synthetic", "v1"),
        "provider_request_id": "request-1",
    }
    if status is AuthorizationStatus.AUTHORIZED:
        return AuthorizationResult(
            status=status,
            protocol_reference="SYNTHETIC-PROTOCOL-1",
            **common,  # type: ignore[arg-type]
        )
    if status is AuthorizationStatus.REJECTED:
        return AuthorizationResult(
            status=status,
            rejection_code="SYNTHETIC-REJECTION",
            rejection_message="synthetic rejection",
            **common,  # type: ignore[arg-type]
        )
    return AuthorizationResult(status=status, **common)  # type: ignore[arg-type]


class _SyntheticPayloadProvider:
    def build(
        self,
        document: CanonicalFiscalDocument,
        access_key: NfeAccessKey,
        authorization: AuthorizationResult,
    ) -> NfceQrCodePayload:
        del document, authorization
        return NfceQrCodePayload(
            f"https://synthetic.invalid/nfce/qrcode?chNFe={access_key.value}"
        )


class _SyntheticQrRenderer:
    def __init__(self, *, wrong_digest: bool = False) -> None:
        self._wrong_digest = wrong_digest

    def render(self, payload: NfceQrCodePayload) -> NfceQrCodeArtifact:
        content = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128">'
            f"<text>{payload.sha256}</text></svg>"
        ).encode()
        digest = "0" * 64 if self._wrong_digest else payload.sha256
        return NfceQrCodeArtifact(
            content=content,
            media_type="image/svg+xml",
            payload_sha256=digest,
        )


class _SyntheticPrintSink:
    def __init__(self, *, wrong_digest: bool = False) -> None:
        self._wrong_digest = wrong_digest
        self.calls = 0

    def submit(self, artifact):  # type: ignore[no-untyped-def]
        self.calls += 1
        digest = "f" * 64 if self._wrong_digest else artifact.content_sha256
        return NfcePrintReceipt(
            printer_reference="synthetic-printer",
            job_reference=f"job-{self.calls}",
            content_sha256=digest,
        )


def _data(*, layout: DanfeNfceLayout = DanfeNfceLayout.FULL) -> DanfeNfceData:
    document = _document()
    return DanfeNfceData(
        document=document,
        access_key=_access_key(document),
        authorization=_authorization(document),
        layout=layout,
        consumer_label="Consumidor <teste>",
    )


def test_prepare_is_deterministic_self_contained_and_html_escaped() -> None:
    service = NfcePrintService(
        qr_payload_provider=_SyntheticPayloadProvider(),
        qr_renderer=_SyntheticQrRenderer(),
    )
    data = _data()

    first = service.prepare(data)
    second = service.prepare(data)
    html = first.content.decode()

    assert first.content == second.content
    assert first.content_sha256 == second.content_sha256
    assert first.media_type == "text/html; charset=utf-8"
    assert "DOCUMENTO AUXILIAR DA NOTA FISCAL DE CONSUMIDOR ELETRÔNICA" in html
    assert "Empresa Fiscal Sintetica &amp; Filhos Ltda" in html
    assert "Produto &lt;sintetico&gt;" in html
    assert "Consumidor &lt;teste&gt;" in html
    assert "Valor a pagar R$" in html
    assert "9,00" in html
    assert "PIX" in html
    assert "data:image/svg+xml;base64," in html
    assert data.access_key.value[:4] in html
    assert "SYNTHETIC-PROTOCOL-1" in html
    assert "http://" not in html


def test_summary_layout_omits_item_table_but_keeps_totals_and_qr() -> None:
    service = NfcePrintService(
        qr_payload_provider=_SyntheticPayloadProvider(),
        qr_renderer=_SyntheticQrRenderer(),
    )

    html = service.prepare(_data(layout=DanfeNfceLayout.SUMMARY)).content.decode()

    assert 'class="items"' not in html
    assert "Produto &lt;sintetico&gt;" not in html
    assert "Qtde. total de itens" in html
    assert "data:image/svg+xml;base64," in html


def test_qr_payload_requires_safe_absolute_https_url() -> None:
    with pytest.raises(FiscalValidationError, match="absolute HTTPS"):
        NfceQrCodePayload("http://example.invalid/nfce")
    with pytest.raises(FiscalValidationError, match="credentials"):
        NfceQrCodePayload("https://user:secret@example.invalid/nfce")
    with pytest.raises(FiscalValidationError, match="fragment"):
        NfceQrCodePayload("https://example.invalid/nfce#fragment")


def test_qr_renderer_cannot_swap_payload_before_danfe_render() -> None:
    service = NfcePrintService(
        qr_payload_provider=_SyntheticPayloadProvider(),
        qr_renderer=_SyntheticQrRenderer(wrong_digest=True),
    )

    with pytest.raises(NfcePrintContractError, match="another payload"):
        service.prepare(_data())


def test_print_sink_receipt_must_match_submitted_artifact_digest() -> None:
    sink = _SyntheticPrintSink(wrong_digest=True)
    service = NfcePrintService(
        qr_payload_provider=_SyntheticPayloadProvider(),
        qr_renderer=_SyntheticQrRenderer(),
        print_sink=sink,
    )

    with pytest.raises(NfcePrintContractError, match="digest"):
        service.print(_data())

    assert sink.calls == 1


def test_print_service_returns_verified_receipt_for_matching_sink() -> None:
    sink = _SyntheticPrintSink()
    service = NfcePrintService(
        qr_payload_provider=_SyntheticPayloadProvider(),
        qr_renderer=_SyntheticQrRenderer(),
        print_sink=sink,
    )

    receipt = service.print(_data())

    assert receipt.printer_reference == "synthetic-printer"
    assert receipt.job_reference == "job-1"
    assert len(receipt.content_sha256) == 64


def test_danfe_rejects_non_authorized_or_cross_scope_result() -> None:
    document = _document()
    key = _access_key(document)
    with pytest.raises(FiscalValidationError, match="authorized"):
        DanfeNfceData(
            document=document,
            access_key=key,
            authorization=_authorization(document, status=AuthorizationStatus.REJECTED),
        )

    other_document = _document(_scope(unit="unit-b"))
    other_authorization = _authorization(other_document)
    with pytest.raises(FiscalValidationError, match="scope"):
        DanfeNfceData(
            document=document,
            access_key=key,
            authorization=other_authorization,
        )


def test_qr_artifact_digest_is_deterministic() -> None:
    payload = NfceQrCodePayload("https://example.invalid/nfce?q=synthetic")
    artifact = _SyntheticQrRenderer().render(payload)

    assert artifact.content_sha256 == hashlib.sha256(artifact.content).hexdigest()
