from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from kordena_fiscal.connectors.bling_canonical import map_bling_document
from kordena_fiscal.documents import (
    FiscalPaymentSnapshot,
    FiscalRecipientSnapshot,
    PaymentMethodKind,
    canonical_sha256,
)
from kordena_fiscal.domain import (
    BrazilianJurisdiction,
    CnaeCode,
    Cnpj,
    ExecutionScope,
    FiscalAddress,
    FiscalEnvironment,
    FiscalProductProfile,
    FiscalProfile,
    FiscalUnitCode,
    FiscalValidationError,
    Money,
    NcmCode,
    ProductOrigin,
    StateRegistration,
    TaxRegimeCode,
)
from kordena_fiscal.tax import (
    TaxRule,
    TaxRuleAmbiguityError,
    TaxRuleNotFoundError,
    TaxRuleOutcome,
    TaxRuleSelector,
)

NOW = datetime(2026, 11, 9, tzinfo=UTC)


@pytest.fixture(params=["sqlite", "postgres"])
def preparation_database(tmp_path, request):
    from test_bling_workflow import workflow_database

    with workflow_database(tmp_path, request.param) as database:
        yield database


@pytest.fixture
def mapping():
    scope = ExecutionScope(
        "tenant", "unit", FiscalEnvironment.HOMOLOGATION, "test", host_namespace="bling"
    )
    issuer = FiscalProfile(
        "issuer",
        scope,
        Cnpj("12345678000195"),
        "Synthetic",
        TaxRegimeCode.SIMPLES_NACIONAL,
        StateRegistration("SP", "123456789"),
        CnaeCode("5611201"),
        FiscalAddress(
            "Rua Sintetica",
            "1",
            "Centro",
            "Sao Paulo",
            BrazilianJurisdiction("SP", "3550308"),
            "01001000",
        ),
        NOW,
    )
    product = FiscalProductProfile(
        "product",
        "p1",
        scope,
        "SKU",
        "Synthetic",
        NcmCode("21069090"),
        FiscalUnitCode("UN"),
        FiscalUnitCode("UN"),
        ProductOrigin.NATIONAL,
        NOW,
    )
    rule = TaxRule(
        "synthetic",
        1,
        TaxRuleSelector(state_code="SP"),
        TaxRuleOutcome("5102", "102", "07", "07"),
        "SYNTHETIC TEST ONLY",
        NOW,
    )
    return dict(
        company_id="company",
        recipient=FiscalRecipientSnapshot(
            Cnpj("12345678000195"), "Synthetic customer", issuer.address, 9, True
        ),
        document_id="doc",
        issued_at=NOW,
        issuer=issuer,
        products_by_code={"SKU": product},
        rules=(rule,),
        payments=(),
    )


def order():
    return {
        "id": 123,
        "itens": [
            {
                "codigo": "SKU",
                "quantidade": "3",
                "valor": "0.3333333333",
                "ncm": "99999999",
                "cfop": "9999",
                "desconto": 10,
            }
        ],
        "totalProdutos": "1.00",
        "total": "1.00",
    }


def test_maps_real_shape_without_provider_tax_hints_or_double_discount(mapping):
    document = map_bling_document(order(), **mapping)
    assert document.items[0].product.ncm.value == "21069090"
    assert document.items[0].tax_decision.outcome.cfop == "5102"
    assert document.items[0].tax_decision.rule_id == "synthetic"
    assert document.items[0].quantity == Decimal("3")
    assert document.totals.net_amount.amount == Decimal("1.00")
    assert canonical_sha256(document) == canonical_sha256(map_bling_document(order(), **mapping))


def test_allocations_reconcile_every_cent_and_payments(mapping):
    raw = {
        "id": 123,
        "itens": [{"codigo": "SKU", "quantidade": "1", "valor": "1.00"} for _ in range(3)],
        "desconto": {"valor": "0.02", "unidade": "REAL"},
        "transporte": {"frete": "0.01"},
        "outrasDespesas": "0.03",
        "totalProdutos": "3.00",
        "total": "3.02",
    }
    mapping["payments"] = (FiscalPaymentSnapshot(PaymentMethodKind.PIX, Money(Decimal("3.02"))),)
    document = map_bling_document(raw, **mapping)
    assert [line.discount_amount.amount for line in document.items] == [
        Decimal(".01"),
        Decimal(".01"),
        0,
    ]
    assert sum(line.surcharge_amount.amount for line in document.items) == Decimal(".04")
    assert document.totals.net_amount.amount == document.totals.payment_amount.amount


