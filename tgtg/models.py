from __future__ import annotations

import copy
from abc import ABC
from enum import Enum, StrEnum, auto
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Self, TypeVar, override

import httpx
import jwt
import orjson as jsonlib
from attrs import Attribute, asdict, field, fields, frozen
from attrs.converters import optional
from babel.numbers import format_currency
from loguru import logger
from whenever import Instant, TimeDelta, minutes

from .api import TGTG_BASE_URL
from .utils import format_time, relative_date

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable

    type JSON = dict[str, Any]
    T = TypeVar("T")
    R = TypeVar("R")

logger = logger.opt(colors=True)


def debug(from_json: Callable[[type[T], JSON], R]) -> Callable[[type[T], JSON], R]:
    @wraps(from_json)
    def wrapper(cls: type[T], data: JSON) -> R:
        try:
            return from_json(cls, data.copy())
        except Exception:
            logger.opt(depth=1).debug(data)
            raise

    return wrapper


def relative_local_datetime(ts: Instant) -> tuple[str, str]:
    local_ts = ts.to_system_tz()
    return relative_date(local_ts.date()).capitalize(), format_time(local_ts.time())


def repr_field(obj: object) -> str:
    match obj:
        case None:
            return repr(None)
        case Enum():
            return obj.name
        case Instant():
            date, time = relative_local_datetime(obj)
            return repr(f"{date} at {time}")
        case _:
            return repr(str(obj))


@frozen
class ColorizeMixin:
    @property
    def _non_default_fields(self) -> list[Attribute[object]]:
        return [f for f in fields(type(self)) if getattr(self, f.name) != f.default]

    def colorize(self) -> str:
        field_repr: list[str] = []

        for f in self._non_default_fields:
            if f.repr:
                value = getattr(self, f.name)
                repr_func = repr if f.repr is True else f.repr

                field_repr.append(f"{f.name}=<normal>{repr_func(value)}</normal>")

        return f"{type(self).__name__}(<dim>{', '.join(field_repr)}</dim>)"


@frozen(kw_only=True)
class Credentials(httpx.Auth):
    access_token: str
    refresh_token: str

    @classmethod
    @debug
    def from_json(cls, data: JSON) -> Self:
        del data["access_token_ttl_seconds"]
        return cls(**data)

    @classmethod
    def load(cls, path: Path) -> Self:
        data = jsonlib.loads(path.read_bytes())
        return cls(**data)

    @override
    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response]:
        if request.url.host == TGTG_BASE_URL.host:
            request.headers["Authorization"] = f"Bearer {self.access_token}"
        yield request

    def needs_refresh(self) -> bool:
        data = jwt.decode(self.access_token, options={"verify_signature": False})
        expiration_time = Instant.from_timestamp(data["exp"])
        return expiration_time <= Instant.now()

    def save(self, path: Path) -> None:
        data = asdict(self)
        path.write_bytes(jsonlib.dumps(data))
        if path.is_relative_to(Path.cwd()):
            logger.debug("Saved credentials to<normal>: ./{}</normal>", path.relative_to(Path.cwd()))
        else:
            logger.debug("Saved credentials to<normal>: {}</normal>", path)


# TODO(https://github.com/ariebovenberg/whenever/issues/37): Replace with whenever's interval type
@frozen
class Interval:
    start: Instant
    end: Instant

    @classmethod
    @debug
    def from_json(cls, data: JSON) -> Self:
        start = Instant.parse_common_iso(data.pop("start"))
        end = Instant.parse_common_iso(data.pop("end"))

        return cls(start, end, **data)

    @override
    def __str__(self) -> str:
        start_date, start_time = relative_local_datetime(self.start)
        end_date, end_time = relative_local_datetime(self.end)

        if start_date == end_date:
            return f"{start_date} {start_time}–{end_time}"  # noqa: RUF001
        return f"{start_date} at {start_time}–{end_date} at {end_time}"  # noqa: RUF001


