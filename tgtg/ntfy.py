from __future__ import annotations

from contextlib import AsyncExitStack
from enum import IntEnum
from typing import Self, override

import httpx
from anyio.abc import AsyncResource
from attrs import field, frozen

from .utils import HTTPX_LIMITS


class Priority(IntEnum):
    MIN = 1
    LOW = 2
    DEFAULT = 3
    HIGH = 4
    MAX = 5
    URGENT = 5


@frozen(eq=False)
class NtfyClient(AsyncResource):
    topic: str

    _exit_stack: AsyncExitStack = field(init=False)
    _httpx: httpx.AsyncClient = field(
        init=False, factory=lambda: httpx.AsyncClient(http2=True, limits=HTTPX_LIMITS, base_url="https://ntfy.sh/")
    )

    @override
    async def __aenter__(self) -> Self:
        async with AsyncExitStack() as exit_stack:
            await exit_stack.enter_async_context(self._httpx)
            object.__setattr__(self, "_exit_stack", exit_stack.pop_all())

        return self

    @override
    async def aclose(self) -> None:
        await self._exit_stack.aclose()

    async def publish(self, message: str, *, priority: Priority = Priority.DEFAULT, tag: str = "") -> None:
        headers: dict[str, str] = {}
        if priority != Priority.DEFAULT:
            headers["X-Priority"] = str(priority)
        if tag:
            headers["X-Tags"] = tag

        await self._httpx.post(self.topic, content=message, headers=headers)