@pytest.mark.parametrize(
    "field,value",
    [
        ("total", "0.99"),
        ("totalProdutos", "1.01"),
        ("id", True),
        ("desconto", {"valor": "10", "unidade": "PERCENTUAL"}),
        ("outrasDespesas", "NaN"),
        ("itens", []),
    ],
)
def test_rejects_unreconciled_or_invalid_facts(mapping, field, value):
    raw = order()
    raw[field] = value
    with pytest.raises(FiscalValidationError):
        map_bling_document(raw, **mapping)


def test_scoped_profiles_and_rule_resolution_are_mandatory(mapping):
    product = mapping["products_by_code"]["SKU"]
    mapping["products_by_code"] = {
        "SKU": replace(product, scope=replace(product.scope, tenant_id="other"))
    }
    with pytest.raises(FiscalValidationError, match="another scope"):
        map_bling_document(order(), **mapping)
    mapping["products_by_code"] = {"SKU": product}
    rule = mapping["rules"][0]
    mapping["rules"] = ()
    with pytest.raises(TaxRuleNotFoundError):
        map_bling_document(order(), **mapping)
    mapping["rules"] = (rule, replace(rule, rule_id="another"))
    with pytest.raises(TaxRuleAmbiguityError):
        map_bling_document(order(), **mapping)


def test_recipient_and_rates_are_bound_to_canonical_fingerprint(mapping):
    from kordena_fiscal.tax.nfe_calculation import NfeRateParameters

    original = map_bling_document(order(), **mapping)
    changed = replace(original, recipient=replace(original.recipient, name="Another recipient"))
    assert canonical_sha256(original) != canonical_sha256(changed)
    rule = mapping["rules"][0]
    mapping["rules"] = (
        replace(
            rule,
            outcome=replace(
                rule.outcome,
                nfe_rates=NfeRateParameters(Decimal(0), Decimal(0), Decimal(0), "net", "net"),
            ),
        ),
    )
    assert canonical_sha256(original) != canonical_sha256(map_bling_document(order(), **mapping))


@pytest.fixture
def signing_material():
    from datetime import timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID, ObjectIdentifier

    from kordena_fiscal.vault import EphemeralCertificateMaterial

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic preparation")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.OtherName(ObjectIdentifier("2.16.76.1.3.3"), b"\x0c\x0e12345678000195")]
            ),
            critical=False,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    return EphemeralCertificateMaterial(
        reference_id="synthetic-preparation",
        password=b"test-only",
        pkcs12_bytes=pkcs12.serialize_key_and_certificates(
            b"test-only", key, cert, None, serialization.BestAvailableEncryption(b"test-only")
        ),
    )


def sale_document(mapping, *, normal=False):
    from kordena_fiscal.domain import Gtin
    from kordena_fiscal.tax.nfe_calculation import NfeRateParameters

    if normal:
        mapping["issuer"] = replace(mapping["issuer"], tax_regime=TaxRegimeCode.NORMAL)
    product = mapping["products_by_code"]["SKU"]
    mapping["products_by_code"] = {"SKU": replace(product, gtin=Gtin("SEM GTIN"))}
    rule = mapping["rules"][0]
    mapping["rules"] = (
        replace(
            rule,
            outcome=replace(
                rule.outcome,
                icms_code="00" if normal else "102",
                pis_cst="01" if normal else "07",
                cofins_cst="01" if normal else "07",
                nfe_rates=NfeRateParameters(
                    Decimal("18") if normal else Decimal(0),
                    Decimal("1.65") if normal else Decimal(0),
                    Decimal("7.6") if normal else Decimal(0),
                    "net_less_icms",
                    "net_less_icms",
                ),
            ),
        ),
    )
    mapping["payments"] = (FiscalPaymentSnapshot(PaymentMethodKind.PIX, Money(Decimal("1.00"))),)
    return map_bling_document(order(), **mapping)


@pytest.mark.parametrize("normal", [False, True])
def test_real_order_to_signed_official_schema_and_crypto(mapping, signing_material, normal):
    from lxml import etree

    from kordena_fiscal.domain import ElectronicInvoiceModel
    from kordena_fiscal.issuance.nfe_builder import NfeSaleOptions, build_nfe_sale
    from kordena_fiscal.signing.nfe_xmldsig import (
        NfeSignatureProfile,
        sign_nfe_envi_xml,
        verify_official_nfe4_signature,
    )
    from kordena_fiscal.xml import AccessKeyInput, build_access_key
    from kordena_fiscal.xml.official_nfe_schema import OfficialNfeEnvelopeValidator

    document = sale_document(mapping, normal=normal)
    key = build_access_key(
        AccessKeyInput(
            "35", NOW, document.issuer.cnpj, ElectronicInvoiceModel.NFE, 1, 1, 1, 12345678
        )
    )
    unsigned = build_nfe_sale(document, key, NfeSaleOptions("VENDA", 1, 9))
    signed = sign_nfe_envi_xml(
        unsigned, signing_material, profile=NfeSignatureProfile.NFE4_OFFICIAL_RSA_SHA1
    )
    OfficialNfeEnvelopeValidator()(signed)
    verify_official_nfe4_signature(etree.fromstring(signed), signing_material)


