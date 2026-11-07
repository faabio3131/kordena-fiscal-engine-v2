"""Offline contract tests for the non-issuing municipal operation."""
import base64
import hashlib
from dataclasses import replace
from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree
from test_mg_homologation_authorization import CNPJ, _request
from test_mg_homologation_authorization import material as material

from kordena_fiscal.domain import Cnpj, FiscalEnvironment, FiscalValidationError
from kordena_fiscal.gateway.nfse_paulistana_envelope import prepare_paulistana_test_batch
from kordena_fiscal.xml.schema import XmlSchemaValidationError

_NS = "http://www.prefeitura.sp.gov.br/nfe"
_DS = "http://www.w3.org/2000/09/xmldsig#"
_CCM = "123456789012"
_XML = f"""<p:PedidoEnvioLoteRPS xmlns:p="{_NS}">
  <Cabecalho Versao="2">
    <CPFCNPJRemetente><CNPJ>{CNPJ}</CNPJ></CPFCNPJRemetente>
    <dtInicio>2026-01-01</dtInicio><dtFim>2026-01-01</dtFim><QtdRPS>1</QtdRPS>
  </Cabecalho>
  <RPS>
    <ChaveRPS><InscricaoPrestador>{_CCM}</InscricaoPrestador>
      <SerieRPS>RTNT</SerieRPS><NumeroRPS>1</NumeroRPS></ChaveRPS>
    <TipoRPS>RPS</TipoRPS><DataEmissao>2026-01-01</DataEmissao>
    <StatusRPS>N</StatusRPS><TributacaoRPS>T</TributacaoRPS><ValorDeducoes>5000</ValorDeducoes>
    <ValorPIS>0</ValorPIS><ValorCOFINS>0</ValorCOFINS><ValorINSS>0</ValorINSS>
    <ValorIR>0</ValorIR><ValorCSLL>0</ValorCSLL><CodigoServico>2658</CodigoServico>
    <AliquotaServicos>0.05</AliquotaServicos><ISSRetido>false</ISSRetido>
    <Discriminacao>Teste &amp; validação</Discriminacao>
    <ValorInicialCobrado>20500</ValorInicialCobrado><ValorIPI>0</ValorIPI>
    <ExigibilidadeSuspensa>0</ExigibilidadeSuspensa><NBS>102010000</NBS>
    <cLocPrestacao>3550308</cLocPrestacao>
    <IBSCBS><finNFSe>0</finNFSe><indFinal>0</indFinal><cIndOp>020301</cIndOp>
      <tpOper>1</tpOper><indDest>0</indDest>
      <valores><trib><gIBSCBS><cClassTrib>000001</cClassTrib></gIBSCBS></trib></valores>
    </IBSCBS>
  </RPS>
</p:PedidoEnvioLoteRPS>""".encode()


def _prepare(calls, **overrides):
    params = dict(
        xml=_XML, scope=_request().scope, issuer_cnpj=Cnpj(CNPJ), issuer_ccm=_CCM,
        resolve_certificate=calls.resolve, preaudit=calls.audit,
    )
    return prepare_paulistana_test_batch(**(params | overrides))


@pytest.mark.parametrize(("party", "intermediary", "suffix"), [
    ("", "", "300000000000000"),
    ("<CPF>00000000000</CPF>", "", "100000000000000"),
    ("<NIF>TEST123</NIF>", "", "400000000000000TEST123"),
    (
        "<NaoNIF>2</NaoNIF>",
        "<CPFCNPJIntermediario><CNPJ>00000000000000</CNPJ></CPFCNPJIntermediario>"
        "<ISSRetidoIntermediario>true</ISSRetidoIntermediario>",
        "400000000000000200000000000000S2",
    ),
])
def test_soap_round_trip_and_both_signatures(material, party, intermediary, suffix):
    calls = Mock()
    calls.resolve.return_value = material
    identity = f"<CPFCNPJTomador>{party}</CPFCNPJTomador>" if party else ""
    xml = _XML.replace(b"<Discriminacao>", (identity + intermediary).encode() + b"<Discriminacao>")
    result = _prepare(calls, xml=xml)
    wrapper = etree.fromstring(result.body)[0][0]
    assert wrapper.tag == f"{{{_NS}}}TesteEnvioLoteRPSRequest"
    assert wrapper.findtext(f"{{{_NS}}}VersaoSchema") == "2"
    assert result.soap_action == f'"{_NS}/TesteEnvioLoteRPS"'
    root = etree.fromstring(wrapper.findtext(f"{{{_NS}}}MensagemXML").encode())
    assert root.findtext("RPS/Discriminacao") == "Teste & validação"
    assert [call[0] for call in calls.mock_calls] == ["audit", "resolve"]
    assert calls.audit.call_args.args[0][0].municipal_service_code == "02658"
    assert calls.resolve.call_args.args == (_request().scope, CNPJ)
    _, cert, _ = pkcs12.load_key_and_certificates(material.pkcs12_bytes, material.password)
    public_key = cert.public_key()
    signed = "123456789012RTNT 00000000000120260101TNN00000000205000000000000050000002658"
    public_key.verify(
        base64.b64decode(root.findtext("RPS/Assinatura")), (signed + suffix).encode(),
        padding.PKCS1v15(), hashes.SHA1(),
    )
    signature = root.find(f"{{{_DS}}}Signature")
    info = signature.find(f"{{{_DS}}}SignedInfo")
    reference = info.find(f"{{{_DS}}}Reference")
    assert reference.get("URI") == ""
    public_key.verify(
        base64.b64decode(signature.findtext(f"{{{_DS}}}SignatureValue")),
        etree.tostring(info, method="c14n", with_comments=False),
        padding.PKCS1v15(), hashes.SHA1(),
    )
    root.remove(signature)
    assert base64.b64decode(reference.findtext(f"{{{_DS}}}DigestValue")) == hashlib.sha1(
        etree.tostring(root, method="c14n", with_comments=False)
    ).digest()


@pytest.mark.parametrize(("overrides", "message"), [
    ({"scope": replace(_request().scope, environment=FiscalEnvironment.PRODUCTION)}, "scope"),
    ({"issuer_ccm": "111"}, "CCM mismatch"),
    ({"xml": _XML.replace(b"Versao=\"2\"", b"Versao=\"1\"")}, "layout mismatch"),
    ({"xml": _XML.replace(b"<QtdRPS>1", b"<QtdRPS>2")}, "count mismatch"),
    ({"xml": _XML.replace(b"<RPS>", b"<RPS><Assinatura/>")}, "existing signature"),
    ({"xml": b"<!DOCTYPE PedidoEnvioLoteRPS>" + _XML}, "existing signature"),
])
def test_rejects_unsafe_inputs_before_audit_and_vault(overrides, message):
    calls = Mock()
    with pytest.raises(FiscalValidationError, match=message):
        _prepare(calls, **overrides)
    assert not calls.mock_calls


def test_audit_can_block_before_vault():
    calls = Mock()
    calls.audit.side_effect = FiscalValidationError("review required")
    with pytest.raises(FiscalValidationError, match="review required"):
        _prepare(calls)
    calls.resolve.assert_not_called()


def test_official_schema_rejects_invalid_layout(material):
    calls = Mock()
    calls.resolve.return_value = material
    with pytest.raises(XmlSchemaValidationError):
        _prepare(calls, xml=_XML.replace(b"<ValorIPI>0</ValorIPI>", b""))
