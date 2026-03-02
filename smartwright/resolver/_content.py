from __future__ import annotations

import asyncio
from typing import Any


class ContentMixin:
    """Mixin providing content interaction methods (links, tables, lists, media, etc.)."""

    # ── Link actions ──────────────────────────────────────────────────────

    async def click_link_by_text(self, text: str, index: int = 0, timeout_ms: int = 7000) -> Any:
        """Click the nth <a> element whose text contains the keyword."""
        locator = self.page.locator(f"a:has-text('{text}')")
        count = await self._wait_for_count(locator, timeout_ms)
        if count == 0:
            raise LookupError(f"No link found containing text '{text}'")
        if index >= count:
            raise IndexError(f"Index {index} out of range for links with text '{text}' (total={count})")
        await self._humanized_pause()
        return await locator.nth(index).click()

    async def get_link_href(self, text: str, index: int = 0, timeout_ms: int = 7000) -> str:
        """Get the href of the nth <a> containing text."""
        locator = self.page.locator(f"a:has-text('{text}')")
        count = await self._wait_for_count(locator, timeout_ms)
        if count == 0:
            raise LookupError(f"No link found containing text '{text}'")
        if index >= count:
            raise IndexError(f"Index {index} out of range (total={count})")
        return await locator.nth(index).get_attribute("href") or ""

    async def capture_all_links(self, timeout_ms: int = 7000) -> list[dict[str, Any]]:
        """Capture all visible <a> elements with text, href, and index."""
        evaluate = getattr(self.page, "evaluate", None)
        if callable(evaluate):
            return await evaluate(
                """() => {
                  const links = document.querySelectorAll('a');
                  return Array.from(links).map((a, i) => ({
                    index_in_type: i,
                    total_in_type: links.length,
                    tag: 'a',
                    text: (a.innerText || '').trim().slice(0, 200),
                    href: a.href || '',
                    target: a.target || '',
                    visible: a.offsetWidth > 0 && a.offsetHeight > 0,
                  })).filter(l => l.visible);
                }"""
            )
        return []

    # ── Table actions ─────────────────────────────────────────────────────

    async def read_table_cell(self, table_index: int, row: int, col: int, timeout_ms: int = 7000) -> str:
        """Read text from a specific cell [row][col] in the nth <table>."""
        target = await self.get_by_type_index("table", table_index, timeout_ms=timeout_ms)
        ev = getattr(target, "evaluate", None)
        if callable(ev):
            result = await ev(
                """(el, args) => {
                  const rows = el.querySelectorAll('tr');
                  const r = rows[args[0]];
                  if (!r) return null;
                  const cells = r.querySelectorAll('td, th');
                  const c = cells[args[1]];
                  return c ? c.innerText.trim() : null;
                }""",
                [row, col],
            )
            if result is None:
                raise IndexError(f"Cell [{row}][{col}] out of range")
            return result
        raise TypeError("Cannot evaluate on table element")

    async def read_table_row(self, table_index: int, row: int, timeout_ms: int = 7000) -> list[str]:
        """Read all cell texts from a specific row in the nth <table>."""
        target = await self.get_by_type_index("table", table_index, timeout_ms=timeout_ms)
        ev = getattr(target, "evaluate", None)
        if callable(ev):
            result = await ev(
                """(el, row) => {
                  const r = el.querySelectorAll('tr')[row];
                  if (!r) return null;
                  return Array.from(r.querySelectorAll('td, th')).map(c => c.innerText.trim());
                }""",
                row,
            )
            if result is None:
                raise IndexError(f"Row {row} out of range")
            return result
        return []

    async def read_full_table(self, table_index: int = 0, timeout_ms: int = 7000) -> list[list[str]]:
        """Read entire <table> as a 2D list of strings."""
        target = await self.get_by_type_index("table", table_index, timeout_ms=timeout_ms)
        ev = getattr(target, "evaluate", None)
        if callable(ev):
            return await ev(
                """el => Array.from(el.querySelectorAll('tr')).map(
                  r => Array.from(r.querySelectorAll('td, th')).map(c => c.innerText.trim())
                )"""
            )
        return []

    async def click_table_cell(self, table_index: int, row: int, col: int, timeout_ms: int = 7000) -> None:
        """Click a specific cell [row][col] in the nth <table>."""
        target = await self.get_by_type_index("table", table_index, timeout_ms=timeout_ms)
        ev = getattr(target, "evaluate", None)
        if callable(ev):
            ok = await ev(
                """(el, args) => {
                  const r = el.querySelectorAll('tr')[args[0]];
                  if (!r) return false;
                  const c = r.querySelectorAll('td, th')[args[1]];
                  if (!c) return false;
                  c.click();
                  return true;
                }""",
                [row, col],
            )
            if not ok:
                raise IndexError(f"Cell [{row}][{col}] out of range")
            return
        raise TypeError("Cannot evaluate on table element")

    # ── List actions ──────────────────────────────────────────────────────

    async def read_list_items(self, list_index: int = 0, list_type: str = "ul", timeout_ms: int = 7000) -> list[str]:
        """Read all <li> texts from the nth <ul> or <ol>."""
        target = await self.get_by_type_index(list_type, list_index, timeout_ms=timeout_ms)
        ev = getattr(target, "evaluate", None)
        if callable(ev):
            return await ev("el => Array.from(el.querySelectorAll('li')).map(li => li.innerText.trim())")
        items = target.locator("li")
        count = await items.count()
        return [(await items.nth(i).inner_text()).strip() for i in range(count)]

    async def click_list_item(
        self, list_index: int, item_index: int, list_type: str = "ul", timeout_ms: int = 7000,
    ) -> None:
        """Click the nth <li> inside the nth <ul>/<ol>."""
        target = await self.get_by_type_index(list_type, list_index, timeout_ms=timeout_ms)
        items = target.locator("li")
        count = await items.count()
        if item_index >= count:
            raise IndexError(f"Item {item_index} out of range (total={count})")
        await self._humanized_pause()
        await items.nth(item_index).click()

    # ── Media actions (video / audio) ─────────────────────────────────────

    async def control_media(
        self, element_type: str, index: int, action: str, timeout_ms: int = 7000,
    ) -> None:
        """Control a <video>/<audio>: actions = play, pause, mute, unmute."""
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        ev = getattr(target, "evaluate", None)
        if not callable(ev):
            raise TypeError("Cannot evaluate on media element")
        actions_map = {
            "play": "el.play()",
            "pause": "el.pause()",
            "mute": "el.muted = true",
            "unmute": "el.muted = false",
        }
        js = actions_map.get(action)
        if not js:
            raise ValueError(f"Unknown media action '{action}'. Use: play, pause, mute, unmute")
        await ev(f"el => {{ {js} }}")

    async def get_media_state(self, element_type: str, index: int, timeout_ms: int = 7000) -> dict[str, Any]:
        """Get playback state of a <video>/<audio>."""
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        ev = getattr(target, "evaluate", None)
        if callable(ev):
            return await ev(
                """el => ({
                  src: el.src || el.currentSrc || '',
                  paused: el.paused,
                  muted: el.muted,
                  volume: el.volume,
                  currentTime: el.currentTime,
                  duration: el.duration || 0,
                  ended: el.ended,
                  readyState: el.readyState,
                })"""
            )
        return {}

    async def get_media_src(self, element_type: str, index: int, timeout_ms: int = 7000) -> str:
        """Get the src of a <video>, <audio>, <img>, <iframe>, or <source>."""
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        return await target.get_attribute("src") or ""

    # ── Image actions ─────────────────────────────────────────────────────

    async def get_image_info(self, index: int, timeout_ms: int = 7000) -> dict[str, Any]:
        """Get info about the nth <img>: src, alt, naturalWidth, etc."""
        target = await self.get_by_type_index("img", index, timeout_ms=timeout_ms)
        ev = getattr(target, "evaluate", None)
        if callable(ev):
            return await ev(
                """el => ({
                  index_in_type: Array.from(document.querySelectorAll('img')).indexOf(el),
                  total_in_type: document.querySelectorAll('img').length,
                  src: el.src || '',
                  alt: el.alt || '',
                  title: el.title || '',
                  naturalWidth: el.naturalWidth,
                  naturalHeight: el.naturalHeight,
                  complete: el.complete,
                  visible: el.offsetWidth > 0 && el.offsetHeight > 0,
                })"""
            )
        return {"src": await target.get_attribute("src") or ""}

    async def capture_all_images(self, timeout_ms: int = 7000) -> list[dict[str, Any]]:
        """Capture all <img> elements with src, alt, and index."""
        evaluate = getattr(self.page, "evaluate", None)
        if callable(evaluate):
            return await evaluate(
                """() => {
                  const imgs = document.querySelectorAll('img');
                  return Array.from(imgs).map((el, i) => ({
                    index_in_type: i,
                    total_in_type: imgs.length,
                    tag: 'img',
                    src: el.src || '',
                    alt: el.alt || '',
                    title: el.title || '',
                    naturalWidth: el.naturalWidth,
                    naturalHeight: el.naturalHeight,
                    visible: el.offsetWidth > 0 && el.offsetHeight > 0,
                  }));
                }"""
            )
        return []

    # ── Iframe actions ────────────────────────────────────────────────────

    async def switch_to_iframe(self, index_or_selector: int | str = 0, timeout_ms: int = 7000) -> Any:
        """Enter an <iframe> context. Pass int for index or str for CSS selector."""
        if isinstance(index_or_selector, int):
            target = await self.get_by_type_index("iframe", index_or_selector, timeout_ms=timeout_ms)
        else:
            locator = self.page.locator(index_or_selector)
            count = await self._wait_for_count(locator, timeout_ms)
            if count == 0:
                raise LookupError(f"No iframe found for '{index_or_selector}'")
            target = locator.first
        cf = getattr(target, "content_frame", None)
        if callable(cf):
            frame = await cf()
        else:
            frame = cf
        if frame is None:
            raise LookupError("Could not access iframe content frame")
        return frame

    async def switch_to_main_frame(self) -> Any:
        """Return to the main frame (top-level page)."""
        main = getattr(self.page, "main_frame", None)
        if main:
            return main
        return self.page

    # ── Dialog actions ────────────────────────────────────────────────────

    async def handle_dialog(
        self, action: str = "accept", prompt_text: str | None = None, timeout_ms: int = 10000,
    ) -> str:
        """Set up a handler for the next JS dialog (alert/confirm/prompt).

        action: 'accept' or 'dismiss'.
        Returns the dialog message text.
        """
        if action not in ("accept", "dismiss"):
            raise ValueError("action must be 'accept' or 'dismiss'")

        result: dict[str, str] = {"message": ""}
        event = asyncio.Event()

        async def _on_dialog(dialog: Any) -> None:
            result["message"] = getattr(dialog, "message", "") or ""
            if action == "accept":
                accept = getattr(dialog, "accept", None)
                if callable(accept):
                    if prompt_text is not None:
                        await accept(prompt_text)
                    else:
                        await accept()
            else:
                dismiss = getattr(dialog, "dismiss", None)
                if callable(dismiss):
                    await dismiss()
            event.set()

        self.page.on("dialog", _on_dialog)
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout_ms / 1000.0)
        except asyncio.TimeoutError:
            pass
        finally:
            try:
                self.page.remove_listener("dialog", _on_dialog)
            except Exception:
                pass
        return result["message"]

    # ── Drag & Drop ───────────────────────────────────────────────────────

    async def drag_and_drop(
        self, source_selector: str, target_selector: str, timeout_ms: int = 7000,
    ) -> None:
        """Drag element from source to target."""
        dad = getattr(self.page, "drag_and_drop", None)
        if callable(dad):
            await dad(source_selector, target_selector, timeout=timeout_ms)
            return
        src = self.page.locator(source_selector)
        dst = self.page.locator(target_selector)
        src_count = await self._wait_for_count(src, timeout_ms)
        dst_count = await self._wait_for_count(dst, timeout_ms)
        if src_count == 0:
            raise LookupError(f"Source '{source_selector}' not found")
        if dst_count == 0:
            raise LookupError(f"Target '{target_selector}' not found")
        src_box = await src.first.bounding_box()
        dst_box = await dst.first.bounding_box()
        if not src_box or not dst_box:
            raise LookupError("Could not get bounding boxes for drag elements")
        sx = src_box["x"] + src_box["width"] / 2
        sy = src_box["y"] + src_box["height"] / 2
        dx = dst_box["x"] + dst_box["width"] / 2
        dy = dst_box["y"] + dst_box["height"] / 2
        await self.page.mouse.move(sx, sy)
        await self.page.mouse.down()
        await asyncio.sleep(0.1)
        await self.page.mouse.move(dx, dy, steps=10)
        await self.page.mouse.up()

    # ── Scroll actions ────────────────────────────────────────────────────

    async def scroll_page(self, direction: str = "down", pixels: int = 500) -> None:
        """Scroll the page. direction: up, down, left, right."""
        deltas = {"down": (0, pixels), "up": (0, -pixels), "left": (-pixels, 0), "right": (pixels, 0)}
        dx, dy = deltas.get(direction, (0, pixels))
        evaluate = getattr(self.page, "evaluate", None)
        if callable(evaluate):
            await evaluate(f"window.scrollBy({dx}, {dy})")
            return
        await self.page.mouse.wheel(dx, dy)

    async def scroll_to_top(self) -> None:
        """Scroll page to the very top."""
        evaluate = getattr(self.page, "evaluate", None)
        if callable(evaluate):
            await evaluate("window.scrollTo(0, 0)")

    async def scroll_to_bottom(self) -> None:
        """Scroll page to the very bottom."""
        evaluate = getattr(self.page, "evaluate", None)
        if callable(evaluate):
            await evaluate("window.scrollTo(0, document.body.scrollHeight)")