def test_atomic_preparation_replays_without_certificate_and_rolls_back_number(
    mapping, signing_material, tmp_path, preparation_database
):
    from kordena_fiscal.application.nfe_preparation import prepare_nfe_sale
    from kordena_fiscal.application.service import FiscalApplicationService
    from kordena_fiscal.issuance.nfe_builder import NfeSaleOptions
    from kordena_fiscal.lifecycle import FiscalDocumentState

    database = preparation_database
    document = sale_document(mapping)
    options = NfeSaleOptions("VENDA", 1, 9)
    with pytest.raises(FiscalValidationError, match="certificate"):
        prepare_nfe_sale(database, document, options=options, series=1, certificate=None, now=NOW)
    result = prepare_nfe_sale(
        database,
        document,
        options=options,
        series=1,
        certificate=signing_material,
        now=datetime.now(UTC),
    )
    assert result == "doc"
    assert (
        prepare_nfe_sale(database, document, options=options, series=1, certificate=None, now=NOW)
        == result
    )
    prepared = FiscalApplicationService(database).load_prepared_document_authorization(
        document.scope, result
    )
    assert prepared.access_key.value[25:34] == "000000001"
    with database() as uow:
        assert uow.lifecycle.get(result).state is FiscalDocumentState.READY_TO_TRANSMIT
        assert len(uow.archive.list_for_document(document.scope, result)) == 2


