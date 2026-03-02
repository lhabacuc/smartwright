from __future__ import annotations

import asyncio
import random
from typing import Any

from smartwright.resolver.replay_mode import ModeConfig


class HelpersMixin:
    """Private helper methods for element resolution, clicking, filling, etc."""

    # ── Private helpers ───────────────────────────────────────────────────

    async def _verify_resolved_element(
        self, target: Any, capture: dict[str, Any], expected_text: str,
    ) -> bool:
        """Verify a resolved element matches the capture (text + position)."""
        from smartwright.resolver._base import _CoordinateHandle

        if isinstance(target, _CoordinateHandle):
            return True
        # Check text if available
        if expected_text and len(expected_text) >= 4:
            try:
                actual = await target.inner_text(timeout=2000)
                if not self._match_text_pattern(actual, f"*{expected_text[:50]}*"):
                    return False  # Text mismatch
            except Exception:
                pass  # Can't check text, continue to position check

        # Check position is within reasonable range of recorded bbox
        bbox = capture.get("bbox")
        if bbox and bbox.get("cx") is not None:
            try:
                actual_bbox = await target.bounding_box()
                if actual_bbox:
                    # Allow 200px drift (page layout changes, but not completely different area)
                    dx = abs((actual_bbox["x"] + actual_bbox["width"] / 2) - bbox["cx"])
                    dy = abs((actual_bbox["y"] + actual_bbox["height"] / 2) - bbox["cy"])
                    if dx > 300 or dy > 300:
                        return False  # Element is in a totally different position
            except Exception:
                pass

        return True

    async def _pick_closest_to_bbox(
        self, locator: Any, count: int, bbox: dict[str, Any],
    ) -> Any | None:
        """Among multiple matching elements, pick the one closest to recorded bbox center."""
        if not bbox or bbox.get("cx") is None:
            return None
        target_cx = bbox["cx"]
        target_cy = bbox["cy"]
        best = None
        best_dist = float("inf")
        for i in range(min(count, 10)):
            try:
                el = locator.nth(i)
                el_bbox = await el.bounding_box()
                if not el_bbox:
                    continue
                # Check visibility
                if el_bbox["width"] == 0 or el_bbox["height"] == 0:
                    continue
                cx = el_bbox["x"] + el_bbox["width"] / 2
                cy = el_bbox["y"] + el_bbox["height"] / 2
                dist = ((cx - target_cx) ** 2 + (cy - target_cy) ** 2) ** 0.5
                if dist < best_dist:
                    best_dist = dist
                    best = el
            except Exception:
                continue
        return best

    async def _wait_page_interactive(
        self, actions: list[dict[str, Any]], goto_index: int, timeout: int,
    ) -> None:
        """After goto, wait for the page to be truly interactive.

        Strategy:
        1. Look at the NEXT action's capture/selector to find what element
           will be needed — wait for it to appear.
        2. Fallback: wait for any common interactive element (textarea, button, input).
        3. Last resort: short fixed delay for SPA rendering.
        """
        max_wait = min(timeout, 15000)

        # 1. Peek at next action's target selector/element
        if goto_index + 1 < len(actions):
            next_act = actions[goto_index + 1]
            # Try the next action's best selector
            next_capture = next_act.get("capture") or {}
            selectors_to_try = list(next_capture.get("selectors", []))
            next_selector = next_act.get("selector", "")
            if next_selector:
                selectors_to_try.insert(0, next_selector)
            # Try next element_type
            next_type = next_act.get("element_type", "")
            if next_type and next_type not in ("div", "span"):
                selectors_to_try.append(next_type)

            for sel in selectors_to_try[:4]:
                try:
                    loc = self.page.locator(sel)
                    await loc.first.wait_for(state="visible", timeout=max_wait)
                    return
                except Exception:
                    continue

        # 2. Fallback: wait for any common interactive element
        for common in (
            "textarea:visible", "input[type='text']:visible",
            "button:visible", "[contenteditable]:visible",
        ):
            try:
                loc = self.page.locator(common)
                await loc.first.wait_for(state="visible", timeout=max_wait)
                return
            except Exception:
                continue

        # 3. Last resort: fixed delay for SPA rendering
        await asyncio.sleep(3.0)

    async def _wait_visible_if_possible(self, locator: Any, timeout_ms: int) -> None:
        wait_for = getattr(locator, "wait_for", None)
        if callable(wait_for):
            await wait_for(state="visible", timeout=timeout_ms)

    async def _wait_for_count(self, locator: Any, timeout_ms: int) -> int:
        deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000.0)
        last_count = 0
        while asyncio.get_event_loop().time() < deadline:
            last_count = await locator.count()
            if last_count > 0:
                return last_count
            await asyncio.sleep(0.1)
        return last_count

    async def _humanized_pause(self) -> None:
        await asyncio.sleep(random.uniform(0.06, 0.22))

    async def _safe_click(self, target: Any, timeout_ms: int = 10000) -> None:
        """Click with automatic retry for interception and visibility issues.

        1. Try normal click
        2. If intercepted: wait for overlay/skeleton to disappear, retry
        3. If not visible: scroll into view, retry
        4. Last resort: force click
        """
        from smartwright.resolver._base import _CoordinateHandle

        # CoordinateHandle has simple click — just use it directly
        if isinstance(target, _CoordinateHandle):
            await target.click()
            return

        is_intercept = False
        is_invisible = False

        # First attempt: normal click
        try:
            await target.click(timeout=min(timeout_ms, 5000))
            return
        except Exception as exc:
            err = str(exc).lower()
            is_intercept = "intercept" in err
            is_invisible = "not visible" in err or "outside of the viewport" in err
            if not is_intercept and not is_invisible:
                raise  # unexpected error — propagate

        # ── Intercepted by overlay / skeleton ──
        if is_intercept:
            # Wait for common overlays (skeletons, loading spinners) to disappear
            overlay_selectors = [
                "[class*='skeleton']",
                "[class*='loading']",
                "[class*='spinner']",
                "[class*='overlay']",
                ".ant-spin-spinning",
            ]
            for sel in overlay_selectors:
                try:
                    loc = self.page.locator(sel)
                    count = await loc.count()
                    if count > 0:
                        # Wait for overlay to detach or become hidden
                        await loc.first.wait_for(state="hidden", timeout=min(timeout_ms, 15000))
                except Exception:
                    pass

            # Retry normal click after overlays cleared
            try:
                await target.click(timeout=3000)
                return
            except Exception:
                pass

        # ── Not visible — scroll into view ──
        if is_invisible or True:  # also try scroll after failed intercept retry
            try:
                siv = getattr(target, "scroll_into_view_if_needed", None)
                if callable(siv):
                    await siv(timeout=3000)
                await asyncio.sleep(0.3)
                await target.click(timeout=3000)
                return
            except Exception:
                pass

        # ── Last resort: force click ──
        await target.click(force=True)

    # ── Fill safety: reject readonly / find editable input ───────────

    async def _is_fillable(self, target: Any) -> bool:
        """Check if a resolved element is actually editable for fill."""
        from smartwright.resolver._base import _CoordinateHandle

        if isinstance(target, _CoordinateHandle):
            return True
        try:
            editable = await target.is_editable()
            if not editable:
                return False
            disabled = await target.is_disabled()
            return not disabled
        except Exception:
            return True  # can't check → assume ok

    async def _find_fillable_input(self, act: dict[str, Any], timeout: int) -> Any:
        """Find the correct editable input when _resolve_element found a readonly one.

        Uses capture attributes (placeholder, name, aria-label, type) to find
        the right input, then falls back to Nth editable input.
        """
        capture = act.get("capture") or {}
        attrs = capture.get("attributes", {})
        etype = act.get("element_type", "input")
        idx = act.get("index", 0) or 0
        expected_text = act.get("text", "") or capture.get("text", "")

        # 1. By placeholder
        placeholder = attrs.get("placeholder", "")
        if placeholder:
            try:
                loc = self.page.get_by_placeholder(placeholder, exact=False)
                if await loc.count() > 0:
                    t = loc.first
                    if await self._is_fillable(t):
                        return t
            except Exception:
                pass

        # 2. By name attribute
        name = attrs.get("name", "")
        if name:
            try:
                loc = self.page.locator(f"{etype}[name='{name}']")
                if await loc.count() > 0:
                    t = loc.first
                    if await self._is_fillable(t):
                        return t
            except Exception:
                pass

        # 3. By aria-label
        aria = attrs.get("aria-label", "")
        if aria:
            try:
                loc = self.page.get_by_label(aria, exact=False)
                if await loc.count() > 0:
                    t = loc.first
                    if await self._is_fillable(t):
                        return t
            except Exception:
                pass

        # 4. By id
        el_id = attrs.get("id", "")
        if el_id:
            try:
                loc = self.page.locator(f"#{el_id}")
                if await loc.count() > 0:
                    t = loc.first
                    if await self._is_fillable(t):
                        return t
            except Exception:
                pass

        # 5. Nth editable input of this type (skip readonly/disabled/hidden)
        try:
            real_index = await self.page.evaluate(
                """([selector, targetIdx]) => {
                    const all = Array.from(document.querySelectorAll(selector));
                    let count = 0;
                    for (let i = 0; i < all.length; i++) {
                        const el = all[i];
                        if (el.readOnly || el.disabled || el.offsetWidth === 0) continue;
                        if (el.type === 'hidden') continue;
                        if (count === targetIdx) return i;
                        count++;
                    }
                    return -1;
                }""",
                [etype, idx],
            )
            if real_index >= 0:
                target = self.page.locator(etype).nth(real_index)
                try:
                    await self._wait_visible_if_possible(target, min(timeout, 3000))
                except Exception:
                    pass
                return target
        except Exception:
            pass

        # 6. Any editable input with matching text
        if expected_text and len(expected_text) >= 3:
            try:
                return await self.find_by_type_at_index_containing(
                    etype, 0, f"*{expected_text[:50]}*", timeout_ms=min(timeout, 3000),
                )
            except Exception:
                pass

        raise LookupError(
            f"No editable input found for fill (type='{etype}', index={idx})"
        )

    # ── Select-custom replay ────────────────────────────────────────
    async def _replay_select_custom(
        self, act: dict[str, Any], timeout: int, config: ModeConfig | None = None,
    ) -> None:
        """Replay a select_custom action (custom dropdown option click).

        Custom dropdowns are dynamically rendered — the li/option element
        only exists while the dropdown is open. Strategy:
        1. Wait for dropdown container to appear (previous click opened it)
        2. Search by text inside dropdown container (most reliable)
        3. Search by role=option with matching text
        4. Search by get_by_text globally
        5. Fall back to _resolve_element (capture selectors)
        """
        if config is None:
            config = ModeConfig()
        sel_text = act.get("selected_text", "")
        value = act.get("value", "")
        search_text = sel_text or value
        list_capture = act.get("list_capture")

        # Small wait for dropdown animation to complete
        await asyncio.sleep(0.4)

        # Strategy 1: Find dropdown container via list_capture, search option by text inside it
        if list_capture and search_text:
            try:
                container = await self.relocate_from_capture(list_capture, timeout_ms=min(timeout, 4000))
                try:
                    wf = getattr(container, "wait_for", None)
                    if callable(wf):
                        await wf(state="visible", timeout=3000)
                except Exception:
                    pass
                option = container.get_by_text(search_text, exact=False)
                count = await option.count()
                if count > 0:
                    if config.humanized_pause:
                        await self._humanized_pause()
                    await self._perform_click(option.first, timeout, config)
                    return
            except Exception:
                pass

        # Strategy 2: Find by role=option or role=menuitem with matching text
        if search_text:
            for role in ("option", "menuitem", "listitem"):
                try:
                    loc = self.page.get_by_role(role, name=search_text, exact=False)
                    count = await loc.count()
                    if count > 0:
                        target = loc.first
                        try:
                            await self._wait_visible_if_possible(target, min(timeout, 3000))
                        except Exception:
                            pass
                        if config.humanized_pause:
                            await self._humanized_pause()
                        await self._perform_click(target, timeout, config)
                        return
                except Exception:
                    continue

        # Strategy 3: Find any visible element with matching text (li, div, span, etc.)
        if search_text:
            safe_text = search_text.replace("'", "\\'")
            for sel_template in (
                f"li:has-text('{safe_text}')",
                f"[role='option']:has-text('{safe_text}')",
                f"[role='menuitem']:has-text('{safe_text}')",
                f"div[class*='option']:has-text('{safe_text}')",
                f"div[class*='item']:has-text('{safe_text}')",
            ):
                try:
                    loc = self.page.locator(sel_template)
                    count = await loc.count()
                    if count > 0:
                        target = loc.first
                        vis = await target.is_visible()
                        if vis:
                            if config.humanized_pause:
                                await self._humanized_pause()
                            await self._perform_click(target, timeout, config)
                            return
                except Exception:
                    continue

        # Strategy 4: Global text search
        if search_text:
            try:
                loc = self.page.get_by_text(search_text, exact=False)
                count = await loc.count()
                for i in range(min(count, 5)):
                    el = loc.nth(i)
                    try:
                        vis = await el.is_visible()
                        if vis:
                            if config.humanized_pause:
                                await self._humanized_pause()
                            await self._perform_click(el, timeout, config)
                            return
                    except Exception:
                        continue
            except Exception:
                pass

        # Strategy 5: Fall back to capture/selector/type+index resolution
        try:
            target = await self._resolve_element(act, timeout, config)
            if config.humanized_pause:
                await self._humanized_pause()
            await self._perform_click(target, timeout, config)
            return
        except Exception:
            pass

        raise LookupError(
            f"select_custom: could not find option "
            f"(text='{search_text}', element_type='{act.get('element_type', '')}', "
            f"index={act.get('index', '')})"
        )
