from __future__ import annotations

import asyncio
import json
import os
import random
from pathlib import Path
from typing import Any

from smartwright._logging import logger
from smartwright.resolver._base import _CoordinateHandle
from smartwright.resolver.replay_mode import ModeConfig, ReplayMode, get_mode_config


class ReplayMixin:
    """Mixin providing replay-related methods extracted from EmergencyResolver."""

    @staticmethod
    def save_actions_to_json(actions: list[dict[str, Any]], path: str) -> str:
        """Save a list of action dicts to a JSON file."""
        from datetime import datetime, timezone

        if not path:
            raise ValueError("path must not be empty")
        numbered = []
        for i, act in enumerate(actions):
            entry = dict(act)
            entry.setdefault("step", i + 1)
            entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
            numbered.append(entry)
        payload = {"version": 1, "recorded_at": datetime.now(timezone.utc).isoformat(), "actions": numbered}
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return path

    @staticmethod
    def load_actions_from_json(path: str) -> list[dict[str, Any]]:
        """Load action list from a JSON file."""
        if not path:
            raise ValueError("path must not be empty")
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Actions file not found: {path}")
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("actions", [])
        raise ValueError(f"Invalid actions file format: {path}")

    async def _resolve_element(
        self, act: dict[str, Any], timeout: int, config: ModeConfig | None = None,
    ) -> Any:
        """Resolve an element from an action dict using mode-aware priority chain.

        Steps (gated by config flags):
        0. [adaptativo] semantic fingerprint matching (ignores id/class)
        1. capture CSS selectors (most specific)
        2. CSS selector from action
        3. type + index + text verification (smart match)
        4. type + text search (resilient to DOM index changes)
        5. type + index (basic fallback)
        6. coordinates (last resort via capture bbox)
        """
        if config is None:
            config = ModeConfig()

        t = int(timeout * config.timeout_factor)

        # 0. Adaptive semantic matching (ignora id/class, usa fingerprint)
        if config.use_adaptive:
            from smartwright.resolver.adaptive_replay import adaptive_resolve
            return await adaptive_resolve(self.page, act, timeout_ms=t)

        capture = act.get("capture")
        selector = act.get("selector", "")
        etype = act.get("element_type", "")
        idx = act.get("index", 0) or 0
        expected_text = act.get("text", "") or (
            capture.get("text", "") if capture else ""
        )

        # Filter selectors for por_id_e_class mode
        if config.selector_filter_stable_only:
            if capture:
                capture = self._filter_stable_capture(capture)
            selector = self._filter_stable_selector(selector)

        # 1. Capture CSS selectors (most specific, fast)
        if config.use_capture_selectors and capture:
            try:
                target = await self.relocate_from_capture(capture, timeout_ms=t)
                if not config.verify_capture:
                    return target
                if await self._verify_resolved_element(target, capture, expected_text):
                    return target
            except Exception:
                pass

        # 2. CSS selector from action
        if config.use_action_selector and selector:
            try:
                loc = self.page.locator(selector)
                count = await loc.count()
                if count == 1:
                    target = loc.first
                    try:
                        await self._wait_visible_if_possible(target, min(t, 3000))
                    except Exception:
                        pass
                    return target
                elif count > 1 and capture and capture.get("bbox"):
                    target = await self._pick_closest_to_bbox(loc, count, capture["bbox"])
                    if target:
                        return target
                    return loc.first
                elif count > 0:
                    return loc.first
            except Exception:
                pass

        # 3. Type + index + text (smart)
        if config.use_type_index_text and etype and expected_text and len(expected_text) >= 3:
            try:
                target = await self.find_by_type_at_index_containing(
                    etype, idx, f"*{expected_text[:60]}*",
                    timeout_ms=min(t, 4000),
                )
                return target
            except Exception:
                pass

        # 4. Type + text (ignoring index)
        if config.use_type_text and etype and expected_text and len(expected_text) >= 3 and idx > 0:
            try:
                target = await self.find_by_type_at_index_containing(
                    etype, 0, f"*{expected_text[:60]}*",
                    timeout_ms=min(t, 3000),
                )
                return target
            except Exception:
                pass

        # 5. Type + index (basic fallback)
        if config.use_type_index and etype and idx is not None:
            try:
                return await self.get_by_type_index(etype, idx, timeout_ms=t)
            except Exception:
                pass

        # 5b. Type + index without visibility wait (element may be off-screen)
        if config.use_type_index and etype and idx is not None:
            try:
                loc = self.page.locator(etype)
                count = await loc.count()
                if count > idx:
                    return loc.nth(idx)
            except Exception:
                pass

        # 6. Coordinates from capture bbox (last resort)
        if config.use_coordinates and capture:
            bbox = capture.get("bbox")
            if bbox and bbox.get("cx") is not None:
                return _CoordinateHandle(self.page, bbox["cx"], bbox["cy"])

        raise LookupError(
            f"Could not resolve element: type='{etype}', index={idx}, "
            f"text='{(expected_text or '')[:40]}'"
        )

    async def _resolve_with_retry(
        self, act: dict[str, Any], timeout: int, config: ModeConfig,
    ) -> Any:
        """Resolve element with optional retries + scroll for mix mode."""
        attempts = config.max_retries if config.retry_on_failure else 1
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                if attempt > 0 and config.scroll_between_retries:
                    await self.scroll_page("down", 300)
                    await asyncio.sleep(0.5)
                return await self._resolve_element(act, timeout, config)
            except Exception as exc:
                last_exc = exc
                if attempt < attempts - 1:
                    await asyncio.sleep(1.0)
        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _filter_stable_capture(capture: dict[str, Any]) -> dict[str, Any]:
        """Return capture with selectors filtered to stable identifiers only."""
        filtered = dict(capture)
        original = capture.get("selectors", [])
        stable = [
            s for s in original
            if any(m in s for m in ("#", "[data-testid", "[aria-label", "[name=", "."))
            and ":nth-of-type" not in s
        ]
        filtered["selectors"] = stable if stable else original[:1]
        return filtered

    @staticmethod
    def _filter_stable_selector(selector: str) -> str:
        """Return selector only if it uses stable identifiers, else empty."""
        if not selector:
            return ""
        if any(m in selector for m in ("#", "[data-testid", "[aria-label", "[name=", ".")):
            if ":nth-of-type" not in selector:
                return selector
        return ""

    async def _perform_click(
        self, target: Any, timeout_ms: int, config: ModeConfig,
    ) -> None:
        """Execute click according to mode config's click_strategy."""
        if isinstance(target, _CoordinateHandle):
            await target.click()
            return
        if config.click_strategy == "force":
            await target.click(force=True)
        elif config.click_strategy == "simple":
            await target.click(timeout=min(timeout_ms, 5000))
        else:
            await self._safe_click(target, timeout_ms=timeout_ms)

    async def _wait_enabled(self, target: Any, timeout_ms: int = 5000) -> None:
        """Wait for an element to become enabled (not disabled)."""
        deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000.0)
        while asyncio.get_event_loop().time() < deadline:
            try:
                disabled = await target.is_disabled()
                if not disabled:
                    return
            except Exception:
                return
            await asyncio.sleep(0.25)

    async def replay_actions(
        self,
        actions: list[dict[str, Any]],
        delay_ms: int = 500,
        on_step: Any = None,
        debug: bool = True,
        screenshot_dir: str = "debug_replay",
        mode: str = "padrao",
    ) -> list[dict[str, Any]]:
        """Replay recorded actions using emergency functions as priority.

        mode: execution mode — rapido, padrao, por_index, por_id_e_class, forcado, mix.
        debug: if True, highlight each element and take screenshots.
        screenshot_dir: directory for debug screenshots.
        on_step: optional async callback(step_index, action_dict, result).
        """
        replay_mode = ReplayMode.from_str(mode)
        cfg = get_mode_config(replay_mode)
        logger.info("replay mode: %s", mode)

        if debug:
            await self._debug_ensure_cursor()

        results: list[dict[str, Any]] = []
        last_url = ""

        for i, act in enumerate(actions):
            action = act.get("action", "")
            value = act.get("value", "")
            url = act.get("url", "")
            timeout = act.get("timeout_ms", 7000)
            step_num = act.get("step", i + 1)
            logger.debug("replay step %d: %s", step_num, action)
            result: dict[str, Any] = {"step": step_num, "action": action, "status": "ok", "error": None}

            try:
                # ── Navigation ────────────────────────────────────
                if action == "goto":
                    target_url = url or value
                    norm = target_url.rstrip("/")
                    if norm and norm != last_url.rstrip("/"):
                        await self.page.goto(target_url)
                        # Wait for full page load (not just DOM)
                        try:
                            await self.page.wait_for_load_state("load", timeout=20000)
                        except Exception:
                            pass
                        # Also wait for network to settle (SPA rendering)
                        try:
                            await self.page.wait_for_load_state("networkidle", timeout=10000)
                        except Exception:
                            pass
                        # Wait for page to be interactive: look for the first
                        # interactive element from the NEXT action's capture
                        await self._wait_page_interactive(actions, i, timeout)
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
                        result["error"] = "duplicate goto"

                # ── Click ─────────────────────────────────────────
                elif action == "click":
                    target = await self._resolve_with_retry(act, timeout, cfg)
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

                # ── Fill ──────────────────────────────────────────
                elif action == "fill":
                    target = await self._resolve_with_retry(act, timeout, cfg)
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

                # ── Checkbox ──────────────────────────────────────
                elif action == "check":
                    raw = act.get("checked", True)
                    checked = raw if isinstance(raw, bool) else str(raw).lower() == "true"
                    target = await self._resolve_with_retry(act, timeout, cfg)
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

                # ── Native select ─────────────────────────────────
                elif action == "select":
                    sel_text = act.get("selected_text", "")
                    sel_idx = act.get("selected_index")
                    target = await self._resolve_with_retry(act, timeout, cfg)
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

                # ── Custom dropdown (role=option, etc.) ───────────
                elif action == "select_custom":
                    if debug:
                        try:
                            os.makedirs(screenshot_dir, exist_ok=True)
                            await self.page.screenshot(
                                path=os.path.join(screenshot_dir, f"step_{step_num:03d}_select_custom_before.png"),
                            )
                        except Exception:
                            pass
                    await self._replay_select_custom(act, timeout, cfg)
                    if debug:
                        try:
                            await self.page.screenshot(
                                path=os.path.join(screenshot_dir, f"step_{step_num:03d}_select_custom_after.png"),
                            )
                        except Exception:
                            pass

                # ── Radio button ──────────────────────────────────
                elif action == "select_radio":
                    name = act.get("name", "")
                    if name and value:
                        await self.select_radio_by_name(name, value, timeout_ms=timeout)
                    else:
                        target = await self._resolve_with_retry(act, timeout, cfg)
                        if debug:
                            await self._debug_highlight(target, step_num, action, screenshot_dir)
                            await self._debug_click_ripple()
                        await target.check()
                        if debug:
                            await self._debug_cleanup()

                # ── Keyboard ──────────────────────────────────────
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

                # ── Hover ─────────────────────────────────────────
                elif action == "hover":
                    target = await self._resolve_with_retry(act, timeout, cfg)
                    if debug:
                        await self._debug_highlight(target, step_num, action, screenshot_dir)
                    hover_fn = getattr(target, "hover", None)
                    if callable(hover_fn):
                        await hover_fn()
                    if debug:
                        await self._debug_cleanup()

                # ── Scroll ────────────────────────────────────────
                elif action == "scroll":
                    direction = act.get("direction", "down")
                    pixels = act.get("pixels", 500)
                    await self.scroll_page(direction, pixels)

                # ── Upload ────────────────────────────────────────
                elif action == "upload":
                    target = await self._resolve_with_retry(act, timeout, cfg)
                    if debug:
                        await self._debug_highlight(target, step_num, action, screenshot_dir)
                        await self._debug_click_ripple()
                    sif = getattr(target, "set_input_files", None)
                    if callable(sif):
                        await sif(value)
                    if debug:
                        await self._debug_cleanup()

                # ── Submit ────────────────────────────────────────
                elif action == "submit":
                    target = await self._resolve_with_retry(act, timeout, cfg)
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

                # ── Drag & Drop ───────────────────────────────────
                elif action == "drag_drop":
                    source = act.get("source_selector", "")
                    target_sel = act.get("target_selector", "")
                    await self.drag_and_drop(source, target_sel, timeout_ms=timeout)

                # ── Dialog ────────────────────────────────────────
                elif action == "dialog":
                    dialog_action = act.get("dialog_action", "accept")
                    await self.handle_dialog(dialog_action, value or None, timeout_ms=timeout)

                # ── Waits ─────────────────────────────────────────
                elif action == "wait":
                    wait_ms = act.get("wait_ms", 1000)
                    await asyncio.sleep(wait_ms / 1000.0)

                elif action == "wait_element":
                    sel = act.get("selector", "") or value
                    await self.wait_for_element(sel, timeout_ms=timeout)

                elif action == "wait_text":
                    await self.wait_for_text_visible(value, timeout_ms=timeout)

                elif action == "wait_url":
                    await self.wait_for_url_contains(value, timeout_ms=timeout)

                # ── Screenshot ────────────────────────────────────
                elif action == "screenshot":
                    fpath = act.get("path", f"screenshot_step_{i+1}.png")
                    etype = act.get("element_type", "")
                    idx = act.get("index", 0) or 0
                    if etype:
                        await self.screenshot_element_by_type_index(etype, idx, fpath, timeout_ms=timeout)

                # ── Wait Download ────────────────────────────────
                elif action == "wait_download":
                    save_dir = act.get("save_dir", "downloads")
                    # If next action is a click that triggers the download,
                    # resolve and click it inside expect_download
                    trigger = None
                    trigger_act = act.get("trigger_action")
                    if trigger_act:
                        try:
                            tgt = await self._resolve_element(trigger_act, timeout)
                            trigger = tgt.click()
                        except Exception:
                            pass
                    dl_result = await self.wait_download(
                        save_dir=save_dir,
                        timeout_ms=timeout,
                        trigger_action=trigger,
                    )
                    result["download"] = dl_result
                    if debug:
                        try:
                            os.makedirs(screenshot_dir, exist_ok=True)
                            await self.page.screenshot(
                                path=os.path.join(screenshot_dir, f"step_{step_num:03d}_download.png"),
                            )
                        except Exception:
                            pass

                # ── Wait Clipboard ────────────────────────────────
                elif action == "wait_clipboard":
                    clip = await self.wait_clipboard(
                        timeout_ms=timeout,
                        poll_interval_ms=act.get("poll_interval_ms", 300),
                    )
                    result["clipboard"] = clip
                    if debug:
                        try:
                            os.makedirs(screenshot_dir, exist_ok=True)
                            await self.page.screenshot(
                                path=os.path.join(screenshot_dir, f"step_{step_num:03d}_clipboard.png"),
                            )
                        except Exception:
                            pass

                # ── Copy to Clipboard ────────────────────────────
                elif action == "copy_to_clipboard":
                    ok = await self.copy_to_clipboard(value)
                    if not ok:
                        result["status"] = "error"
                        result["error"] = "Failed to copy to clipboard"

                else:
                    result["status"] = "skipped"
                    result["error"] = f"Unknown action: {action}"

            except Exception as exc:
                result["status"] = "error"
                result["error"] = str(exc)

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
                    await asyncio.sleep(0.01)  # yield to event loop

        if debug:
            await self._debug_remove_all()

        return results

    async def replay_actions_from_json(
        self,
        path: str,
        delay_ms: int = 500,
        on_step: Any = None,
        debug: bool = True,
        screenshot_dir: str = "debug_replay",
        mode: str = "padrao",
    ) -> list[dict[str, Any]]:
        """Load actions from JSON and replay them."""
        actions = self.load_actions_from_json(path)
        return await self.replay_actions(
            actions, delay_ms=delay_ms, on_step=on_step,
            debug=debug, screenshot_dir=screenshot_dir, mode=mode,
        )
