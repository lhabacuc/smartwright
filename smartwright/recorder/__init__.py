from __future__ import annotations

import asyncio
import json
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_RECORDER_JS = """
() => {
  if (window.__swRecorderActive) return;
  window.__swRecorderActive = true;
  window.__swRecorderPaused = false;

  const IGNORE_TAGS = new Set(["script","style","link","meta","head","html","noscript","svg","path","circle","rect","line","polyline","polygon","ellipse","g","use","defs","clipPath","mask"]);
  const INTERACTIVE_TAGS = new Set(["button","a","input","textarea","select","details","summary","label"]);
  const INTERACTIVE_ROLES = new Set(["button","link","menuitem","option","tab","switch","checkbox","radio","combobox","listbox","menu","textbox","searchbox"]);

  // Climb from inner element (svg, span, etc.) to nearest interactive ancestor
  const resolveInteractive = (el) => {
    let cur = el;
    for (let i = 0; i < 8 && cur && cur !== document.body; i++) {
      const tag = (cur.tagName || "").toLowerCase();
      if (INTERACTIVE_TAGS.has(tag)) return cur;
      const role = (cur.getAttribute && cur.getAttribute("role") || "").toLowerCase();
      if (INTERACTIVE_ROLES.has(role)) return cur;
      if (cur.onclick || cur.getAttribute && cur.getAttribute("tabindex")) return cur;
      cur = cur.parentElement;
    }
    // If nothing interactive found, return the original but resolve svg/path to parent
    cur = el;
    for (let i = 0; i < 4 && cur; i++) {
      const tag = (cur.tagName || "").toLowerCase();
      if (!IGNORE_TAGS.has(tag)) return cur;
      cur = cur.parentElement;
    }
    return el;
  };

  const captureElement = (el) => {
    if (!el || !el.tagName) return null;
    const tag = (el.tagName || "").toLowerCase();
    if (IGNORE_TAGS.has(tag)) return null;

    const rect = el.getBoundingClientRect();
    const attrs = {};
    const interesting = [
      "id","class","name","role","type","href","src",
      "aria-label","aria-selected","aria-checked","aria-expanded",
      "placeholder","title","data-testid","data-id","data-value",
      "data-action","value","for","action","alt","contenteditable"
    ];
    for (const a of interesting) {
      const v = el.getAttribute(a);
      if (v) attrs[a] = v;
    }

    const allSameTag = Array.from(document.querySelectorAll(tag));
    const indexInType = allSameTag.indexOf(el);

    const selectors = [];
    if (el.id) selectors.push("#" + CSS.escape(el.id));
    const testId = el.getAttribute("data-testid");
    if (testId) selectors.push("[data-testid='" + testId.replace(/'/g, "\\\\'") + "']");
    const ariaLabel = el.getAttribute("aria-label");
    if (ariaLabel) selectors.push(tag + "[aria-label='" + ariaLabel.replace(/'/g, "\\\\'") + "']");
    const name = el.getAttribute("name");
    if (name) selectors.push(tag + "[name='" + name.replace(/'/g, "\\\\'") + "']");
    const placeholder = el.getAttribute("placeholder");
    if (placeholder) selectors.push(tag + "[placeholder='" + placeholder.replace(/'/g, "\\\\'") + "']");
    const role = el.getAttribute("role");
    if (role) selectors.push(tag + "[role='" + role + "']");
    const classes = Array.from(el.classList || []).filter(c => c.length > 1 && !/^[0-9]/.test(c)).slice(0, 3);
    if (classes.length > 0) selectors.push(tag + "." + classes.map(c => CSS.escape(c)).join("."));
    const parent = el.parentElement;
    if (parent) {
      const siblings = Array.from(parent.children).filter(s => s.tagName === el.tagName);
      const idx = siblings.indexOf(el);
      if (idx >= 0) {
        const prefix = parent.id ? "#" + CSS.escape(parent.id) + " > " : parent.tagName.toLowerCase() + " > ";
        selectors.push(prefix + tag + ":nth-of-type(" + (idx + 1) + ")");
      }
    }

    return {
      tag,
      index_in_type: indexInType >= 0 ? indexInType : null,
      total_in_type: allSameTag.length,
      text: (el.innerText || "").trim().slice(0, 200),
      attributes: attrs,
      bbox: {
        x: Math.round(rect.x), y: Math.round(rect.y),
        width: Math.round(rect.width), height: Math.round(rect.height),
        cx: Math.round(rect.x + rect.width / 2),
        cy: Math.round(rect.y + rect.height / 2),
      },
      selectors,
      visible: rect.width > 0 && rect.height > 0,
    };
  };

  const sendRaw = (payload) => {
    if (window.__swRecorderPaused) return;
    window._sw_record_event(JSON.stringify(payload)).catch(() => {});
  };

  const send = (actionType, el, extra) => {
    if (window.__swRecorderPaused) return;
    const capture = captureElement(el);
    if (!capture) return;
    sendRaw({
      action: actionType,
      element_type: capture.tag,
      index: capture.index_in_type,
      value: extra || "",
      url: window.location.href,
      capture,
    });
  };

  const sendExtended = (actionType, el, extra) => {
    if (window.__swRecorderPaused) return;
    const capture = captureElement(el);
    if (!capture) return;
    const payload = {
      action: actionType,
      element_type: capture.tag,
      index: capture.index_in_type,
      value: "",
      url: window.location.href,
      capture,
    };
    Object.assign(payload, extra);
    sendRaw(payload);
  };

  // --- Click ---
  document.addEventListener("click", (e) => {
    const raw = e.target;
    const el = resolveInteractive(raw);
    const tag = (el.tagName || "").toLowerCase();
    const role = (el.getAttribute("role") || "").toLowerCase();

    // Skip click on input/textarea (it's just focus, fill will follow)
    if (tag === "input" || tag === "textarea") return;
    const ce = el.getAttribute("contenteditable");
    if (ce === "true" || ce === "") return;

    // Custom dropdown option — explicit ARIA roles
    const isAriaOption = (role === "option" || role === "menuitem" || role === "listitem");
    // Custom dropdown option — li/div inside a dropdown-like container
    const dropdownParent = (tag === "li" || tag === "div")
      ? el.closest("[role='listbox'], [role='menu'], [role='combobox'], [role='select'], [class*='dropdown'], [class*='popover'], [class*='popup'], [class*='menu'], [class*='select'], ul[class]")
      : null;
    if (isAriaOption || dropdownParent) {
      const text = (el.innerText || "").trim().slice(0, 200);
      const dataValue = el.getAttribute("data-value") || el.getAttribute("value") || "";
      let listParent = el.closest("[role='listbox'], [role='menu'], [role='combobox'], [role='select']") || dropdownParent;
      const listCapture = listParent ? captureElement(listParent) : null;
      sendExtended("select_custom", el, {
        value: dataValue || text,
        selected_text: text,
        list_capture: listCapture,
      });
      return;
    }

    // Native <option> click
    if (tag === "option") {
      const sel = el.closest("select");
      if (sel) {
        const text = el.text || el.innerText || "";
        sendExtended("select", sel, {
          value: el.value || "",
          selected_text: text.trim(),
          selected_index: el.index,
          name: sel.name || "",
        });
        return;
      }
    }

    send("click", el, "");
  }, true);

  // --- Input (typing) — includes contenteditable ---
  let inputDebounce = {};
  const handleInput = (el) => {
    const tag = (el.tagName || "").toLowerCase();
    const editable = el.getAttribute("contenteditable");
    const isEditable = editable === "true" || editable === "";
    const val = isEditable ? (el.innerText || "").trim() : (el.value || "");
    const key = tag + (el.name || el.id || el.getAttribute("data-testid") || "x");
    clearTimeout(inputDebounce[key]);
    inputDebounce[key] = setTimeout(() => {
      send("fill", el, val);
      delete inputDebounce[key];
    }, 800);
  };
  document.addEventListener("input", (e) => handleInput(e.target), true);

  // MutationObserver for contenteditable
  const ceObserver = new MutationObserver((mutations) => {
    for (const m of mutations) {
      let el = m.target;
      if (el.nodeType === Node.TEXT_NODE) el = el.parentElement;
      if (!el || !el.getAttribute) continue;
      const ce = el.getAttribute("contenteditable");
      if (ce === "true" || ce === "") handleInput(el);
    }
  });
  ceObserver.observe(document.body, { childList: true, subtree: true, characterData: true });

  // --- Change (select, checkbox, radio, file) ---
  document.addEventListener("change", (e) => {
    const el = e.target;
    const tag = (el.tagName || "").toLowerCase();
    const type = (el.type || "").toLowerCase();
    if (tag === "select") {
      const selText = el.options && el.selectedIndex >= 0 ? el.options[el.selectedIndex].text : "";
      sendExtended("select", el, {
        value: el.value || "",
        selected_text: selText.trim(),
        selected_index: el.selectedIndex,
        name: el.name || "",
      });
    } else if (type === "checkbox") {
      sendExtended("check", el, {
        value: el.value || "",
        checked: el.checked,
        name: el.name || "",
      });
    } else if (type === "radio") {
      sendExtended("select_radio", el, {
        value: el.value || "",
        name: el.name || "",
      });
    } else if (type === "file") {
      const names = Array.from(el.files || []).map(f => f.name).join(", ");
      send("upload", el, names);
    } else {
      send("fill", el, el.value || "");
    }
  }, true);

  // --- Submit ---
  document.addEventListener("submit", (e) => {
    const el = resolveInteractive(e.target);
    send("submit", el, "");
  }, true);

  // --- Scroll ---
  let scrollTimer = null;
  let scrollStart = { x: window.scrollX, y: window.scrollY };
  window.addEventListener("scroll", () => {
    if (window.__swRecorderPaused) return;
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      const dx = window.scrollX - scrollStart.x;
      const dy = window.scrollY - scrollStart.y;
      if (Math.abs(dx) > 50 || Math.abs(dy) > 50) {
        let direction = "down";
        let pixels = Math.abs(dy);
        if (dy < 0) { direction = "up"; }
        else if (Math.abs(dx) > Math.abs(dy)) {
          direction = dx > 0 ? "right" : "left";
          pixels = Math.abs(dx);
        }
        sendRaw({
          action: "scroll", element_type: "", index: null,
          value: "", direction, pixels: Math.round(pixels),
          url: window.location.href, capture: null,
        });
      }
      scrollStart = { x: window.scrollX, y: window.scrollY };
    }, 400);
  }, true);

  // --- Special keys ---
  document.addEventListener("keydown", (e) => {
    const special = ["Enter","Escape","Tab","Backspace","Delete"];
    const hasModifier = e.ctrlKey || e.metaKey || e.altKey;
    if (special.includes(e.key) || hasModifier) {
      let combo = "";
      if (e.ctrlKey || e.metaKey) combo += "Control+";
      if (e.altKey) combo += "Alt+";
      if (e.shiftKey) combo += "Shift+";
      combo += e.key;
      const tag = (e.target.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea") {
        if (!hasModifier && e.key !== "Enter" && e.key !== "Escape" && e.key !== "Tab") return;
      }
      const el = resolveInteractive(e.target);
      send("press_keys", el, combo);
    }
  }, true);

  // --- Clipboard copy detection ---
  document.addEventListener("copy", () => {
    if (window.__swRecorderPaused) return;
    setTimeout(async () => {
      let text = "";
      try {
        text = await navigator.clipboard.readText();
      } catch(e) {
        const sel = window.getSelection();
        text = sel ? sel.toString() : "";
      }
      if (text) {
        sendRaw({
          action: "wait_clipboard",
          element_type: "", index: null,
          value: text.slice(0, 5000),
          url: window.location.href,
          capture: null,
          clipboard_text: text.slice(0, 5000),
        });
      }
    }, 150);
  }, true);
}
"""