@frozen(kw_only=True)
class Favorite(ColorizeMixin):
    class Packaging(Enum):
        BAG_ALLOWED = auto()
        CANT_BRING_ANYTHING = auto()
        MUST_BRING_BAG = auto()
        MUST_BRING_PACKAGING = auto()

        @property
        def is_provided(self) -> bool:
            return self != self.MUST_BRING_PACKAGING  # type: ignore[comparison-overlap]

    class Tag(StrEnum):
        CHECK_AGAIN_LATER = "Check again later"
        ENDING_SOON = "Ending soon"
        NOTHING_TO_SAVE_TODAY = "Nothing today"
        SOLD_OUT = "Sold out"
        X_ITEMS_LEFT = "X left"

        # Generic tags
        SELLING_FAST = "Selling fast"

        @classmethod
        @debug
        def from_json(cls, data: JSON) -> Favorite.Tag | None:
            match data["id"]:
                case "NEW":
                    return None
                case "GENERIC":
                    tag = cls[data["variant"]]
                case _:
                    tag = cls[data["id"]]

            if tag != cls.X_ITEMS_LEFT:
                assert data["short_text"] == tag, data["short_text"]
            return tag

    id: int = field(
        repr=repr_field,  # TODO(https://github.com/ghostty-org/ghostty/issues/904): Remove `repr` when Ghostty word selection is less greedy
        converter=int,
    )
    name: str
    tag: Tag = field(default=Tag.NOTHING_TO_SAVE_TODAY, repr=repr_field)
    num_available: int = field(default=0, alias="items_available")
    pickup_interval: Interval | None = field(default=None, repr=repr_field, converter=optional(Interval.from_json))  # type: ignore[misc]
    sold_out_at: Instant | None = field(
        default=None,
        repr=repr_field,
        converter=optional(Instant.parse_common_iso),  # type: ignore[misc]
    )
    packaging: Packaging | None = field(
        default=None,
        repr=repr_field,
        converter=[Packaging.__getitem__, lambda p: None if p.is_provided else p],  # type: ignore[attr-defined, misc]
    )

    @classmethod
    @debug
    def from_json(cls, data: JSON) -> Self:
        def build_name(item: JSON, store: JSON) -> str:
            name: list[str] = [store["store_name"].strip()]
            if store_branch := store.get("branch", "").strip():
                name.extend(("-", store_branch))
            item_name = item["name"].strip() or "Surprise Bag"
            name.append(f"({item_name})")

            return " ".join(name)

        def convert_tags(data: Iterable[JSON]) -> Favorite.Tag:
            tags = list(filter(None, map(cls.Tag.from_json, data)))
            assert len(tags) == 1, tags
            return tags[0]

        item: JSON = data.pop("item")
        store: JSON = data.pop("store")
        item_tags: list[JSON] = data.pop("item_tags")

        assert not item["can_user_supply_packaging"], item["can_user_supply_packaging"]

        for key in (
            "display_name",
            "pickup_location",
            "distance",
            "favorite",
            "subscribed_to_notification",
            "in_sales_window",
            "new_item",
            "item_type",
        ):
            del data[key]
        for key in "purchase_end", "sharing_url", "matches_filters", "item_card":
            if key in data:
                del data[key]

        return cls(
            id=item["item_id"],
            name=build_name(item, store),
            packaging=item["packaging_option"],
            tag=convert_tags(item_tags),
            **data,
        )

    @property
    def is_interesting(self) -> bool:
        fields_ = fields(type(self))
        uninteresting_fields = {fields_.id, fields_.name}
        return not set(self._non_default_fields) <= uninteresting_fields

    @property
    def is_selling(self) -> bool:
        return self.tag in {self.Tag.ENDING_SOON, self.Tag.SELLING_FAST, self.Tag.X_ITEMS_LEFT}

    @property
    def is_sold_out(self) -> bool:
        return self.tag == self.Tag.SOLD_OUT

    def colorize_diff(self, old_item: Self) -> str:
        field_repr: list[str] = []

        for f in fields(type(self)):
            if f.repr and not (f.default == getattr(self, f.name) == getattr(old_item, f.name)):
                value = getattr(self, f.name)
                old_value = getattr(old_item, f.name)
                repr_func = repr if f.repr is True else f.repr

                if value == old_value:
                    field_repr.append(f"{f.name}={repr_func(value)}")
                else:
                    field_repr.append(f"{f.name}=<normal><bold>{repr_func(value)}</bold></normal>")

        return f"{type(self).__name__}(<dim>{', '.join(field_repr)}</dim>)"