def test_configured_native_preparer_queues_signed_document_atomically(
    mapping, signing_material, tmp_path, monkeypatch, preparation_database
):
    import base64
    import hashlib
    import json

    from test_bling_workflow import Transport, create_installation, review_client

    from kordena_fiscal.application.service import FiscalApplicationService
    from kordena_fiscal.runtime.bling_preparation import BlingSalePreparer
    from kordena_fiscal.vault.encrypted_a1 import EncryptedA1Vault
    from kordena_fiscal.xml.official_nfe_schema import OfficialNfeEnvelopeValidator

    database = preparation_database
    _db, application, orders = create_installation(database)
    sale_document(mapping)
    from kordena_fiscal.control_plane.models import FiscalOrganization, FiscalUnitRegistration

    with database() as uow:
        uow.control_plane.add_organization(FiscalOrganization("tenant", "Synthetic"))
        uow.control_plane.add_unit(
            FiscalUnitRegistration(
                "tenant", "unit", "Synthetic", frozenset({FiscalEnvironment.HOMOLOGATION})
            )
        )
        uow.control_plane.add_profile(mapping["issuer"])
        uow.commercial.add_product_profile(mapping["products_by_code"]["SKU"])
        uow.commit()
    raw = {
        **order(),
        "situacao": {"id": 1},
        "parcelas": [{"valor": "1.00", "formaPagamento": {"id": 7}}],
    }
    row = orders.stage(123, raw, event_id="native-test", now=NOW)
    policy = {
        "schema_version": 1,
        "policy_id": "SYNTHETIC-ONLY",
        "version": 1,
        "company_id": orders.company_id,
        "tenant_id": "tenant",
        "unit_id": "unit",
        "environment": "homologation",
        "issuer_profile_id": "issuer",
        "issuer_profile_version": 1,
        "products": {"SKU": {"product_id": "p1", "version": 1}},
        "payment_methods": {"7": "pix"},
        "series": 1,
        "sale_options": {"nature": "VENDA", "presence": 1, "freight_mode": 9},
        "rules": [
            {
                "rule_id": "synthetic-rule",
                "version": 1,
                "source_normative": "SYNTHETIC ONLY",
                "effective_from": NOW.isoformat(),
                "priority": 1,
                "selector": {
                    "state_code": "SP",
                    "tax_regime": 1,
                    "recipient_profile": "consumer_final",
                    "ncm_prefix": "2106",
                },
                "outcome": {
                    "cfop": "5102",
                    "icms_code": "102",
                    "pis_cst": "07",
                    "cofins_cst": "07",
                    "nfe_rates": {
                        "icms_rate": "0",
                        "pis_rate": "0",
                        "cofins_rate": "0",
                        "pis_base": "net",
                        "cofins_base": "net",
                    },
                },
            }
        ],
    }
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    preparer = BlingSalePreparer(
        {"NFCORE_BLING_FISCAL_POLICY_FILE": str(path), "NFCORE_BLING_FISCAL_POLICY_SHA256": digest}
    )
    payload = {
        "snapshot_sha256": row["snapshot_sha256"],
        "policy_sha256": digest,
        "issued_at": NOW.isoformat(),
        "recipient": {
            "document": "12345678000195",
            "name": "Synthetic buyer",
            "street": "Rua Sintetica",
            "number": "1",
            "district": "Centro",
            "municipality_name": "Sao Paulo",
            "municipality_ibge_code": "3550308",
            "state": "SP",
            "postal_code": "01001000",
            "ie_indicator": 9,
            "final_consumer": True,
        },
    }
    with pytest.raises(FiscalValidationError):
        preparer.prepare(orders, 123, payload, "reviewer")
    assert orders.get(123)["document_id"] is None
    monkeypatch.setenv("NFCORE_A1_VAULT_DIR", str(tmp_path / "vault"))
    monkeypatch.setenv("NFCORE_A1_VAULT_KEY_BASE64", base64.b64encode(bytes(range(32))).decode())
    vault = EncryptedA1Vault.from_environ()
    vault.provision(
        scope=orders.scope,
        issuer_cnpj="12345678000195",
        pkcs12_bytes=signing_material.pkcs12_bytes,
        password=signing_material.password,
    )
    client = review_client(orders, preparer=preparer)
    path = "/v1/portal/integrations/bling/orders/123"
    assert client.get(path).json()["preparation"]["sha256"] == digest
    assert client.post(path + "/prepare", json=payload).status_code == 403
    response = client.post(
        path + "/prepare", json=payload, headers={"X-CSRF-Token": client.cookies.get("nfcore_csrf")}
    )
    assert response.status_code == 200, response.text
    document_id = response.json()["document_id"]
    assert orders.get(123)["state"] == "queued"
    assert orders.get(123)["document_id"] == document_id
    prepared = FiscalApplicationService(database).load_prepared_document_authorization(
        orders.scope, document_id
    )
    OfficialNfeEnvelopeValidator()(prepared.signed_xml)
    monkeypatch.delenv("NFCORE_A1_VAULT_DIR")
    monkeypatch.delenv("NFCORE_A1_VAULT_KEY_BASE64")
    assert preparer.prepare(orders, 123, payload, "reviewer") == document_id
    assert prepared.access_key.value[25:34] == "000000001"

    from kordena_fiscal.application.bling_orders import ISSUE_ORDER, PUBLISH_STATUS
    from kordena_fiscal.application.bling_processing import BlingProcessingHandler
    from kordena_fiscal.application.bling_status_delivery import BlingStatusPublisher
    from kordena_fiscal.application.outbox_worker import DurableFiscalOutboxWorker
    from kordena_fiscal.contingency import FiscalOutboxStatus
    from kordena_fiscal.contingency.outbox import OutboxClaimSelection
    from kordena_fiscal.gateway import FiscalGatewayClient
    from kordena_fiscal.runtime.fiscal_runtime import CanonicalFiscalOperationPath
    from kordena_fiscal.runtime.provider_issuance_handler import build_provider_issuance_handler

    transport = Transport()
    fiscal_path = CanonicalFiscalOperationPath(
        application,
        handlers={
            "issueFiscalDocument": build_provider_issuance_handler(
                application,
                resolve_prepared=application.load_prepared_document_authorization,
                gateway=FiscalGatewayClient(transport),
            )
        },
    )
    issue = BlingProcessingHandler(orders, lambda _id: raw, fiscal_path)
    worker = DurableFiscalOutboxWorker(
        uow_factory=database,
        handler=issue,
        claim_selection=OutboxClaimSelection(orders.scope, frozenset({ISSUE_ORDER})),
    )
    (job,) = worker.run_once(now=datetime.now(UTC))
    assert job.status is FiscalOutboxStatus.SUCCEEDED
    assert orders.get(123)["state"] == "authorized"
    issue.dispatch(job)
    assert transport.calls == 1
    writes = []
    publisher = BlingStatusPublisher(
        orders,
        {"authorized": 10, "rejected": 11},
        lambda _id: raw,
        lambda order_id, status_id: writes.append((order_id, status_id)),
    )
    returned = DurableFiscalOutboxWorker(
        uow_factory=database,
        handler=publisher,
        claim_selection=OutboxClaimSelection(orders.scope, frozenset({PUBLISH_STATUS})),
    )
    assert returned.run_once(now=datetime.now(UTC))[0].status is FiscalOutboxStatus.SUCCEEDED
    assert writes == [(123, 10)]


