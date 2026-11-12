"""Jundiaí GissOnline v2.04 issuance uses the durable issuer/RPS and checked ports."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from lxml import etree

from kordena_fiscal.domain import Cnpj, ExecutionScope, FiscalEnvironment, TaxRegimeCode
from kordena_fiscal.gateway.jundiai_giss_issue_builder import (
    JundiaiGissIssueError,
    JundiaiGissRecipient,
    JundiaiGissTaxFields,
    build_jundiai_giss_issue_xml,
    prepare_jundiai_giss_signed_issue,
)
from kordena_fiscal.gateway.sp4_municipal_canonical import Sp4OriginalRps
from kordena_fiscal.issuance.nfe_nfse import NfseAuthorizationRequest
from kordena_fiscal.runtime.sp4_municipal_request_factories import (
    build_jundiai_giss_issue_request_factory,
)

_TYPES = "{http://www.giss.com.br/tipos-v2_04.xsd}"
_ISSUE = "{http://www.giss.com.br/enviar-lote-rps-envio-v2_04.xsd}"


def _original() -> Sp4OriginalRps:
    return Sp4OriginalRps(
        scope=ExecutionScope(
            tenant_id="jundiai", unit_id="city", host_namespace="nfcore",
            environment=FiscalEnvironment.HOMOLOGATION,
            correlation_id="giss-issue",
        ),
        document_id="original-rps", request_fingerprint="c" * 64,
        issuer_cnpj=Cnpj("11222333000181"), issuer_ibge="3525904",
        competence_date=date(2026, 11, 12), rps_number="42",
        rps_series="NF", gross_amount=Decimal("150.00"),
        municipal_batch_id="144",
    )


def _request(original: Sp4OriginalRps) -> NfseAuthorizationRequest:
    req = Mock(spec=NfseAuthorizationRequest)
    d = req.document
    d.scope = original.scope
    d.document_id = original.document_id
    d.issuer.cnpj = original.issuer_cnpj
    d.issuer.tax_regime = TaxRegimeCode.NORMAL
    d.competence_date = original.competence_date
    d.totals.gross_amount.amount = original.gross_amount
    d.issued_at = datetime(2026, 11, 12, tzinfo=UTC)
    d.service_jurisdiction.state_code = "SP"
    d.service_jurisdiction.municipality_ibge_code = "3525904"
    service = Mock()
    service.gross_amount.amount = original.gross_amount
    service.deduction_amount.amount = Decimal("0.00")
    service.iss_amount.amount = Decimal("3.00")
    service.iss_withheld = False
    service.description = "Consultoria de sistemas"
    d.services = (service,)
    req.request_fingerprint = original.request_fingerprint
    return req


def _fields() -> JundiaiGissTaxFields:
    return JundiaiGissTaxFields(
        municipal_registration="1234567", item_lista_servico="01.07",
        municipal_taxation_code="819", iss_exigibility="1",
        incidence_ibge="3525904", iss_rate=Decimal("0.0200"),
        issuer_special_regime="1", optante_simples="2", fiscal_incentive="2",
        national_service_code="120011000",
        recipient=JundiaiGissRecipient(
            tax_id="11222333000181", name="Cliente Teste",
            street="Rua das Flores", street_number="55", district="Centro",
            city_ibge="3525904", state="SP", postal_code="13201000",
            phone="11999999999",
        ),
    )


def test_giss_issue_one_rps_lot_with_original_receipt_and_taker() -> None:
    original = _original()
    xml = build_jundiai_giss_issue_xml(
        request=_request(original), original=original, fields=_fields(),
    )
    root = etree.fromstring(xml)
    assert root.tag == _ISSUE + "EnviarLoteRpsEnvio"
    lot = root.find(_ISSUE + "LoteRps")
    assert lot is not None
    assert lot.attrib["versao"] == "2.04"
    assert lot.findtext(_TYPES + "NumeroLote") == "144"
    assert lot.findtext(_TYPES + "QuantidadeRps") == "1"
    assert lot.findtext(".//" + _TYPES + "IdentificacaoRps/" + _TYPES + "Numero") == "42"
    assert lot.findtext(".//" + _TYPES + "IdentificacaoRps/" + _TYPES + "Serie") == "NF"
    assert lot.findtext(".//" + _TYPES + "Valores/" + _TYPES + "ValorServicos") == "150.00"
    assert lot.findtext(".//" + _TYPES + "TomadorServico/" + _TYPES + "RazaoSocial") == (
        "Cliente Teste"
    )
    assert lot.findtext(".//" + _TYPES + "OptanteSimplesNacional") == "2"
    assert lot.findtext(".//" + _TYPES + "CodigoNbs") == "120011000"


@pytest.mark.parametrize("change", [
    {"rps_number": "43"}, {"gross_amount": Decimal("149.00")},
    {"issuer_ibge": "3505708"},
])
def test_giss_issuer_rps_and_amount_cannot_be_replaced(change: dict[str, object]) -> None:
    original = _original()
    other = replace(original, **change)
    if "rps_number" in change:
        # RPS number is independently reserved by the existing application;
        # both numbers may be valid, but must be bound by the existing RPS verifier.
        assert build_jundiai_giss_issue_xml(
            request=_request(other), original=other, fields=_fields(),
        )
        return
    with pytest.raises(JundiaiGissIssueError):
        build_jundiai_giss_issue_xml(
            request=_request(original), original=other, fields=_fields(),
        )


def test_signed_rps_identity_mismatch_before_official_xsd() -> None:
    original = _original()
    validator = Mock()
    with pytest.raises(JundiaiGissIssueError, match="does not match"):
        prepare_jundiai_giss_signed_issue(
            request=_request(original), original=original, fields=_fields(),
            sign_xml=lambda xml: xml.replace(b"<tipos:Numero>42</tipos:Numero>",
                                             b"<tipos:Numero>43</tipos:Numero>"),
            validate_signed_xml=validator,
        )
    validator.assert_not_called()


def test_jundiai_issue_and_safe_read_only_query_share_factory() -> None:
    original = _original()
    issue_validator = Mock()
    query_validator = Mock()
    factory = build_jundiai_giss_issue_request_factory(
        resolve_issue_fields=lambda _r, _o: _fields(),
        resolve_municipal_registration=lambda _scope, _issuer: "1234567",
        sign_issue=lambda xml: xml,
        validate_signed_issue=issue_validator,
        sign_rps_query=lambda xml: xml,
        validate_signed_query=query_validator,
    )
    issue = factory(_request(original), original, "RecepcionarLoteRps")
    query = factory(_request(original), original, "ConsultarNfsePorRps")
    assert issue.method == "RecepcionarLoteRps"
    assert query.method == "ConsultarNfsePorRps"
    assert b"144" in issue.signed_xml
    assert b"42" in query.signed_xml
    issue_validator.assert_called_once()
    query_validator.assert_called_once()


def test_2026_optional_rtc_requires_complete_reviewed_classification() -> None:
    original = _original()
    with pytest.raises(JundiaiGissIssueError, match="Partial"):
        build_jundiai_giss_issue_xml(
            request=_request(original), original=original,
            fields=replace(_fields(), rtc_cst="000"),
        )