@frozen(kw_only=True)
class Item(Favorite):
    purchase_limit: int | None = field(default=None, alias="user_purchase_limit")
    next_drop: Instant | None = field(
        default=None,
        repr=repr_field,
        converter=optional(Instant.parse_common_iso),  # type: ignore[misc]
        alias="next_sales_window_purchase_start",
    )
    blocked_until: Instant | None = field(
        default=None,
        repr=repr_field,
        converter=optional(Instant.parse_common_iso),  # type: ignore[misc]
        alias="reservation_blocked_until",
    )

    @property
    def max_quantity(self) -> int:
        return min(self.num_available, self.purchase_limit or self.num_available)


@frozen(kw_only=True)
class Price:
    code: str
    decimals: int
    minor_units: int

    @classmethod
    @debug
    def from_json(cls, data: JSON) -> Self:
        return cls(**data)

    def __add__(self, other: Self) -> Self:
        if not isinstance(other, Price):  # pyright: ignore[reportUnnecessaryIsInstance]
            return NotImplemented  # type: ignore[unreachable]  # pyright: ignore[reportUnreachable]
        if self.code != other.code or self.decimals != other.decimals:
            raise ValueError("Incompatible currencies")

        return copy.replace(self, minor_units=self.minor_units + other.minor_units)  # type: ignore[type-var]

    def __sub__(self, other: Self) -> Self:
        if not isinstance(other, Price):  # pyright: ignore[reportUnnecessaryIsInstance]
            return NotImplemented  # type: ignore[unreachable]  # pyright: ignore[reportUnreachable]
        if self.code != other.code or self.decimals != other.decimals:
            raise ValueError("Incompatible currencies")

        return copy.replace(self, minor_units=self.minor_units - other.minor_units)  # type: ignore[type-var]

    @override
    def __str__(self) -> str:
        return format_currency(self.minor_units / 10**self.decimals, self.code)


@frozen(kw_only=True)
class Order:
    class State(Enum):
        ACTIVE = auto()
        CANCELLED = auto()
        NOT_COLLECTED = auto()
        REDEEMED = auto()
        REFUNDED = auto()

    id: str = field(alias="order_id")
    state: State = field(repr=repr_field, converter=State.__getitem__)  # type: ignore[misc]
    pickup_interval: Interval = field(repr=repr_field, converter=optional(Interval.from_json))  # type: ignore[misc]
    quantity: int
    total_price: Price = field(repr=repr_field, converter=Price.from_json)  # type: ignore[misc]
    time_of_purchase: Instant = field(repr=repr_field, converter=Instant.parse_common_iso)  # type: ignore[misc]
    item_id: str
    pickup_window_changed: bool
    has_dynamic_price: bool
    last_updated_at: Instant = field(repr=repr_field, converter=Instant.parse_common_iso)  # type: ignore[misc]


@frozen(kw_only=True)
class RedeemedOrder(Order):
    redeemed_at: Instant = field(
        repr=repr_field,
        converter=Instant.parse_common_iso,  # type: ignore[misc]
        alias="redeemed_at_utc",
    )


@frozen(kw_only=True)
class RefundedOrder(Order):
    payment_state: str  # TODO: Make this an enum (Payment.State?)
    cancelling_entity: str  # TODO: Make this an enum (Entity?)
    cancelled_or_refunded_at: Instant = field(repr=repr_field, converter=Instant.parse_common_iso)  # type: ignore[misc]


@frozen(kw_only=True)
class Payment:
    class State(Enum):
        AUTHORIZATION_INITIATED = auto()
        AUTHORIZED = auto()
        CANCELLED = auto()
        CAPTURED = auto()
        FAILED = auto()
        FULLY_REFUNDED = auto()

    id: int = field(
        repr=repr_field,  # TODO(https://github.com/ghostty-org/ghostty/issues/904): Remove `repr` when Ghostty word selection is less greedy
        converter=int,
        alias="payment_id",
    )
    payment_provider: str
    state: State = field(repr=repr_field, converter=State.__getitem__)  # type: ignore[misc]

    @classmethod
    @debug
    def from_json(cls, data: JSON) -> Payment:
        for key in "order_id", "user_id":
            del data[key]

        match cls.State[data["state"]]:
            case cls.State.FAILED:
                return FailedPayment(**data)
            case _:
                return Payment(**data)