class ActionRecorder:
    """Records user actions in a live browser session for later replay."""

    # Default profile directory (relative to save_path parent)
    DEFAULT_PROFILE = ".smartwright_profile"

    def __init__(
        self,
        headless: bool = False,
        save_path: str = "recording.json",
        browser_args: list[str] | None = None,
        user_data_dir: str | None = None,
        stealth: bool = False,
        stealth_config: Any = None,
        record_video_dir: str | None = None,
        record_video_size: dict[str, int] | None = None,
        record_har_path: str | None = None,
    ) -> None:
        self.headless = headless
        self.save_path = save_path
        self.browser_args = browser_args or ["--start-maximized"]
        self.stealth_enabled = stealth
        self.stealth_config = stealth_config
        self.record_video_dir = record_video_dir
        self.record_video_size = record_video_size
        self.record_har_path = record_har_path
        # Persistent profile keeps login/cookies across record & replay sessions
        if user_data_dir:
            self.user_data_dir = user_data_dir
        else:
            parent = str(Path(save_path).resolve().parent)
            self.user_data_dir = str(Path(parent) / self.DEFAULT_PROFILE)
        self._actions: list[dict[str, Any]] = []
        self._paused = False
        self._recording = False
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._step_counter = 0

    @property
    def actions(self) -> list[dict[str, Any]]:
        return list(self._actions)

    @property
    def page(self) -> Any:
        return self._page

    async def start(self, url: str | None = None) -> Any:
        """Launch browser, inject listeners, return page for the user to interact.

        The recorder runs until stop() is called or the user presses Ctrl+C.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise ImportError("playwright is required: pip install playwright") from exc

        self._playwright = await async_playwright().start()

        # ── Stealth: override args if enabled ──
        launch_args = list(self.browser_args)
        ignored_args: list[str] = []
        if self.stealth_enabled:
            from smartwright.stealth import (
                StealthConfig,
                get_stealth_args,
                get_ignored_default_args,
            )
            scfg = self.stealth_config or StealthConfig()
            launch_args = get_stealth_args(scfg)
            ignored_args = get_ignored_default_args(scfg)

        # ── Build extra context options (video, HAR) ──
        ctx_kwargs: dict[str, Any] = {
            "headless": self.headless,
            "args": launch_args,
            "no_viewport": True,
        }
        if ignored_args:
            ctx_kwargs["ignore_default_args"] = ignored_args
        if self.record_video_dir:
            Path(self.record_video_dir).mkdir(parents=True, exist_ok=True)
            ctx_kwargs["record_video_dir"] = self.record_video_dir
            if self.record_video_size:
                ctx_kwargs["record_video_size"] = self.record_video_size
        if self.record_har_path:
            ctx_kwargs["record_har_path"] = self.record_har_path

        # Use persistent context to keep login/cookies across sessions
        Path(self.user_data_dir).mkdir(parents=True, exist_ok=True)
        self._context = await self._playwright.chromium.launch_persistent_context(
            self.user_data_dir,
            **ctx_kwargs,
        )
        self._browser = None  # persistent context has no separate browser

        # ── Apply stealth JS injections ──
        if self.stealth_enabled:
            from smartwright.stealth import apply_stealth as _apply_stealth
            scfg = self.stealth_config
            await _apply_stealth(self._context, scfg)

        self._page = (
            self._context.pages[0]
            if self._context.pages
            else await self._context.new_page()
        )

        # Navigate first, then inject — expose_function on about:blank
        # can cause TargetClosedError when the page navigates away.
        if url:
            await self._page.goto(url)
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            self._actions.append(self._make_action("goto", url=url))

        await self._inject_recorder(self._page)

        self._context.on("page", self._on_new_page)
        # Detect downloads on all pages in this context
        self._page.on("download", lambda dl: asyncio.ensure_future(self._on_download(dl)))

        self._recording = True

        return self._page

    async def stop(self) -> list[dict[str, Any]]:
        """Stop recording, save to JSON, close browser, return actions."""
        self._recording = False
        # Renumber steps sequentially
        actions = list(self._actions)
        for i, act in enumerate(actions):
            act["step"] = i + 1

        if self.save_path:
            self._save_json(actions)

        # Capture video paths before closing context
        self._video_paths: list[str] = []
        if self.record_video_dir and self._context:
            try:
                for pg in self._context.pages:
                    vid = pg.video
                    if vid:
                        path = await vid.path()
                        if path:
                            self._video_paths.append(str(path))
            except Exception:
                pass

        # Save storage state (cookies/localStorage) for portability
        if self._context:
            try:
                state_path = str(Path(self.save_path).with_suffix(".state.json"))
                await self._context.storage_state(path=state_path)
            except Exception:
                pass

        # Close context (persistent context acts as browser+context)
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass

        self._browser = None
        self._context = None
        self._playwright = None
        self._page = None
        return actions

    @property
    def video_paths(self) -> list[str]:
        """Return paths to recorded video files (available after stop())."""
        return getattr(self, "_video_paths", [])

    def pause(self) -> None:
        """Pause recording (events are ignored until resume)."""
        self._paused = True
        if self._page:
            try:
                asyncio.get_event_loop().create_task(
                    self._page.evaluate("window.__swRecorderPaused = true")
                )
            except Exception:
                pass

    def resume(self) -> None:
        """Resume recording after pause."""
        self._paused = False
        if self._page:
            try:
                asyncio.get_event_loop().create_task(
                    self._page.evaluate("window.__swRecorderPaused = false")
                )
            except Exception:
                pass

    async def wait_until_closed(self) -> list[dict[str, Any]]:
        """Block until the user closes the browser window, then save and return actions."""
        if not self._page:
            return self._actions

        closed = asyncio.Event()

        def _on_close() -> None:
            closed.set()

        self._page.on("close", lambda _=None: _on_close())

        loop = asyncio.get_event_loop()
        stop_event = asyncio.Event()

        def _sig_handler() -> None:
            stop_event.set()

        try:
            loop.add_signal_handler(signal.SIGINT, _sig_handler)
        except (NotImplementedError, OSError):
            pass

        done, _ = await asyncio.wait(
            [asyncio.create_task(closed.wait()), asyncio.create_task(stop_event.wait())],
            return_when=asyncio.FIRST_COMPLETED,
        )

        try:
            loop.remove_signal_handler(signal.SIGINT)
        except (NotImplementedError, OSError):
            pass

        return await self.stop()

    # ── Internal ──────────────────────────────────────────────────────────

    async def _inject_recorder(self, page: Any) -> None:
        """Inject JS event listeners and expose the bridge function."""
        try:
            await page.expose_function("_sw_record_event", self._on_js_event)
        except Exception:
            # Already exposed in this context (new tab in same context)
            pass
        await page.evaluate(_RECORDER_JS)
        page.on("framenavigated", lambda _: self._reinject_on_navigate(page))

    async def _reinject_on_navigate(self, page: Any) -> None:
        """Re-inject JS listeners after a navigation (SPA or full reload)."""
        if not self._recording:
            return
        try:
            await page.evaluate(_RECORDER_JS)
        except Exception:
            pass

    def _same_element(self, a: dict, b: dict) -> bool:
        """Check if two action dicts refer to the same DOM element."""
        if a.get("element_type") == b.get("element_type") and a.get("index") == b.get("index"):
            s1 = a.get("selector", "")
            s2 = b.get("selector", "")
            if s1 and s2 and s1 == s2:
                return True
            if a.get("element_type") and a.get("index") is not None:
                return True
        return False

    async def _on_js_event(self, payload_json: str) -> None:
        """Callback invoked by the injected JS for each user action."""
        if self._paused or not self._recording:
            return
        try:
            data = json.loads(payload_json)
        except Exception:
            return

        action_type = data.get("action", "")
        if not action_type:
            return

        now = datetime.now(timezone.utc)

        # Build entry
        self._step_counter += 1
        # Extract element text from capture for smart resolution during replay
        cap = data.get("capture")
        el_text = (cap.get("text", "") if cap else "")

        entry: dict[str, Any] = {
            "step": self._step_counter,
            "action": action_type,
            "element_type": data.get("element_type", ""),
            "index": data.get("index"),
            "value": data.get("value", ""),
            "text": el_text,
            "url": data.get("url", ""),
            "selector": "",
            "capture": cap,
            "timestamp": now.isoformat(),
        }
        # Extra fields for select/check/radio/clipboard
        for k in ("selected_text", "selected_index", "name", "checked", "list_capture", "direction", "pixels", "clipboard_text"):
            if k in data:
                entry[k] = data[k]

        capture = data.get("capture")
        if capture and capture.get("selectors"):
            entry["selector"] = capture["selectors"][0]

        # --- Smart deduplication / collapsing ---

        if self._actions:
            last = self._actions[-1]
            elapsed = (now - datetime.fromisoformat(last["timestamp"])).total_seconds()

            # Collapse consecutive fills on the same element: keep only the last value
            if action_type == "fill" and last.get("action") == "fill" and self._same_element(last, entry):
                last["value"] = entry["value"]
                last["timestamp"] = entry["timestamp"]
                self._step_counter -= 1
                return

            # Drop click that was just focus before a fill (same element, <1.5s)
            # This is checked retroactively: if we get a fill and last was click on same element
            if action_type == "fill" and last.get("action") == "click" and self._same_element(last, entry) and elapsed < 1.5:
                self._actions.pop()

            # Deduplicate exact same event within 0.3s
            if (
                last.get("action") == action_type
                and self._same_element(last, entry)
                and last.get("value") == entry.get("value", "")
                and elapsed < 0.3
            ):
                self._step_counter -= 1
                return

        self._actions.append(entry)

    _NOISE_URL_FRAGMENTS = frozenset({
        "about:blank", "googletagmanager.com", "google-analytics.com",
        "facebook.com/tr", "doubleclick.net", "googlesyndication.com",
        "sw_iframe", "service_worker", "recaptcha", "gstatic.com",
    })

    def _is_noise_url(self, url: str) -> bool:
        if not url or url == "about:blank":
            return True
        return any(frag in url for frag in self._NOISE_URL_FRAGMENTS)

    def _on_navigation(self, frame: Any) -> None:
        """Record page navigations, skipping noise (service workers, analytics, etc.)."""
        if self._paused or not self._recording:
            return
        # Only track main frame navigations
        try:
            page = getattr(frame, "page", None)
            if page and hasattr(page, "main_frame"):
                if frame != page.main_frame:
                    return
        except Exception:
            pass
        try:
            url = frame.url if hasattr(frame, "url") else ""
        except Exception:
            url = ""
        if self._is_noise_url(url):
            return
        # Deduplicate: skip if last action is goto to same URL (or URL that normalizes the same)
        norm = url.rstrip("/")
        for prev in reversed(self._actions[-3:]):
            if prev.get("action") == "goto":
                if prev.get("url", "").rstrip("/") == norm:
                    return
                break
        self._step_counter += 1
        self._actions.append(self._make_action("goto", url=url))

    async def _on_download(self, download: Any) -> None:
        """Record a download event with file info."""
        if self._paused or not self._recording:
            return
        try:
            suggested = download.suggested_filename or "unknown"
            url = download.url or ""
            # Save to a temp dir so we keep the file
            save_dir = str(Path(self.save_path).resolve().parent / "downloads")
            Path(save_dir).mkdir(parents=True, exist_ok=True)
            dest = str(Path(save_dir) / suggested)
            # Avoid overwrite
            import os as _os
            base, ext = _os.path.splitext(dest)
            counter = 1
            while _os.path.exists(dest):
                dest = f"{base}_{counter}{ext}"
                counter += 1
            await download.save_as(dest)
            try:
                size = _os.path.getsize(dest)
            except Exception:
                size = 0
            self._step_counter += 1
            self._actions.append({
                "step": self._step_counter,
                "action": "wait_download",
                "element_type": "",
                "index": None,
                "value": suggested,
                "text": "",
                "url": url,
                "selector": "",
                "capture": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "save_dir": "downloads",
                "download_info": {
                    "filename": _os.path.basename(dest),
                    "path": _os.path.abspath(dest),
                    "url": url,
                    "size": size,
                    "suggested_filename": suggested,
                },
            })
        except Exception:
            pass

    async def _on_new_page(self, page: Any) -> None:
        """Inject recorder into new tabs/popups."""
        if not self._recording:
            return
        try:
            await self._inject_recorder(page)
            page.on("download", lambda dl: asyncio.ensure_future(self._on_download(dl)))
        except Exception:
            pass

    def _make_action(self, action: str, **kwargs: Any) -> dict[str, Any]:
        self._step_counter += 1
        entry: dict[str, Any] = {
            "step": self._step_counter,
            "action": action,
            "element_type": "",
            "index": None,
            "value": "",
            "url": "",
            "selector": "",
            "capture": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        entry.update(kwargs)
        return entry

    def _save_json(self, actions: list[dict[str, Any]]) -> None:
        payload = {
            "version": 1,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "actions": actions,
        }
        Path(self.save_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.save_path).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
