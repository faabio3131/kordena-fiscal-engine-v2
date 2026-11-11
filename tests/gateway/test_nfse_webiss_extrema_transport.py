"""Homologation transport tests: strictly synthetic endpoints and A1 material."""
import ssl
from dataclasses import replace
from unittest.mock import Mock

import pytest
from test_mg_homologation_authorization import CNPJ, _request
from test_mg_homologation_authorization import material as material
from test_nfse_webiss_extrema import _response_xml, _soap, _xml
from test_nfse_webiss_extrema import synthetic_schema as synthetic_schema

from kordena_fiscal.domain import Cnpj, FiscalEnvironment, FiscalValidationError
from kordena_fiscal.gateway.nfse_webiss_extrema import ExtremaWebissOperation
from kordena_fiscal.gateway.nfse_webiss_extrema_transport import (
    ExtremaWebissHomologationClient,
    VerifiedExtremaHomologationEndpoint,
)

# Test-only invented hostname; never treated as a real official WebISS endpoint.
_TEST_URL = "https://extrema-homologacao.webiss.com.br/ws/nfse.asmx"
_EVIDENCE_SOURCE = "https://extremamg.webiss.com.br/"
_EVIDENCE_SHA256 = "a" * 64


def _endpoint(url=_TEST_URL):
    return VerifiedExtremaHomologationEndpoint(
        url=url, evidence_source_url=_EVIDENCE_SOURCE,
        evidence_sha256=_EVIDENCE_SHA256,
    )


def _client(synthetic_schema, calls, **kwargs):
    return ExtremaWebissHomologationClient(
        endpoint=_endpoint(), schema=synthetic_schema,
        resolve_certificate=calls.resolve, exchange=calls.exchange, **kwargs,
    )


def test_rejects_production_destination_without_certificate_access():
    with pytest.raises(FiscalValidationError, match="unsafe"):
        _endpoint("https://extremamg.webiss.com.br/ws/nfse.asmx")


@pytest.mark.parametrize("url", [
    "http://extrema-homologacao.webiss.com.br/ws/nfse.asmx",
    "https://extrema-homologacao.webiss.com.br/other",
    "https://127.0.0.1/ws/nfse.asmx",
    "https://extrema-homologacao.webiss.com.br@127.0.0.1/ws/nfse.asmx",
    "https://extrema-homologacao.webiss.com.br/ws/nfse.asmx?target=prod",
])
def test_rejects_untrusted_target_urls(url):
    with pytest.raises(FiscalValidationError, match="unsafe"):
        _endpoint(url)


def test_mutation_uses_canonical_scoped_a1_and_no_automatic_retries(
    synthetic_schema, material,
):
    operation = ExtremaWebissOperation.GENERATE
    calls = Mock()
    calls.resolve.return_value = material
    calls.exchange.return_value = _soap(operation, _response_xml(operation))
    client = _client(synthetic_schema, calls)
    result = client.request(
        operation=operation, signed_or_query_xml=_xml(operation),
        scope=_request().scope, issuer_cnpj=Cnpj(CNPJ),
        issuer_municipality_ibge="3125101",
    )
    assert result.operation is operation
    assert result.xml == _response_xml(operation)
    calls.resolve.assert_called_once_with(_request().scope, CNPJ)
    calls.exchange.assert_called_once()
    prepared, tls, timeout, destination = calls.exchange.call_args.args
    assert tls.minimum_version is ssl.TLSVersion.TLSv1_2
    assert prepared.soap_action.endswith('/GerarNfse"')
    assert timeout == 15
    assert destination.url == _TEST_URL


def test_wrong_tenant_scope_fails_before_vault_or_transport(synthetic_schema):
    calls = Mock()
    client = _client(synthetic_schema, calls)
    operation = ExtremaWebissOperation.GENERATE
    with pytest.raises(FiscalValidationError, match="homologation"):
        client.request(
            operation=operation, signed_or_query_xml=_xml(operation),
            scope=replace(_request().scope, environment=FiscalEnvironment.PRODUCTION),
            issuer_cnpj=Cnpj(CNPJ), issuer_municipality_ibge="3125101",
        )
    calls.resolve.assert_not_called()
    calls.exchange.assert_not_called()


def test_wrong_issuer_fails_before_vault_or_transport(synthetic_schema):
    calls = Mock()
    client = _client(synthetic_schema, calls)
    operation = ExtremaWebissOperation.GENERATE
    with pytest.raises(FiscalValidationError, match="CNPJ"):
        client.request(
            operation=operation, signed_or_query_xml=_xml(operation, issuer="0" * 14),
            scope=_request().scope, issuer_cnpj=Cnpj(CNPJ),
            issuer_municipality_ibge="3125101",
        )
    calls.assert_not_called()


def test_transport_fails_closed_for_unusable_endpoint(synthetic_schema):
    calls = Mock()
    with pytest.raises(FiscalValidationError, match="endpoint"):
        ExtremaWebissHomologationClient(
            endpoint=None, schema=synthetic_schema, resolve_certificate=calls.resolve,
        )
    calls.assert_not_called()


def test_invalid_timeout_rejected(synthetic_schema):
    calls = Mock()
    with pytest.raises(FiscalValidationError, match="timeout"):
        _client(synthetic_schema, calls, timeout_seconds=0)
    calls.assert_not_called()