@frozen(kw_only=True)
class FailedPayment(Payment):
    class FailureReason(Enum):
        FAILED = auto()
        PAYMENT_METHOD_EXPIRED = auto()

    failure_reason: FailureReason = field(repr=repr_field, converter=FailureReason.__getitem__)  # type: ignore[misc]

    @override
    @classmethod
    def from_json(cls, data: JSON) -> Self:
        raise NotImplementedError


@frozen(kw_only=True)
class Reservation(ColorizeMixin):
    class State(Enum):
        RESERVED = auto()

    id: str
    item_id: int = field(
        repr=repr_field,  # TODO(https://github.com/ghostty-org/ghostty/issues/904): Remove `repr` when Ghostty word selection is less greedy
        converter=int,
    )
    state: State = field(repr=repr_field, converter=State.__getitem__)  # type: ignore[misc]
    quantity: int
    total_price: Price = field(repr=repr_field, converter=Price.from_json)  # type: ignore[misc]
    reserved_at: Instant = field(repr=repr_field, converter=Instant.parse_common_iso)  # type: ignore[misc]

    TTL: ClassVar[TimeDelta] = minutes(4)

    @classmethod
    @debug
    def from_json(cls, data: JSON) -> Self:
        order_line: JSON = data.pop("order_line")
        reserved_at: str = data.pop("reserved_at")
        reserved_at += "Z"

        for key in "user_id", "order_type", "might_be_eligible_for_reward":
            del data[key]

        return cls(
            quantity=order_line["quantity"], total_price=order_line["total_price"], reserved_at=reserved_at, **data
        )

    @property
    def expires_at(self) -> Instant:
        return self.reserved_at + self.TTL


@frozen(kw_only=True)
class Voucher(ABC):
    class State(Enum):
        ACTIVE = auto()
        USED = auto()

    class Type(Enum):
        EASY = auto()
        REGULAR = auto()
        USER_REFERRAL = auto()

    class Version(Enum):
        COUNTRY_BASED_SINGLE_USE_VOUCHER = auto()
        CURRENCY_BASED_MULTI_USE_VOUCHER = auto()

    id: int = field(
        repr=repr_field,  # TODO(https://github.com/ghostty-org/ghostty/issues/904): Remove `repr` when Ghostty word selection is less greedy
        converter=int,
    )
    name: str
    state: State = field(repr=repr_field, converter=State.__getitem__)  # type: ignore[misc]
    type: Type = field(repr=repr_field, converter=Type.__getitem__)  # type: ignore[misc]
    version: Version = field(repr=False, converter=Version.__getitem__)  # type: ignore[misc]

    @classmethod
    @debug
    def from_json(cls, data: JSON) -> Voucher:  # type: ignore[return]
        if "store_filter_type" in data:
            assert (store_filter_type := data.pop("store_filter_type")) == "NONE", store_filter_type

        for key in "valid_from", "valid_to":
            del data[key]
        for key in "short_description", "terms_link", "country_id":
            if key in data:
                del data[key]

        match cls.Version[data["version"]]:
            case cls.Version.COUNTRY_BASED_SINGLE_USE_VOUCHER:
                return SingleUseVoucher(**data)
            case cls.Version.CURRENCY_BASED_MULTI_USE_VOUCHER:
                if "items_left" in data:
                    assert not (items_left := data.pop("items_left")), items_left

                return MultiUseVoucher(**data)


@frozen(kw_only=True)
class MultiUseVoucher(Voucher):
    amount: Price = field(repr=repr_field, converter=Price.from_json, alias="current_amount")  # type: ignore[misc]
    original_amount: Price | None = field(default=None, repr=repr_field, converter=optional(Price.from_json))  # type: ignore[misc]

    @override
    @classmethod
    def from_json(cls, data: JSON) -> Self:
        raise NotImplementedError


@frozen(kw_only=True)
class SingleUseVoucher(Voucher):
    max_item_price: Price | None = field(default=None, repr=repr_field, converter=optional(Price.from_json))  # type: ignore[misc]
    items_left: int
    num_items: int | None = field(default=None, alias="number_of_items")

    @override
    @classmethod
    def from_json(cls, data: JSON) -> Self:
        raise NotImplementedError
