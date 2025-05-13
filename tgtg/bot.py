from __future__ import annotations

import sys
from asyncio import CancelledError
from collections import defaultdict, deque
from contextlib import AsyncExitStack
from functools import partial
from http.cookiejar import MozillaCookieJar
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import anyio
import apscheduler
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
from whenever import Instant, TimeDelta, minutes, seconds

from . import items
from .client import TgtgClient
from .errors import TgtgApiError, TgtgCaptchaError, TgtgLimitExceededError, TgtgPaymentError, TgtgSaleClosedError
from .models import Credentials, Favorite, Item, Reservation
from .utils import format_time, relative_date

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
    tracked_items: dict[int, Favorite | None]
    held_items: dict[int, deque[Reservation]] = field(init=False, factory=lambda: defaultdict(deque))
    scheduled_snipes: dict[int, Instant | None] = field(init=False, factory=dict)

    client: TgtgClient = field(
        init=False,
        factory=lambda: TgtgClient.from_credentials(Credentials.load(CREDENTIALS_PATH), MozillaCookieJar(COOKIES_PATH)),
    )

    API_FLAPPING_COOLDOWN: ClassVar[TimeDelta] = minutes(2)
    CATCH_RESERVATION_DELAY: ClassVar[TimeDelta] = seconds(1)
    CHECK_FAVORITES_TRIGGER: ClassVar[Trigger] = IntervalTrigger(seconds=2)
    SNIPE_MAX_ATTEMPTS: ClassVar[int] = 6

    async def _del_scheduled_snipe(self, item_id: int, *, conflict_policy: ConflictPolicy) -> str:
        return await self.client._scheduler.add_schedule(
            partial(self.scheduled_snipes.pop, item_id),
            DateTrigger((Instant.now() + self.API_FLAPPING_COOLDOWN).py_datetime()),
            id=f"del-scheduled-snipe-{item_id}",
            conflict_policy=conflict_policy,
        )

    async def _schedule_catch(self, reservation: Reservation) -> str:
        return await self.client._scheduler.add_schedule(
            partial(self.catch, reservation),
            DateTrigger((reservation.expires_at + self.CATCH_RESERVATION_DELAY).py_datetime()),
            id=f"catch-reservation-{reservation.id}",
            conflict_policy=ConflictPolicy.exception,
        )

    async def _untrack_item(self, item_id: int) -> None:
        logger.warning("Untracking item {}", item_id)
        await self.client.unfavorite(item_id)
        del self.tracked_items[item_id]

    @logger.catch
    @retry_policy
    async def hold(self, item: Item) -> Reservation | None:
        try:
            reservation = await self.client.reserve(item, item.max_quantity)
        except TgtgApiError as e:
            logger.error("Item {}<normal>: {!r}</normal>", item.id, e)
            if isinstance(e, TgtgLimitExceededError):
                await self._untrack_item(item.id)
            return None
        else:
            logger.success(f"<normal>{reservation.colorize()}</normal>")
            await self.client.ntfy.publish(f"Held: {reservation.quantity}x {item.name}", tag="hourglass_flowing_sand")
            self.held_items[item.id].append(reservation)
            await self._schedule_catch(reservation)
            return reservation

    @logger.catch
    @retry_policy
    async def catch(self, held: Reservation) -> Reservation | None:
        try:
            reservation = await self.client.reserve(held.item_id, held.quantity)
        except TgtgApiError as e:
            logger_func = logger.warning if isinstance(e, TgtgSaleClosedError) else logger.error
            logger_func("Item {}<normal>: {!r}</normal>", held.item_id, e)
            if isinstance(e, TgtgLimitExceededError):
                await self._untrack_item(held.item_id)
            return None
        else:
            logger.success(f"<normal>{reservation.colorize()}</normal>")
            self.held_items[held.item_id].append(reservation)
            await self._schedule_catch(reservation)
            return reservation
        finally:
            self.held_items[held.item_id].remove(held)

    @logger.catch
    @retry_policy
    async def order(self, item: Item) -> JSON | None:
        try:
            reservation = await self.client.reserve(item, item.max_quantity)
        except TgtgApiError as e:
            logger.error("Item {}<normal>: {!r}</normal>", item.id, e)
            if isinstance(e, TgtgLimitExceededError):
                await self._untrack_item(item.id)
            return None
        else:
            logger.debug(reservation)

            try:
                await self.client.pay(reservation)
            except TgtgPaymentError as e:
                logger.warning("Item {}<normal>: {!r}</normal>", item.id, e)
                # TODO: See if I can hold without aborting
                await self.client.abort_reservation(reservation)
                await self.hold(item)
                return None
            except TgtgApiError as e:
                logger.error("Item {}<normal>: {!r}</normal>", item.id, e)
                return None
            else:
                order: JSON = (await self.client.get_order(reservation.id))["order"]
                logger.success(order)
                await self.client.ntfy.publish(f"Ordered: {order['quantity']}x {item.name}", tag="shopping_cart")
                return order

    async def snipe(self, item_id: int) -> Reservation | None:
        logger.info("Sniping item {}...", item_id)
        await self._del_scheduled_snipe(item_id, conflict_policy=ConflictPolicy.exception)

        for attempt in range(self.SNIPE_MAX_ATTEMPTS):
            item = await self.client.get_item(item_id)
            if did_item_change := item.num_available or not item.is_check_again_later:
                logger.info(f"Snipe attempt {attempt + 1}<normal>: {item.colorize()}</normal>")  # noqa: G004

            if item.num_available and (reservation := await self.hold(item)):
                if attempt == self.SNIPE_MAX_ATTEMPTS - 1:
                    logger.warning("Snipe succeeded on final ({}th) attempt", self.SNIPE_MAX_ATTEMPTS)
                return reservation

            if did_item_change:
                logger.warning(f"Unexpected<normal>: {item.colorize()}</normal>")  # noqa: G004
                break
        else:
            logger.warning(
                "Item {}<normal>: Unchanged after {} snipe attempts</normal>", item_id, self.SNIPE_MAX_ATTEMPTS
            )
        return None

    @logger.catch
    async def check_favorites(self) -> None:
        async def process_favorite(fave: Favorite) -> None:
            if fave.id in self.tracked_items:
                if (old_fave := self.tracked_items[fave.id]) == fave:
                    return
                if (
                    old_fave is not None
                    and old_fave.is_sold_out
                    and fave.is_selling
                    and any(
                        fave.num_available == reservation.quantity for reservation in reversed(self.held_items[fave.id])
                    )
                ):
                    # Ignore API flapping after reserving an item
                    return
                if (
                    old_fave is not None
                    and old_fave.is_sold_out
                    and fave.is_sold_out
                    and fave.sold_out_at is not None
                    and self.held_items[fave.id]
                    # Rounding mode is a best guess unless I can test a `Reservation` with exactly half-second `reserved_at` timestamp
                    and fave.sold_out_at < self.held_items[fave.id][-1].reserved_at.round(mode="half_ceil")
                ):
                    # Ignore `Favorite.sold_out_at` API flapping
                    return

                self.tracked_items[fave.id] = fave

                logger_func = logger.debug if fave.id in items.ignored else logger.info
                if old_fave is not None:
                    if (
                        (old_fave.is_check_again_later or old_fave.is_selling or old_fave.is_sold_out)
                        and fave.is_sold_out
                        and any(
                            (old_fave.is_sold_out or old_fave.num_available == reservation.quantity)
                            # Rounding mode is a best guess unless I can test a `Reservation` with exactly half-second `reserved_at` timestamp
                            and fave.sold_out_at == reservation.reserved_at.round(mode="half_ceil")
                            for reservation in reversed(self.held_items[fave.id])
                        )
                    ):
                        # Lower logging severity when item updates after reserving
                        logger_func = logger.debug

                    logger_func(f"Changed<normal>: {fave.colorize_diff(old_fave)}</normal>")
                elif fave.is_interesting:
                    logger_func(f"<normal>{fave.colorize()}</normal>")

                if fave.id in items.ignored:
                    return
            elif fave.is_interesting or fave.id not in items.inactive:
                logger.warning(
                    f"{'Inactive' if fave.id in items.inactive else 'Unknown'}<normal>: {fave.colorize()}</normal>"  # noqa: G004
                )
                self.tracked_items[fave.id] = fave

            item: Item | None = None
            if fave.num_available:
                item = await self.client.get_item(fave.id)
                if item.num_available != fave.num_available:
                    logger.warning(f"Updated<normal>: {item.to_favorite().colorize_diff(fave)}</normal>")  # noqa: G004
                if item.num_available:
                    await self.hold(item)

            if not fave.is_check_again_later and self.scheduled_snipes.get(fave.id, True) is None:
                await self._del_scheduled_snipe(fave.id, conflict_policy=ConflictPolicy.do_nothing)
            elif fave.is_check_again_later and fave.id not in self.scheduled_snipes:
                if item is None:
                    item = await self.client.get_item(fave.id)
                if item.next_drop:
                    try:
                        await self.client._scheduler.add_schedule(
                            partial(self.snipe, item.id),
                            DateTrigger(item.next_drop.py_datetime()),
                            id=f"snipe-item-{item.id}",
                            conflict_policy=ConflictPolicy.exception,
                        )
                    except apscheduler.ConflictingIdError as e:
                        logger.error("{!r}", e)
                    else:
                        local_ts = item.next_drop.to_system_tz()
                        logger.info(
                            "Item {}<normal>: Snipe scheduled for {} at {}</normal>",
                            item.id,
                            relative_date(local_ts.date()),
                            format_time(local_ts.time()),
                        )
                else:
                    logger.debug("Item {}<normal>: No upcoming drop</normal>", item.id)

                self.scheduled_snipes[item.id] = item.next_drop

        async with create_task_group() as tg:
            try:
                async for fave in self.client._get_favorites():
                    tg.start_soon(process_favorite, fave)
            except (TgtgCaptchaError, httpx.TransportError) as e:
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
