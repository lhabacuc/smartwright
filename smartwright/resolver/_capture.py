from __future__ import annotations
import asyncio
import random
from typing import Any

from smartwright.resolver._base import _CoordinateHandle


class CaptureMixin:
    """Mixin providing element capture & relocate/replay methods."""

    # ── Element capture & replay ────────────────────────────────────────

    async def capture_element(
        self,
        element_type: str,
        index: int,
        timeout_ms: int = 7000,
    ) -> dict[str, Any]:
        """Capture full snapshot of an element: position, attributes, relocators."""
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        return await self._build_capture(target)

    async def capture_element_by_selector(
        self,
        selector: str,
        timeout_ms: int = 7000,
    ) -> dict[str, Any]:
        """Capture snapshot of first element matching CSS selector."""
        if not selector:
            raise ValueError("selector must not be empty")
        locator = self.page.locator(selector)
        count = await self._wait_for_count(locator, timeout_ms)
        if count == 0:
            raise LookupError(f"No elements found for selector '{selector}'")
        target = locator.first
        await self._wait_visible_if_possible(target, timeout_ms)
        return await self._build_capture(target)

    async def capture_element_containing(
        self,
        element_type: str,
        contains: str,
        timeout_ms: int = 7000,
    ) -> dict[str, Any]:
        """Capture snapshot of first element of type whose text/attrs contain keyword."""
        target = await self.find_first_type_containing(
            element_type, contains, timeout_ms=timeout_ms,
        )
        return await self._build_capture(target)

    async def relocate_from_capture(
        self,
        capture: dict[str, Any],
        timeout_ms: int = 7000,
    ) -> Any:
        """Re-find a previously captured element using its stored selectors."""
        if not capture or not capture.get("selectors"):
            raise ValueError("capture must contain a non-empty 'selectors' list")

        for sel in capture["selectors"]:
            try:
                locator = self.page.locator(sel)
                count = await locator.count()
                if count > 0:
                    target = locator.first
                    try:
                        await self._wait_visible_if_possible(target, min(timeout_ms, 3000))
                    except Exception:
                        pass
                    return target
            except Exception:
                continue

        # Fallback: try by tag + index_in_type (e.g. the 2nd button)
        tag = capture.get("tag", "")
        idx = capture.get("index_in_type")
        if tag and idx is not None and idx >= 0:
            try:
                locator = self.page.locator(tag)
                count = await locator.count()
                if idx < count:
                    target = locator.nth(idx)
                    try:
                        await self._wait_visible_if_possible(target, min(timeout_ms, 3000))
                    except Exception:
                        pass
                    return target
            except Exception:
                pass

        # Fallback: try by text content
        text = capture.get("text", "")
        if text and len(text) >= 4:
            snippet = text[:80]
            try:
                locator = self.page.get_by_text(snippet, exact=False)
                count = await locator.count()
                if count > 0:
                    return locator.first
            except Exception:
                pass

        # Last resort: click by saved coordinates
        bbox = capture.get("bbox")
        if bbox and bbox.get("cx") is not None:
            return _CoordinateHandle(self.page, bbox["cx"], bbox["cy"])

        raise LookupError(
            f"Could not relocate element from capture "
            f"(tag={capture.get('tag')}, selectors tried={len(capture.get('selectors', []))})"
        )

    async def click_from_capture(
        self,
        capture: dict[str, Any],
        timeout_ms: int = 7000,
        humanized: bool = True,
    ) -> Any:
        """Relocate a captured element and click it."""
        target = await self.relocate_from_capture(capture, timeout_ms=timeout_ms)
        if humanized:
            await self._humanized_pause()
        return await target.click()

    async def fill_from_capture(
        self,
        capture: dict[str, Any],
        value: str,
        timeout_ms: int = 7000,
        humanized: bool = True,
    ) -> Any:
        """Relocate a captured element and fill it."""
        target = await self.relocate_from_capture(capture, timeout_ms=timeout_ms)
        if humanized:
            press_sequentially = getattr(target, "press_sequentially", None)
            if callable(press_sequentially):
                await target.fill("")
                await press_sequentially(value, delay=random.randint(18, 45))
                return None
            await self._humanized_pause()
        return await target.fill(value)

    async def hover_from_capture(
        self,
        capture: dict[str, Any],
        timeout_ms: int = 7000,
    ) -> Any:
        """Relocate a captured element and hover over it."""
        target = await self.relocate_from_capture(capture, timeout_ms=timeout_ms)
        hover = getattr(target, "hover", None)
        if callable(hover):
            await hover()
        return target

    async def read_from_capture(
        self,
        capture: dict[str, Any],
        timeout_ms: int = 7000,
    ) -> str:
        """Relocate a captured element and read its text."""
        target = await self.relocate_from_capture(capture, timeout_ms=timeout_ms)
        return (await target.inner_text()).strip()

    async def _build_capture(self, locator: Any) -> dict[str, Any]:
        """Extract full snapshot from a resolved locator via JS evaluation."""
        evaluate = getattr(self.page, "evaluate", None)
        evaluate_handle = getattr(locator, "evaluate", None)

        # Try to extract everything via JS on the element handle
        if callable(evaluate_handle):
            try:
                return await evaluate_handle(
                    """
                    (el) => {
                      const rect = el.getBoundingClientRect();
                      const attrs = {};
                      const interesting = [
                        "id", "class", "name", "role", "type", "href", "src",
                        "aria-label", "aria-describedby", "placeholder", "title",
                        "data-testid", "data-id", "data-action", "value", "for",
                        "action", "method", "target", "alt"
                      ];
                      for (const a of interesting) {
                        const v = el.getAttribute(a);
                        if (v) attrs[a] = v;
                      }

                      const tag = (el.tagName || "").toLowerCase();
                      const text = (el.innerText || "").trim().slice(0, 200);

                      // Index among ALL elements of same tag in the page
                      const allSameTag = Array.from(document.querySelectorAll(tag));
                      const indexInType = allSameTag.indexOf(el);
                      const totalInType = allSameTag.length;

                      // Build relocation selectors ordered by specificity
                      const selectors = [];
                      const id = el.id;
                      if (id) selectors.push("#" + CSS.escape(id));

                      const testId = el.getAttribute("data-testid");
                      if (testId) selectors.push("[data-testid='" + testId.replace(/'/g, "\\\\'") + "']");

                      const ariaLabel = el.getAttribute("aria-label");
                      if (ariaLabel) selectors.push(tag + "[aria-label='" + ariaLabel.replace(/'/g, "\\\\'") + "']");

                      const name = el.getAttribute("name");
                      if (name) selectors.push(tag + "[name='" + name.replace(/'/g, "\\\\'") + "']");

                      const placeholder = el.getAttribute("placeholder");
                      if (placeholder) selectors.push(tag + "[placeholder='" + placeholder.replace(/'/g, "\\\\'") + "']");

                      // Class-based selector (use first 3 meaningful classes)
                      const classes = Array.from(el.classList || [])
                        .filter(c => c.length > 1 && !/^[0-9]/.test(c))
                        .slice(0, 3);
                      if (classes.length > 0) {
                        selectors.push(tag + "." + classes.map(c => CSS.escape(c)).join("."));
                      }

                      // Structural: tag + nth-of-type
                      const parent = el.parentElement;
                      if (parent) {
                        const siblings = Array.from(parent.children).filter(s => s.tagName === el.tagName);
                        const idx = siblings.indexOf(el);
                        if (idx >= 0) {
                          const parentTag = parent.tagName.toLowerCase();
                          const parentId = parent.id;
                          const prefix = parentId
                            ? "#" + CSS.escape(parentId) + " > "
                            : parentTag + " > ";
                          selectors.push(prefix + tag + ":nth-of-type(" + (idx + 1) + ")");
                        }
                      }

                      return {
                        tag,
                        index_in_type: indexInType >= 0 ? indexInType : null,
                        total_in_type: totalInType,
                        text,
                        attributes: attrs,
                        bbox: {
                          x: Math.round(rect.x),
                          y: Math.round(rect.y),
                          width: Math.round(rect.width),
                          height: Math.round(rect.height),
                          cx: Math.round(rect.x + rect.width / 2),
                          cy: Math.round(rect.y + rect.height / 2),
                        },
                        selectors,
                        visible: rect.width > 0 && rect.height > 0,
                      };
                    }
                    """
                )
            except Exception:
                pass

        # Fallback: build capture from Playwright locator API
        cap: dict[str, Any] = {
            "tag": "", "index_in_type": None, "total_in_type": None,
            "text": "", "attributes": {}, "bbox": {}, "selectors": [], "visible": True,
        }
        try:
            cap["text"] = ((await locator.inner_text()) or "").strip()[:200]
        except Exception:
            pass
        for attr in ("id", "class", "name", "role", "type", "aria-label", "placeholder", "data-testid", "href", "title"):
            try:
                val = await locator.get_attribute(attr)
                if val:
                    cap["attributes"][attr] = val
            except Exception:
                continue
        try:
            box = await locator.bounding_box()
            if box:
                cap["bbox"] = {
                    "x": round(box["x"]),
                    "y": round(box["y"]),
                    "width": round(box["width"]),
                    "height": round(box["height"]),
                    "cx": round(box["x"] + box["width"] / 2),
                    "cy": round(box["y"] + box["height"] / 2),
                }
        except Exception:
            pass
        # Try to resolve tag and index via page JS
        page_evaluate = getattr(self.page, "evaluate", None)
        element_handle = getattr(locator, "element_handle", None)
        if callable(page_evaluate) and callable(element_handle):
            try:
                handle = await element_handle()
                info = await page_evaluate(
                    """(el) => {
                      const tag = (el.tagName || "").toLowerCase();
                      const all = Array.from(document.querySelectorAll(tag));
                      return { tag, index: all.indexOf(el), total: all.length };
                    }""",
                    handle,
                )
                if info:
                    cap["tag"] = info.get("tag", "")
                    idx = info.get("index", -1)
                    cap["index_in_type"] = idx if idx >= 0 else None
                    cap["total_in_type"] = info.get("total")
            except Exception:
                pass

        # Build selectors from attributes
        a = cap["attributes"]
        if a.get("id"):
            cap["selectors"].append(f"#{a['id']}")
        if a.get("data-testid"):
            cap["selectors"].append(f"[data-testid='{a['data-testid']}']")
        if a.get("aria-label"):
            cap["selectors"].append(f"[aria-label='{a['aria-label']}']")
        if a.get("name"):
            cap["selectors"].append(f"[name='{a['name']}']")
        if a.get("class"):
            cls = a["class"].split()[:3]
            if cls:
                cap["selectors"].append("." + ".".join(cls))
        return cap
