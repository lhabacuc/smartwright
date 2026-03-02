from __future__ import annotations

import asyncio
import random
from typing import Any


class InteractMixin:
    """Mixin providing element interaction methods.

    Expects ``self.page`` (from BaseMixin) and helper methods such as
    ``_wait_for_count``, ``_wait_visible_if_possible``, ``_humanized_pause``,
    ``_wait_enabled``, and ``get_by_type_index``.
    """

    # ── First-type-containing helpers ─────────────────────────────────

    async def find_first_type_containing(
        self,
        element_type: str,
        contains: str,
        timeout_ms: int = 7000,
        attrs: tuple[str, ...] = ("aria-label", "placeholder", "name", "id", "value", "title"),
    ) -> Any:
        locator = self.page.locator(element_type)
        count = await self._wait_for_count(locator, timeout_ms)
        if count == 0:
            raise LookupError(f"No elements found for type '{element_type}'")

        needle = contains.strip().lower()
        for i in range(count):
            item = locator.nth(i)
            haystack_parts: list[str] = []
            try:
                text = await item.inner_text()
                if text:
                    haystack_parts.append(text)
            except Exception:
                pass

            for attr in attrs:
                try:
                    val = await item.get_attribute(attr)
                    if val:
                        haystack_parts.append(val)
                except Exception:
                    continue

            haystack = " ".join(haystack_parts).lower()
            if needle and needle in haystack:
                await self._wait_visible_if_possible(item, timeout_ms)
                return item

        raise LookupError(
            f"No element of type '{element_type}' contains '{contains}' "
            f"in text/attributes"
        )

    async def click_first_type_containing(
        self,
        element_type: str,
        contains: str,
        timeout_ms: int = 7000,
        humanized: bool = True,
    ) -> Any:
        target = await self.find_first_type_containing(element_type, contains, timeout_ms=timeout_ms)
        if humanized:
            await self._humanized_pause()
        return await target.click()

    async def fill_first_type_containing(
        self,
        element_type: str,
        contains: str,
        value: str,
        timeout_ms: int = 7000,
        humanized: bool = True,
    ) -> Any:
        target = await self.find_first_type_containing(element_type, contains, timeout_ms=timeout_ms)
        if humanized:
            press_sequentially = getattr(target, "press_sequentially", None)
            if callable(press_sequentially):
                await target.fill("")
                await press_sequentially(value, delay=random.randint(18, 45))
                return None
            await self._humanized_pause()
        return await target.fill(value)

    async def read_first_type_containing(self, element_type: str, contains: str, timeout_ms: int = 7000) -> str:
        target = await self.find_first_type_containing(element_type, contains, timeout_ms=timeout_ms)
        return (await target.inner_text()).strip()

    # ── Smart type + index + text pattern functions ──────────────────

    @staticmethod
    def _match_text_pattern(text: str, pattern: str) -> bool:
        """Match text against a glob-like pattern.

        Patterns:
          "*text*"  -> contains "text"
          "text*"   -> starts with "text"
          "*text"   -> ends with "text"
          "text"    -> contains "text" (default)
        All comparisons are case-insensitive.
        """
        if not pattern:
            return True
        t = text.strip().lower()
        p = pattern.strip().lower()
        starts_wild = p.startswith("*")
        ends_wild = p.endswith("*")
        core = p.lstrip("*").rstrip("*")
        if not core:
            return True
        if starts_wild and ends_wild:
            return core in t
        if starts_wild:
            return t.endswith(core)
        if ends_wild:
            return t.startswith(core)
        return core in t

    async def find_by_type_at_index_containing(
        self,
        element_type: str,
        index: int,
        text_pattern: str,
        timeout_ms: int = 7000,
    ) -> Any:
        """Find the Nth element of a type whose text matches a pattern.

        Example: find_by_type_at_index_containing("div", 7, "*max*")
        -> finds the 8th div (0-based) that contains "max" in its text.

        The filtering is done in-browser (JS) for performance.
        """
        if index < 0:
            raise ValueError("index must be >= 0")

        # Escape for JS string literal
        safe_type = element_type.replace("\\", "\\\\").replace("'", "\\'")
        safe_pattern = text_pattern.replace("\\", "\\\\").replace("'", "\\'")

        real_index = await self.page.evaluate(
            """([type, pattern, targetIdx]) => {
                const all = Array.from(document.querySelectorAll(type));
                const p = pattern.toLowerCase();
                const startsWild = p.startsWith('*');
                const endsWild = p.endsWith('*');
                const core = p.replace(/^\\*+|\\*+$/g, '');
                if (!core) return targetIdx < all.length ? targetIdx : -1;
                let matchCount = 0;
                for (let i = 0; i < all.length; i++) {
                    const t = (all[i].innerText || '').trim().toLowerCase();
                    let ok = false;
                    if (startsWild && endsWild) ok = t.includes(core);
                    else if (startsWild) ok = t.endsWith(core);
                    else if (endsWild) ok = t.startsWith(core);
                    else ok = t.includes(core);
                    if (ok) {
                        if (matchCount === targetIdx) return i;
                        matchCount++;
                    }
                }
                return -1;
            }""",
            [safe_type, safe_pattern, index],
        )

        if real_index < 0:
            raise LookupError(
                f"No '{element_type}' at index {index} matching text '{text_pattern}'"
            )

        target = self.page.locator(element_type).nth(real_index)
        try:
            await self._wait_visible_if_possible(target, min(timeout_ms, 3000))
        except Exception:
            pass
        return target

    async def click_by_type_at_index_containing(
        self,
        element_type: str,
        index: int,
        text_pattern: str,
        timeout_ms: int = 7000,
        humanized: bool = True,
    ) -> Any:
        """Click the Nth element of a type whose text matches a pattern.

        Example: click_by_type_at_index_containing("div", 7, "*max*")
        """
        target = await self.find_by_type_at_index_containing(
            element_type, index, text_pattern, timeout_ms=timeout_ms,
        )
        if humanized:
            await self._humanized_pause()
        await self._wait_enabled(target, min(timeout_ms, 3000))
        return await target.click()

    async def fill_by_type_at_index_containing(
        self,
        element_type: str,
        index: int,
        text_pattern: str,
        value: str,
        timeout_ms: int = 7000,
        humanized: bool = True,
    ) -> Any:
        """Fill the Nth element of a type whose text matches a pattern.

        Example: fill_by_type_at_index_containing("textarea", 0, "*message*", "hello")
        """
        target = await self.find_by_type_at_index_containing(
            element_type, index, text_pattern, timeout_ms=timeout_ms,
        )
        if humanized:
            ps = getattr(target, "press_sequentially", None)
            if callable(ps):
                await target.fill("")
                await ps(value, delay=random.randint(18, 45))
                return None
            await self._humanized_pause()
        return await target.fill(value)

    async def read_by_type_at_index_containing(
        self,
        element_type: str,
        index: int,
        text_pattern: str,
        timeout_ms: int = 7000,
    ) -> str:
        """Read text of the Nth element of a type whose text matches a pattern."""
        target = await self.find_by_type_at_index_containing(
            element_type, index, text_pattern, timeout_ms=timeout_ms,
        )
        return (await target.inner_text()).strip()

    _PLACEHOLDER_PATTERNS = frozenset({
        "thinking...", "thinking", "digitando", "digitando...",
        "...", "pensando...", "pensando", "gerando", "gerando...",
        "generating", "generating...",
    })

    @staticmethod
    def _is_placeholder_text(text: str) -> bool:
        norm = " ".join(text.split()).lower().strip()
        if not norm or len(norm) < 20:
            # Could be placeholder if very short
            if norm in InteractMixin._PLACEHOLDER_PATTERNS:
                return True
            # Also treat anything under 5 chars as placeholder-like
            if len(norm) < 5:
                return True
        return False

    # ── Intelligent emergency functions ──────────────────────────────────

    async def wait_for_element(self, selector: str, timeout_ms: int = 15000) -> Any:
        if not selector:
            raise ValueError("selector must not be empty")
        locator = self.page.locator(selector)
        count = await self._wait_for_count(locator, timeout_ms)
        if count == 0:
            raise LookupError(f"No elements found for selector '{selector}' within timeout")
        target = locator.first
        await self._wait_visible_if_possible(target, timeout_ms)
        return target

    async def wait_for_url_contains(self, substring: str, timeout_ms: int = 15000) -> str:
        if not substring:
            raise ValueError("substring must not be empty")
        deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000.0)
        while asyncio.get_event_loop().time() < deadline:
            url = getattr(self.page, "url", "") or ""
            if substring in url:
                return url
            await asyncio.sleep(0.25)
        raise TimeoutError(f"URL never contained '{substring}' within {timeout_ms}ms (last: {url})")

    async def select_option_by_type_index(
        self,
        element_type: str,
        index: int,
        value: str,
        timeout_ms: int = 7000,
    ) -> Any:
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        select_option = getattr(target, "select_option", None)
        if not callable(select_option):
            raise TypeError(f"Element at index {index} does not support select_option")
        return await select_option(value)

    async def check_by_type_index(
        self,
        element_type: str,
        index: int,
        checked: bool = True,
        timeout_ms: int = 7000,
    ) -> Any:
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        set_checked = getattr(target, "set_checked", None)
        if callable(set_checked):
            return await set_checked(checked)
        if checked:
            return await target.check()
        return await target.uncheck()

    async def upload_file_by_type_index(
        self,
        element_type: str,
        index: int,
        file_paths: str | list[str],
        timeout_ms: int = 7000,
    ) -> Any:
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        set_input_files = getattr(target, "set_input_files", None)
        if not callable(set_input_files):
            raise TypeError(f"Element at index {index} does not support set_input_files")
        return await set_input_files(file_paths)

    async def press_keys(self, keys: str, timeout_ms: int = 7000) -> None:
        if not keys:
            raise ValueError("keys must not be empty")
        keyboard = getattr(self.page, "keyboard", None)
        if keyboard is None:
            raise AttributeError("page does not expose a keyboard object")
        press = getattr(keyboard, "press", None)
        if not callable(press):
            raise AttributeError("page.keyboard does not have a press method")
        await press(keys)

    async def hover_by_type_index(
        self,
        element_type: str,
        index: int,
        timeout_ms: int = 7000,
    ) -> Any:
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        hover = getattr(target, "hover", None)
        if not callable(hover):
            raise TypeError(f"Element at index {index} does not support hover")
        await hover()
        return target

    async def scroll_to_element(self, selector: str, timeout_ms: int = 7000) -> Any:
        if not selector:
            raise ValueError("selector must not be empty")
        locator = self.page.locator(selector)
        count = await self._wait_for_count(locator, timeout_ms)
        if count == 0:
            raise LookupError(f"No elements found for selector '{selector}'")
        target = locator.first
        scroll = getattr(target, "scroll_into_view_if_needed", None)
        if callable(scroll):
            await scroll(timeout=timeout_ms)
        return target

    async def get_attribute_by_type_index(
        self,
        element_type: str,
        index: int,
        attribute: str,
        timeout_ms: int = 7000,
    ) -> str | None:
        if not attribute:
            raise ValueError("attribute must not be empty")
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        return await target.get_attribute(attribute)

    async def read_all_by_type(self, element_type: str, timeout_ms: int = 7000) -> list[str]:
        locator = self.page.locator(element_type)
        count = await self._wait_for_count(locator, timeout_ms)
        results: list[str] = []
        for i in range(count):
            try:
                txt = (await locator.nth(i).inner_text()).strip()
                if txt:
                    results.append(txt)
            except Exception:
                continue
        return results

    async def screenshot_element_by_type_index(
        self,
        element_type: str,
        index: int,
        path: str,
        timeout_ms: int = 7000,
    ) -> str:
        if not path:
            raise ValueError("path must not be empty")
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        screenshot = getattr(target, "screenshot", None)
        if not callable(screenshot):
            raise TypeError(f"Element at index {index} does not support screenshot")
        await screenshot(path=path)
        return path

    async def wait_for_text_visible(self, text: str, timeout_ms: int = 15000) -> Any:
        if not text:
            raise ValueError("text must not be empty")
        locator = self.page.get_by_text(text)
        deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000.0)
        while asyncio.get_event_loop().time() < deadline:
            count = await locator.count()
            if count > 0:
                target = locator.first
                await self._wait_visible_if_possible(target, timeout_ms)
                return target
            await asyncio.sleep(0.25)
        raise LookupError(f"Text '{text}' never became visible within {timeout_ms}ms")
