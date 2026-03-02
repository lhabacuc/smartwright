from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PageMixin:
    """Page-level operations extracted from EmergencyResolver."""

    # ── Page info ─────────────────────────────────────────────────────────

    async def get_page_title(self) -> str:
        """Get the document title."""
        title = getattr(self.page, "title", None)
        if callable(title):
            return await title()
        evaluate = getattr(self.page, "evaluate", None)
        if callable(evaluate):
            return await evaluate("document.title")
        return ""

    async def get_page_url(self) -> str:
        """Get the current page URL."""
        return getattr(self.page, "url", "") or ""

    async def get_computed_style(
        self, element_type: str, index: int, css_property: str, timeout_ms: int = 7000,
    ) -> str:
        """Read a computed CSS property from an element."""
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        ev = getattr(target, "evaluate", None)
        if callable(ev):
            return await ev(f"el => window.getComputedStyle(el).getPropertyValue('{css_property}')")
        return ""

    # ── Bulk capture / recording ──────────────────────────────────────────

    async def capture_all_inputs(self, timeout_ms: int = 7000) -> list[dict[str, Any]]:
        """Snapshot ALL <input> and <textarea> elements with values and index."""
        evaluate = getattr(self.page, "evaluate", None)
        if callable(evaluate):
            return await evaluate(
                """() => {
                  const inputs = document.querySelectorAll('input, textarea');
                  return Array.from(inputs).map((el, i) => {
                    const tag = el.tagName.toLowerCase();
                    const allOfTag = document.querySelectorAll(tag);
                    return {
                      tag,
                      type: el.type || '',
                      index_in_type: Array.from(allOfTag).indexOf(el),
                      total_in_type: allOfTag.length,
                      index_in_inputs: i,
                      total_inputs: inputs.length,
                      name: el.name || '',
                      id: el.id || '',
                      value: el.value || '',
                      checked: !!el.checked,
                      placeholder: el.placeholder || '',
                      disabled: el.disabled,
                      readOnly: el.readOnly || false,
                      'aria-label': el.getAttribute('aria-label') || '',
                      visible: el.offsetWidth > 0 && el.offsetHeight > 0,
                    };
                  });
                }"""
            )
        return []

    async def capture_all_buttons(self, timeout_ms: int = 7000) -> list[dict[str, Any]]:
        """Snapshot ALL <button> and input[type=button/submit/reset] elements."""
        evaluate = getattr(self.page, "evaluate", None)
        if callable(evaluate):
            return await evaluate(
                """() => {
                  const btns = document.querySelectorAll(
                    "button, input[type='button'], input[type='submit'], input[type='reset'], [role='button']"
                  );
                  const allButtons = document.querySelectorAll('button');
                  return Array.from(btns).map((el, i) => ({
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    index_in_buttons: i,
                    total_buttons: btns.length,
                    index_in_type: Array.from(allButtons).indexOf(el),
                    total_in_type: allButtons.length,
                    text: (el.innerText || '').trim().slice(0, 200),
                    name: el.name || '',
                    id: el.id || '',
                    'class': (el.className || '').toString(),
                    'aria-label': el.getAttribute('aria-label') || '',
                    disabled: el.disabled || false,
                    visible: el.offsetWidth > 0 && el.offsetHeight > 0,
                  }));
                }"""
            )
        return []

    async def capture_all_selects(self, timeout_ms: int = 7000) -> list[dict[str, Any]]:
        """Snapshot ALL <select> elements with their options."""
        evaluate = getattr(self.page, "evaluate", None)
        if callable(evaluate):
            return await evaluate(
                """() => {
                  const sels = document.querySelectorAll('select');
                  return Array.from(sels).map((el, i) => ({
                    tag: 'select',
                    index_in_type: i,
                    total_in_type: sels.length,
                    name: el.name || '',
                    id: el.id || '',
                    multiple: el.multiple,
                    disabled: el.disabled,
                    selectedIndex: el.selectedIndex,
                    selectedText: el.selectedIndex >= 0 && el.options[el.selectedIndex]
                      ? el.options[el.selectedIndex].text : '',
                    options: Array.from(el.options).map((o, j) => ({
                      index: j, value: o.value, text: o.text, selected: o.selected,
                    })),
                    visible: el.offsetWidth > 0 && el.offsetHeight > 0,
                  }));
                }"""
            )
        return []

    async def capture_all_headings(self, timeout_ms: int = 7000) -> list[dict[str, Any]]:
        """Snapshot all heading elements (h1-h6) with text and index."""
        evaluate = getattr(self.page, "evaluate", None)
        if callable(evaluate):
            return await evaluate(
                """() => {
                  const hs = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
                  return Array.from(hs).map((el, i) => {
                    const tag = el.tagName.toLowerCase();
                    const allOfTag = document.querySelectorAll(tag);
                    return {
                      tag,
                      level: parseInt(tag[1]),
                      index_in_headings: i,
                      total_headings: hs.length,
                      index_in_type: Array.from(allOfTag).indexOf(el),
                      total_in_type: allOfTag.length,
                      text: (el.innerText || '').trim().slice(0, 300),
                      id: el.id || '',
                      visible: el.offsetWidth > 0 && el.offsetHeight > 0,
                    };
                  });
                }"""
            )
        return []

    async def capture_page_elements(self, timeout_ms: int = 7000) -> dict[str, Any]:
        """Full interactive-element inventory of the page for recording."""
        evaluate = getattr(self.page, "evaluate", None)
        if not callable(evaluate):
            return {}
        return await evaluate(
            """() => {
              const collect = (sel) => {
                const els = document.querySelectorAll(sel);
                return Array.from(els).map((el, i) => {
                  const tag = el.tagName.toLowerCase();
                  const rect = el.getBoundingClientRect();
                  const allOfTag = document.querySelectorAll(tag);
                  return {
                    tag,
                    type: el.type || '',
                    index_in_group: i,
                    index_in_type: Array.from(allOfTag).indexOf(el),
                    total_in_type: allOfTag.length,
                    text: (el.innerText || '').trim().slice(0, 150),
                    value: el.value || '',
                    name: el.name || '',
                    id: el.id || '',
                    'class': (el.className || '').toString().slice(0, 200),
                    href: el.href || '',
                    src: el.src || '',
                    alt: el.alt || '',
                    'aria-label': el.getAttribute('aria-label') || '',
                    placeholder: el.placeholder || '',
                    checked: !!el.checked,
                    disabled: !!el.disabled,
                    visible: rect.width > 0 && rect.height > 0,
                    bbox: {
                      x: Math.round(rect.x), y: Math.round(rect.y),
                      w: Math.round(rect.width), h: Math.round(rect.height),
                      cx: Math.round(rect.x + rect.width / 2),
                      cy: Math.round(rect.y + rect.height / 2),
                    },
                  };
                });
              };
              return {
                inputs: collect('input'),
                textareas: collect('textarea'),
                buttons: collect('button, [role="button"]'),
                selects: collect('select'),
                links: collect('a'),
                images: collect('img'),
                videos: collect('video'),
                audios: collect('audio'),
                iframes: collect('iframe'),
                headings: collect('h1, h2, h3, h4, h5, h6'),
                tables: collect('table'),
                lists: collect('ul, ol'),
                forms: collect('form'),
                dialogs: collect('dialog, [role="dialog"]'),
              };
            }"""
        )

    # ── DOM Serializer ────────────────────────────────────────────────────

    async def serialize_dom(self, config: Any = None) -> Any:
        """Serialize page DOM into compact LLM-friendly text with element metadata.

        Returns a DOMSnapshot with .text (formatted string), .elements (metadata list),
        .stats, .url, .title. Use snapshot.to_capture(N) to convert [N] into a dict
        compatible with relocate_from_capture().
        """
        from smartwright.resolver.dom_serializer import serialize_dom as _serialize
        return await _serialize(self.page, config)

    async def serialize_dom_text(self, config: Any = None) -> str:
        """Convenience: return only the serialized text (no metadata)."""
        snapshot = await self.serialize_dom(config)
        return snapshot.text

    # ── JavaScript execution ─────────────────────────────────────────────

    async def eval_js(self, code: str, arg: Any = None) -> Any:
        """Execute arbitrary JavaScript on the page and return the result."""
        if arg is not None:
            return await self.page.evaluate(code, arg)
        return await self.page.evaluate(code)

    async def eval_js_handle(self, code: str, arg: Any = None) -> Any:
        """Execute JS and return a JSHandle (for complex objects)."""
        if arg is not None:
            return await self.page.evaluate_handle(code, arg)
        return await self.page.evaluate_handle(code)

    # ── Element state checks ──────────────────────────────────────────────

    async def element_exists(self, selector: str) -> bool:
        """Check if at least one element matching the selector exists."""
        return await self.page.locator(selector).count() > 0

    async def element_count(self, selector: str) -> int:
        """Count elements matching a selector."""
        return await self.page.locator(selector).count()

    async def is_visible(self, element_type: str, index: int) -> bool:
        """Check if element is visible on the page."""
        try:
            target = self.page.locator(element_type).nth(index)
            return await target.is_visible()
        except Exception:
            return False

    async def is_enabled(self, element_type: str, index: int) -> bool:
        """Check if element is enabled (not disabled)."""
        try:
            target = self.page.locator(element_type).nth(index)
            return await target.is_enabled()
        except Exception:
            return False

    async def is_checked(self, element_type: str, index: int) -> bool:
        """Check if checkbox/radio is checked."""
        try:
            target = self.page.locator(element_type).nth(index)
            return await target.is_checked()
        except Exception:
            return False

    async def has_class(self, element_type: str, index: int, class_name: str) -> bool:
        """Check if element has a specific CSS class."""
        try:
            target = await self.get_by_type_index(element_type, index)
            classes = await target.get_attribute("class") or ""
            return class_name in classes.split()
        except Exception:
            return False

    async def get_classes(self, element_type: str, index: int) -> list[str]:
        """Get all CSS classes of an element."""
        try:
            target = await self.get_by_type_index(element_type, index)
            classes = await target.get_attribute("class") or ""
            return classes.split()
        except Exception:
            return []

    async def get_bounding_box(self, element_type: str, index: int) -> dict[str, float] | None:
        """Get element bounding box {x, y, width, height}."""
        try:
            target = await self.get_by_type_index(element_type, index)
            return await target.bounding_box()
        except Exception:
            return None

    # ── Advanced click actions ─────────────────────────────────────────────

    async def double_click(self, element_type: str, index: int, timeout_ms: int = 7000) -> None:
        """Double-click an element."""
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        await target.dblclick()

    async def right_click(self, element_type: str, index: int, timeout_ms: int = 7000) -> None:
        """Right-click (context menu) on an element."""
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        await target.click(button="right")

    async def focus(self, element_type: str, index: int, timeout_ms: int = 7000) -> None:
        """Focus an element."""
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        await target.focus()

    async def click_at_coordinates(self, x: float, y: float) -> None:
        """Click at specific page coordinates."""
        await self.page.mouse.click(x, y)

    async def mouse_move(self, x: float, y: float) -> None:
        """Move mouse to specific page coordinates."""
        await self.page.mouse.move(x, y)

    async def mouse_wheel(self, delta_x: float = 0, delta_y: float = -300) -> None:
        """Scroll with mouse wheel. Negative delta_y = scroll up."""
        await self.page.mouse.wheel(delta_x, delta_y)

    # ── Page-level operations ──────────────────────────────────────────────

    async def page_screenshot(self, path: str = "screenshot.png", full_page: bool = False) -> str:
        """Take a page screenshot. Returns the file path."""
        await self.page.screenshot(path=path, full_page=full_page)
        return os.path.abspath(path)

    async def page_text(self) -> str:
        """Extract all visible text from the page body."""
        return await self.page.inner_text("body")

    async def page_html(self) -> str:
        """Get the full page HTML content."""
        return await self.page.content()

    async def page_pdf(self, path: str = "page.pdf") -> str:
        """Save the page as PDF (only works in headless mode). Returns path."""
        await self.page.pdf(path=path)
        return os.path.abspath(path)

    async def set_viewport(self, width: int, height: int) -> None:
        """Set the viewport size."""
        await self.page.set_viewport_size({"width": width, "height": height})

    async def go_back(self) -> None:
        """Navigate back in browser history."""
        await self.page.go_back()

    async def go_forward(self) -> None:
        """Navigate forward in browser history."""
        await self.page.go_forward()

    async def reload(self) -> None:
        """Reload the current page."""
        await self.page.reload()

    # ── Cookie management ──────────────────────────────────────────────────

    async def get_cookies(self) -> list[dict[str, Any]]:
        """Get all cookies for the current page."""
        context = self.page.context
        return await context.cookies()

    async def set_cookie(self, name: str, value: str, **kwargs: Any) -> None:
        """Set a cookie. kwargs can include: domain, path, expires, httpOnly, secure, sameSite."""
        context = self.page.context
        cookie: dict[str, Any] = {"name": name, "value": value}
        if "url" not in kwargs and "domain" not in kwargs:
            cookie["url"] = self.page.url
        cookie.update(kwargs)
        await context.add_cookies([cookie])

    async def clear_cookies(self) -> None:
        """Clear all cookies."""
        context = self.page.context
        await context.clear_cookies()

    # ── LocalStorage & SessionStorage ──────────────────────────────────────

    async def get_local_storage(self, key: str) -> str | None:
        """Read a value from localStorage."""
        return await self.page.evaluate(
            "(k) => localStorage.getItem(k)", key,
        )

    async def set_local_storage(self, key: str, value: str) -> None:
        """Write a value to localStorage."""
        await self.page.evaluate(
            "([k, v]) => localStorage.setItem(k, v)", [key, value],
        )

    async def remove_local_storage(self, key: str) -> None:
        """Remove a key from localStorage."""
        await self.page.evaluate(
            "(k) => localStorage.removeItem(k)", key,
        )

    async def clear_local_storage(self) -> None:
        """Clear all localStorage."""
        await self.page.evaluate("() => localStorage.clear()")

    async def get_all_local_storage(self) -> dict[str, str]:
        """Get all localStorage key-value pairs."""
        return await self.page.evaluate(
            "() => { const o = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); o[k] = localStorage.getItem(k); } return o; }"
        )

    async def get_session_storage(self, key: str) -> str | None:
        """Read a value from sessionStorage."""
        return await self.page.evaluate(
            "(k) => sessionStorage.getItem(k)", key,
        )

    async def set_session_storage(self, key: str, value: str) -> None:
        """Write a value to sessionStorage."""
        await self.page.evaluate(
            "([k, v]) => sessionStorage.setItem(k, v)", [key, value],
        )

    async def clear_session_storage(self) -> None:
        """Clear all sessionStorage."""
        await self.page.evaluate("() => sessionStorage.clear()")

    # ── Network / Response waiting ─────────────────────────────────────────

    async def wait_for_response(
        self, url_pattern: str, timeout_ms: int = 30000,
    ) -> dict[str, Any]:
        """Wait for a network response matching url_pattern (substring match).

        Returns dict with: url, status, headers, body (text).
        """
        resp = await self.page.wait_for_response(
            lambda r: url_pattern in r.url,
            timeout=timeout_ms,
        )
        try:
            body = await resp.text()
        except Exception:
            body = ""
        return {
            "url": resp.url,
            "status": resp.status,
            "headers": resp.headers,
            "body": body,
        }

    async def wait_for_load(self, state: str = "load", timeout_ms: int = 30000) -> None:
        """Wait for page load state: 'load', 'domcontentloaded', or 'networkidle'."""
        await self.page.wait_for_load_state(state, timeout=timeout_ms)

    # ── File system operations ─────────────────────────────────────────────

    @staticmethod
    async def read_file(
        path: str,
        encoding: str = "utf-8",
        max_size: int = 10 * 1024 * 1024,
    ) -> dict[str, Any]:
        """Read a file from disk.

        Returns dict: path, content, size, encoding.
        For binary files, content is None and binary_b64 contains base64 data.
        """
        import base64

        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {path}")
        size = p.stat().st_size
        if size > max_size:
            raise ValueError(f"File too large: {size} bytes (max {max_size})")

        result: dict[str, Any] = {
            "path": str(p.resolve()),
            "size": size,
            "encoding": encoding,
        }

        try:
            result["content"] = p.read_text(encoding=encoding)
            result["binary"] = False
        except (UnicodeDecodeError, ValueError):
            result["content"] = None
            result["binary_b64"] = base64.b64encode(p.read_bytes()).decode("ascii")
            result["binary"] = True

        return result

    @staticmethod
    async def write_file(
        path: str,
        content: str,
        append: bool = False,
        encoding: str = "utf-8",
        mkdir: bool = True,
    ) -> dict[str, Any]:
        """Write or append text to a file.

        Returns dict: path, size, appended.
        """
        p = Path(path)
        if mkdir:
            p.parent.mkdir(parents=True, exist_ok=True)

        if append:
            with open(p, "a", encoding=encoding) as f:
                f.write(content)
        else:
            p.write_text(content, encoding=encoding)

        return {
            "path": str(p.resolve()),
            "size": p.stat().st_size,
            "appended": append,
        }

    @staticmethod
    async def list_files(
        directory: str = ".",
        pattern: str = "*",
        recursive: bool = False,
    ) -> list[dict[str, Any]]:
        """List files in a directory matching a glob pattern.

        Returns list of dicts: name, path, size, is_dir.
        """
        p = Path(directory)
        if not p.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        entries = p.rglob(pattern) if recursive else p.glob(pattern)
        results: list[dict[str, Any]] = []
        for entry in sorted(entries):
            try:
                stat = entry.stat()
                results.append({
                    "name": entry.name,
                    "path": str(entry.resolve()),
                    "size": stat.st_size,
                    "is_dir": entry.is_dir(),
                })
            except OSError:
                pass
        return results

    @staticmethod
    async def file_exists(path: str) -> bool:
        """Check if a file or directory exists."""
        return Path(path).exists()

    @staticmethod
    async def delete_file(path: str) -> dict[str, Any]:
        """Delete a file (not a directory).

        Returns dict: path, deleted.
        """
        p = Path(path)
        if not p.exists():
            return {"path": str(p.resolve()), "deleted": False, "error": "not found"}
        if p.is_dir():
            return {"path": str(p.resolve()), "deleted": False, "error": "is a directory"}
        p.unlink()
        return {"path": str(p.resolve()), "deleted": True}

    @staticmethod
    async def file_info(path: str) -> dict[str, Any]:
        """Get file metadata: size, modified time, type."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {path}")
        stat = p.stat()
        return {
            "path": str(p.resolve()),
            "name": p.name,
            "size": stat.st_size,
            "is_dir": p.is_dir(),
            "is_file": p.is_file(),
            "extension": p.suffix,
            "modified": stat.st_mtime,
        }

    @staticmethod
    async def copy_file(src: str, dst: str) -> dict[str, Any]:
        """Copy a file to another location."""
        import shutil
        src_p = Path(src)
        dst_p = Path(dst)
        if not src_p.exists():
            raise FileNotFoundError(f"Source not found: {src}")
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        result_path = shutil.copy2(str(src_p), str(dst_p))
        return {
            "src": str(src_p.resolve()),
            "dst": str(Path(result_path).resolve()),
            "size": Path(result_path).stat().st_size,
        }

    @staticmethod
    async def move_file(src: str, dst: str) -> dict[str, Any]:
        """Move a file to another location."""
        import shutil
        src_p = Path(src)
        dst_p = Path(dst)
        if not src_p.exists():
            raise FileNotFoundError(f"Source not found: {src}")
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        result_path = shutil.move(str(src_p), str(dst_p))
        return {
            "src": str(src_p.resolve()),
            "dst": str(Path(result_path).resolve()),
        }

    # ── Recording utilities (GIF, HAR) ────────────────────────────────────

    @staticmethod
    async def generate_gif(
        screenshot_dir: str = "debug_screenshots",
        output_path: str = "recording.gif",
        duration_ms: int = 800,
        loop: int = 0,
    ) -> dict[str, Any]:
        """Generate an animated GIF from debug screenshots.

        Args:
            screenshot_dir: directory containing screenshot PNG files.
            output_path: path to save the GIF.
            duration_ms: duration per frame in milliseconds.
            loop: 0 = infinite loop, N = loop N times.

        Returns:
            dict: path, frames, size.
        """
        try:
            from PIL import Image
        except ImportError:
            raise ImportError("Pillow is required for GIF generation: pip install Pillow")

        src = Path(screenshot_dir)
        if not src.is_dir():
            raise FileNotFoundError(f"Screenshot directory not found: {screenshot_dir}")

        # Collect PNGs sorted by name (step_001_*, step_002_*, ...)
        pngs = sorted(src.glob("*.png"))
        if not pngs:
            raise FileNotFoundError(f"No PNG files found in {screenshot_dir}")

        frames: list[Image.Image] = []
        for png_path in pngs:
            img = Image.open(png_path).convert("RGBA")
            # Convert to palette mode for smaller GIF
            img = img.convert("RGB")
            frames.append(img)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=loop,
            optimize=True,
        )

        return {
            "path": str(Path(output_path).resolve()),
            "frames": len(frames),
            "size": Path(output_path).stat().st_size,
        }

    @staticmethod
    async def read_har(path: str) -> dict[str, Any]:
        """Read and parse a HAR (HTTP Archive) file.

        Returns dict with summary and entries.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"HAR file not found: {path}")

        with open(p, "r", encoding="utf-8") as f:
            har = json.load(f)

        log = har.get("log", {})
        entries = log.get("entries", [])

        summary: list[dict[str, Any]] = []
        for entry in entries:
            req = entry.get("request", {})
            resp = entry.get("response", {})
            summary.append({
                "method": req.get("method", ""),
                "url": req.get("url", ""),
                "status": resp.get("status", 0),
                "status_text": resp.get("statusText", ""),
                "size": resp.get("content", {}).get("size", 0),
                "mime_type": resp.get("content", {}).get("mimeType", ""),
                "time_ms": entry.get("time", 0),
            })

        return {
            "path": str(p.resolve()),
            "version": log.get("version", ""),
            "total_entries": len(entries),
            "entries": summary,
        }

    @staticmethod
    async def extract_har_apis(
        path: str,
        filter_pattern: str = "/api/",
    ) -> list[dict[str, Any]]:
        """Extract API calls from a HAR file.

        Filters entries by URL pattern and returns method, url, status,
        request body, and response body for each.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"HAR file not found: {path}")

        with open(p, "r", encoding="utf-8") as f:
            har = json.load(f)

        entries = har.get("log", {}).get("entries", [])
        apis: list[dict[str, Any]] = []

        for entry in entries:
            req = entry.get("request", {})
            resp = entry.get("response", {})
            url = req.get("url", "")

            if filter_pattern and filter_pattern not in url:
                continue

            # Extract request body
            req_body = None
            post_data = req.get("postData")
            if post_data:
                req_body = post_data.get("text", "")

            # Extract response body
            resp_body = None
            resp_content = resp.get("content", {})
            if resp_content.get("text"):
                resp_body = resp_content["text"]

            apis.append({
                "method": req.get("method", ""),
                "url": url,
                "status": resp.get("status", 0),
                "request_headers": {h["name"]: h["value"] for h in req.get("headers", [])},
                "request_body": req_body,
                "response_body": resp_body,
                "mime_type": resp_content.get("mimeType", ""),
                "time_ms": entry.get("time", 0),
            })

        return apis
