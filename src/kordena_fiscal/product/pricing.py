"""Versioned commercial pricing catalog for FM Fiscal.

Prices, plans, packages, add-ons and promotions are configuration data. The model is deliberately
separate from fiscal authority so commercial changes never rewrite fiscal-domain rules.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum


class CommercialPricingError(ValueError):
    """Raised when commercial pricing configuration is invalid."""


class BillingCadence(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"
    ONE_TIME = "one_time"


class DiscountKind(StrEnum):
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"
    FREE_DAYS = "free_days"


def _required_text(value: str, field_name: str, max_length: int = 256) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        raise CommercialPricingError(
            f"{field_name} must be non-blank and <= {max_length} chars"
        )
    return normalized


def _optional_text(value: str | None, field_name: str, max_length: int = 256) -> str | None:
    if value is None:
        return None
    return _required_text(value, field_name, max_length)


def _money(value: Decimal | str | int | float, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise CommercialPricingError(f"{field_name} must be decimal-compatible")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CommercialPricingError(f"{field_name} must be decimal-compatible") from exc
    if amount < Decimal("0"):
        raise CommercialPricingError(f"{field_name} cannot be negative")
    return amount


def _aware(value: datetime | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise CommercialPricingError(f"{field_name} must be timezone-aware")
    return value


def _active_window(starts_at: datetime | None, ends_at: datetime | None, at: datetime) -> bool:
    if at.tzinfo is None or at.utcoffset() is None:
        raise CommercialPricingError("at must be timezone-aware")
    return (starts_at is None or starts_at <= at) and (ends_at is None or at < ends_at)


@dataclass(frozen=True, slots=True)
class PriceDefinition:
    price_id: str
    currency: str
    cadence: BillingCadence
    base_amount: Decimal
    per_document_amount: Decimal = Decimal("0")
    setup_amount: Decimal = Decimal("0")
    external_price_reference: str | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "price_id", _required_text(self.price_id, "price_id", 128))
        currency = self.currency.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise CommercialPricingError("currency must be a three-letter code")
        if not isinstance(self.cadence, BillingCadence):
            raise CommercialPricingError("cadence must be BillingCadence")
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "base_amount", _money(self.base_amount, "base_amount"))
        object.__setattr__(
            self,
            "per_document_amount",
            _money(self.per_document_amount, "per_document_amount"),
        )
        object.__setattr__(self, "setup_amount", _money(self.setup_amount, "setup_amount"))
        object.__setattr__(
            self,
            "external_price_reference",
            _optional_text(self.external_price_reference, "external_price_reference", 320),
        )


@dataclass(frozen=True, slots=True)
class PlanDefinition:
    plan_id: str
    display_name: str
    edition_id: str
    price_ids: tuple[str, ...]
    trial_days: int = 0
    tags: tuple[str, ...] = ()
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", _required_text(self.plan_id, "plan_id", 128))
        object.__setattr__(
            self,
            "display_name",
            _required_text(self.display_name, "display_name", 160),
        )
        object.__setattr__(self, "edition_id", _required_text(self.edition_id, "edition_id", 128))
        prices = tuple(_required_text(item, "price_id", 128) for item in self.price_ids)
        if not prices or len(prices) != len(set(prices)):
            raise CommercialPricingError("plan price_ids must be non-empty and unique")
        if not isinstance(self.trial_days, int) or isinstance(self.trial_days, bool) or self.trial_days < 0:
            raise CommercialPricingError("trial_days must be integer >= 0")
        object.__setattr__(self, "price_ids", prices)
        object.__setattr__(self, "tags", tuple(_required_text(item, "tag", 64) for item in self.tags))


@dataclass(frozen=True, slots=True)
class AddOnDefinition:
    add_on_id: str
    display_name: str
    price_ids: tuple[str, ...]
    entitlement_ids: tuple[str, ...] = ()
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "add_on_id", _required_text(self.add_on_id, "add_on_id", 128))
        object.__setattr__(
            self,
            "display_name",
            _required_text(self.display_name, "display_name", 160),
        )
        prices = tuple(_required_text(item, "price_id", 128) for item in self.price_ids)
        if not prices or len(prices) != len(set(prices)):
            raise CommercialPricingError("add-on price_ids must be non-empty and unique")
        object.__setattr__(self, "price_ids", prices)
        object.__setattr__(
            self,
            "entitlement_ids",
            tuple(_required_text(item, "entitlement_id", 128) for item in self.entitlement_ids),
        )


@dataclass(frozen=True, slots=True)
class PackageDefinition:
    package_id: str
    display_name: str
    plan_id: str
    add_on_ids: tuple[str, ...]
    price_ids: tuple[str, ...]
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "package_id", _required_text(self.package_id, "package_id", 128))
        object.__setattr__(
            self,
            "display_name",
            _required_text(self.display_name, "display_name", 160),
        )
        object.__setattr__(self, "plan_id", _required_text(self.plan_id, "plan_id", 128))
        object.__setattr__(
            self,
            "add_on_ids",
            tuple(_required_text(item, "add_on_id", 128) for item in self.add_on_ids),
        )
        prices = tuple(_required_text(item, "price_id", 128) for item in self.price_ids)
        if not prices or len(prices) != len(set(prices)):
            raise CommercialPricingError("package price_ids must be non-empty and unique")
        object.__setattr__(self, "price_ids", prices)


@dataclass(frozen=True, slots=True)
class PromotionDefinition:
    promotion_id: str
    display_name: str
    kind: DiscountKind
    value: Decimal
    eligible_price_ids: tuple[str, ...]
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    coupon_code: str | None = None
    max_redemptions: int | None = None
    stackable: bool = False
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "promotion_id",
            _required_text(self.promotion_id, "promotion_id", 128),
        )
        object.__setattr__(
            self,
            "display_name",
            _required_text(self.display_name, "display_name", 160),
        )
        if not isinstance(self.kind, DiscountKind):
            raise CommercialPricingError("kind must be DiscountKind")
        value = _money(self.value, "value")
        if self.kind is DiscountKind.PERCENTAGE and not (Decimal("0") < value <= Decimal("100")):
            raise CommercialPricingError("percentage promotion must be > 0 and <= 100")
        if self.kind is DiscountKind.FREE_DAYS and value != value.to_integral_value():
            raise CommercialPricingError("free_days promotion value must be an integer")
        eligible = tuple(_required_text(item, "eligible_price_id", 128) for item in self.eligible_price_ids)
        if not eligible or len(eligible) != len(set(eligible)):
            raise CommercialPricingError("eligible_price_ids must be non-empty and unique")
        starts = _aware(self.starts_at, "starts_at")
        ends = _aware(self.ends_at, "ends_at")
        if starts is not None and ends is not None and ends <= starts:
            raise CommercialPricingError("ends_at must be after starts_at")
        if self.max_redemptions is not None and (
            not isinstance(self.max_redemptions, int)
            or isinstance(self.max_redemptions, bool)
            or self.max_redemptions < 1
        ):
            raise CommercialPricingError("max_redemptions must be integer >= 1")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "eligible_price_ids", eligible)
        object.__setattr__(self, "starts_at", starts)
        object.__setattr__(self, "ends_at", ends)
        object.__setattr__(
            self,
            "coupon_code",
            _optional_text(self.coupon_code, "coupon_code", 80),
        )

    def active_at(self, at: datetime, *, coupon_code: str | None = None) -> bool:
        if not self.enabled or not _active_window(self.starts_at, self.ends_at, at):
            return False
        if self.coupon_code is None:
            return True
        return coupon_code is not None and coupon_code.strip().casefold() == self.coupon_code.casefold()


@dataclass(frozen=True, slots=True)
class TenantPriceOverride:
    override_id: str
    tenant_id: str
    price_id: str
    base_amount: Decimal | None = None
    per_document_amount: Decimal | None = None
    setup_amount: Decimal | None = None
    contract_reference: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "override_id", _required_text(self.override_id, "override_id", 128))
        object.__setattr__(self, "tenant_id", _required_text(self.tenant_id, "tenant_id", 160))
        object.__setattr__(self, "price_id", _required_text(self.price_id, "price_id", 128))
        if self.base_amount is None and self.per_document_amount is None and self.setup_amount is None:
            raise CommercialPricingError("tenant override must replace at least one amount")
        for field_name in ("base_amount", "per_document_amount", "setup_amount"):
            amount = getattr(self, field_name)
            if amount is not None:
                object.__setattr__(self, field_name, _money(amount, field_name))
        starts = _aware(self.starts_at, "starts_at")
        ends = _aware(self.ends_at, "ends_at")
        if starts is not None and ends is not None and ends <= starts:
            raise CommercialPricingError("ends_at must be after starts_at")
        object.__setattr__(self, "starts_at", starts)
        object.__setattr__(self, "ends_at", ends)
        object.__setattr__(
            self,
            "contract_reference",
            _optional_text(self.contract_reference, "contract_reference", 320),
        )

    def active_at(self, at: datetime) -> bool:
        return self.enabled and _active_window(self.starts_at, self.ends_at, at)


@dataclass(frozen=True, slots=True)
class ResolvedPrice:
    price_id: str
    currency: str
    cadence: BillingCadence
    base_amount: Decimal
    per_document_amount: Decimal
    setup_amount: Decimal
    applied_override_id: str | None
    applied_promotion_ids: tuple[str, ...]
    bonus_trial_days: int


@dataclass(frozen=True, slots=True)
class CommercialPricingConfiguration:
    configuration_id: str
    version: int
    prices: tuple[PriceDefinition, ...]
    plans: tuple[PlanDefinition, ...]
    add_ons: tuple[AddOnDefinition, ...] = ()
    packages: tuple[PackageDefinition, ...] = ()
    promotions: tuple[PromotionDefinition, ...] = ()
    tenant_overrides: tuple[TenantPriceOverride, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "configuration_id",
            _required_text(self.configuration_id, "configuration_id", 160),
        )
        if self.version < 1:
            raise CommercialPricingError("version must be >= 1")
        self._assert_unique("price", tuple(item.price_id for item in self.prices))
        self._assert_unique("plan", tuple(item.plan_id for item in self.plans))
        self._assert_unique("add-on", tuple(item.add_on_id for item in self.add_ons))
        self._assert_unique("package", tuple(item.package_id for item in self.packages))
        self._assert_unique("promotion", tuple(item.promotion_id for item in self.promotions))
        self._assert_unique("override", tuple(item.override_id for item in self.tenant_overrides))
        known_prices = {item.price_id for item in self.prices}
        known_plans = {item.plan_id for item in self.plans}
        known_add_ons = {item.add_on_id for item in self.add_ons}
        for plan in self.plans:
            self._require_known("plan price", plan.price_ids, known_prices)
        for add_on in self.add_ons:
            self._require_known("add-on price", add_on.price_ids, known_prices)
        for package in self.packages:
            if package.plan_id not in known_plans:
                raise CommercialPricingError("package references unknown plan")
            self._require_known("package add-on", package.add_on_ids, known_add_ons)
            self._require_known("package price", package.price_ids, known_prices)
        for promotion in self.promotions:
            self._require_known("promotion price", promotion.eligible_price_ids, known_prices)
        for override in self.tenant_overrides:
            if override.price_id not in known_prices:
                raise CommercialPricingError("tenant override references unknown price")

    @staticmethod
    def _assert_unique(kind: str, ids: tuple[str, ...]) -> None:
        if len(ids) != len(set(ids)):
            raise CommercialPricingError(f"{kind} ids must be unique")

    @staticmethod
    def _require_known(kind: str, ids: Sequence[str], known: set[str]) -> None:
        unknown = set(ids) - known
        if unknown:
            raise CommercialPricingError(f"{kind} references unknown ids: {', '.join(sorted(unknown))}")

    def price(self, price_id: str) -> PriceDefinition:
        wanted = price_id.strip()
        for price in self.prices:
            if price.price_id == wanted:
                return price
        raise CommercialPricingError(f"unknown price: {wanted}")

    def resolve_price(
        self,
        price_id: str,
        *,
        at: datetime,
        tenant_id: str | None = None,
        coupon_code: str | None = None,
    ) -> ResolvedPrice:
        price = self.price(price_id)
        if not price.enabled:
            raise CommercialPricingError("price is disabled")
        base = price.base_amount
        per_document = price.per_document_amount
        setup = price.setup_amount
        applied_override: str | None = None
        if tenant_id is not None:
            normalized_tenant = tenant_id.strip()
            matching = [
                item
                for item in self.tenant_overrides
                if item.tenant_id == normalized_tenant
                and item.price_id == price.price_id
                and item.active_at(at)
            ]
            if len(matching) > 1:
                raise CommercialPricingError("multiple active tenant overrides for the same price")
            if matching:
                override = matching[0]
                base = override.base_amount if override.base_amount is not None else base
                per_document = (
                    override.per_document_amount
                    if override.per_document_amount is not None
                    else per_document
                )
                setup = override.setup_amount if override.setup_amount is not None else setup
                applied_override = override.override_id

        eligible_promotions = [
            promotion
            for promotion in self.promotions
            if price.price_id in promotion.eligible_price_ids
            and promotion.active_at(at, coupon_code=coupon_code)
        ]
        non_stackable = [item for item in eligible_promotions if not item.stackable]
        if len(non_stackable) > 1:
            raise CommercialPricingError("multiple non-stackable promotions are active for the price")
        if non_stackable:
            eligible_promotions = non_stackable

        applied_promotions: list[str] = []
        bonus_trial_days = 0
        for promotion in sorted(eligible_promotions, key=lambda item: item.promotion_id):
            if promotion.kind is DiscountKind.PERCENTAGE:
                factor = (Decimal("100") - promotion.value) / Decimal("100")
                base *= factor
                per_document *= factor
                setup *= factor
            elif promotion.kind is DiscountKind.FIXED_AMOUNT:
                base = max(Decimal("0"), base - promotion.value)
            else:
                bonus_trial_days += int(promotion.value)
            applied_promotions.append(promotion.promotion_id)

        return ResolvedPrice(
            price_id=price.price_id,
            currency=price.currency,
            cadence=price.cadence,
            base_amount=base.quantize(Decimal("0.01")),
            per_document_amount=per_document.quantize(Decimal("0.01")),
            setup_amount=setup.quantize(Decimal("0.01")),
            applied_override_id=applied_override,
            applied_promotion_ids=tuple(applied_promotions),
            bonus_trial_days=bonus_trial_days,
        )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> CommercialPricingConfiguration:
        return cls(
            configuration_id=_string(payload.get("configuration_id"), "configuration_id"),
            version=_integer(payload.get("version"), "version"),
            prices=tuple(_price_from_mapping(item) for item in _mapping_sequence(payload.get("prices"), "prices")),
            plans=tuple(_plan_from_mapping(item) for item in _mapping_sequence(payload.get("plans"), "plans")),
            add_ons=tuple(
                _add_on_from_mapping(item)
                for item in _mapping_sequence(payload.get("add_ons", ()), "add_ons")
            ),
            packages=tuple(
                _package_from_mapping(item)
                for item in _mapping_sequence(payload.get("packages", ()), "packages")
            ),
            promotions=tuple(
                _promotion_from_mapping(item)
                for item in _mapping_sequence(payload.get("promotions", ()), "promotions")
            ),
            tenant_overrides=tuple(
                _override_from_mapping(item)
                for item in _mapping_sequence(payload.get("tenant_overrides", ()), "tenant_overrides")
            ),
        )


class CommercialPricingRegistry:
    """Optimistic authority for replacing the active pricing configuration without code changes."""

    def __init__(self) -> None:
        self._current: CommercialPricingConfiguration | None = None

    @property
    def current(self) -> CommercialPricingConfiguration | None:
        return self._current

    def publish(
        self,
        configuration: CommercialPricingConfiguration,
        *,
        expected_version: int | None,
    ) -> CommercialPricingConfiguration:
        current = self._current
        if current is None:
            if expected_version is not None or configuration.version != 1:
                raise CommercialPricingError("first pricing configuration must be version 1")
        else:
            if expected_version != current.version:
                raise CommercialPricingError("pricing configuration version conflict")
            if configuration.version != current.version + 1:
                raise CommercialPricingError("pricing configuration version must increment by one")
        self._current = configuration
        return configuration


def _price_from_mapping(payload: Mapping[str, object]) -> PriceDefinition:
    return PriceDefinition(
        price_id=_string(payload.get("price_id"), "price_id"),
        currency=_string(payload.get("currency"), "currency"),
        cadence=BillingCadence(_string(payload.get("cadence"), "cadence")),
        base_amount=_decimal(payload.get("base_amount"), "base_amount"),
        per_document_amount=_decimal(payload.get("per_document_amount", "0"), "per_document_amount"),
        setup_amount=_decimal(payload.get("setup_amount", "0"), "setup_amount"),
        external_price_reference=_optional_string(
            payload.get("external_price_reference"),
            "external_price_reference",
        ),
        enabled=_boolean(payload.get("enabled", True), "enabled"),
    )


def _plan_from_mapping(payload: Mapping[str, object]) -> PlanDefinition:
    return PlanDefinition(
        plan_id=_string(payload.get("plan_id"), "plan_id"),
        display_name=_string(payload.get("display_name"), "display_name"),
        edition_id=_string(payload.get("edition_id"), "edition_id"),
        price_ids=tuple(_string_sequence(payload.get("price_ids"), "price_ids")),
        trial_days=_integer(payload.get("trial_days", 0), "trial_days"),
        tags=tuple(_string_sequence(payload.get("tags", ()), "tags")),
        enabled=_boolean(payload.get("enabled", True), "enabled"),
    )


def _add_on_from_mapping(payload: Mapping[str, object]) -> AddOnDefinition:
    return AddOnDefinition(
        add_on_id=_string(payload.get("add_on_id"), "add_on_id"),
        display_name=_string(payload.get("display_name"), "display_name"),
        price_ids=tuple(_string_sequence(payload.get("price_ids"), "price_ids")),
        entitlement_ids=tuple(
            _string_sequence(payload.get("entitlement_ids", ()), "entitlement_ids")
        ),
        enabled=_boolean(payload.get("enabled", True), "enabled"),
    )


def _package_from_mapping(payload: Mapping[str, object]) -> PackageDefinition:
    return PackageDefinition(
        package_id=_string(payload.get("package_id"), "package_id"),
        display_name=_string(payload.get("display_name"), "display_name"),
        plan_id=_string(payload.get("plan_id"), "plan_id"),
        add_on_ids=tuple(_string_sequence(payload.get("add_on_ids", ()), "add_on_ids")),
        price_ids=tuple(_string_sequence(payload.get("price_ids"), "price_ids")),
        enabled=_boolean(payload.get("enabled", True), "enabled"),
    )


def _promotion_from_mapping(payload: Mapping[str, object]) -> PromotionDefinition:
    return PromotionDefinition(
        promotion_id=_string(payload.get("promotion_id"), "promotion_id"),
        display_name=_string(payload.get("display_name"), "display_name"),
        kind=DiscountKind(_string(payload.get("kind"), "kind")),
        value=_decimal(payload.get("value"), "value"),
        eligible_price_ids=tuple(
            _string_sequence(payload.get("eligible_price_ids"), "eligible_price_ids")
        ),
        starts_at=_optional_datetime(payload.get("starts_at"), "starts_at"),
        ends_at=_optional_datetime(payload.get("ends_at"), "ends_at"),
        coupon_code=_optional_string(payload.get("coupon_code"), "coupon_code"),
        max_redemptions=_optional_integer(payload.get("max_redemptions"), "max_redemptions"),
        stackable=_boolean(payload.get("stackable", False), "stackable"),
        enabled=_boolean(payload.get("enabled", True), "enabled"),
    )


def _override_from_mapping(payload: Mapping[str, object]) -> TenantPriceOverride:
    return TenantPriceOverride(
        override_id=_string(payload.get("override_id"), "override_id"),
        tenant_id=_string(payload.get("tenant_id"), "tenant_id"),
        price_id=_string(payload.get("price_id"), "price_id"),
        base_amount=_optional_decimal(payload.get("base_amount"), "base_amount"),
        per_document_amount=_optional_decimal(
            payload.get("per_document_amount"),
            "per_document_amount",
        ),
        setup_amount=_optional_decimal(payload.get("setup_amount"), "setup_amount"),
        contract_reference=_optional_string(
            payload.get("contract_reference"),
            "contract_reference",
        ),
        starts_at=_optional_datetime(payload.get("starts_at"), "starts_at"),
        ends_at=_optional_datetime(payload.get("ends_at"), "ends_at"),
        enabled=_boolean(payload.get("enabled", True), "enabled"),
    )


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CommercialPricingError(f"{field_name} must be a mapping")
    return value


def _mapping_sequence(value: object, field_name: str) -> Sequence[Mapping[str, object]]:
    if not isinstance(value, (list, tuple)):
        raise CommercialPricingError(f"{field_name} must be a sequence")
    return tuple(_mapping(item, f"{field_name} item") for item in value)


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise CommercialPricingError(f"{field_name} must be string")
    return value


def _optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _string(value, field_name)


def _string_sequence(value: object, field_name: str) -> Sequence[str]:
    if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
        raise CommercialPricingError(f"{field_name} must be a string sequence")
    return tuple(value)


def _integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise CommercialPricingError(f"{field_name} must be integer")
    return value


def _optional_integer(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    return _integer(value, field_name)


def _boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise CommercialPricingError(f"{field_name} must be bool")
    return value


def _decimal(value: object, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise CommercialPricingError(f"{field_name} must be decimal-compatible")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CommercialPricingError(f"{field_name} must be decimal-compatible") from exc


def _optional_decimal(value: object, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return _decimal(value, field_name)


def _optional_datetime(value: object, field_name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise CommercialPricingError(f"{field_name} must be ISO datetime string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CommercialPricingError(f"{field_name} must be ISO datetime string") from exc
    return _aware(parsed, field_name)
