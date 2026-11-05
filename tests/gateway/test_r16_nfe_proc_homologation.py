"""SEFAZ-SP protocol-bound nfeProc: no remote call or taxpayer credential."""
from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from lxml import etree

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.gateway.authorization import AuthorizationRequest
from kordena_fiscal.gateway.nfe_sp_homologation import (
    NFE_NAMESPACE,
    _authorized_nfe_proc,
)

_ACCESS_KEY = "3" * 44
_NS = NFE_NAMESPACE


def _nfe() -> etree._Element:
    return etree.fromstring(
        (
            f'<enviNFe xmlns="{_NS}" versao="4.00"><NFe>'
            f'<infNFe Id="NFe{_ACCESS_KEY}"/><Signature/></NFe></enviNFe>'
        ).encode()
    )


def _reply(status: str = "100", key: str = _ACCESS_KEY) -> etree._Element:
    return etree.fromstring(
        (
            f'<retEnviNFe xmlns="{_NS}"><protNFe versao="4.00"><infProt>'
            f'<chNFe>{key}</chNFe><tpAmb>2</tpAmb><cStat>{status}</cStat>'
            f'<nProt>123</nProt><digVal>SHA256</digVal>'
            "</infProt></protNFe></retEnviNFe>"
        ).encode()
    )


def _request() -> AuthorizationRequest:
    return cast(
        AuthorizationRequest,
        SimpleNamespace(access_key=SimpleNamespace(value=_ACCESS_KEY)),
    )


def test_matching_protocol_produces_nfe_proc_without_mutating_invoice() -> None:
    signed = _nfe()
    xml = _authorized_nfe_proc(signed, _reply(), _request())
    root = etree.fromstring(xml)
    assert root.tag == f"{{{_NS}}}nfeProc"
    assert root.get("versao") == "4.00"
    assert len(root.findall(f"{{{_NS}}}NFe")) == 1
    assert root.findtext(f".//{{{_NS}}}chNFe") == _ACCESS_KEY
    assert signed.tag == f"{{{_NS}}}enviNFe"


@pytest.mark.parametrize(
    ("status", "key"), [
        ("101", _ACCESS_KEY), ("100", "4" * 44),
    ],
)
def test_protocol_mismatch_is_not_archivable(status: str, key: str) -> None:
    with pytest.raises(FiscalValidationError):
        _authorized_nfe_proc(_nfe(), _reply(status, key), _request())
