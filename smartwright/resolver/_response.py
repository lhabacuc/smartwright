from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ResponseMixin:
    """Response extraction, clipboard, and download operations extracted from EmergencyResolver."""

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
            if norm in ResponseMixin._PLACEHOLDER_PATTERNS:
                return True
            # Also treat anything under 5 chars as placeholder-like
            if len(norm) < 5:
                return True
        return False

    async def wait_response_text(
        self,
        timeout_ms: int = 90000,
        stable_rounds: int = 3,
        poll_interval_ms: int = 900,
    ) -> str:
        if stable_rounds < 1:
            raise ValueError("stable_rounds must be >= 1")
        if poll_interval_ms < 100:
            raise ValueError("poll_interval_ms must be >= 100")

        deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000.0)
        best = ""
        best_norm = ""
        unchanged = 0

        while asyncio.get_event_loop().time() < deadline:
            current = await self._extract_response_text_heuristic()
            # Filter out placeholder responses
            if current and self._is_placeholder_text(current):
                current = ""
            # Require minimum length to count as a real response
            if current and len(current.strip()) < 20:
                current = ""

            if current:
                current_norm = " ".join(current.split())
                if current_norm == best_norm:
                    unchanged += 1
                else:
                    best = current
                    best_norm = current_norm
                    unchanged = 0

                # Retorna apenas quando texto estabilizar para evitar parcial de streaming.
                if unchanged >= stable_rounds:
                    return best

            await asyncio.sleep(poll_interval_ms / 1000.0)

        return best

    async def wait_and_click_copy_button(
        self,
        timeout_ms: int = 20000,
        poll_interval_ms: int = 350,
    ) -> bool:
        if poll_interval_ms < 100:
            raise ValueError("poll_interval_ms must be >= 100")

        deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000.0)
        while asyncio.get_event_loop().time() < deadline:
            if await self._click_copy_button_by_dom_heuristic():
                return True
            if await self._click_copy_button_by_fallbacks():
                return True
            await asyncio.sleep(poll_interval_ms / 1000.0)
        return False

    async def _extract_response_text_heuristic(self) -> str:
        text = await self._extract_by_dom_heuristic()
        if text:
            return text
        return await self._extract_by_locator_fallbacks()

    async def _extract_by_dom_heuristic(self) -> str:
        evaluate = getattr(self.page, "evaluate", None)
        if not callable(evaluate):
            return ""
        try:
            out = await evaluate(
                """
                () => {
                  const selectors = [
                    "main article",
                    "article",
                    "[role='article']",
                    "[role='status']",
                    "[role='log']",
                    "[aria-live]",
                    "section",
                    "div",
                    "p",
                    "li"
                  ];
                  const nodes = document.querySelectorAll(selectors.join(","));
                  const keywords = ["assistant", "answer", "response", "reply", "bot", "chat", "message", "markdown"];
                  const userKeywords = ["user", "human", "prompt"];
                  const assistantKeywords = ["assistant", "response", "answer", "bot"];
                  const placeholders = ["thinking...", "digitando", "digitando...", "...", "pensando...", "gerando", "gerando..."];
                  let best = "";
                  let bestScore = -1e9;
                  let bestPos = -1e9;

                  const isVisible = (el) => {
                    const style = window.getComputedStyle(el);
                    if (!style) return true;
                    if (style.visibility === "hidden" || style.display === "none") return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                  };

                  const isPlaceholder = (txt) => {
                    const norm = txt.toLowerCase().replace(/\\s+/g, " ").trim();
                    return placeholders.includes(norm) || norm.length < 5;
                  };

                  const ancestorMarker = (el) => {
                    let cur = el;
                    for (let i = 0; i < 6 && cur; i++) {
                      const cls = (cur.className || "").toString().toLowerCase();
                      const id = (cur.id || "").toLowerCase();
                      const combined = `${cls} ${id}`;
                      if (userKeywords.some((k) => combined.includes(k))) return "user";
                      if (assistantKeywords.some((k) => combined.includes(k))) return "assistant";
                      cur = cur.parentElement;
                    }
                    return "";
                  };

                  for (const el of nodes) {
                    if (!isVisible(el)) continue;
                    const text = (el.innerText || "").trim();
                    if (!text || text.length < 20) continue;
                    if (isPlaceholder(text)) continue;

                    const tag = (el.tagName || "").toLowerCase();
                    if (["script", "style", "input", "textarea", "button", "select", "option"].includes(tag)) continue;

                    const role = (el.getAttribute("role") || "").toLowerCase();
                    const ariaLive = (el.getAttribute("aria-live") || "").toLowerCase();
                    const cls = (el.className || "").toString().toLowerCase();
                    const id = (el.id || "").toLowerCase();
                    const marker = `${role} ${ariaLive} ${cls} ${id}`;
                    const rect = el.getBoundingClientRect();

                    let score = 0;
                    if (tag === "article") score += 3;
                    if (["article", "status", "log"].includes(role)) score += 4;
                    if (ariaLive) score += 4;
                    if (text.length >= 50) score += 2;
                    if (text.length >= 120) score += 1;
                    if (keywords.some((k) => marker.includes(k))) score += 3;
                    if (/\\n/.test(text)) score += 1;
                    score += Math.min(4, Math.max(0, rect.top / 350));

                    // Penalize user-message containers
                    if (userKeywords.some((k) => marker.includes(k))) score -= 10;
                    // Boost assistant-message containers
                    if (assistantKeywords.some((k) => marker.includes(k))) score += 6;

                    // Check ancestor elements for user/assistant context
                    const ancestor = ancestorMarker(el);
                    if (ancestor === "user") score -= 10;
                    if (ancestor === "assistant") score += 6;

                    if (score > bestScore || (score === bestScore && rect.top >= bestPos)) {
                      best = text;
                      bestScore = score;
                      bestPos = rect.top;
                    }
                  }

                  return best || "";
                }
                """
            )
            return str(out or "").strip()
        except Exception:
            return ""

    async def _extract_by_locator_fallbacks(self) -> str:
        candidates = [
            "[class*='assistant'] [class*='markdown']",
            "[class*='assistant'] [class*='content']",
            "[role='status']",
            "[role='log']",
            "[aria-live]",
            "article",
            "main article",
            "[data-testid*='assistant']",
            "[data-testid*='message']",
            "[class*='assistant']",
            "[id*='assistant']",
            "[class*='response']",
            "[id*='response']",
            "[class*='message']:not([class*='user'])",
            "[id*='message']:not([id*='user'])",
        ]
        best = ""
        for selector in candidates:
            try:
                locator = self.page.locator(selector)
                count = await locator.count()
                if count <= 0:
                    continue
                el = locator.nth(count - 1)
                txt = (await el.inner_text()).strip()
                if len(txt) < 20:
                    continue
                if self._is_placeholder_text(txt):
                    continue
                # Skip if element is inside a user-message container
                try:
                    user_ancestor = self.page.locator(f"[class*='user'] >> {selector}")
                    user_count = await user_ancestor.count()
                    if user_count > 0:
                        user_txt = (await user_ancestor.nth(user_count - 1).inner_text()).strip()
                        if user_txt == txt:
                            continue
                except Exception:
                    pass
                if len(txt) >= len(best):
                    best = txt
            except Exception:
                continue
        return best

    async def _click_copy_button_by_dom_heuristic(self) -> bool:
        evaluate = getattr(self.page, "evaluate", None)
        if not callable(evaluate):
            return False
        try:
            out = await evaluate(
                """
                () => {
                  const keywords = ["copy", "copiar", "clipboard", "duplicar", "copie"];
                  const nodes = document.querySelectorAll(
                    "button, [role='button'], [aria-label], [title], [data-testid], [class], [id]"
                  );
                  const isVisible = (el) => {
                    const s = window.getComputedStyle(el);
                    if (!s) return true;
                    if (s.visibility === "hidden" || s.display === "none") return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                  };
                  const hasKeyword = (el) => {
                    const text = [
                      el.innerText || "",
                      el.getAttribute("aria-label") || "",
                      el.getAttribute("title") || "",
                      el.getAttribute("data-testid") || "",
                      el.id || "",
                      (el.className || "").toString(),
                    ].join(" ").toLowerCase();
                    return keywords.some((k) => text.includes(k));
                  };

                  let candidate = null;
                  let bestY = -1e9;
                  for (const raw of nodes) {
                    const el = raw.matches("button, [role='button']")
                      ? raw
                      : raw.closest("button, [role='button']");
                    if (!el) continue;
                    if (!isVisible(el)) continue;
                    if (!hasKeyword(el) && !hasKeyword(raw)) continue;
                    const y = el.getBoundingClientRect().top;
                    if (y >= bestY) {
                      candidate = el;
                      bestY = y;
                    }
                  }

                  if (!candidate) return false;
                  candidate.click();
                  return true;
                }
                """
            )
            return bool(out)
        except Exception:
            return False

    async def _click_copy_button_by_fallbacks(self) -> bool:
        keywords = ("copy", "copiar", "clipboard", "duplicar", "copie")

        get_by_role = getattr(self.page, "get_by_role", None)
        if callable(get_by_role):
            for keyword in keywords:
                try:
                    locator = self.page.get_by_role("button", name=keyword)
                    count = await locator.count()
                    if count > 0:
                        await locator.nth(count - 1).click()
                        return True
                except Exception:
                    continue

        try:
            locator = self.page.locator("button")
            count = await locator.count()
            for idx in range(count):
                item = locator.nth(idx)
                parts: list[str] = []
                try:
                    txt = await item.inner_text()
                    if txt:
                        parts.append(txt)
                except Exception:
                    pass
                for attr in ("aria-label", "title", "name", "id", "data-testid", "class"):
                    try:
                        val = await item.get_attribute(attr)
                        if val:
                            parts.append(val)
                    except Exception:
                        continue
                haystack = " ".join(parts).lower()
                if any(keyword in haystack for keyword in keywords):
                    await item.click()
                    return True
        except Exception:
            return False
        return False

    # ── Download & Clipboard ──────────────────────────────────────────────

    async def wait_download(
        self,
        save_dir: str = "downloads",
        timeout_ms: int = 30000,
        trigger_action: Any = None,
    ) -> dict[str, Any]:
        """Wait for a download event and save the file.

        Args:
            save_dir: directory where the downloaded file will be saved.
            trigger_action: optional coroutine to trigger the download
                            (e.g., a button click). If None, waits for an
                            already-initiated download.
            timeout_ms: max wait time in milliseconds.

        Returns:
            dict with keys: filename, path, url, size, suggested_filename.
        """
        os.makedirs(save_dir, exist_ok=True)

        async with self.page.expect_download(timeout=timeout_ms) as dl_info:
            if trigger_action is not None:
                await trigger_action

        download = dl_info.value
        suggested = download.suggested_filename or "download"
        dest = os.path.join(save_dir, suggested)

        # Avoid overwriting — add counter if file exists
        base, ext = os.path.splitext(dest)
        counter = 1
        while os.path.exists(dest):
            dest = f"{base}_{counter}{ext}"
            counter += 1

        await download.save_as(dest)

        try:
            size = os.path.getsize(dest)
        except Exception:
            size = 0

        return {
            "filename": os.path.basename(dest),
            "path": os.path.abspath(dest),
            "url": download.url,
            "size": size,
            "suggested_filename": suggested,
        }

    async def wait_clipboard(
        self,
        timeout_ms: int = 10000,
        poll_interval_ms: int = 300,
    ) -> dict[str, Any]:
        """Read the current clipboard content (text and/or rich content).

        Tries multiple strategies:
        1. navigator.clipboard.readText() (requires permission)
        2. document.execCommand('paste') in a temporary textarea
        3. Poll for clipboard change after a copy event

        Returns:
            dict with keys: text, html (if available), timestamp.
        """
        text = ""
        html = ""

        # Strategy 1: Clipboard API (readText)
        try:
            text = await self.page.evaluate("""
                async () => {
                    try {
                        return await navigator.clipboard.readText();
                    } catch(e) {
                        return "";
                    }
                }
            """)
        except Exception:
            pass

        # Strategy 2: Read HTML from clipboard if available
        if not html:
            try:
                html = await self.page.evaluate("""
                    async () => {
                        try {
                            const items = await navigator.clipboard.read();
                            for (const item of items) {
                                if (item.types.includes('text/html')) {
                                    const blob = await item.getType('text/html');
                                    return await blob.text();
                                }
                            }
                        } catch(e) {}
                        return "";
                    }
                """)
            except Exception:
                pass

        # Strategy 3: execCommand paste fallback (for older pages / no permission)
        if not text:
            try:
                text = await self.page.evaluate("""
                    () => {
                        const ta = document.createElement('textarea');
                        ta.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0;';
                        document.body.appendChild(ta);
                        ta.focus();
                        document.execCommand('paste');
                        const val = ta.value;
                        ta.remove();
                        return val;
                    }
                """)
            except Exception:
                pass

        # Strategy 4: Poll — wait for a copy event to populate the clipboard
        if not text:
            deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000.0)
            # Inject a clipboard listener that saves the copied text
            try:
                await self.page.evaluate("""
                    () => {
                        if (window.__swClipboardListener) return;
                        window.__swClipboardListener = true;
                        window.__swLastCopied = "";
                        document.addEventListener("copy", () => {
                            setTimeout(async () => {
                                try {
                                    window.__swLastCopied = await navigator.clipboard.readText();
                                } catch(e) {
                                    const sel = window.getSelection();
                                    window.__swLastCopied = sel ? sel.toString() : "";
                                }
                            }, 100);
                        });
                    }
                """)
            except Exception:
                pass

            while asyncio.get_event_loop().time() < deadline:
                try:
                    text = await self.page.evaluate("() => window.__swLastCopied || ''")
                    if text:
                        break
                except Exception:
                    pass
                await asyncio.sleep(poll_interval_ms / 1000.0)

        return {
            "text": text or "",
            "html": html or "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def copy_to_clipboard(self, text: str) -> bool:
        """Write text to the page clipboard.

        Returns True if successful.
        """
        try:
            await self.page.evaluate(
                "async (t) => { await navigator.clipboard.writeText(t); }",
                text,
            )
            return True
        except Exception:
            pass
        # Fallback: execCommand
        try:
            await self.page.evaluate("""
                (t) => {
                    const ta = document.createElement('textarea');
                    ta.value = t;
                    ta.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0;';
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand('copy');
                    ta.remove();
                }
            """, text)
            return True
        except Exception:
            return False
