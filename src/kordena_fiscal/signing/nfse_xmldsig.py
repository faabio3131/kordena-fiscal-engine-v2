"""Enveloped XMLDSig RSA/SHA-256 for official National NFS-e DPS XML.

The caller supplies an authorized tenant-bound A1 from the existing Vault.
No taxpayer information is inferred or inserted in this signing boundary.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding, pkcs12
from lxml import etree

from kordena_fiscal.domain import FiscalValidationError
from kordena_fiscal.vault import EphemeralCertificateMaterial

_DS = "http://www.w3.org/2000/09/xmldsig#"
_C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
_RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
_SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"
_ENVELOPED = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"


def sign_nfse_dps_xml(
    unsigned_xml: bytes, certificate_material: EphemeralCertificateMaterial
) -> bytes:
    """Sign the unique infDPS/Id reference and embed one Signature in DPS."""
    if not unsigned_xml or len(unsigned_xml) > 2_097_152:
        raise FiscalValidationError("DPS inválida ou excede limite de assinatura")
    try:
        root = etree.fromstring(
            unsigned_xml,
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
    except etree.XMLSyntaxError:
        raise FiscalValidationError("XML DPS inválido") from None
    if etree.QName(root).localname != "DPS":
        raise FiscalValidationError("Assinatura NFS-e requer DPS")
    info_nodes = [
        child for child in root if etree.QName(child).localname == "infDPS"
    ]
    if len(info_nodes) != 1:
        raise FiscalValidationError("Assinatura requer uma infDPS")
    info = info_nodes[0]
    identifier = info.get("Id", "")
    if not identifier.startswith("DPS") or len(identifier) > 100:
        raise FiscalValidationError("Id de DPS inválido")
    environments = [
        child for child in root.iter() if etree.QName(child).localname == "tpAmb"
    ]
    if len(environments) != 1 or environments[0].text != "2":
        raise FiscalValidationError("Assinatura DPS permitida somente em tpAmb=2")
    if any(etree.QName(child).localname == "Signature" for child in root):
        raise FiscalValidationError("DPS já está assinada")
    key, cert, _ = pkcs12.load_key_and_certificates(
        certificate_material.pkcs12_bytes, certificate_material.password
    )
    if not isinstance(key, rsa.RSAPrivateKey) or cert is None:
        raise FiscalValidationError("Assinatura DPS exige identidade A1 RSA")

    signature = etree.Element(f"{{{_DS}}}Signature", nsmap={"ds": _DS})
    signed_info = etree.SubElement(signature, f"{{{_DS}}}SignedInfo")
    etree.SubElement(signed_info, f"{{{_DS}}}CanonicalizationMethod", Algorithm=_C14N)
    etree.SubElement(signed_info, f"{{{_DS}}}SignatureMethod", Algorithm=_RSA_SHA256)
    reference = etree.SubElement(signed_info, f"{{{_DS}}}Reference", URI="#" + identifier)
    transforms = etree.SubElement(reference, f"{{{_DS}}}Transforms")
    etree.SubElement(transforms, f"{{{_DS}}}Transform", Algorithm=_ENVELOPED)
    etree.SubElement(transforms, f"{{{_DS}}}Transform", Algorithm=_C14N)
    etree.SubElement(reference, f"{{{_DS}}}DigestMethod", Algorithm=_SHA256)
    canonical_info = etree.tostring(info, method="c14n", exclusive=False, with_comments=False)
    etree.SubElement(reference, f"{{{_DS}}}DigestValue").text = base64.b64encode(
        hashlib.sha256(canonical_info).digest()
    ).decode("ascii")
    root.append(signature)
    canonical_signed_info = etree.tostring(
        signed_info, method="c14n", exclusive=False, with_comments=False
    )
    etree.SubElement(signature, f"{{{_DS}}}SignatureValue").text = base64.b64encode(
        key.sign(canonical_signed_info, padding.PKCS1v15(), hashes.SHA256())
    ).decode("ascii")
    key_info = etree.SubElement(signature, f"{{{_DS}}}KeyInfo")
    x509_data = etree.SubElement(key_info, f"{{{_DS}}}X509Data")
    etree.SubElement(x509_data, f"{{{_DS}}}X509Certificate").text = base64.b64encode(
        cert.public_bytes(Encoding.DER)
    ).decode("ascii")
    return etree.tostring(root, encoding="utf-8", xml_declaration=True)
