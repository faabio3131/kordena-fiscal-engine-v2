"""XMLDSig enveloped NF-e signer using the A1 identity supplied by the fiscal Vault.

Signs infNFe by its exact Id, with SHA-256/RSA and exclusive ownership of the
Signature element. The caller must still perform XSD validation before dispatch.
"""
from __future__ import annotations

import base64
from hashlib import sha256

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding, pkcs12
from lxml import etree

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.vault import EphemeralCertificateMaterial

_NFE = "http://www.portalfiscal.inf.br/nfe"
_DS = "http://www.w3.org/2000/09/xmldsig#"
_C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
_ENVELOPED = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"
_SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"
_RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"


def _c14n(element: etree._Element) -> bytes:
    return etree.tostring(element, method="c14n", exclusive=False, with_comments=False)


def sign_nfe_envi_xml(
    unsigned_xml: bytes, certificate_material: EphemeralCertificateMaterial
) -> bytes:
    """Sign exactly one model-55 infNFe element; reject existing signatures.

    XML is parsed with disabled entity/network resolution, and certificate/key
    remain ephemeral. A signer cannot silently replace someone else's signature.
    """
    try:
        root = etree.fromstring(
            unsigned_xml,
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
    except etree.XMLSyntaxError:
        raise FiscalValidationError("XML de NF-e inválido para assinatura") from None
    if root.tag != f"{{{_NFE}}}enviNFe" or root.get("versao") != "4.00":
        raise FiscalValidationError("Assinatura requer lote enviNFe versão 4.00")
    invoices = root.findall(f"{{{_NFE}}}NFe")
    if len(invoices) != 1:
        raise FiscalValidationError("Assinatura A1 exige exatamente uma NF-e por lote")
    invoice = invoices[0]
    if invoice.find(f"{{{_DS}}}Signature") is not None:
        raise FiscalValidationError("XML de NF-e já possui assinatura")
    info = invoice.find(f"{{{_NFE}}}infNFe")
    if info is None:
        raise FiscalValidationError("infNFe ausente")
    identifier = info.get("Id", "")
    if not identifier.startswith("NFe") or len(identifier) != 47:
        raise FiscalValidationError("Id de infNFe inválido")
    environment = invoice.find(f".//{{{_NFE}}}ide/{{{_NFE}}}tpAmb")
    if environment is None or environment.text != "2":
        raise FiscalValidationError(
            "Assinatura fiscal de homologação exige tpAmb=2"
        )
    key, cert, _ = pkcs12.load_key_and_certificates(
        certificate_material.pkcs12_bytes,
        certificate_material.password,
    )
    if not isinstance(key, rsa.RSAPrivateKey) or cert is None:
        raise FiscalValidationError("Assinatura XMLDSig exige certificado A1 RSA")

    signature = etree.Element(f"{{{_DS}}}Signature", nsmap={"ds": _DS})
    signed_info = etree.SubElement(signature, f"{{{_DS}}}SignedInfo")
    etree.SubElement(signed_info, f"{{{_DS}}}CanonicalizationMethod", Algorithm=_C14N)
    etree.SubElement(signed_info, f"{{{_DS}}}SignatureMethod", Algorithm=_RSA_SHA256)
    reference = etree.SubElement(signed_info, f"{{{_DS}}}Reference", URI="#" + identifier)
    transforms = etree.SubElement(reference, f"{{{_DS}}}Transforms")
    etree.SubElement(transforms, f"{{{_DS}}}Transform", Algorithm=_ENVELOPED)
    etree.SubElement(transforms, f"{{{_DS}}}Transform", Algorithm=_C14N)
    etree.SubElement(reference, f"{{{_DS}}}DigestMethod", Algorithm=_SHA256)
    etree.SubElement(reference, f"{{{_DS}}}DigestValue").text = base64.b64encode(
        sha256(_c14n(info)).digest()
    ).decode("ascii")
    # Place Signature first so inherited namespace context is identical
    # while SignedInfo is canonically serialized and after insertion.
    invoice.append(signature)
    etree.SubElement(signature, f"{{{_DS}}}SignatureValue").text = base64.b64encode(
        key.sign(_c14n(signed_info), padding.PKCS1v15(), hashes.SHA256())
    ).decode("ascii")
    key_info = etree.SubElement(signature, f"{{{_DS}}}KeyInfo")
    x509_data = etree.SubElement(key_info, f"{{{_DS}}}X509Data")
    etree.SubElement(x509_data, f"{{{_DS}}}X509Certificate").text = base64.b64encode(
        cert.public_bytes(Encoding.DER)
    ).decode("ascii")
    return etree.tostring(root, encoding="utf-8", xml_declaration=True)


def sign_nfe_event_xml(
    unsigned_xml: bytes,
    certificate_material: EphemeralCertificateMaterial,
    *,
    root_name: str,
    signed_name: str,
    parent_name: str,
) -> bytes:
    """Sign an official SEFAZ infEvento/infInut by Id using RSA-SHA256 XMLDSig."""
    if (root_name, signed_name, parent_name) not in {
        ("envEvento", "infEvento", "evento"),
        ("inutNFe", "infInut", "inutNFe"),
    }:
        raise FiscalValidationError("Unsupported fiscal event signing target")
    try:
        root = etree.fromstring(
            unsigned_xml, parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
    except etree.XMLSyntaxError:
        raise FiscalValidationError("Invalid fiscal event XML") from None
    if root.tag != f"{{{_NFE}}}{root_name}":
        raise FiscalValidationError("Unexpected fiscal event root")
    parents = [root] if parent_name == root_name else root.findall(f"{{{_NFE}}}{parent_name}")
    if len(parents) != 1:
        raise FiscalValidationError("Exactly one fiscal event is required")
    parent = parents[0]
    info = parent.find(f"{{{_NFE}}}{signed_name}")
    identifier = info.get("Id") if info is not None else None
    if info is None or not isinstance(identifier, str) or not identifier.startswith("ID"):
        raise FiscalValidationError("Event reference Id is required")
    if parent.find(f"{{{_DS}}}Signature") is not None:
        raise FiscalValidationError("Event already signed")
    key, cert, _ = pkcs12.load_key_and_certificates(
        certificate_material.pkcs12_bytes, certificate_material.password
    )
    if not isinstance(key, rsa.RSAPrivateKey) or cert is None:
        raise FiscalValidationError("Event XMLDSig requires RSA A1 certificate")
    signature = etree.Element(f"{{{_DS}}}Signature", nsmap={"ds": _DS})
    signed_info = etree.SubElement(signature, f"{{{_DS}}}SignedInfo")
    etree.SubElement(signed_info, f"{{{_DS}}}CanonicalizationMethod", Algorithm=_C14N)
    etree.SubElement(signed_info, f"{{{_DS}}}SignatureMethod", Algorithm=_RSA_SHA256)
    reference = etree.SubElement(
        signed_info, f"{{{_DS}}}Reference", URI="#" + identifier
    )
    transforms = etree.SubElement(reference, f"{{{_DS}}}Transforms")
    etree.SubElement(transforms, f"{{{_DS}}}Transform", Algorithm=_ENVELOPED)
    etree.SubElement(transforms, f"{{{_DS}}}Transform", Algorithm=_C14N)
    etree.SubElement(reference, f"{{{_DS}}}DigestMethod", Algorithm=_SHA256)
    etree.SubElement(reference, f"{{{_DS}}}DigestValue").text = base64.b64encode(
        sha256(_c14n(info)).digest()
    ).decode("ascii")
    parent.append(signature)
    etree.SubElement(signature, f"{{{_DS}}}SignatureValue").text = base64.b64encode(
        key.sign(_c14n(signed_info), padding.PKCS1v15(), hashes.SHA256())
    ).decode("ascii")
    info_node = etree.SubElement(signature, f"{{{_DS}}}KeyInfo")
    cert_node = etree.SubElement(info_node, f"{{{_DS}}}X509Data")
    etree.SubElement(cert_node, f"{{{_DS}}}X509Certificate").text = base64.b64encode(
        cert.public_bytes(Encoding.DER)
    ).decode("ascii")
    return etree.tostring(root, encoding="utf-8", xml_declaration=True)
