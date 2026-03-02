from __future__ import annotations

import random
from typing import Any


class FormMixin:
    """Mixin providing form and input interaction methods."""

    # ── Input / Form actions ────────────────────────────────────────────

    async def read_input_value(self, element_type: str, index: int, timeout_ms: int = 7000) -> str:
        """Read the .value property of an input/textarea/select."""
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        ev = getattr(target, "input_value", None)
        if callable(ev):
            return await ev()
        ev2 = getattr(target, "evaluate", None)
        if callable(ev2):
            return str(await ev2("el => el.value || ''"))
        return ""

    async def clear_input(self, element_type: str, index: int, timeout_ms: int = 7000) -> None:
        """Clear an input/textarea."""
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        await target.fill("")

    async def fill_input_by_label(
        self, label_text: str, value: str, timeout_ms: int = 7000, humanized: bool = True,
    ) -> Any:
        """Find input by its associated <label> text and fill it."""
        locator = self.page.get_by_label(label_text)
        count = await self._wait_for_count(locator, timeout_ms)
        if count == 0:
            raise LookupError(f"No input found for label '{label_text}'")
        target = locator.first
        if humanized:
            ps = getattr(target, "press_sequentially", None)
            if callable(ps):
                await target.fill("")
                await ps(value, delay=random.randint(18, 45))
                return None
            await self._humanized_pause()
        return await target.fill(value)

    async def toggle_checkbox(self, element_type: str, index: int, timeout_ms: int = 7000) -> bool:
        """Toggle checkbox and return new state."""
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        ev = getattr(target, "evaluate", None)
        if callable(ev):
            return await ev("el => { el.checked = !el.checked; el.dispatchEvent(new Event('change', {bubbles:true})); return el.checked; }")
        is_checked = getattr(target, "is_checked", None)
        if callable(is_checked) and await is_checked():
            await target.uncheck()
            return False
        await target.check()
        return True

    async def select_radio_by_name(self, name: str, value: str, timeout_ms: int = 7000) -> None:
        """Select a radio button by its name group and value."""
        selector = f"input[type='radio'][name='{name}'][value='{value}']"
        locator = self.page.locator(selector)
        count = await self._wait_for_count(locator, timeout_ms)
        if count == 0:
            raise LookupError(f"No radio found with name='{name}' value='{value}'")
        await locator.first.check()

    async def submit_form(self, index: int = 0, timeout_ms: int = 7000) -> None:
        """Submit the nth <form> on the page."""
        target = await self.get_by_type_index("form", index, timeout_ms=timeout_ms)
        ev = getattr(target, "evaluate", None)
        if callable(ev):
            await ev("el => el.submit()")
            return
        try:
            btn = target.locator("button[type='submit'], input[type='submit']")
            if await btn.count() > 0:
                await btn.first.click()
                return
        except Exception:
            pass
        await self.press_keys("Enter")

    async def read_form_state(self, index: int = 0, timeout_ms: int = 7000) -> list[dict[str, Any]]:
        """Capture all field values of the nth <form>."""
        target = await self.get_by_type_index("form", index, timeout_ms=timeout_ms)
        ev = getattr(target, "evaluate", None)
        if not callable(ev):
            return []
        return await ev(
            """el => {
              const fields = el.querySelectorAll('input, textarea, select');
              return Array.from(fields).map(f => ({
                tag: f.tagName.toLowerCase(),
                type: f.type || '',
                name: f.name || '',
                id: f.id || '',
                value: f.value || '',
                checked: !!f.checked,
                placeholder: f.placeholder || '',
                disabled: f.disabled,
                index_in_form: Array.from(fields).indexOf(f),
              }));
            }"""
        )

    async def reset_form(self, index: int = 0, timeout_ms: int = 7000) -> None:
        """Reset the nth <form> to its default values."""
        target = await self.get_by_type_index("form", index, timeout_ms=timeout_ms)
        ev = getattr(target, "evaluate", None)
        if callable(ev):
            await ev("el => el.reset()")

    # ── Select / Dropdown actions ─────────────────────────────────────────

    async def select_option_by_label(
        self, element_type: str, index: int, label: str, timeout_ms: int = 7000,
    ) -> Any:
        """Select an option by its visible text label."""
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        so = getattr(target, "select_option", None)
        if callable(so):
            return await so(label=label)
        raise TypeError(f"Element does not support select_option")

    async def read_selected_option(self, element_type: str, index: int, timeout_ms: int = 7000) -> str:
        """Read the currently selected option text."""
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        ev = getattr(target, "evaluate", None)
        if callable(ev):
            return await ev("el => el.options && el.selectedIndex >= 0 ? el.options[el.selectedIndex].text : el.value || ''")
        return ""

    async def read_all_options(self, element_type: str, index: int, timeout_ms: int = 7000) -> list[dict[str, str]]:
        """Read all options from a <select> element."""
        target = await self.get_by_type_index(element_type, index, timeout_ms=timeout_ms)
        ev = getattr(target, "evaluate", None)
        if callable(ev):
            return await ev(
                """el => el.options
                  ? Array.from(el.options).map((o, i) => ({
                      index: i, value: o.value, text: o.text, selected: o.selected
                    }))
                  : []"""
            )
        return []
