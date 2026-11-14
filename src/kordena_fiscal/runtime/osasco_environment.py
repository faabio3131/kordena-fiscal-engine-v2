"""Opt-in Osasco WCF startup on the canonical NFCore API and fiscal database.

An operator-reviewed local manifest pins current WSDL/XSD bytes and per-taxpayer
RTC classifications. Its contents are metadata, never a municipal key.
The only key reader is the existing scoped FiscalSecretVault + Control Plane
over the already configured PostgreSQL unit-of-work and GSM workload identity.
No tax provider is inferred at runtime from municipality or browser data.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from google.auth.external_account import Credentials as FederatedCredentials
from google.cloud import secretmanager_v1
from lxml import etree

from kordena_fiscal.application.service import FiscalApplicationService
from kordena_fiscal.domain import Cnpj, FiscalValidationError
from kordena_fiscal.gateway.osasco_rtc_tax_policy import OsascoReviewedRtcPolicy
from kordena_fiscal.gateway.sp4_municipal_canonical import Sp4OriginalRps, Sp4VerifiedInvoice
from kordena_fiscal.issuance.nfe_nfse import NfseAuthorizationRequest
from kordena_fiscal.persistence.ports import FiscalUnitOfWorkFactory
from kordena_fiscal.vault.contracts import SecretResolutionService
from kordena_fiscal.vault.external import (
    ExternalFiscalSecretVault,
    SecretAccessAuditEvent,
)
from kordena_fiscal.vault.google_secret_manager import (
    DurableGsmReader,
    GoogleFiscalSecretClient,
    GoogleSdkSecretAccess,
)
from kordena_fiscal.xml.schema import SchemaResource, SchemaSet, XmlSchemaValidator

from .config import RuntimeConfigurationError
from .osasco_operational_composition import OsascoTrustedRuntimePorts
from .osasco_pinned_composition import (
    OsascoReviewedSchemaPorts,
    build_osasco_pinned_operational_ports,
)
from .osasco_wsdl_contract import OsascoPinnedWcfWsdl, load_osasco_pinned_wsdl

_ENV = "NFCORE_OSASCO_RTC_CONFIG_PATH"
_MAX = 2_097_152
_SOAP = "{http://schemas.xmlsoap.org/soap/envelope/}"
_WCF = "{http://tempuri.org/}"
_REQUESTS = ("RTC_EmitirNFE", "ConsultarNotaCompleta", "Cancelar")
_SCHEMAS = _REQUESTS + ("ConsultarNotaCompletaResponse", "CancelarResponse")
_TAX_MONEY = frozenset({
    "iss_rate", "pis", "cofins", "csll", "income_tax", "inss", "other_taxes",
})
_TAX_DATES = frozenset({"effective_from", "effective_through"})


def _object(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise RuntimeConfigurationError("Invalid Osasco " + label)
    return value


def _local_resource(directory: Path, name: object, digest: object) -> bytes:
    if (
        not isinstance(name, str) or not name
        or not isinstance(digest, str) or len(digest) != 64
        or any(ch not in "0123456789abcdef" for ch in digest)
        or Path(name).is_absolute() or ".." in Path(name).parts
        or name.startswith(("/", "\\"))
    ):
        raise RuntimeConfigurationError("Invalid Osasco pinned resource")
    base = directory.resolve()
    candidate = (base / name).resolve()
    if not candidate.is_relative_to(base) or not candidate.is_file():
        raise RuntimeConfigurationError("Osasco reviewed resource unavailable")
    if not 0 < candidate.stat().st_size <= _MAX:
        raise RuntimeConfigurationError("Osasco reviewed resource exceeds limit")
    content = candidate.read_bytes()
    if hashlib.sha256(content).hexdigest() != digest:
        raise RuntimeConfigurationError("Osasco WSDL/XSD SHA-256 differs from manifest")
    return content


def _parse_policy(value: object) -> OsascoReviewedRtcPolicy:
    required = set(OsascoReviewedRtcPolicy.__dataclass_fields__) - {
        "no_iss_incidence", "additional_info",
    }
    if not isinstance(value, dict) or not required.issubset(value) or (
        set(value) - required - {"no_iss_incidence", "additional_info"}
    ):
        raise RuntimeConfigurationError("Osasco fiscal policy fields incomplete")
    parsed = dict(value)
    try:
        for key in _TAX_MONEY:
            raw = parsed[key]
            if not isinstance(raw, str) or not raw or any(
                ch not in "0123456789." for ch in raw
            ):
                raise ValueError
            parsed[key] = Decimal(raw)
        for key in _TAX_DATES:
            if parsed[key] is not None:
                if not isinstance(parsed[key], str):
                    raise ValueError
                parsed[key] = date.fromisoformat(parsed[key])
        policy = OsascoReviewedRtcPolicy(**parsed)
        if (
            not isinstance(policy.source_normative, str)
            or not policy.source_normative.startswith(("http://", "https://"))
            or policy.municipal_service_code.strip() == ""
            or not policy.test_only
        ):
            raise ValueError
        return policy
    except (ValueError, TypeError, KeyError, InvalidOperation):
        raise RuntimeConfigurationError("Invalid Osasco reviewed RTC policy") from None


@dataclass(frozen=True, slots=True)
class _Issuer:
    tenant_id: str
    unit_id: str
    issuer_cnpj: str
    profile_id: str
    profile_version: int
    tax_regime: int
    policy: OsascoReviewedRtcPolicy

    @classmethod
    def parse(cls, value: object) -> _Issuer:
        row = _object(value, set(cls.__dataclass_fields__), "issuer")
        try:
            if (
                not all(isinstance(row[key], str) and row[key].strip()
                        for key in ("tenant_id", "unit_id", "issuer_cnpj", "profile_id"))
                or any("*" in row[key] for key in ("tenant_id", "unit_id", "profile_id"))
                or Cnpj(row["issuer_cnpj"]).value != row["issuer_cnpj"]
                or type(row["profile_version"]) is not int
                or row["profile_version"] <= 0
                or type(row["tax_regime"]) is not int
                or row["tax_regime"] != 3
            ):
                raise ValueError
            return cls(
                tenant_id=row["tenant_id"], unit_id=row["unit_id"],
                issuer_cnpj=row["issuer_cnpj"], profile_id=row["profile_id"],
                profile_version=row["profile_version"], tax_regime=row["tax_regime"],
                policy=_parse_policy(row["policy"]),
            )
        except (ValueError, TypeError, KeyError):
            raise RuntimeConfigurationError("Invalid Osasco scoped issuer") from None

    def matches(self, request: NfseAuthorizationRequest) -> bool:
        document = request.document
        return (
            document.scope.tenant_id == self.tenant_id
            and document.scope.unit_id == self.unit_id
            and document.issuer.cnpj.value == self.issuer_cnpj
            and document.issuer.profile_id == self.profile_id
            and document.issuer.version == self.profile_version
            and document.issuer.tax_regime.value == self.tax_regime
            and document.issuer.address.jurisdiction.municipality_ibge_code == "3534401"
            and document.scope.environment.value == "homologation"
        )


def _element(raw: bytes, expected: str) -> etree._Element:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= _MAX:
        raise FiscalValidationError("Osasco XML contract is missing or oversized")
    try:
        node = etree.fromstring(raw, parser=etree.XMLParser(
            load_dtd=False, resolve_entities=False, no_network=True, huge_tree=False,
        ))
    except etree.XMLSyntaxError:
        raise FiscalValidationError("Malformed Osasco contract XML") from None
    if node.tag != expected or getattr(node.getroottree().docinfo, "doctype", ""):
        raise FiscalValidationError("Osasco XML contract root differs")
    return node


def _soap_result(raw: bytes, method: str) -> etree._Element:
    root = _element(raw, _SOAP + "Envelope")
    bodies = root.findall(_SOAP + "Body")
    if len(bodies) != 1 or len(bodies[0]) != 1:
        raise FiscalValidationError("Ambiguous Osasco SOAP result")
    response = bodies[0][0]
    if response.tag != _WCF + method:
        raise FiscalValidationError("Osasco SOAP result operation differs")
    return response


class _SecretAudit:
    """Metadata-only audit; never log municipal credential material."""

    def record(self, event: SecretAccessAuditEvent) -> None:
        logging.getLogger("kordena_fiscal.osasco").info(
            "municipal_secret_access %s %s %s %s",
            event.outcome, event.provider_id, event.environment, event.workload_id,
        )


@dataclass(frozen=True, slots=True)
class OsascoReviewedStartup:
    wsdl: OsascoPinnedWcfWsdl
    validators: Mapping[str, XmlSchemaValidator]
    issuers: tuple[_Issuer, ...]
    gsm_project: str
    gsm_project_number: str
    gsm_resources: frozenset[str]
    workload_id: str

    @classmethod
    def load(cls, filename: str) -> OsascoReviewedStartup:
        path = Path(filename)
        if (
            not path.is_absolute() or not path.is_file()
            or not 0 < path.stat().st_size <= 131_072
        ):
            raise RuntimeConfigurationError("Osasco requires absolute operator manifest path")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            raise RuntimeConfigurationError("Osasco operator manifest is invalid") from None
        config = _object(document, {
            "mode", "wsdl_file", "wsdl_sha256", "binding_name",
            "xsd_resources", "xsd_roots", "issuers", "gsm",
        }, "operator manifest")
        if config["mode"] != "reviewed-homologation":
            raise RuntimeConfigurationError("Osasco operator mode unavailable")
        wfile = _local_resource(path.parent, config["wsdl_file"], config["wsdl_sha256"])
        wsdl = load_osasco_pinned_wsdl(
            document=wfile, expected_sha256=config["wsdl_sha256"],
            binding_name=config["binding_name"],
        )
        raw_resources = config["xsd_resources"]
        roots = _object(config["xsd_roots"], set(_SCHEMAS), "XSD roots")
        if not isinstance(raw_resources, dict) or not raw_resources:
            raise RuntimeConfigurationError("Osasco official XSD resources missing")
        resources = tuple(
            SchemaResource(
                name=name, content=_local_resource(path.parent, name, digest),
                sha256=digest,
            )
            for name, digest in raw_resources.items()
        )
        validators: dict[str, XmlSchemaValidator] = {}
        for operation, name in roots.items():
            if name not in raw_resources:
                raise RuntimeConfigurationError("Osasco official XSD entrypoint missing")
            validators[operation] = XmlSchemaValidator(SchemaSet(
                version="osasco-wcf-2026-reviewed", root_schema=name,
                resources=resources, source_uri=(
                    "https://homolog-nfe.osasco.sp.gov.br/"
                    "EissnfeWebServices/NotaFiscalEletronica.svc?wsdl"
                ),
            ))
        data = config["issuers"]
        if not isinstance(data, list) or not data:
            raise RuntimeConfigurationError("Osasco needs scoped issuer rules")
        issuers = tuple(_Issuer.parse(item) for item in data)
        identities = {
            (item.tenant_id, item.unit_id, item.issuer_cnpj, item.profile_id)
            for item in issuers
        }
        if len(issuers) != len(identities):
            raise RuntimeConfigurationError("Duplicate Osasco scoped issuer rule")
        gsm = _object(config["gsm"], {
            "project_id", "project_number", "resources", "workload_id",
        }, "GSM allowlist")
        project = gsm["project_id"]
        number = gsm["project_number"]
        resources = gsm["resources"]
        workload = gsm["workload_id"]
        if (
            not isinstance(project, str) or not 5 <= len(project) <= 63
            or not all(c.islower() or c.isdigit() or c == "-" for c in project)
            or not isinstance(number, str) or not number.isascii()
            or not number.isdecimal() or not 6 <= len(number) <= 20
            or not isinstance(resources, list) or not resources
            or not all(
                isinstance(resource, str)
                and resource.startswith("projects/" + project + "/secrets/")
                and len(resource) <= 350 and resource.count("/") == 3
                for resource in resources
            )
            or len(resources) != len(set(resources))
            or workload != "nfcore-api"
        ):
            raise RuntimeConfigurationError("Osasco GSM tenant resource allowlist invalid")
        return cls(
            wsdl=wsdl, validators=validators, issuers=issuers,
            gsm_project=project, gsm_project_number=number,
            gsm_resources=frozenset(resources), workload_id=workload,
        )

    def _issuer(self, request: NfseAuthorizationRequest) -> _Issuer:
        candidates = [issuer for issuer in self.issuers if issuer.matches(request)]
        if len(candidates) != 1:
            raise FiscalValidationError("Osasco reviewed issuer/profile is not configured")
        if len(request.document.services) != 1:
            raise FiscalValidationError("Osasco requires single canonical service")
        return candidates[0]

    def schema_ports(self) -> OsascoReviewedSchemaPorts:
        def check_request(operation: str, raw: bytes) -> None:
            root = _element(raw, _WCF + operation)
            # The original request has an empty secret placeholder by design.
            # Substitute a strictly local XSD-only sentinel. It is NEVER sent.
            keys = [
                node for node in root.iter()
                if etree.QName(node).localname == "ChaveAutenticacao"
            ]
            if len(keys) != 1 or keys[0].text:
                raise FiscalValidationError("Osasco secret must not be in prepared XML")
            keys[0].text = "00000000-0000-0000-0000-000000000000"
            self.validators[operation].validate_document(etree.tostring(root))

        def full_invoice(invoice: Sp4VerifiedInvoice) -> None:
            if invoice.issuer_ibge != "3534401":
                raise FiscalValidationError("Wrong municipality in Osasco invoice proof")
            reply = _soap_result(invoice.authorized_xml, "ConsultarNotaCompletaResponse")
            self.validators["ConsultarNotaCompletaResponse"].validate_document(
                etree.tostring(reply),
            )
            # Separate decoder has already correlated RPS/CNPJ/amount/number.
            if not invoice.invoice_number or not invoice.verification_code:
                raise FiscalValidationError("Unverified Osasco fiscal invoice")

        def cancellation(
            raw: bytes, original: Sp4OriginalRps, invoice: Sp4VerifiedInvoice,
        ) -> bool | None:
            if (
                original.issuer_ibge != "3534401"
                or original.issuer_cnpj != invoice.issuer_cnpj
                or original.rps_number != invoice.rps_number
            ):
                raise FiscalValidationError("Osasco cancelled document differs")
            reply = _soap_result(raw, "CancelarResponse")
            self.validators["CancelarResponse"].validate_document(etree.tostring(reply))
            result = [
                node for node in reply
                if etree.QName(node).localname == "CancelarResult"
            ]
            if len(result) != 1:
                return None
            errors = [
                node for node in result[0].iter()
                if etree.QName(node).localname.lower() == "erro"
            ]
            if len(errors) != 1 or errors[0].text is None:
                return None
            value = errors[0].text.strip().lower()
            return True if value == "false" else False if value == "true" else None

        return OsascoReviewedSchemaPorts(
            validate_issuance=lambda raw: check_request("RTC_EmitirNFE", raw),
            validate_query=lambda raw: check_request("ConsultarNotaCompleta", raw),
            validate_cancellation=lambda raw: check_request("Cancelar", raw),
            verify_full_invoice=full_invoice,
            verify_cancellation=cancellation,
        )

    def build_ports(
        self,
        application: FiscalApplicationService,
        *,
        secrets: SecretResolutionService,
        uow_factory: FiscalUnitOfWorkFactory,
    ) -> OsascoTrustedRuntimePorts:
        return build_osasco_pinned_operational_ports(
            application=application, unit_of_work_factory=uow_factory,
            secrets=secrets, workload_id=self.workload_id, wsdl=self.wsdl,
            schema=self.schema_ports(),
            resolve_policy=lambda request, original: self._issuer(request).policy,
            fiscal_issuer_policy=lambda request: self._issuer(request),
        )


def build_osasco_secret_service(
    startup: OsascoReviewedStartup, uow_factory: FiscalUnitOfWorkFactory,
    source: Mapping[str, str],
) -> SecretResolutionService:
    """Reuse canonical scoped GSM/Control Plane; no process env municipal key."""
    runtime = source.get("NFCORE_ENVIRONMENT", "")
    if runtime not in {"staging", "production"}:
        raise RuntimeConfigurationError("Osasco requires staging/production workload")
    try:
        if runtime == "production":
            from .production_gsm import ProductionWorkloadIdentity, production_credentials

            credentials, expiry = production_credentials(
                source, ProductionWorkloadIdentity(
                    role="API", project=startup.gsm_project,
                    service_account=source["NFCORE_GSM_API_SERVICE_ACCOUNT"],
                ),
            )
        else:
            import google.auth

            credential_path = Path(source["NFCORE_OSASCO_GSM_WIF_FILE"])
            stat_info = credential_path.lstat()
            if (
                not credential_path.is_absolute()
                or not stat.S_ISREG(stat_info.st_mode)
                or stat_info.st_mode & 0o077
                or stat_info.st_uid != os.getuid()
                or not 128 <= stat_info.st_size <= 65536
            ):
                raise ValueError
            credentials, _ = google.auth.load_credentials_from_file(
                str(credential_path), scopes=[
                    "https://www.googleapis.com/auth/cloud-platform",
                ],
            )
            if not isinstance(credentials, FederatedCredentials):
                raise ValueError
            expiry = None
        client = secretmanager_v1.SecretManagerServiceClient(
            credentials=credentials,
            client_options={
                "api_endpoint": "secretmanager.googleapis.com",
                "universe_domain": "googleapis.com",
            },
        )
    except Exception:
        raise RuntimeConfigurationError("Osasco GSM trusted workload unavailable") from None
    reader = DurableGsmReader(
        uow_factory=uow_factory,
        access=GoogleSdkSecretAccess(client, bootstrap_not_after=expiry),
        environment=runtime, workload_id=startup.workload_id,
        allowed_resources=startup.gsm_resources,
        project_numbers={startup.gsm_project: startup.gsm_project_number},
    )
    return SecretResolutionService(
        unit_of_work_factory=uow_factory,
        vault=ExternalFiscalSecretVault(
            client=GoogleFiscalSecretClient(reader),
            audit=_SecretAudit(),
        ),
    )


def build_osasco_port_builder_from_environ(
    environ: Mapping[str, str],
    *,
    secrets_factory: Callable[
        [OsascoReviewedStartup, FiscalUnitOfWorkFactory], SecretResolutionService
    ] | None = None,
) -> Callable[[FiscalApplicationService], OsascoTrustedRuntimePorts] | None:
    """Enable a complete Osasco bridge in api:app only from an operator manifest."""
    filename = environ.get(_ENV, "").strip()
    if not filename:
        return None
    if environ.get("NFCORE_ENVIRONMENT") not in {"staging", "production"}:
        raise RuntimeConfigurationError("Osasco configuration requires staging/production")
    startup = OsascoReviewedStartup.load(filename)

    def build(application: FiscalApplicationService) -> OsascoTrustedRuntimePorts:
        # The one FiscalApplicationService is created by canonical composition;
        # use its very same unit of work, not another database/fiscal engine.
        uow_factory: FiscalUnitOfWorkFactory = application._uow_factory
        service = (
            secrets_factory(startup, uow_factory)
            if secrets_factory is not None
            else build_osasco_secret_service(startup, uow_factory, environ)
        )
        if not isinstance(service, SecretResolutionService):
            raise RuntimeConfigurationError("Osasco requires canonical scoped secrets")
        return startup.build_ports(
            application, secrets=service, uow_factory=uow_factory,
        )

    return build
