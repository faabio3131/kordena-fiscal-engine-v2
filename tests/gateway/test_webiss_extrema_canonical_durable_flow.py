"""Extrema official-XSD canonical persistence/numbering/authorization/recovery E2E.

All CNPJ, certificate and invoice identifiers are synthetic. Never transmits
HTTP, never impersonates a real taxpayer and never certifies live homologation.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from test_nfv1_nfse_dps_builder_and_preaudit_wiring import (
    _certificate,
    _mg_request,
)
from test_webiss_extrema_official_rtc_accepted_receipts import (
    _accepted_xml,
    _wrap_soap,
)

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.archive import RetentionPolicyMetadata
from kordena_fiscal.domain import (
    BrazilianJurisdiction, Cnpj, ExecutionScope, FiscalEnvironment, FiscalValidationError,
    TaxRegimeCode,
)
from kordena_fiscal.gateway.authorization import AuthorizationStatus
from kordena_fiscal.gateway.mg_webiss_soap import (
    EXTREMA_WEBISS_PROVIDER_ID, WebissExtremaHomologationTransport,
)
from kordena_fiscal.gateway.nfse_abrasf203_envelope import Abrasf203Operation
from kordena_fiscal.gateway.webiss_2026_schema import load_pinned_extrema_webiss_rtc_schema
from kordena_fiscal.gateway.webiss_extrema_canonical import (
    WebissExtremaCanonicalNfseGateway,
)
from kordena_fiscal.issuance import NfseGatewayClient, NfseQueryClient
from kordena_fiscal.issuance.webiss_extrema_builder import (
    ExtremaRpsIntent, ExtremaServiceTaker, build_extrema_rps_xml,
    decode_extrema_intent, encode_extrema_intent,
)
from kordena_fiscal.lifecycle import FiscalDocumentState
from kordena_fiscal.persistence.sqlite import SqliteFiscalDatabase
from kordena_fiscal.xml.schema import XmlSchemaValidationError
from kordena_fiscal.gateway.authorization import AuthorizationStatus

NOW = datetime(2026, 11, 11, 12, tzinfo=UTC)
RETENTION = RetentionPolicyMetadata(policy_id="nfcore-fiscal-archive", policy_version=1)


def _request():
    return _mg_request(
        "3125101", "Extrema", tax_regime=TaxRegimeCode.NORMAL,
    )


def _intent(app: FiscalApplicationService, request) -> ExtremaRpsIntent:
    reservation = app.reserve_extrema_rps_number(
        scope=request.document.scope, municipality_ibge="3125101", series=1,
    )
    return ExtremaRpsIntent(
        request_fingerprint=request.request_fingerprint,
        issuer_cnpj=request.document.issuer.cnpj,
        reservation=reservation,
        rule_reference="urn:nfcore:test:rtc-policy:2026:rev1",
        exigibilidade_iss="1",
        incidence_municipality_ibge="3125101",
        iss_rate_fraction=Decimal("0.0300"),
        incentive_fiscal=False,
        nbs_code="123456789",
        rtc_operation_indicator="010101",
        rtc_cst="000",
        rtc_tax_class="000001",
        taker=ExtremaServiceTaker(
            reference=request.document.service_taker_reference,
            cnpj=Cnpj("12345678000195"),
            legal_name="Tomador de teste sintético",
        ),
    )


def _success_response(operation: Abrasf203Operation, intent) -> bytes:
    old = _accepted_xml(operation)
    insertion = (
        "<Rps><IdentificacaoRps>"
        f"<Numero>{intent.reservation.number}</Numero>"
        f"<Serie>{intent.reservation.key.series}</Serie>"
        "<Tipo>1</Tipo></IdentificacaoRps>"
        "<DataEmissao>2026-11-06</DataEmissao><Status>1</Status></Rps>"
    ).encode()
    # The mocked official receiver must echo the immutable original RPS
    # identity and canonical buyer in its signed/validated response.
    updated = old.replace(
        b"<Competencia>", insertion + b"<Competencia>", 1,
    ).replace(
        b"<Cnpj>11222333000181</Cnpj></CpfCnpj>"
        b"</IdentificacaoTomador>",
        b"<Cnpj>12345678000195</Cnpj></CpfCnpj>"
        b"</IdentificacaoTomador>",
        1,
    )
    return _wrap_soap(operation, updated)


def _gateway(app, intent, exchange):
    evidence, validator = load_pinned_extrema_webiss_rtc_schema()
    resolver = Mock()
    resolver.resolve_provider_id.return_value = EXTREMA_WEBISS_PROVIDER_ID
    certificate = Mock(return_value=_certificate())
    transport = WebissExtremaHomologationTransport(
        provider_resolver=resolver, resolve_certificate=certificate,
        municipal_schema_evidence=evidence,
        municipal_schema_validator=validator, exchange=exchange,
    )
    canonical_preaudit, service_preaudit = Mock(), Mock()
    gateway = WebissExtremaCanonicalNfseGateway(
        transport=transport,
        load_intent=app.load_extrema_rps_intent,
        resolve_certificate=certificate,
        canonical_preaudit=canonical_preaudit,
        service_preaudit=service_preaudit,
        municipal_validator=validator,
    )
    return gateway, resolver, certificate, canonical_preaudit, service_preaudit


def test_builder_generates_real_xsd_valid_webiss_2026_rtc_rps(tmp_path):
    database = SqliteFiscalDatabase(tmp_path / "rps-xsd.sqlite")
    database.initialize()
    app = FiscalApplicationService(database)
    request = _request()
    intent = _intent(app, request)
    _, validator = load_pinned_extrema_webiss_rtc_schema()
    xml = build_extrema_rps_xml(request, intent, validator=validator)
    validator.validate_document(xml)
    assert b"<CodigoNbs>123456789</CodigoNbs>" in xml
    assert b"<cClassTrib>000001</cClassTrib>" in xml
    assert b"<ValorIss>3.00</ValorIss>" in xml
    assert b"<Aliquota>0.0300</Aliquota>" in xml
    assert b"<Numero>1</Numero>" in xml
    assert decode_extrema_intent(
        encode_extrema_intent(intent), scope=request.document.scope, request=request,
    ) == intent
    with pytest.raises(FiscalValidationError, match="tax intent"):
        build_extrema_rps_xml(
            request, replace(intent, iss_rate_fraction=Decimal("0.0500")),
            validator=validator,
        )


def test_canonical_durable_issue_replay_query_without_resend(tmp_path):
    db = SqliteFiscalDatabase(tmp_path / "extrema-end-to-end.sqlite")
    db.initialize()
    app = FiscalApplicationService(db)
    request = _request()
    intent = _intent(app, request)
    app.prepare_nfse_authorization(
        request.document, occurred_at=NOW, retention=RETENTION, extrema_intent=intent,
    )
    restarted = FiscalApplicationService(SqliteFiscalDatabase(db.path))
    assert restarted.load_extrema_rps_intent(
        request.document.scope, request.document.document_id,
    ) == intent
    with pytest.raises(Exception, match="cannot change"):
        restarted.prepare_nfse_authorization(
            request.document, occurred_at=NOW, retention=RETENTION,
            extrema_intent=replace(intent, rtc_tax_class="000002"),
        )
    calls = []
    def exchange(data, soap_action, _context, _timeout):
        calls.append(soap_action)
        if "GerarNfse" in soap_action:
            return _wrap_soap(
                Abrasf203Operation.GENERATE,
                ('<GerarNfseResposta xmlns="http://www.abrasf.org.br/nfse.xsd"/>').encode(),
            )
        assert "ConsultarNfsePorRps" in soap_action
        return _success_response(Abrasf203Operation.QUERY_RPS, intent)

    gateway, resolver, cert, audit, service_audit = _gateway(restarted, intent, exchange)
    first = restarted.authorize_prepared_document(
        document_id=request.document.document_id, request=request,
        gateway=NfseGatewayClient(gateway), occurred_at=NOW,
    )
    assert first.recovery_required
    assert first.lifecycle.state is FiscalDocumentState.TRANSMITTING
    assert len(calls) == 1 and "GerarNfse" in calls[0]
    same = restarted.authorize_prepared_document(
        document_id=request.document.document_id, request=request,
        gateway=NfseGatewayClient(gateway), occurred_at=NOW,
    )
    assert same.replay
    assert len(calls) == 1
    result = restarted.reconcile_prepared_nfse_authorization(
        scope=request.document.scope, document_id=request.document.document_id,
        client=NfseQueryClient(gateway), occurred_at=NOW, retention=RETENTION,
    )
    assert result.lifecycle.state is FiscalDocumentState.AUTHORIZED
    assert result.query_result.status is AuthorizationStatus.AUTHORIZED
    assert len(calls) == 2
    assert cert.call_count > 0
    assert audit.call_count == 1
    assert service_audit.call_count == 1


def test_no_duplicate_reserved_rps_or_cross_tenant_use(tmp_path):
    db = SqliteFiscalDatabase(tmp_path / "scope.sqlite")
    db.initialize()
    app = FiscalApplicationService(db)
    request = _request()
    first = _intent(app, request)
    second = _intent(app, request)
    assert first.reservation.number + 1 == second.reservation.number
    app.prepare_nfse_authorization(
        request.document, occurred_at=NOW, retention=RETENTION, extrema_intent=first,
    )
    other = replace(request.document.scope, tenant_id="attacker")
    with pytest.raises(Exception):
        app.load_extrema_rps_intent(other, request.document.document_id)
    with pytest.raises(FiscalValidationError):
        build_extrema_rps_xml(
            request, replace(first, reservation=replace(first.reservation, key=replace(
                first.reservation.key, unit_id="other-unit",
            ))),
            validator=load_pinned_extrema_webiss_rtc_schema()[1],
        )


def test_tampered_immutable_archive_and_rtc_rejected_before_a1(tmp_path):
    db = SqliteFiscalDatabase(tmp_path / "tamper.sqlite")
    db.initialize()
    app = FiscalApplicationService(db)
    request = _request()
    intent = _intent(app, request)
    bad_raw = encode_extrema_intent(intent).replace(b"000001", b"000002")
    altered = decode_extrema_intent(
        bad_raw, scope=request.document.scope, request=request,
    )
    assert altered != intent
    bad_scope = replace(request.document.scope, environment=FiscalEnvironment.PRODUCTION)
    with pytest.raises(FiscalValidationError):
        app.reserve_extrema_rps_number(
            scope=bad_scope, municipality_ibge="3125101", series=1,
        )
    wrong_muni = replace(
        request.document, service_jurisdiction=BrazilianJurisdiction("MG", "3170107"),
    )
    from kordena_fiscal.issuance import NfseAuthorizationRequest
    with pytest.raises(FiscalValidationError):
        build_extrema_rps_xml(
            NfseAuthorizationRequest.build(wrong_muni),
            intent, validator=load_pinned_extrema_webiss_rtc_schema()[1],
        )
