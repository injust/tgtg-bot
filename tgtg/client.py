from __future__ import annotations

import copy
from contextlib import AsyncExitStack
from http import HTTPStatus
from http.cookiejar import CookieJar, FileCookieJar, MozillaCookieJar
from http.cookies import SimpleCookie
from itertools import count, repeat
from json import JSONDecodeError
from typing import TYPE_CHECKING, ClassVar, Self, cast, overload, override
from uuid import UUID, uuid4

import anyio
import httpx
import humanize
import orjson as jsonlib
from anyio import create_task_group
from anyio.abc import AsyncResource
from apscheduler import AsyncScheduler
from attrs import Factory, asdict, define, field
from attrs.converters import default_if_none
from babel.core import default_locale
from loguru import logger
from packaging.version import Version
from tenacity import retry, retry_if_exception_type, stop_after_attempt
from whenever import Instant, SystemDateTime, TimeDelta, minutes, seconds

from .api import TGTG_BASE_URL, TgtgApi
from .errors import (
    TgtgAlreadyAbortedError,
    TgtgApiError,
    TgtgCancelDeadlineError,
    TgtgCaptchaError,
    TgtgEmailChangeError,
    TgtgItemDeletedError,
    TgtgItemDisabledError,
    TgtgLimitExceededError,
    TgtgLoginError,
    TgtgPaymentError,
    TgtgReservationBlockedError,
    TgtgSaleClosedError,
    TgtgSoldOutError,
    TgtgUnauthorizedError,
    TgtgValidationError,
)
from .models import Credentials, Favorite, Item, MultiUseVoucher, Payment, Reservation, Voucher
from .ntfy import NtfyClient, Priority
from .utils import (
    HTTPX_LIMITS,
    format_tz_offset,
    httpx_remove_HTTPStatusError_info_suffix,
    httpx_response_json_or_text,
    httpx_response_jsonlib,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterable

    from .models import JSON

logger = logger.opt(colors=True)
httpx.Response.json = httpx_response_jsonlib  # type: ignore[method-assign]
httpx.Response.raise_for_status = httpx_remove_HTTPStatusError_info_suffix(httpx.Response.raise_for_status)  # type: ignore[assignment, method-assign]  # pyright: ignore[reportAttributeAccessIssue]


@define(eq=False)
class DataDomeSdk(AsyncResource):
    cookies: CookieJar
    last_sync: Instant = field(init=False, default=Instant.from_timestamp(0))
    timestamps: list[Instant] = field(init=False, factory=list)

    _exit_stack: AsyncExitStack = field(init=False)
    _httpx: httpx.AsyncClient = field(
        init=False,
        factory=lambda: httpx.AsyncClient(
            headers={"Accept-Encoding": "gzip", "User-Agent": "okhttp/5.0.0-alpha.14"}, http2=True, limits=HTTPX_LIMITS
        ),
    )

    SYNC_INTERVAL: ClassVar[TimeDelta] = seconds(10)

    def __attrs_post_init__(self) -> None:
        del self._httpx.headers["Accept"]  # TODO(https://github.com/encode/httpx/discussions/3037)

    @override
    async def __aenter__(self) -> Self:
        async with AsyncExitStack() as exit_stack:
            await exit_stack.enter_async_context(self._httpx)
            self._exit_stack = exit_stack.pop_all()

        return self

    @override
    async def aclose(self) -> None:
        await self._exit_stack.aclose()

    async def on_response(self, response: httpx.Response) -> None:
        now = Instant.now()
        self.timestamps.append(now)

        if now - self.last_sync < self.SYNC_INTERVAL or not self.cookies:
            return

        cookie = next(
            cookie
            for cookie in self.cookies
            if cookie.domain.removeprefix(".") == TGTG_BASE_URL.host and cookie.name == "datadome"
        )
        self.last_sync = now
        timestamps = self.timestamps
        self.timestamps = []

        r = await self._httpx.post(
            "https://api-sdk.datadome.co/sdk/",
            data={
                "cid": cookie.value,
                "ddk": "1D42C2CA6131C526E09F294FE96F94",
                "request": response.request.url,
                "ua": TgtgClient.USER_AGENT,
                "events": "["
                + ", ".join(
                    f'{{"id":1, "message":"response validation", "source":"sdk", "date":{ts.timestamp_millis()}}}'
                    for ts in timestamps
                )
                + "]",
                "inte": "android-java-okhttp",
                "ddv": "1.14.6",
                "ddvc": TgtgClient.APP_VERSION,
                "os": "Android",
                "osr": 15,
                "osn": "VANILLA_ICE_CREAM",
                "osv": 35,
                "screen_x": 1080,
                "screen_y": 2205,
                "screen_d": 2.625,
                "camera": '{"auth":"false", "info":"{}"}',
                "mdl": "Pixel 6a",
                "prd": "bluejay",
                "mnf": "Google",
                "dev": "bluejay",
                "hrd": "bluejay",
                "fgp": f"google/bluejay/bluejay:15/{TgtgClient.BUILD_ID}/{TgtgClient.BUILD_NUMBER}:user/release-keys",
                "tgs": "release-keys",
            },
        )
        r.status_code = HTTPStatus(r.status_code)

        data = r.json()
        match data["status"]:
            case HTTPStatus.OK:
                cookie.value = SimpleCookie(data["cookie"])["datadome"].value
            case _:
                logger.error("{!r}<normal>: {}</normal>", r.status_code, data)


@define(eq=False)
class TgtgClient(AsyncResource):
    @staticmethod
    def _load_cookies(cookies: FileCookieJar) -> FileCookieJar:
        if not cookies and cookies.filename:
            try:
                cookies.load()
            except FileNotFoundError as e:
                logger.debug(e)
                logger.warning("Could not load cookies from {!r}, using an empty CookieJar", cookies.filename)

        return cookies

    cookies: FileCookieJar = field(converter=[default_if_none(factory=MozillaCookieJar), _load_cookies])  # type: ignore[misc]
    credentials: Credentials = field(init=False)
    email: str = field(init=False)
    user_id: int = field(init=False, converter=int)

    correlation_id: UUID = field(init=False, factory=uuid4)
    device_id: UUID = field(init=False, factory=uuid4)

    datadome: DataDomeSdk = field(
        init=False, default=Factory(lambda self: DataDomeSdk(cast("TgtgClient", self).cookies), takes_self=True)
    )
    ntfy: NtfyClient = field(init=False, factory=lambda: NtfyClient("tgtg-injust"))

    _exit_stack: AsyncExitStack = field(init=False)
    _httpx: httpx.AsyncClient = field(
        init=False,
        default=Factory(
            lambda self: httpx.AsyncClient(
                headers={
                    "Accept-Encoding": "gzip",
                    "Accept-Language": cast("TgtgClient", self).LANGUAGE,
                    "User-Agent": cast("TgtgClient", self).USER_AGENT,
                    "X-Correlation-ID": str(cast("TgtgClient", self).correlation_id),
                },
                cookies=cast("TgtgClient", self).cookies,
                http2=True,
                timeout=httpx.Timeout(5, read=2),  # Fail faster if server randomly drops the request
                limits=HTTPX_LIMITS,
                event_hooks={"response": [cast("TgtgClient", self).datadome.on_response]},
                base_url=TGTG_BASE_URL,
            ),
            takes_self=True,
        ),
    )
    _scheduler: AsyncScheduler = field(init=False, factory=AsyncScheduler)  # pyright: ignore[reportArgumentType, reportCallIssue, reportUnknownVariableType]

    APP_VERSION: ClassVar[Version] = Version("25.5.3")
    BUILD_ID: ClassVar[str] = "BP1A.250505.005"
    BUILD_NUMBER: ClassVar[int] = 13277524
    DEVICE_TYPE: ClassVar[str] = "ANDROID"
    USER_AGENT: ClassVar[str] = f"TGTG/{APP_VERSION} Dalvik/2.1.0 (Linux; U; Android 15; Pixel 6a Build/{BUILD_ID})"

    LANGUAGE: ClassVar[str] = (default_locale() or "en_US").replace("_", "-")
    # Scarborough, Toronto, Canada
    LOCATION: ClassVar[dict[str, float]] = {"latitude": 43.7729744, "longitude": -79.2576479}
    # NOTE: This is actually a float on the wire, but the app constrains it to integer values
    RADIUS: ClassVar[int] = 30
    assert 0 < RADIUS <= 30

    @classmethod
    def from_credentials(cls, credentials: Credentials, cookies: FileCookieJar | None = None) -> Self:
        client = cls(cookies)  # pyright: ignore[reportArgumentType]
        client.credentials = credentials
        return client

    @classmethod
    def from_email(cls, email: str, cookies: FileCookieJar | None = None) -> Self:
        client = cls(cookies)  # pyright: ignore[reportArgumentType]
        client.email = email
        return client

    def __attrs_post_init__(self) -> None:
        assert self.cookies is self._httpx.cookies.jar
        del self._httpx.headers["Accept"]  # TODO(https://github.com/encode/httpx/discussions/3037)

        logger.debug("TGTG app version<normal>: {}</normal>", self.APP_VERSION)
        logger.debug("User agent<normal>: {}</normal>", self.USER_AGENT)

    @override
    async def __aenter__(self) -> Self:
        async with AsyncExitStack() as exit_stack:
            await exit_stack.enter_async_context(self._httpx)
            await exit_stack.enter_async_context(self.datadome)
            await exit_stack.enter_async_context(self.ntfy)

            if not hasattr(self, "credentials"):
                self.credentials = await self.login(self.email)

            startup_data = await self.get_startup_data()
            self.email = startup_data["user"]["email"]
            self.user_id = startup_data["user"]["user_id"]
            logger.debug("Email<normal>: {}</normal>", self.email)

            tg = await exit_stack.enter_async_context(create_task_group())
            tg.start_soon(self._check_rewards)
            tg.start_soon(self._check_user_profile)
            await exit_stack.enter_async_context(self._scheduler)
            await tg.start(self._scheduler.run_until_stopped)

            self._exit_stack = exit_stack.pop_all()

        return self

    @override
    async def aclose(self) -> None:
        await self._exit_stack.aclose()

    @retry(
        stop=stop_after_attempt(2),
        retry=retry_if_exception_type(
            (
                httpx.ReadTimeout,  # Server sporadically drops requests without processing them, should be safe to retry
                httpx.RemoteProtocolError,  # https://github.com/encode/httpx/discussions/3549
            )
        ),
        reraise=True,
    )
    async def _post(self, endpoint: TgtgApi, *path_params: str | int, json: JSON | None = None) -> JSON:
        if endpoint.include_credentials and endpoint != TgtgApi.TOKEN_REFRESH:
            await self.refresh_credentials()

        headers = {"Content-Type": f"application/json{'' if json is None else '; charset=utf-8'}"}
        if endpoint in {TgtgApi.FAVORITES, TgtgApi.ITEMS, TgtgApi.ITEM_STATUS}:
            headers["X-24HourFormat"] = "false"
            headers["X-TimezoneOffset"] = format_tz_offset(SystemDateTime.now().offset)
        r = await self._httpx.post(
            endpoint.format(*path_params),
            content=None if json is None else jsonlib.dumps(json),
            headers=headers,
            auth=self.credentials if endpoint.include_credentials else httpx.USE_CLIENT_DEFAULT,
        )
        r.status_code = HTTPStatus(r.status_code)

        match r.status_code, endpoint:
            case HTTPStatus.BAD_REQUEST, TgtgApi.USER_EMAIL_CHANGE if r.json() == {
                "errors": [{"code": "INVALID_EMAIL_CHANGE_REQUEST"}]
            }:
                raise TgtgEmailChangeError
            case HTTPStatus.BAD_REQUEST, TgtgApi.ITEM_STATUS if r.json() == {"errors": [{"code": "VALIDATION_ERROR"}]}:
                raise TgtgValidationError
            case HTTPStatus.UNAUTHORIZED, _ if endpoint.include_credentials and endpoint != TgtgApi.TOKEN_REFRESH:
                logger.warning("{!r}<normal>: {}</normal>", r.status_code, httpx_response_json_or_text(r))

                try:
                    await self.refresh_credentials(force=True)
                except TgtgApiError as e:
                    raise ValueError("Invalid credentials") from e
                else:
                    return await self._post(endpoint, *path_params, json=json)
            case HTTPStatus.FORBIDDEN, _ if "X-DD-B" in r.headers:
                # TODO: Handle DataDome CAPTCHA
                logger.opt(colors=False).debug(r.text)
                await self.ntfy.publish("DataDome CAPTCHA", priority=Priority.HIGH, tag="rotating_light")
                await self._scheduler.stop()
                raise TgtgCaptchaError
            case HTTPStatus.FORBIDDEN, _ if r.json() == {"errors": [{"code": "UNAUTHORIZED"}]}:
                raise TgtgUnauthorizedError
            case HTTPStatus.GONE, TgtgApi.ITEM_STATUS if r.json() == {"errors": [{"code": "ENTITY_DELETED"}]}:
                raise TgtgItemDeletedError
            case HTTPStatus.GONE, TgtgApi.ITEM_STATUS if r.json() == {"errors": [{"code": "ENTITY_DISABLED"}]}:
                raise TgtgItemDisabledError
            case HTTPStatus.ACCEPTED, TgtgApi.AUTH_BY_POLLING if not r.content:
                return {}
            case (
                HTTPStatus.OK,
                TgtgApi.USER_DATA_EXPORT
                | TgtgApi.USER_DELETE
                | TgtgApi.USER_EMAIL_CHANGE
                | TgtgApi.USER_SET_DEVICE
                | TgtgApi.ITEM_FAVORITE,
            ) if not r.content:
                return {}
            case HTTPStatus.OK, _:
                pass
            case _:
                logger.error("{!r}<normal>: {}</normal>", r.status_code, httpx_response_json_or_text(r))
                r.raise_for_status()

        try:
            data: JSON = r.json()
        except JSONDecodeError as e:
            raise ValueError("Could not decode response as JSON", r.text) from e
        else:
            return data

    async def login(self, email: str) -> Credentials:
        data = await self._post(TgtgApi.AUTH_BY_EMAIL, json={"device_type": self.DEVICE_TYPE, "email": email})

        match data["state"]:
            case "TERMS":
                raise TgtgLoginError(f"{email} is not linked to a TGTG account (hint: sign up in the app first)")
            case "WAIT":
                return await self.poll_login(email, data["polling_id"])
            case _:
                raise TgtgApiError(data)

    async def poll_login(self, email: str, polling_id: str) -> Credentials:
        POLLING_INTERVAL = seconds(5)
        POLLING_MAX_TRIES = minutes(2) // POLLING_INTERVAL

        logger.info("Click the link in your email to continue...")

        for _ in range(POLLING_MAX_TRIES):
            data = await self._post(
                TgtgApi.AUTH_BY_POLLING,
                json={"device_type": self.DEVICE_TYPE, "email": email, "request_polling_id": polling_id},
            )

            if data:
                logger.success("Successfully logged in")
                return Credentials.from_json(data)

            logger.debug("Sleeping for {}...", humanize.precisedelta(POLLING_INTERVAL.py_timedelta()))
            await anyio.sleep(POLLING_INTERVAL.in_seconds())

        raise TgtgLoginError(f"Max polling tries ({POLLING_MAX_TRIES}) reached")

    async def refresh_credentials(self, *, force: bool = False) -> None:
        if not (force or self.credentials.needs_refresh()):
            return

        logger.debug("Forcing credentials refresh..." if force else "Refreshing credentials...")
        data = await self._post(TgtgApi.TOKEN_REFRESH, json={"refresh_token": self.credentials.refresh_token})
        self.credentials = Credentials.from_json(data)
        logger.debug("Successfully refreshed credentials")

    async def get_startup_data(self) -> JSON:
        return await self._post(TgtgApi.APP_ON_STARTUP)

    async def export_user_data(self) -> None:
        await self._post(TgtgApi.USER_DATA_EXPORT, self.user_id, json={"email": self.email})

    async def delete_user(self, confirmation: str = "") -> None:
        if confirmation != "I KNOW WHAT I'M DOING":
            raise ValueError("Are you sure?")
        await self._post(TgtgApi.USER_DELETE, self.user_id, json={"email": self.email})

    async def change_user_email(self, new_email: str) -> None:
        await self._post(TgtgApi.USER_EMAIL_CHANGE, json={"new_email": new_email})

    async def get_user_email_status(self) -> JSON:
        return await self._post(TgtgApi.USER_EMAIL_STATUS)

    async def get_user_profile(self) -> JSON:
        return await self._post(TgtgApi.USER_PROFILE)

    async def _check_user_profile(self) -> None:
        profile = await self.get_user_profile()
        for key in "co2e_saved", "money_saved":
            del profile[key]
        for key in ("latest_completed_order",):
            if key in profile:
                del profile[key]

        if profile["show_special_reward_card"] is False:
            del profile["show_special_reward_card"]
        if profile["feature_cards"] == {"cards": []}:
            del profile["feature_cards"]
        if profile["feature_details"] == [
            {"type": "ORDERS", "state": "ACTIVE"},
            {"type": "IMPACT_TRACKER", "state": "ACTIVE"},
        ]:
            del profile["feature_details"]
        if profile["voucher_tooltip"] == {
            "show_new_voucher_tooltip": False,
            "show_expiring_soon_voucher_tooltip": False,
        }:
            del profile["voucher_tooltip"]

        if profile:
            logger.warning("User profile<normal>: {}</normal>", profile)

    async def set_user_device(self) -> None:
        await self._post(TgtgApi.USER_SET_DEVICE, json={"device_id": self.device_id})

    async def get_invitation_status(self, order_id: str) -> JSON:
        return await self._post(TgtgApi.INVITATION_STATUS, order_id)

    async def get_invitation_link_status(self, invitation_uuid: str) -> JSON:
        return await self._post(TgtgApi.INVITATION_LINK_STATUS, invitation_uuid)

    async def get_order_from_invitation(self, invitation_id: int) -> JSON:
        return await self._post(TgtgApi.INVITATION_ORDER_STATUS, invitation_id)

    async def accept_invitation(self, invitation_uuid: str) -> JSON:
        return await self._post(TgtgApi.INVITATION_ACCEPT, invitation_uuid)

    async def create_invitation(self, order_id: str) -> JSON:
        return await self._post(TgtgApi.INVITATION_CREATE, order_id)

    async def disable_invitation(self, invitation_id: int) -> JSON:
        return await self._post(TgtgApi.INVITATION_DISABLE, invitation_id)

    async def return_invitation(self, invitation_id: int) -> JSON:
        return await self._post(TgtgApi.INVITATION_RETURN, invitation_id)

    async def get_favorites(self, pages: Iterable[int] | None = None) -> list[Favorite]:
        return [f async for f in self._get_favorites(pages)]

    async def _get_favorites(self, pages: Iterable[int] | None = None) -> AsyncGenerator[Favorite]:
        PAGE_SIZE = 50  # Even if >50, server responds with at most 50 items

        if pages is None:
            pages = count()

        for page_num in pages:
            data = await self._post(
                TgtgApi.FAVORITES,
                json={
                    "origin": self.LOCATION,
                    "radius": float(self.RADIUS),
                    "paging": {"page": page_num, "size": PAGE_SIZE},
                    "bucket": {"filler_type": "Favorites"},
                    "filters": [],
                },
            )

            page = data.get("mobile_bucket", {}).get("items", [])
            for item in map(Favorite.from_json, page):
                yield item

            assert "has_more" not in data
            if len(page) < PAGE_SIZE:
                break

    async def get_item(self, item_id: int) -> Item:
        data = await self._post(TgtgApi.ITEM_STATUS, item_id, json={"origin": self.LOCATION})
        return Item.from_json(data)  # type: ignore[return-value]

    @overload
    async def _set_favorite(self, item: Favorite, /, *, is_favorite: bool) -> None: ...
    @overload
    async def _set_favorite(self, item_id: int, /, *, is_favorite: bool) -> None: ...
    async def _set_favorite(self, item_or_id: Favorite | int, *, is_favorite: bool) -> None:
        item_id = item_or_id.id if isinstance(item_or_id, Favorite) else item_or_id

        await self._post(TgtgApi.ITEM_FAVORITE, item_id, json={"is_favorite": is_favorite})

    @overload
    async def favorite(self, item: Favorite, /) -> None: ...
    @overload
    async def favorite(self, item_id: int, /) -> None: ...
    async def favorite(self, item_or_id: Favorite | int) -> None:
        await self._set_favorite(item_or_id, is_favorite=True)

    @overload
    async def unfavorite(self, item: Favorite, /) -> None: ...
    @overload
    async def unfavorite(self, item_id: int, /) -> None: ...
    async def unfavorite(self, item_or_id: Favorite | int) -> None:
        await self._set_favorite(item_or_id, is_favorite=False)

    @overload
    async def reserve(self, item: Favorite, /, quantity: int = 1) -> Reservation: ...
    @overload
    async def reserve(self, item_id: int, /, quantity: int = 1) -> Reservation: ...
    async def reserve(self, item_or_id: Favorite | int, quantity: int = 1) -> Reservation:
        item_id = item_or_id.id if isinstance(item_or_id, Favorite) else item_or_id

        data = await self._post(TgtgApi.ORDER_CREATE, item_id, json={"item_count": quantity})

        match data["state"]:
            case "SALE_CLOSED":
                raise TgtgSaleClosedError
            case "SOLD_OUT":
                raise TgtgSoldOutError
            case "USER_BLOCKED":
                item = await self.get_item(item_id)
                assert item.blocked_until is not None
                logger.error(
                    "Reservation blocked for<normal>: {}</normal>",
                    humanize.precisedelta((item.blocked_until - Instant.now()).py_timedelta()),
                )
                raise TgtgReservationBlockedError
            case "INSUFFICIENT_STOCK":
                item = await self.get_item(item_id)
                logger.error(
                    "Insufficient stock<normal>: <bold>{}</bold> available but <bold>{}</bold> requested</normal>",
                    item.num_available,
                    quantity,
                )
                return await self.reserve(item, item.max_quantity)
            case "OVER_USER_WINDOW_LIMIT":
                item = await self.get_item(item_id)
                logger.error(
                    "Purchase limit exceeded<normal>: <bold>{}</bold> allowed but <bold>{}</bold> requested</normal>",
                    item.purchase_limit,
                    quantity,
                )
                assert item.purchase_limit is not None
                if quantity <= item.purchase_limit:
                    raise TgtgLimitExceededError
                return await self.reserve(item, item.max_quantity)
            case "SUCCESS":
                return Reservation.from_json(data["order"])
            case _:
                raise TgtgApiError(data)

    @overload
    async def abort_reservation(self, reservation: Reservation, /) -> JSON: ...
    @overload
    async def abort_reservation(self, reservation_id: str, /) -> JSON: ...
    async def abort_reservation(self, reservation_or_id: Reservation | str) -> JSON:
        reservation_id = reservation_or_id.id if isinstance(reservation_or_id, Reservation) else reservation_or_id

        data = await self._post(TgtgApi.ORDER_ABORT, reservation_id, json={"cancel_reason_id": 1})

        match data["state"]:
            case "ALREADY_ABORTED":
                raise TgtgAlreadyAbortedError
            case "SUCCESS":
                return data
            case _:
                raise TgtgApiError(data)

    async def get_orders(self) -> list[JSON]:
        return [o async for o in self._get_orders()]

    async def _get_orders(self) -> AsyncGenerator[JSON]:
        async def pages() -> AsyncGenerator[JSON]:
            PAGE_SIZE = 20

            yield (page := await self._post(TgtgApi.ORDERS, json={"paging": {"size": PAGE_SIZE}}))

            while page["has_more"]:
                yield (
                    page := await self._post(
                        TgtgApi.ORDERS,
                        json={
                            "paging": {
                                "size": PAGE_SIZE,
                                "next_page_year": page["next_page_year"],
                                "next_page_month": page["next_page_month"],
                            }
                        },
                    )
                )

        async for page in pages():
            for month in page["orders_per_month"]:
                for order in month["orders"]:
                    yield order

    async def get_active_orders(self) -> list[JSON]:
        data = await self._post(TgtgApi.ORDERS_ACTIVE)
        assert not data["has_more"], data["has_more"]

        orders: list[JSON] = data["orders"]
        return orders

    async def get_order(self, order_id: str) -> JSON:
        return await self._post(TgtgApi.ORDER_STATUS, order_id)

    async def _get_order_short(self, order_id: str) -> JSON:
        return await self._post(TgtgApi.ORDER_STATUS_SHORT, order_id)

    async def cancel_order(self, order_id: str) -> JSON:
        data = await self._post(TgtgApi.ORDER_CANCEL, order_id, json={"cancel_reason_id": 1})

        match data["state"]:
            case "CANCEL_DEADLINE_EXCEEDED":
                raise TgtgCancelDeadlineError
            case "SUCCESS":
                del data["order"]
                return data
            case _:
                raise TgtgApiError(data)

    async def cancel_order_via_support(self, order_id: str, message: str = "Please cancel my order") -> JSON:
        data = await self._post(
            TgtgApi.SUPPORT_REQUEST,
            json={
                "file_urls": [],
                "message": message,
                "subject": "I want to cancel my order",
                "reason": "BAD_ORDER_EXPERIENCE",
                "topic": "CANCEL_ORDER",
                "order_id": order_id,
                "refunding_types": ["VOUCHER", "ORIGINAL_PAYMENT", "REFUSE_REFUND"],
                "confirmation_required_for_duplicate_requests": True,
            },
        )

        match data["support_request_state"]:
            case "ORDER_CANCELLED":
                del data["brief_order"]
                return data
            case _:
                raise TgtgApiError(data)

    @overload
    async def _pay(self, reservation: Reservation, /, authorizations: Iterable[JSON]) -> list[Payment]: ...
    @overload
    async def _pay(self, reservation_id: str, /, authorizations: Iterable[JSON]) -> list[Payment]: ...
    async def _pay(self, reservation_or_id: Reservation | str, authorizations: Iterable[JSON]) -> list[Payment]:
        reservation_id = reservation_or_id.id if isinstance(reservation_or_id, Reservation) else reservation_or_id

        data = await self._post(TgtgApi.ORDER_PAY, reservation_id, json={"authorizations": list(authorizations)})
        return list(map(Payment.from_json, data["payments"]))

    async def pay(self, reservation: Reservation, voucher: MultiUseVoucher | None = None) -> list[Payment]:
        if voucher is None:
            vouchers = [
                v
                for v in await self.get_active_vouchers()
                if isinstance(v, MultiUseVoucher) and v.amount.code == reservation.total_price.code
            ]
            if not vouchers:
                raise TgtgPaymentError("No vouchers available")
            voucher = max(vouchers, key=lambda voucher: voucher.amount.minor_units)
        elif reservation.total_price.code != voucher.amount.code:
            raise ValueError(
                f"Voucher currency ({voucher.amount.code}) does not match order currency ({reservation.total_price.code})"
            )
        else:
            assert reservation.total_price.decimals == voucher.amount.decimals

        # TODO: 21 vouchers (num_ones=10) caused payment failure
        num_ones = max(4, reservation.total_price.minor_units // voucher.amount.minor_units)
        div, mod = divmod(reservation.total_price.minor_units - num_ones, voucher.amount.minor_units)
        amounts = [voucher.amount.minor_units] * div
        if mod:
            amounts.append(mod)
        amounts.extend(repeat(1, num_ones))

        payments = await self._pay(
            reservation,
            [
                {
                    "authorization_payload": {
                        "voucher_id": voucher.id,
                        "save_payment_method": False,
                        "type": "voucherAuthorizationPayload",
                    },
                    "payment_provider": "VOUCHER",
                    "return_url": "adyencheckout://com.app.tgtg.itemview",
                    "amount": asdict(copy.replace(voucher.amount, minor_units=amount)),  # type: ignore[type-var]
                }
                for amount in amounts
            ],
        )
        logger.debug(payments)

        while any(payment.state == Payment.State.AUTHORIZATION_INITIATED for payment in payments):
            await anyio.sleep(1)
            payments = await self.get_order_payment_status(reservation.id)
            logger.debug(payments)

        if any(payment.state == Payment.State.FAILED for payment in payments):
            raise TgtgPaymentError(
                {payment.failure_reason for payment in payments if payment.state == Payment.State.FAILED}
            )

        updated_voucher = await self.get_voucher(voucher.id)
        assert isinstance(updated_voucher, MultiUseVoucher)
        if (deducted_amount := voucher.amount - updated_voucher.amount).minor_units != 1:
            logger.warning("{} deducted from voucher {}", deducted_amount, voucher.id)
            await self.ntfy.publish(f"{deducted_amount} deducted from voucher", priority=Priority.HIGH, tag="tickets")

        assert all(payment.state in {Payment.State.CAPTURED, Payment.State.FULLY_REFUNDED} for payment in payments), (
            payments
        )
        return payments

    async def get_payment_status(self, payment_id: int) -> Payment:
        data = await self._post(TgtgApi.PAYMENT_STATUS, payment_id)
        return Payment.from_json(data)

    async def get_order_payment_status(self, order_id: str) -> list[Payment]:
        data = await self._post(TgtgApi.ORDER_PAYMENT_STATUS, order_id)
        return list(map(Payment.from_json, data["payments"]))

    async def get_rewards(self) -> list[JSON]:
        data = await self._post(TgtgApi.REWARDS)
        rewards: list[JSON] = data["rewards"]
        return rewards

    async def _check_rewards(self) -> None:
        if rewards := await self.get_rewards():
            logger.warning("Rewards<normal>: {}</normal>", rewards)

    async def get_active_vouchers(self) -> list[Voucher]:
        data = await self._post(TgtgApi.VOUCHERS_ACTIVE)
        return list(map(Voucher.from_json, data["vouchers"]))

    async def get_used_vouchers(self) -> list[Voucher]:
        data = await self._post(TgtgApi.VOUCHERS_USED)
        return list(map(Voucher.from_json, data["vouchers"]))

    async def add_voucher(self, voucher_code: str) -> JSON:
        return await self._post(
            TgtgApi.VOUCHER_ADD, json={"activation_code": voucher_code, "device_id": self.device_id}
        )

    async def get_voucher(self, voucher_id: int) -> Voucher:
        data = await self._post(TgtgApi.VOUCHER_STATUS, voucher_id)
        return Voucher.from_json(data["voucher"])
