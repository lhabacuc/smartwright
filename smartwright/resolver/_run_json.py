from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from smartwright._logging import logger
from smartwright.resolver.replay_mode import ModeConfig, ReplayMode, get_mode_config


class RunJsonMixin:
    """Mixin providing run_json-related methods extracted from EmergencyResolver."""

    @staticmethod
    def _normalize_action(raw: dict[str, Any], step_num: int) -> dict[str, Any]:
        """Normalize a hand-written action dict, filling missing fields.

        Accepts shorthand keys and fills sensible defaults so the user
        can write minimal JSON like:
            {"action": "click", "selector": "#btn"}
            {"action": "fill", "text": "Email", "value": "a@b.com"}
            {"action": "goto", "url": "https://example.com"}
            {"action": "wait", "ms": 2000}
            {"action": "press", "key": "Enter"}
        """
        act: dict[str, Any] = {}

        # ── action name (required, with aliases) ──
        action = raw.get("action", raw.get("tipo", "")).strip().lower()
        # common aliases
        _ALIASES: dict[str, str] = {
            "press": "press_keys",
            "press_key": "press_keys",
            "keys": "press_keys",
            "key": "press_keys",
            "type": "fill",
            "input": "fill",
            "write": "fill",
            "navigate": "goto",
            "open": "goto",
            "nav": "goto",
            "go": "goto",
            "tap": "click",
            "select_option": "select",
            "dropdown": "select_custom",
            "radio": "select_radio",
            "checkbox": "check",
            "file": "upload",
            "download": "wait_download",
            "clipboard": "wait_clipboard",
            "copy": "copy_to_clipboard",
            "dnd": "drag_drop",
            "drag": "drag_drop",
            "alert": "dialog",
            "confirm": "dialog",
            "prompt": "dialog",
            "sleep": "wait",
            "delay": "wait",
            "pause": "wait",
            "wait_for": "wait_element",
            "wait_selector": "wait_element",
            "screenshot": "screenshot",
            "snap": "screenshot",
            "back": "go_back",
            "forward": "go_forward",
            "refresh": "reload",
            "eval": "eval_js",
            "js": "eval_js",
            "javascript": "eval_js",
            "read_file": "read_file",
            "write_file": "write_file",
            "save_file": "write_file",
            "list_files": "list_files",
            "ls": "list_files",
            "dir": "list_files",
            "file_exists": "file_exists",
            "exists": "file_exists",
            "delete_file": "delete_file",
            "rm": "delete_file",
            "remove": "delete_file",
            "copy_file": "copy_file",
            "cp": "copy_file",
            "move_file": "move_file",
            "mv": "move_file",
            "file_info": "file_info",
            "stat": "file_info",
        }
        action = _ALIASES.get(action, action)
        act["action"] = action
        act["step"] = raw.get("step", step_num)

        # ── element identification (flexible) ──
        act["element_type"] = raw.get("element_type", raw.get("type", raw.get("tag", "")))
        act["index"] = raw.get("index", raw.get("idx", raw.get("i", None)))
        act["selector"] = raw.get("selector", raw.get("css", raw.get("sel", "")))
        act["text"] = raw.get("text", raw.get("label", raw.get("contains", "")))
        act["capture"] = raw.get("capture", None)

        # ── value (flexible) ──
        act["value"] = raw.get("value", raw.get("val", ""))

        # ── url ──
        act["url"] = raw.get("url", raw.get("href", raw.get("link", "")))

        # ── action-specific fields ──
        # fill: if no element_type but has selector, infer from selector
        if action == "fill" and not act["element_type"] and not act["selector"]:
            act["element_type"] = "input"  # most common fill target

        # press_keys: value from key/keys aliases
        if action == "press_keys":
            if not act["value"]:
                act["value"] = raw.get("key", raw.get("keys", raw.get("combo", "")))

        # wait: normalize ms
        if action == "wait":
            act["wait_ms"] = raw.get("wait_ms", raw.get("ms", raw.get("delay", raw.get("value", 1000))))
            if isinstance(act["wait_ms"], str):
                try:
                    act["wait_ms"] = int(act["wait_ms"])
                except ValueError:
                    act["wait_ms"] = 1000

        # scroll
        if action == "scroll":
            act["direction"] = raw.get("direction", raw.get("dir", "down"))
            act["pixels"] = raw.get("pixels", raw.get("px", raw.get("distance", 500)))

        # select
        if action == "select":
            act["selected_text"] = raw.get("selected_text", raw.get("option", raw.get("label", "")))
            act["selected_index"] = raw.get("selected_index", raw.get("option_index", None))
            act["name"] = raw.get("name", "")

        # select_custom
        if action == "select_custom":
            act["selected_text"] = raw.get("selected_text", raw.get("option", raw.get("text", "")))
            act.setdefault("list_capture", raw.get("list_capture", None))

        # check
        if action == "check":
            act["checked"] = raw.get("checked", raw.get("check", True))
            act["name"] = raw.get("name", "")

        # radio
        if action == "select_radio":
            act["name"] = raw.get("name", raw.get("group", ""))
            if not act["value"]:
                act["value"] = raw.get("option", "")

        # upload
        if action == "upload":
            if not act["value"]:
                act["value"] = raw.get("file", raw.get("files", raw.get("path", "")))

        # drag_drop
        if action == "drag_drop":
            act["source_selector"] = raw.get("source_selector", raw.get("source", raw.get("from", "")))
            act["target_selector"] = raw.get("target_selector", raw.get("target", raw.get("to", "")))

        # dialog
        if action == "dialog":
            act["dialog_action"] = raw.get("dialog_action", raw.get("accept", "accept"))
            if not act["value"]:
                act["value"] = raw.get("prompt_text", raw.get("response", ""))

        # wait_download
        if action == "wait_download":
            act["save_dir"] = raw.get("save_dir", raw.get("dir", "downloads"))

        # wait_element
        if action == "wait_element":
            if not act["selector"]:
                act["selector"] = act.get("value", "") or act.get("text", "")

        # wait_text
        if action == "wait_text":
            if not act["value"]:
                act["value"] = act.get("text", "")

        # wait_url
        if action == "wait_url":
            if not act["value"]:
                act["value"] = act.get("url", "") or act.get("text", "")

        # screenshot
        if action == "screenshot":
            act["path"] = raw.get("path", raw.get("file", raw.get("save", f"screenshot_step_{step_num}.png")))

        # eval_js
        if action == "eval_js":
            act["code"] = raw.get("code", raw.get("script", raw.get("js", raw.get("value", ""))))

        # go_back, go_forward, reload — no extra fields needed
        # goto: already handled via url

        # file operations
        if action in ("read_file", "write_file", "delete_file", "file_exists",
                       "file_info", "copy_file", "move_file"):
            act["path"] = raw.get("path", raw.get("file", raw.get("value", "")))
        if action == "write_file":
            act["content"] = raw.get("content", raw.get("text", raw.get("data", "")))
            act["append"] = raw.get("append", False)
        if action == "list_files":
            act["directory"] = raw.get("directory", raw.get("dir", raw.get("path", ".")))
            act["pattern"] = raw.get("pattern", raw.get("glob", "*"))
            act["recursive"] = raw.get("recursive", False)
        if action == "copy_file":
            act["src"] = raw.get("src", raw.get("from", raw.get("path", "")))
            act["dst"] = raw.get("dst", raw.get("to", raw.get("dest", "")))
        if action == "move_file":
            act["src"] = raw.get("src", raw.get("from", raw.get("path", "")))
            act["dst"] = raw.get("dst", raw.get("to", raw.get("dest", "")))

        # timeout override
        act["timeout_ms"] = raw.get("timeout_ms", raw.get("timeout", 7000))
        if isinstance(act["timeout_ms"], str):
            try:
                act["timeout_ms"] = int(act["timeout_ms"])
            except ValueError:
                act["timeout_ms"] = 7000

        # ── Auto-infer element_type from selector ──
        if not act["element_type"] and act["selector"]:
            sel = act["selector"]
            # Simple tag selectors like "button", "input.class", "div#id"
            for tag in ("input", "button", "select", "textarea", "a", "div", "span",
                        "form", "img", "video", "audio", "iframe", "table", "li", "ul", "ol"):
                if sel.startswith(tag) and (len(sel) == len(tag) or sel[len(tag)] in ".#[:( "):
                    act["element_type"] = tag
                    break

        return act

    async def _resolve_manual_element(
        self, act: dict[str, Any], timeout: int, config: ModeConfig | None = None,
    ) -> Any:
        """Resolve element from a normalized manual action.

        More tolerant than _resolve_element: tries selector, text, role,
        type+index in a flexible order, and never requires capture.
        """
        # Adaptive mode: use semantic fingerprint matching
        if config is not None and config.use_adaptive:
            from smartwright.resolver.adaptive_replay import adaptive_resolve
            return await adaptive_resolve(self.page, act, timeout_ms=timeout)

        selector = act.get("selector", "")
        etype = act.get("element_type", "")
        idx = act.get("index")
        text = act.get("text", "")
        capture = act.get("capture")

        # 1. If capture exists, use standard resolution
        if capture:
            try:
                return await self.relocate_from_capture(capture, timeout_ms=timeout)
            except Exception:
                pass

        # 2. CSS selector (most direct)
        if selector:
            try:
                loc = self.page.locator(selector)
                cnt = await loc.count()
                if cnt == 1:
                    target = loc.first
                    try:
                        await self._wait_visible_if_possible(target, min(timeout, 3000))
                    except Exception:
                        pass
                    return target
                elif cnt > 1:
                    # If index given, use it to pick from matches
                    if idx is not None and cnt > idx:
                        return loc.nth(idx)
                    return loc.first
            except Exception:
                pass

        # 3. Text-based search (very flexible for manual JSON)
        if text:
            # 3a. type + text
            if etype:
                try:
                    return await self.find_by_type_at_index_containing(
                        etype, idx or 0, f"*{text}*", timeout_ms=min(timeout, 4000),
                    )
                except Exception:
                    pass
            # 3b. get_by_text (global)
            try:
                loc = self.page.get_by_text(text, exact=False)
                cnt = await loc.count()
                if cnt > 0:
                    target = loc.nth(idx or 0)
                    try:
                        await self._wait_visible_if_possible(target, min(timeout, 3000))
                    except Exception:
                        pass
                    return target
            except Exception:
                pass
            # 3c. get_by_role with name
            for role in ("button", "link", "textbox", "checkbox", "radio", "option",
                         "menuitem", "tab", "heading"):
                try:
                    loc = self.page.get_by_role(role, name=text)
                    cnt = await loc.count()
                    if cnt > 0:
                        return loc.nth(idx or 0)
                except Exception:
                    pass

        # 4. Type + index (no text)
        if etype and idx is not None:
            try:
                return await self.get_by_type_index(etype, idx, timeout_ms=timeout)
            except Exception:
                pass
            # Without visibility wait
            try:
                loc = self.page.locator(etype)
                cnt = await loc.count()
                if cnt > idx:
                    return loc.nth(idx)
            except Exception:
                pass

        # 5. Type alone (first element of that type)
        if etype:
            try:
                return await self.get_by_type_index(etype, 0, timeout_ms=timeout)
            except Exception:
                pass

        raise LookupError(
            f"Cannot find element: selector='{selector}', type='{etype}', "
            f"index={idx}, text='{text[:40]}'"
        )

    async def run_json(
        self,
        actions: list[dict[str, Any]],
        delay_ms: int = 400,
        on_step: Any = None,
        debug: bool = True,
        screenshot_dir: str = "debug_run",
        mode: str = "padrao",
        continue_on_error: bool = True,
        base_url: str = "",
    ) -> list[dict[str, Any]]:
        """Execute manually-written JSON actions with tolerance for missing fields.

        Unlike replay_actions(), this function:
        - Accepts minimal JSON (only 'action' + essential fields needed)
        - Supports shorthand aliases (e.g. 'press' -> 'press_keys', 'type' -> 'fill')
        - Auto-fills defaults for missing fields
        - Resolves elements flexibly (selector, text, type+index — whatever is provided)
        - Continues on error by default (continue_on_error=True)
        - Supports extra actions: go_back, go_forward, reload, eval_js

        Example minimal JSON::

            [
                {"action": "goto", "url": "https://example.com"},
                {"action": "fill", "selector": "#email", "value": "a@b.com"},
                {"action": "fill", "text": "Password", "value": "123456"},
                {"action": "click", "text": "Login"},
                {"action": "wait", "ms": 2000},
                {"action": "screenshot", "path": "result.png"}
            ]
        """
        import random

        replay_mode = ReplayMode.from_str(mode)
        cfg = get_mode_config(replay_mode)

        if debug:
            await self._debug_ensure_cursor()

        results: list[dict[str, Any]] = []
        last_url = ""

        for i, raw in enumerate(actions):
            act = self._normalize_action(raw, i + 1)
            action = act["action"]
            value = act.get("value", "")
            url = act.get("url", "")
            timeout = act.get("timeout_ms", 7000)
            step_num = act.get("step", i + 1)

            if not action:
                results.append({"step": step_num, "action": "", "status": "skipped", "error": "no action"})
                continue

            logger.debug("run_json step %d: %s", step_num, action)
            result: dict[str, Any] = {"step": step_num, "action": action, "status": "ok", "error": None}

            try:
                # ── goto ──
                if action == "goto":
                    target_url = url or value
                    if base_url and target_url and not target_url.startswith(("http://", "https://")):
                        target_url = base_url.rstrip("/") + "/" + target_url.lstrip("/")
                    norm = target_url.rstrip("/")
                    if norm and norm != last_url.rstrip("/"):
                        await self.page.goto(target_url)
                        try:
                            await self.page.wait_for_load_state("load", timeout=20000)
                        except Exception:
                            pass
                        try:
                            await self.page.wait_for_load_state("networkidle", timeout=10000)
                        except Exception:
                            pass
                        last_url = target_url
                        if debug:
                            try:
                                os.makedirs(screenshot_dir, exist_ok=True)
                                await self.page.screenshot(
                                    path=os.path.join(screenshot_dir, f"step_{step_num:03d}_goto.png"),
                                )
                            except Exception:
                                pass
                    else:
                        result["status"] = "skipped"
                        result["error"] = "duplicate goto or empty url"

                # ── click ──
                elif action == "click":
                    target = await self._resolve_manual_element(act, timeout, cfg)
                    if debug:
                        await self._debug_highlight(target, step_num, action, screenshot_dir)
                    await self._wait_enabled(target, timeout)
                    if cfg.humanized_pause:
                        await self._humanized_pause()
                    if debug:
                        await self._debug_click_ripple()
                    await self._perform_click(target, timeout, cfg)
                    if debug:
                        await self._debug_cleanup()

                # ── fill ──
                elif action == "fill":
                    target = await self._resolve_manual_element(act, timeout, cfg)
                    if not await self._is_fillable(target):
                        target = await self._find_fillable_input(act, timeout)
                    if debug:
                        await self._debug_highlight(target, step_num, f"fill={value[:20]}", screenshot_dir)
                    if cfg.humanized_pause:
                        await self._humanized_pause()
                    if debug:
                        await self._debug_click_ripple()
                    if cfg.humanized_typing:
                        ps = getattr(target, "press_sequentially", None)
                        if callable(ps):
                            await target.fill("")
                            await ps(value, delay=random.randint(18, 45))
                        else:
                            await target.fill(value)
                    else:
                        await target.fill(value)
                    if debug:
                        await self._debug_cleanup()

                # ── check ──
                elif action == "check":
                    raw_checked = act.get("checked", True)
                    checked = raw_checked if isinstance(raw_checked, bool) else str(raw_checked).lower() == "true"
                    target = await self._resolve_manual_element(act, timeout, cfg)
                    if debug:
                        await self._debug_highlight(target, step_num, action, screenshot_dir)
                        await self._debug_click_ripple()
                    sc = getattr(target, "set_checked", None)
                    if callable(sc):
                        await sc(checked)
                    elif checked:
                        await target.check()
                    else:
                        await target.uncheck()
                    if debug:
                        await self._debug_cleanup()

                # ── select ──
                elif action == "select":
                    sel_text = act.get("selected_text", "")
                    sel_idx = act.get("selected_index")
                    target = await self._resolve_manual_element(act, timeout, cfg)
                    if debug:
                        await self._debug_highlight(target, step_num, f"select={sel_text or value}", screenshot_dir)
                        await self._debug_click_ripple()
                    so = getattr(target, "select_option", None)
                    if callable(so):
                        if value:
                            await so(value)
                        elif sel_text:
                            await so(label=sel_text)
                        elif sel_idx is not None:
                            await so(index=sel_idx)
                        else:
                            await self._perform_click(target, timeout, cfg)
                    else:
                        await self._perform_click(target, timeout, cfg)
                    if debug:
                        await self._debug_cleanup()

                # ── select_custom ──
                elif action == "select_custom":
                    if debug:
                        try:
                            os.makedirs(screenshot_dir, exist_ok=True)
                            await self.page.screenshot(
                                path=os.path.join(screenshot_dir, f"step_{step_num:03d}_select_custom.png"),
                            )
                        except Exception:
                            pass
                    await self._replay_select_custom(act, timeout, cfg)

                # ── select_radio ──
                elif action == "select_radio":
                    name = act.get("name", "")
                    if name and value:
                        await self.select_radio_by_name(name, value, timeout_ms=timeout)
                    else:
                        target = await self._resolve_manual_element(act, timeout, cfg)
                        if debug:
                            await self._debug_highlight(target, step_num, action, screenshot_dir)
                            await self._debug_click_ripple()
                        await target.check()
                        if debug:
                            await self._debug_cleanup()

                # ── press_keys ──
                elif action == "press_keys":
                    if debug:
                        try:
                            os.makedirs(screenshot_dir, exist_ok=True)
                            await self.page.screenshot(
                                path=os.path.join(screenshot_dir, f"step_{step_num:03d}_press_{value}.png"),
                            )
                        except Exception:
                            pass
                    await self.press_keys(value)

                # ── hover ──
                elif action == "hover":
                    target = await self._resolve_manual_element(act, timeout, cfg)
                    if debug:
                        await self._debug_highlight(target, step_num, action, screenshot_dir)
                    hover_fn = getattr(target, "hover", None)
                    if callable(hover_fn):
                        await hover_fn()
                    if debug:
                        await self._debug_cleanup()

                # ── scroll ──
                elif action == "scroll":
                    direction = act.get("direction", "down")
                    pixels = act.get("pixels", 500)
                    await self.scroll_page(direction, pixels)

                # ── upload ──
                elif action == "upload":
                    target = await self._resolve_manual_element(act, timeout, cfg)
                    if debug:
                        await self._debug_highlight(target, step_num, action, screenshot_dir)
                        await self._debug_click_ripple()
                    sif = getattr(target, "set_input_files", None)
                    if callable(sif):
                        await sif(value)
                    if debug:
                        await self._debug_cleanup()

                # ── submit ──
                elif action == "submit":
                    target = await self._resolve_manual_element(act, timeout, cfg)
                    if debug:
                        await self._debug_highlight(target, step_num, action, screenshot_dir)
                        await self._debug_click_ripple()
                    ev = getattr(target, "evaluate", None)
                    if callable(ev):
                        await ev("el => el.submit ? el.submit() : el.click()")
                    else:
                        await self._perform_click(target, timeout, cfg)
                    if debug:
                        await self._debug_cleanup()

                # ── drag_drop ──
                elif action == "drag_drop":
                    source = act.get("source_selector", "")
                    target_sel = act.get("target_selector", "")
                    if source and target_sel:
                        await self.drag_and_drop(source, target_sel, timeout_ms=timeout)
                    else:
                        result["status"] = "error"
                        result["error"] = "drag_drop needs source and target selectors"

                # ── dialog ──
                elif action == "dialog":
                    dialog_action = act.get("dialog_action", "accept")
                    await self.handle_dialog(dialog_action, value or None, timeout_ms=timeout)

                # ── wait ──
                elif action == "wait":
                    wait_ms = act.get("wait_ms", 1000)
                    await asyncio.sleep(wait_ms / 1000.0)

                elif action == "wait_element":
                    sel = act.get("selector", "") or value
                    if sel:
                        await self.wait_for_element(sel, timeout_ms=timeout)
                    else:
                        result["status"] = "error"
                        result["error"] = "wait_element needs selector"

                elif action == "wait_text":
                    txt = value or act.get("text", "")
                    if txt:
                        await self.wait_for_text_visible(txt, timeout_ms=timeout)
                    else:
                        result["status"] = "error"
                        result["error"] = "wait_text needs text"

                elif action == "wait_url":
                    pattern = value or act.get("url", "")
                    if pattern:
                        await self.wait_for_url_contains(pattern, timeout_ms=timeout)
                    else:
                        result["status"] = "error"
                        result["error"] = "wait_url needs url pattern"

                # ── screenshot ──
                elif action == "screenshot":
                    fpath = act.get("path", f"screenshot_step_{step_num}.png")
                    etype = act.get("element_type", "")
                    idx = act.get("index")
                    if etype and idx is not None:
                        await self.screenshot_element_by_type_index(etype, idx, fpath, timeout_ms=timeout)
                    else:
                        os.makedirs(os.path.dirname(fpath) or ".", exist_ok=True)
                        await self.page.screenshot(path=fpath, full_page=True)
                    result["path"] = fpath

                # ── wait_download ──
                elif action == "wait_download":
                    save_dir = act.get("save_dir", "downloads")
                    dl_result = await self.wait_download(save_dir=save_dir, timeout_ms=timeout)
                    result["download"] = dl_result

                # ── wait_clipboard ──
                elif action == "wait_clipboard":
                    clip = await self.wait_clipboard(timeout_ms=timeout)
                    result["clipboard"] = clip

                # ── copy_to_clipboard ──
                elif action == "copy_to_clipboard":
                    ok = await self.copy_to_clipboard(value)
                    if not ok:
                        result["status"] = "error"
                        result["error"] = "Failed to copy to clipboard"

                # ── go_back ──
                elif action == "go_back":
                    await self.page.go_back()
                    try:
                        await self.page.wait_for_load_state("load", timeout=10000)
                    except Exception:
                        pass

                # ── go_forward ──
                elif action == "go_forward":
                    await self.page.go_forward()
                    try:
                        await self.page.wait_for_load_state("load", timeout=10000)
                    except Exception:
                        pass

                # ── reload ──
                elif action == "reload":
                    await self.page.reload()
                    try:
                        await self.page.wait_for_load_state("load", timeout=10000)
                    except Exception:
                        pass

                # ── eval_js ──
                elif action == "eval_js":
                    code = act.get("code", "") or value
                    if code:
                        js_result = await self.page.evaluate(code)
                        result["js_result"] = js_result
                    else:
                        result["status"] = "error"
                        result["error"] = "eval_js needs code"

                # ── double_click ──
                elif action == "double_click":
                    target = await self._resolve_manual_element(act, timeout, cfg)
                    if debug:
                        await self._debug_highlight(target, step_num, action, screenshot_dir)
                        await self._debug_click_ripple()
                    await target.dblclick()
                    if debug:
                        await self._debug_cleanup()

                # ── right_click ──
                elif action == "right_click":
                    target = await self._resolve_manual_element(act, timeout, cfg)
                    if debug:
                        await self._debug_highlight(target, step_num, action, screenshot_dir)
                        await self._debug_click_ripple()
                    await target.click(button="right")
                    if debug:
                        await self._debug_cleanup()

                # ── focus ──
                elif action == "focus":
                    target = await self._resolve_manual_element(act, timeout, cfg)
                    await target.focus()

                # ── File system operations ──
                elif action == "read_file":
                    fpath = act.get("path", "")
                    if fpath:
                        result["file"] = await self.read_file(fpath)
                    else:
                        result["status"] = "error"
                        result["error"] = "read_file needs path"

                elif action == "write_file":
                    fpath = act.get("path", "")
                    content = act.get("content", "")
                    if fpath:
                        result["file"] = await self.write_file(
                            fpath, content, append=act.get("append", False),
                        )
                    else:
                        result["status"] = "error"
                        result["error"] = "write_file needs path"

                elif action == "list_files":
                    directory = act.get("directory", ".")
                    pattern = act.get("pattern", "*")
                    result["files"] = await self.list_files(
                        directory, pattern, recursive=act.get("recursive", False),
                    )

                elif action == "file_exists":
                    fpath = act.get("path", "")
                    result["exists"] = await self.file_exists(fpath) if fpath else False

                elif action == "delete_file":
                    fpath = act.get("path", "")
                    if fpath:
                        result["file"] = await self.delete_file(fpath)
                    else:
                        result["status"] = "error"
                        result["error"] = "delete_file needs path"

                elif action == "file_info":
                    fpath = act.get("path", "")
                    if fpath:
                        result["file"] = await self.file_info(fpath)
                    else:
                        result["status"] = "error"
                        result["error"] = "file_info needs path"

                elif action == "copy_file":
                    src = act.get("src", "")
                    dst = act.get("dst", "")
                    if src and dst:
                        result["file"] = await self.copy_file(src, dst)
                    else:
                        result["status"] = "error"
                        result["error"] = "copy_file needs src and dst"

                elif action == "move_file":
                    src = act.get("src", "")
                    dst = act.get("dst", "")
                    if src and dst:
                        result["file"] = await self.move_file(src, dst)
                    else:
                        result["status"] = "error"
                        result["error"] = "move_file needs src and dst"

                else:
                    result["status"] = "skipped"
                    result["error"] = f"Unknown action: {action}"

            except Exception as exc:
                result["status"] = "error"
                result["error"] = str(exc)
                logger.warning("run_json step %d error: %s", step_num, exc)
                if not continue_on_error:
                    results.append(result)
                    if callable(on_step):
                        try:
                            await on_step(i, act, result)
                        except Exception:
                            pass
                    break

            results.append(result)

            if callable(on_step):
                try:
                    await on_step(i, act, result)
                except Exception:
                    pass

            if i < len(actions) - 1:
                if cfg.inter_step_delay and delay_ms > 0 and cfg.delay_factor > 0:
                    effective = delay_ms * cfg.delay_factor
                    jitter = random.uniform(0.8, 1.2)
                    await asyncio.sleep((effective / 1000.0) * jitter)
                else:
                    await asyncio.sleep(0.01)

        if debug:
            await self._debug_remove_all()

        return results

    async def run_json_file(
        self,
        path: str,
        delay_ms: int = 400,
        on_step: Any = None,
        debug: bool = True,
        screenshot_dir: str = "debug_run",
        mode: str = "padrao",
        continue_on_error: bool = True,
        base_url: str = "",
    ) -> list[dict[str, Any]]:
        """Load a hand-written JSON file and execute it with tolerance.

        The JSON file should contain a list of action dicts.
        See run_json() for the format and supported actions.
        """
        actions = self.load_actions_from_json(path)
        return await self.run_json(
            actions, delay_ms=delay_ms, on_step=on_step,
            debug=debug, screenshot_dir=screenshot_dir, mode=mode,
            continue_on_error=continue_on_error, base_url=base_url,
        )
