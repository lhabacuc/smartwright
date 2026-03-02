from __future__ import annotations

import asyncio
from typing import Any


class _CoordinateHandle:
    """Minimal handle that clicks/fills at saved page coordinates (last-resort relocation)."""

    def __init__(self, page: object, cx: float, cy: float) -> None:
        self._page = page
        self._cx = cx
        self._cy = cy

    async def click(self) -> None:
        await self._page.mouse.click(self._cx, self._cy)

    async def fill(self, value: str) -> None:
        await self._page.mouse.click(self._cx, self._cy)
        await self._page.keyboard.type(value)

    async def hover(self) -> None:
        await self._page.mouse.move(self._cx, self._cy)

    async def inner_text(self) -> str:
        return ""


class BaseMixin:
    """Mixin providing core element-lookup and interaction helpers.

    Expects ``self.page`` to be set by the composing class.
    Also expects ``self._wait_for_count`` and ``self._wait_visible_if_possible``
    to be available (provided by the composing class or another mixin).
    """

    def __init__(self, page: object) -> None:
        self.page = page

    async def get_by_type_index(self, element_type: str, index: int, timeout_ms: int = 7000) -> Any:
        if index < 0:
            raise ValueError("index must be >= 0")
        locator = self.page.locator(element_type)
        count = await self._wait_for_count(locator, timeout_ms)
        if count == 0:
            raise LookupError(f"No elements found for type '{element_type}'")
        if index >= count:
            raise IndexError(f"Index {index} out of range for type '{element_type}' (total={count})")
        target = locator.nth(index)
        await self._wait_visible_if_possible(target, timeout_ms)
        return target

    async def get_by_role_index(self, role: str, index: int, timeout_ms: int = 7000) -> Any:
        if index < 0:
            raise ValueError("index must be >= 0")
        locator = self.page.get_by_role(role)
        count = await self._wait_for_count(locator, timeout_ms)
        if count == 0:
            raise LookupError(f"No elements found for role '{role}'")
        if index >= count:
            raise IndexError(f"Index {index} out of range for role '{role}' (total={count})")
        target = locator.nth(index)
        await self._wait_visible_if_possible(target, timeout_ms)
        return target

    async def get_by_text_index(self, text: str, index: int, timeout_ms: int = 7000) -> Any:
        if index < 0:
            raise ValueError("index must be >= 0")
        locator = self.page.get_by_text(text)
        count = await self._wait_for_count(locator, timeout_ms)
        if count == 0:
            raise LookupError(f"No elements found containing text '{text}'")
        if index >= count:
            raise IndexError(f"Index {index} out of range for text '{text}' (total={count})")
        target = locator.nth(index)
        await self._wait_visible_if_possible(target, timeout_ms)
        return target

    async def fill_by_type_index(self, element_type: str, index: int, value: str, timeout_ms: int = 7000) -> Any:
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        return await target.fill(value)

    async def click_by_type_index(self, element_type: str, index: int, timeout_ms: int = 7000) -> Any:
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        return await target.click()

    async def read_by_type_index(self, element_type: str, index: int, timeout_ms: int = 7000) -> str:
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        return (await target.inner_text()).strip()

    async def fill_by_role_index(self, role: str, index: int, value: str, timeout_ms: int = 7000) -> Any:
        target = await self.get_by_role_index(role, index, timeout_ms=timeout_ms)
        return await target.fill(value)

    async def click_by_role_index(self, role: str, index: int, timeout_ms: int = 7000) -> Any:
        target = await self.get_by_role_index(role, index, timeout_ms=timeout_ms)
        return await target.click()

    async def read_by_role_index(self, role: str, index: int, timeout_ms: int = 7000) -> str:
        target = await self.get_by_role_index(role, index, timeout_ms=timeout_ms)
        return (await target.inner_text()).strip()

    async def click_by_text_index(self, text: str, index: int, timeout_ms: int = 7000) -> Any:
        target = await self.get_by_text_index(text, index, timeout_ms=timeout_ms)
        return await target.click()

    async def read_by_text_index(self, text: str, index: int, timeout_ms: int = 7000) -> str:
        target = await self.get_by_text_index(text, index, timeout_ms=timeout_ms)
        return (await target.inner_text()).strip()
