from __future__ import annotations

import asyncio
import os
import random
from typing import Any


from smartwright._logging import logger


class DebugMixin:
    """Debug helpers: virtual cursor, highlight overlays, screenshots."""

    # ── Debug: virtual cursor + highlight + screenshot ───────────────

    # JS to inject the virtual cursor element (called once per replay)
    _DEBUG_CURSOR_INIT_JS = """
    () => {
        if (document.getElementById('__sw_cursor')) return;

        const cur = document.createElement('div');
        cur.id = '__sw_cursor';
        cur.style.cssText = [
            'position:fixed', 'top:-40px', 'left:-40px',
            'width:28px', 'height:28px',
            'z-index:2147483647', 'pointer-events:none',
            'transition:top 0.35s cubic-bezier(.4,0,.2,1),left 0.35s cubic-bezier(.4,0,.2,1)',
            'filter:drop-shadow(1px 2px 2px rgba(0,0,0,.35))',
        ].join(';');

        // Default pointer SVG
        cur.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28" id="__sw_cursor_svg">
          <path d="M2 2 L2 24 L8.5 17.5 L14 26 L18 24 L12.5 15.5 L22 15.5 Z"
                fill="#FF4444" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/>
        </svg>`;
        document.body.appendChild(cur);

        // Ripple container
        const ripple = document.createElement('div');
        ripple.id = '__sw_cursor_ripple';
        ripple.style.cssText = [
            'position:fixed', 'top:0', 'left:0',
            'width:40px', 'height:40px', 'border-radius:50%',
            'border:3px solid #FF4444', 'background:rgba(255,68,68,0.15)',
            'z-index:2147483646', 'pointer-events:none',
            'opacity:0', 'transform:scale(0)',
            'transition:none',
        ].join(';');
        document.body.appendChild(ripple);
    }
    """

    # JS to move cursor to target and show highlight
    _DEBUG_HIGHLIGHT_JS = """
    ([bx, by, bw, bh, step, action]) => {
        // Remove old highlight overlay (not cursor)
        document.querySelectorAll('.__sw_debug').forEach(el => el.remove());

        const cx = bx + bw / 2;
        const cy = by + bh / 2;

        // ── Move virtual cursor ──
        const cur = document.getElementById('__sw_cursor');
        if (cur) {
            cur.style.top = cy + 'px';
            cur.style.left = cx + 'px';

            // Change cursor shape based on action
            const svg = document.getElementById('__sw_cursor_svg');
            if (svg) {
                const isFill = action.startsWith('fill');
                const isHover = action === 'hover';
                if (isFill) {
                    svg.innerHTML = '<rect x="11" y="2" width="3" height="24" rx="1.5" fill="#FF4444" stroke="#fff" stroke-width="1.2"/>';
                } else if (isHover) {
                    svg.innerHTML = '<path d="M14 2 C8 2 2 8 2 14 C2 20 8 26 14 26 C20 26 26 20 26 14 C26 8 20 2 14 2Z" fill="none" stroke="#FF4444" stroke-width="2.5"/><circle cx="14" cy="14" r="4" fill="#FF4444"/>';
                } else {
                    svg.innerHTML = '<path d="M2 2 L2 24 L8.5 17.5 L14 26 L18 24 L12.5 15.5 L22 15.5 Z" fill="#FF4444" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/>';
                }
            }
        }

        // ── Highlight box ──
        const ov = document.createElement('div');
        ov.className = '__sw_debug';
        ov.style.cssText = 'position:fixed;top:'+(by-3)+'px;left:'+(bx-3)+'px;width:'+(bw+6)+'px;height:'+(bh+6)+'px;border:3px solid #FF4444;background:rgba(255,68,68,0.12);z-index:2147483640;pointer-events:none;border-radius:4px;box-shadow:0 0 12px rgba(255,68,68,0.4);';
        const lb = document.createElement('div');
        lb.className = '__sw_debug';
        lb.style.cssText = 'position:fixed;top:'+Math.max(0,by-28)+'px;left:'+bx+'px;background:#FF4444;color:#fff;padding:2px 10px;font:bold 13px monospace;z-index:2147483641;pointer-events:none;border-radius:4px 4px 0 0;white-space:nowrap;letter-spacing:0.5px;';
        lb.textContent = '#' + step + ' ' + action;
        document.body.appendChild(ov);
        document.body.appendChild(lb);
    }
    """

    # JS to fire a click ripple animation at the cursor position
    _DEBUG_CLICK_RIPPLE_JS = """
    () => {
        const cur = document.getElementById('__sw_cursor');
        const ripple = document.getElementById('__sw_cursor_ripple');
        if (!cur || !ripple) return;
        const cx = parseFloat(cur.style.left) || 0;
        const cy = parseFloat(cur.style.top) || 0;
        ripple.style.transition = 'none';
        ripple.style.top = (cy - 20) + 'px';
        ripple.style.left = (cx - 20) + 'px';
        ripple.style.opacity = '1';
        ripple.style.transform = 'scale(0.3)';
        // Force reflow
        void ripple.offsetWidth;
        ripple.style.transition = 'opacity 0.4s ease-out, transform 0.4s ease-out';
        ripple.style.opacity = '0';
        ripple.style.transform = 'scale(1.8)';
    }
    """

    _DEBUG_CLEANUP_JS = """
    () => { document.querySelectorAll('.__sw_debug').forEach(el => el.remove()); }
    """

    _DEBUG_CURSOR_REMOVE_JS = """
    () => {
        const c = document.getElementById('__sw_cursor');
        if (c) c.remove();
        const r = document.getElementById('__sw_cursor_ripple');
        if (r) r.remove();
        document.querySelectorAll('.__sw_debug').forEach(el => el.remove());
    }
    """

    async def _debug_ensure_cursor(self) -> None:
        """Inject the virtual cursor element if not already present."""
        try:
            await self.page.evaluate(self._DEBUG_CURSOR_INIT_JS)
            logger.debug("debug: cursor injected")
        except Exception:
            pass

    async def _debug_highlight(
        self, target: Any, step: int, action: str, screenshot_dir: str,
    ) -> None:
        """Move virtual cursor to element, highlight it, take screenshot."""
        from smartwright.resolver._base import _CoordinateHandle

        # Ensure cursor exists
        await self._debug_ensure_cursor()

        bbox = None
        try:
            if isinstance(target, _CoordinateHandle):
                bbox = {
                    "x": target._cx - 20, "y": target._cy - 20,
                    "width": 40, "height": 40,
                }
            else:
                bbox = await target.bounding_box()
        except Exception:
            pass

        if bbox:
            try:
                await self.page.evaluate(
                    self._DEBUG_HIGHLIGHT_JS,
                    [bbox["x"], bbox["y"], bbox["width"], bbox["height"], step, action],
                )
                # Wait for cursor animation to reach target
                await asyncio.sleep(0.38)
            except Exception:
                pass

        # Screenshot (cursor + highlight visible)
        try:
            os.makedirs(screenshot_dir, exist_ok=True)
            path = os.path.join(screenshot_dir, f"step_{step:03d}_{action}.png")
            await self.page.screenshot(path=path)
            logger.debug("debug: screenshot %s", path)
        except Exception:
            pass

    async def _debug_click_ripple(self) -> None:
        """Show click ripple animation at the cursor position."""
        try:
            await self.page.evaluate(self._DEBUG_CLICK_RIPPLE_JS)
            await asyncio.sleep(0.15)
        except Exception:
            pass

    async def _debug_cleanup(self) -> None:
        """Remove debug highlight elements (keeps cursor alive)."""
        try:
            await self.page.evaluate(self._DEBUG_CLEANUP_JS)
        except Exception:
            pass

    async def _debug_remove_all(self) -> None:
        """Remove everything: cursor, ripple, highlights."""
        try:
            await self.page.evaluate(self._DEBUG_CURSOR_REMOVE_JS)
        except Exception:
            pass
