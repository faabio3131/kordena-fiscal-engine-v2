"""Normalização de pedidos Bling/Tiny para pré-ingestão fiscal, SEM emissão.

A validação de assinatura, replay, tenant, unidade, idempotência e autorização
permanece no ingress canônico; este módulo não oferece endpoint ou webhook.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any


class ConnectorValidationError(ValueError):
    """Pedido externo não possui dados suficientes para normalização segura."""


_UF = frozenset(
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
)
_MONEY = Decimal("0.01")


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ConnectorValidationError(f"{label}: objeto esperado")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, (str, int)) or isinstance(value, bool) or not str(value).strip():
        raise ConnectorValidationError(f"{label}: valor obrigatório")
    return str(value).strip()


def _decimal(value: Any, label: str, *, allow_zero: bool) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ConnectorValidationError(f"{label}: número obrigatório")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ConnectorValidationError(f"{label}: número inválido") from exc
    if not number.is_finite() or number < 0 or (not allow_zero and number == 0):
        raise ConnectorValidationError(f"{label}: valor não permitido")
    return number


def _money(value: Any, label: str) -> Decimal:
    number = _decimal(value, label, allow_zero=True)
    exponent = number.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -2:
        raise ConnectorValidationError(f"{label}: precisão monetária superior a centavos")
    return number.quantize(_MONEY, rounding=ROUND_HALF_UP)


def _code(value: Any, label: str, digits: int) -> str:
    normalized = _text(value, label).replace(".", "")
    if not re.fullmatch(r"[0-9]{" + str(digits) + r"}", normalized):
        raise ConnectorValidationError(f"{label}: formato inválido")
    return normalized


def _document(value: Any) -> str:
    raw = _text(value, "documento")
    normalized = re.sub(r"[.\-/]", "", raw)
    if not normalized.isascii() or not normalized.isdecimal() or len(normalized) not in (11, 14):
        raise ConnectorValidationError("documento: CPF/CNPJ em formato inválido")
    return normalized


def normalize_erp_order(payload: Mapping[str, Any], *, platform: str) -> dict[str, Any]:
    """Extrai pré-ingestão validada; NÃO é FiscalOperationContract nem XML."""
    data = _mapping(payload, "payload")
    if platform == "BLING_V3":
        order = _mapping(data.get("data", data), "data")
        customer = _mapping(order.get("contato"), "contato")
        origin_items = order.get("itens")
        freight = _mapping(order.get("transporte", {}), "transporte").get("frete", "0")
        discount = _mapping(order.get("desconto", {}), "desconto").get("valor", "0")
        customer_uf = _mapping(customer.get("endereco"), "endereco").get("uf")
    elif platform == "TINY_ERP":
        order = _mapping(data.get("pedido", data), "pedido")
        customer = _mapping(order.get("cliente"), "cliente")
        origin_items = order.get("itens")
        freight = order.get("valor_frete", "0")
        discount = order.get("valor_desconto", "0")
        customer_uf = customer.get("uf")
    else:
        raise ConnectorValidationError("plataforma não homologada")
    if not isinstance(origin_items, list) or not origin_items or len(origin_items) > 500:
        raise ConnectorValidationError("itens: lista não vazia de até 500 itens obrigatória")
    uf = _text(customer_uf, "UF").upper()
    if uf not in _UF:
        raise ConnectorValidationError("UF inválida")
    items: list[dict[str, Any]] = []
    for index, raw in enumerate(origin_items, 1):
        line = _mapping(raw, f"item {index}")
        if platform == "TINY_ERP":
            line = _mapping(line.get("item", line), f"item {index}")
        qty = _decimal(line.get("quantidade"), "quantidade", allow_zero=False)
        unit = _decimal(
            line.get("valor" if platform == "BLING_V3" else "valor_unitario"),
            "valor_unitario",
            allow_zero=True,
        )
        product = qty * unit
        if not product.is_finite() or product > Decimal("999999999999.99"):
            raise ConnectorValidationError("valor do item fora de faixa")
        items.append(
            {
                "nItem": index,
                "cProd": _text(line.get("codigo"), "codigo"),
                "xProd": _text(line.get("descricao"), "descricao"),
                "NCM": _code(line.get("ncm"), "NCM", 8),
                "CFOP": _code(line.get("cfop"), "CFOP", 4),
                "qCom": qty,
                "vUnCom": unit,
                "vProd": product.quantize(_MONEY, rounding=ROUND_HALF_UP),
            }
        )
    total = sum((i["vProd"] for i in items), Decimal("0.00"))
    document_field = "numeroDocumento" if platform == "BLING_V3" else "cpf_cnpj"
    order_id = order.get("id")
    if platform == "BLING_V3" and type(order_id) is int and order_id > 0:
        order_id = str(order_id)
    return {
        "source_platform": platform,
        "external_order_id": _text(order_id, "id do pedido"),
        "customer": {
            "document": _document(customer.get(document_field)),
            "name": _text(customer.get("nome"), "nome"),
            "state": uf,
        },
        "items": items,
        "totals": {
            "vProd": total,
            "vFrete": _money(freight, "frete"),
            "vDesc": _money(discount, "desconto"),
        },
        "fiscal_review_required": True,
        "authoritative": False,
    }
