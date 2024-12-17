from __future__ import annotations

import sys
from asyncio import CancelledError
from contextlib import AsyncExitStack
from functools import partial
from http.cookiejar import MozillaCookieJar
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import anyio
import httpx
from anyio import create_task_group
from apscheduler import ConflictPolicy
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from attrs import field, frozen
from loguru import logger
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)
from whenever import TimeDelta, seconds

from . import items
from .client import TgtgClient
from .errors import TgtgApiError
from .models import Credentials, Item, Reservation

if TYPE_CHECKING:
    from apscheduler.abc import Trigger

    from .models import JSON

logger = logger.opt(colors=True)
retry_policy = retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(0.5),
    retry=retry_if_exception_type(httpx.TransportError)
    | retry_if_exception(lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.is_server_error),
    before_sleep=before_sleep_log(logger, "DEBUG"),  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
)

COOKIES_PATH = (Path.cwd() / "cookies.txt").resolve()
CREDENTIALS_PATH = (Path.cwd() / "credentials.json").resolve()


@frozen(eq=False)
class Bot:
    tracked_items: dict[int, Item | None]

    client: TgtgClient = field(
        init=False,
        factory=lambda: TgtgClient.from_credentials(Credentials.load(CREDENTIALS_PATH), MozillaCookieJar(COOKIES_PATH)),
    )

    CATCH_RESERVATION_DELAY: ClassVar[TimeDelta] = seconds(1)
    CHECK_FAVORITES_TRIGGER: ClassVar[Trigger] = IntervalTrigger(seconds=2)

    @logger.catch
    @retry_policy
    async def hold(self, item: Item, quantity: int) -> Reservation | None:
        try:
            reservation = await self.client.reserve(item, quantity)
        except TgtgApiError as e:
            logger.error("Item {}<normal>: {!r}</normal>", item.id, e)
            return None
        else:
            logger.success(f"<normal>{reservation.colorize()}</normal>")

            await self.client._scheduler.add_schedule(
                partial(self.hold, item, reservation.quantity),
                DateTrigger((reservation.expires_at + self.CATCH_RESERVATION_DELAY).py_datetime()),
                id=f"catch-reservation-{reservation.id}",
                conflict_policy=ConflictPolicy.exception,
            )

            return reservation

    @logger.catch
    @retry_policy
    async def order(self, item: Item, quantity: int) -> JSON | None:
        try:
            reservation = await self.client.reserve(item, quantity)
            logger.debug(reservation)
            await self.client.pay(reservation)
            order: JSON = (await self.client.get_order(reservation.id))["order"]
        except TgtgApiError as e:
            logger.error("Item {}<normal>: {!r}</normal>", item.id, e)
            return None
        else:
            logger.success(order)
            return order

    @logger.catch
    async def check_favorites(self) -> None:
        async def process_item(item: Item) -> None:
            if item.id in self.tracked_items:
                if (old_item := self.tracked_items[item.id]) == item:
                    return
                self.tracked_items[item.id] = item

                logger_func = logger.debug if item.id in items.ignored else logger.info
                if old_item is not None:
                    if old_item.tag == Item.Tag.CHECK_AGAIN_LATER != item.tag or not (
                        old_item.in_sales_window or item.in_sales_window or old_item.tag or item.tag
                    ):
                        logger_func = logger.warning
                    logger_func(f"Changed<normal>: {item.colorize_diff(old_item)}</normal>")
                elif item.is_interesting:
                    logger_func(f"<normal>{item.colorize()}</normal>")

                if item.id in items.ignored:
                    return
            elif item.is_interesting or item.id not in items.inactive:
                logger.warning(
                    f"{'Inactive' if item.id in items.inactive else 'Unknown'}<normal>: {item.colorize()}</normal>"  # noqa: G004
                )
                self.tracked_items[item.id] = item

            if item.num_available and item.in_sales_window:
                await self.hold(item, item.num_available)

        async with create_task_group() as tg:
            try:
                async for item in self.client._get_favorites():
                    tg.start_soon(process_item, item)
            except httpx.TransportError as e:
                logger.error("{!r}", e)

    @logger.catch(onerror=lambda _: sys.exit(1))
    async def run(self) -> None:
        async with AsyncExitStack() as exit_stack:
            await exit_stack.enter_async_context(self.client)
            exit_stack.callback(self.client.cookies.save, str(COOKIES_PATH))
            # `Credentials` instance is replaced on refresh
            exit_stack.callback(lambda: self.client.credentials.save(CREDENTIALS_PATH))

            await self.client._scheduler.add_schedule(
                self.check_favorites,
                self.CHECK_FAVORITES_TRIGGER,
                id="check-favorites",
                conflict_policy=ConflictPolicy.exception,
            )

            try:
                await self.client._scheduler.wait_until_stopped()
            except* (CancelledError, KeyboardInterrupt):
                logger.debug("Shutting down")


if __name__ == "__main__":
    # https://github.com/Delgan/loguru/issues/368#issuecomment-731087512
    logger = logger.patch(lambda record: record.update(name=__spec__.name))  # type: ignore[call-arg]

    tracked_items = dict.fromkeys(chain(items.ignored, items.tracked))
    anyio.run(Bot(tracked_items).run)