@pytest.mark.parametrize(
    "method",
    [
        PaymentMethodKind.PIX,
        PaymentMethodKind.CASH,
        PaymentMethodKind.BOLETO,
        PaymentMethodKind.VOUCHER,
        PaymentMethodKind.CREDIT_CARD,
        PaymentMethodKind.DEBIT_CARD,
    ],
)
def test_internet_sale_payment_groups_match_official_schema(mapping, signing_material, method):
    from kordena_fiscal.domain import ElectronicInvoiceModel
    from kordena_fiscal.issuance.nfe_builder import NfeSaleOptions, build_nfe_sale
    from kordena_fiscal.signing.nfe_xmldsig import NfeSignatureProfile, sign_nfe_envi_xml
    from kordena_fiscal.xml import AccessKeyInput, build_access_key
    from kordena_fiscal.xml.official_nfe_schema import OfficialNfeEnvelopeValidator

    doc = sale_document(mapping)
    doc = replace(doc, payments=(FiscalPaymentSnapshot(method, Money(Decimal("1.00"))),))
    key = build_access_key(
        AccessKeyInput("35", NOW, doc.issuer.cnpj, ElectronicInvoiceModel.NFE, 1, 1, 1, 12345678)
    )
    options = NfeSaleOptions(
        "VENDA",
        2,
        9,
        intermediary_indicator=1,
        intermediary_cnpj="12345678000195",
        intermediary_registration="synthetic-merchant",
        card_integration_type=2,
    )
    signed = sign_nfe_envi_xml(
        build_nfe_sale(doc, key, options),
        signing_material,
        profile=NfeSignatureProfile.NFE4_OFFICIAL_RSA_SHA1,
    )
    OfficialNfeEnvelopeValidator()(signed)


def test_canonical_rate_arithmetic_is_explicit_and_unsupported_never_defaults_to_zero(mapping):
    from kordena_fiscal.tax.nfe_calculation import calculate_nfe_line

    doc = sale_document(mapping, normal=True)
    decision = doc.items[0].tax_decision
    taxes = calculate_nfe_line(decision, net_amount=Decimal("100.00"), regime=TaxRegimeCode.NORMAL)
    assert taxes.icms_base == Decimal("100.00")
    assert taxes.icms_amount == Decimal("18.00")
    assert taxes.pis_base == taxes.cofins_base == Decimal("82.00")
    assert taxes.pis_amount == Decimal("1.35")
    assert taxes.cofins_amount == Decimal("6.23")
    for outcome in (
        replace(decision.outcome, nfe_rates=None),
        replace(decision.outcome, icms_code="60"),
        replace(decision.outcome, pis_cst="49"),
        replace(decision.outcome, ibs_cbs_classification_code="000001"),
    ):
        with pytest.raises(FiscalValidationError):
            calculate_nfe_line(
                replace(decision, outcome=outcome),
                net_amount=Decimal("100.00"),
                regime=TaxRegimeCode.NORMAL,
            )


def test_snapshot_conflict_rolls_back_signed_preparation_and_number(
    mapping, signing_material, tmp_path, preparation_database
):
    from kordena_fiscal.application.bling_orders import BlingOrders
    from kordena_fiscal.application.nfe_preparation import prepare_nfe_sale
    from kordena_fiscal.issuance.nfe_builder import NfeSaleOptions
    from kordena_fiscal.persistence import PersistenceConflictError

    db = preparation_database
    doc = sale_document(mapping)
    orders = BlingOrders(db, doc.scope, "company")
    row = orders.stage(123, order(), event_id="one", now=NOW)
    orders.stage(123, {**order(), "observacoes": "changed"}, event_id="two", now=NOW)
    options = NfeSaleOptions("VENDA", 1, 9)
    with pytest.raises(PersistenceConflictError):
        orders.prepare_sale(
            123,
            doc,
            snapshot_sha256=row["snapshot_sha256"],
            actor_id="actor",
            now=datetime.now(UTC),
            options=options,
            series=1,
            certificate=signing_material,
        )
    with db() as uow:
        assert uow.lifecycle.get(doc.document_id) is None
        assert not uow.archive.list_for_document(doc.scope, doc.document_id)
    from kordena_fiscal.application.service import FiscalApplicationService

    prepare_nfe_sale(
        db, doc, options=options, series=1, certificate=signing_material, now=datetime.now(UTC)
    )
    request = FiscalApplicationService(db).load_prepared_document_authorization(
        doc.scope, doc.document_id
    )
    assert request.access_key.value[25:34] == "000000001"
