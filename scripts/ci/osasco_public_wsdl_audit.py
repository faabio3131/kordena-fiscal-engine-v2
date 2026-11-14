"""Download-only audit of the public Osasco municipality WCF contract.

Runs in an isolated GitHub Actions branch, fetching ONLY public HTTPS WSDL/XSD
metadata. Never POST, import credentials, or call fiscal emission endpoints.
The resulting byte-for-byte evidence is committed only to the probe branch.
"""
from __future__ import annotations

import hashlib
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from lxml import etree

TARGET = "https://homolog-nfe.osasco.sp.gov.br/EissnfeWebServices/NotaFiscalEletronica.svc?singleWsdl"
WSDL = "{http://schemas.xmlsoap.org/wsdl/}"
SOAP = "{http://schemas.xmlsoap.org/wsdl/soap/}"
XSD = "{http://www.w3.org/2001/XMLSchema}"
MAX_DOWNLOAD = 12 * 1024 * 1024
REQUIRED = ("RTC_EmitirNFE", "ConsultarNotaCompleta", "Cancelar")
DEST = Path("contracts/official/osasco/homologation")
EXPECTED_DOMAIN = "homolog-nfe.osasco.sp.gov.br"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Unexpected redirected official WSDL")


def download(url: str) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != EXPECTED_DOMAIN or parsed.username:
        raise RuntimeError("Unapproved Osasco public WSDL URL")
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        NoRedirect(),
    )
    with opener.open(urllib.request.Request(
        url, headers={"User-Agent": "NFCore-WSDL-ReadOnly-Audit/1.0",
                      "Accept": "text/xml, application/xml"},
    ), timeout=35) as response:
        raw = response.read(MAX_DOWNLOAD + 1)
        if response.status != 200 or not 100 <= len(raw) <= MAX_DOWNLOAD:
            raise RuntimeError("Osasco WSDL status or size rejected")
        if "html" in response.headers.get("Content-Type", "").lower():
            raise RuntimeError("Osasco service returned HTML instead of contract XML")
        return raw


def parse(raw: bytes, expected_root: str) -> etree._Element:
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise RuntimeError("Municipal WSDL contains forbidden DTD/entity")
    root = etree.fromstring(raw, parser=etree.XMLParser(
        no_network=True, resolve_entities=False, load_dtd=False,
        huge_tree=False, recover=False,
    ))
    if root.tag != expected_root or root.getroottree().docinfo.doctype:
        raise RuntimeError("Unexpected official contract XML root")
    return root


def main() -> None:
    raw = download(TARGET)
    root = parse(raw, WSDL + "definitions")
    bindings: dict[str, dict[str, str]] = {}
    for binding in root.findall(WSDL + "binding"):
        name = binding.get("name")
        if not name or binding.find(SOAP + "binding") is None:
            continue
        operations: dict[str, str] = {}
        for op in binding.findall(WSDL + "operation"):
            soap_op = op.find(SOAP + "operation")
            if soap_op is None or not soap_op.get("soapAction") or not op.get("name"):
                continue
            operations[op.get("name")] = soap_op.get("soapAction")
        if all(method in operations for method in REQUIRED):
            bindings[name] = operations

    if not bindings:
        raise RuntimeError("Official Osasco WSDL lacks required SOAP 1.1 operations")
    schemas = root.findall(".//" + XSD + "schema")
    if not schemas:
        raise RuntimeError("Official WSDL contains no inline XSD schemas")
    namespaces = [s.get("targetNamespace", "") for s in schemas]
    if len(set(namespaces)) != len(namespaces):
        # Preserve duplicate namespace schemas without silently dropping any.
        print("NOTE: duplicate inline XSD namespace declarations", flush=True)

    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "NotaFiscalEletronica.singleWsdl.xml").write_bytes(raw)
    schema_evidence = []
    for n, schema in enumerate(schemas):
        content = etree.tostring(schema, encoding="utf-8", xml_declaration=True)
        filename = f"inline-xsd-{n:03}.xsd"
        (DEST / filename).write_bytes(content)
        schema_evidence.append({
            "file": filename, "target_namespace": namespaces[n],
            "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content),
            "elements": sorted(x.get("name") for x in schema.findall(XSD + "element")
                               if x.get("name")),
        })
    manifest = {
        "source": TARGET,
        "observed_utc": datetime.now(UTC).isoformat(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
        "bindings": bindings,
        "inline_schemas": schema_evidence,
        "purpose": "Public official WSDL/XSD evidence only; no municipal authorization",
    }
    (DEST / "audited-contract.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print("OFFICIAL_WSDL_SHA256 " + manifest["sha256"], flush=True)
    print("OFFICIAL_WSDL_SIZE " + str(len(raw)), flush=True)
    print("OFFICIAL_XSD_COUNT " + str(len(schemas)), flush=True)
    print("OFFICIAL_WCF_BINDINGS " + json.dumps(bindings), flush=True)
    print("OFFICIAL_XSD_NAMESPACES " + json.dumps(sorted(set(namespaces))), flush=True)
    print("NO FISCAL TRANSACTIONS WERE PERFORMED", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, urllib.error.URLError, etree.XMLSyntaxError) as exc:
        print("OFFICIAL CONTRACT AUDIT FAILED: " + str(exc)[:300], file=sys.stderr)
        raise SystemExit(1) from None
