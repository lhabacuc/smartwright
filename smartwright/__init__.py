from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from playwright.async_api import BrowserContext, Page

    from smartwright.captcha.solver import CaptchaSolver
    from smartwright.resolver.dom_diff import PageDiff as _PageDiff
    from smartwright.resolver.dom_serializer import DOMSerializerConfig, DOMSnapshot

from smartwright._logging import setup_logging
from smartwright.captcha.solver import CaptchaType, detect_captcha
from smartwright.constants import VERSION
from smartwright.core.engine import DecisionEngine
from smartwright.exceptions import (
    CaptchaNotDetectedError,
    CaptchaSolverError,
    CaptureError,
    DialogError,
    ElementNotFoundError,
    ElementResolutionError,
    FillError,
    NavigationError,
    NetworkError,
    ProxyError,
    ProxyExhaustedError,
    ReplayError,
    RetryExhaustedError,
    SessionError,
    SmartwrightError,
    TabError,
    TimeoutError,
)
from smartwright.proxy import ProxyConfig, ProxyRotator, RotationStrategy
from smartwright.resolver.dom_diff import PageDiff, diff_snapshots
from smartwright.resolver.emergency import EmergencyResolver
from smartwright.retry import BackoffStrategy, RetryConfig, retry, with_retry

__version__ = VERSION

__all__ = [
    "Smartwright",
    "SmartwrightError",
    "ElementNotFoundError",
    "ElementResolutionError",
    "ReplayError",
    "FillError",
    "NavigationError",
    "TimeoutError",
    "CaptureError",
    "DialogError",
    "NetworkError",
    # Retry
    "RetryConfig",
    "BackoffStrategy",
    "with_retry",
    "retry",
    "RetryExhaustedError",
    # Proxy
    "ProxyConfig",
    "ProxyRotator",
    "RotationStrategy",
    "ProxyError",
    "ProxyExhaustedError",
    # Session
    "SessionError",
    # Page Diff
    "PageDiff",
    "diff_snapshots",
    # Captcha
    "CaptchaType",
    "detect_captcha",
    "CaptchaSolverError",
    "CaptchaNotDetectedError",
    # Tabs
    "TabError",
    # Logging
    "setup_logging",
]


DEFAULT_INTENTS = {
    "login_button": ["Entrar", "Login", "Sign in"],
    "email_field": ["Email", "E-mail", "Username"],
    "password_field": ["Senha", "Password"],
}


class Smartwright:
    """Motor de automacao web adaptativo com 290+ metodos.

    Oferece tres modos de interacao:
    - **Semantico (intent-driven)**: ``click("login_button")`` — resolve por intencao.
    - **Emergency (type+index)**: ``emergency_click("button", 0)`` — acesso direto.
    - **Replay**: grava acoes do usuario e reproduz com resolucao inteligente.

    Args:
        page: Objeto Page do Playwright.
        request_context: ``context.request`` do Playwright (para chamadas API).
        intents: Mapa de intencoes semanticas ``{"login_button": ["Entrar", "Login"]}``.
        semantic_map: Mapa semantico avancado com roles e patterns.
        store_path: Caminho do ficheiro de persistencia de conhecimento.
        ai_advisor: Advisor IA opcional (ex: GroqAdvisor) para fallback.
        debug: Se True, ativa depuracao visual (cursor, highlight, screenshots).

    Exemplo::

        sw = Smartwright(page=page, request_context=context.request, debug=True)
        await sw.set_debug(screenshot_dir="debug")
        await sw.goto("https://example.com")
        await sw.emergency_fill("input", 0, "user@test.com")
        await sw.emergency_click_by_text("Login")
    """

    def __init__(
        self,
        page: Page,
        request_context: object,
        intents: dict[str, list[str]] | None = None,
        semantic_map: dict[str, dict[str, list[str]]] | None = None,
        store_path: str = ".smartwright_knowledge.json",
        ai_advisor: object | None = None,
        debug: bool = False,
    ) -> None:
        self.page = page
        self.engine = DecisionEngine(
            page=page,
            request_context=request_context,
            intents=intents or DEFAULT_INTENTS,
            semantic_map=semantic_map,
            store_path=store_path,
            ai_advisor=ai_advisor,
        )
        self.emergency = EmergencyResolver(page)

        # Debug visual
        self._debug = debug
        self._debug_dir = "debug_screenshots"
        self._debug_pause_ms = 350
        self._debug_step = 0
        self._debug_cursor_ready = False

    async def set_debug(
        self,
        enabled: bool = True,
        screenshot_dir: str = "debug_screenshots",
        pause_ms: int = 350,
    ) -> None:
        """Ativa/desativa depuracao visual em todas as acoes.

        Quando ativo, cada acao mostra:
        - Cursor virtual animado
        - Highlight do elemento alvo (borda colorida)
        - Efeito ripple nos clicks
        - Screenshot automatico por step
        """
        self._debug = enabled
        self._debug_dir = screenshot_dir
        self._debug_pause_ms = pause_ms
        self._debug_step = 0
        if enabled:
            os.makedirs(screenshot_dir, exist_ok=True)
            await self.emergency._debug_ensure_cursor()
            self._debug_cursor_ready = True

    async def _dbg(self, target: Any, label: str, is_click: bool = True) -> None:
        """Debug visual: highlight + cursor + ripple + screenshot."""
        if not self._debug:
            return
        if not self._debug_cursor_ready:
            await self.emergency._debug_ensure_cursor()
            self._debug_cursor_ready = True
        self._debug_step += 1
        await self.emergency._debug_highlight(
            target, self._debug_step, label, self._debug_dir,
        )
        await asyncio.sleep(self._debug_pause_ms / 1000)
        if is_click:
            await self.emergency._debug_click_ripple()

    async def _dbg_end(self) -> None:
        """Limpa elementos de debug apos acao."""
        if self._debug:
            await self.emergency._debug_cleanup()

    def attach_network_learning(self) -> None:
        """Ativa network learning — intercepta trafego e descobre APIs."""
        self.engine.attach_network_learning()

    async def goto(self, url: str) -> None:
        """Navega para a URL e ativa network learning automaticamente."""
        self.engine.attach_network_learning()
        await self.page.goto(url)

    async def click(self, intent: str) -> Any:
        """Click semantico por intencao. Ex: ``await sw.click("login_button")``."""
        return await self.engine.run(action="click", intent=intent)

    async def fill(self, intent: str, value: str) -> Any:
        """Fill semantico por intencao. Ex: ``await sw.fill("email_field", "a@b.com")``."""
        return await self.engine.run(action="fill", intent=intent, value=value)

    async def read(self, intent: str) -> Any:
        """Read semantico por intencao. Ex: ``await sw.read("price_label")``."""
        return await self.engine.run(action="read", intent=intent)

    async def emergency_fill(self, element_type: str, index: int, value: str, timeout_ms: int = 7000) -> Any:
        """Preenche o N-esimo elemento do tipo HTML. Ex: ``emergency_fill("input", 0, "email@test.com")``."""
        if self._debug:
            target = await self.emergency.get_by_type_index(element_type, index, timeout_ms)
            await self._dbg(target, f"fill {element_type}[{index}]", is_click=False)
            await target.fill(value)
            await self._dbg_end()
            return None
        return await self.emergency.fill_by_type_index(element_type, index, value, timeout_ms=timeout_ms)

    async def emergency_click(self, element_type: str, index: int, timeout_ms: int = 7000) -> Any:
        """Clica no N-esimo elemento do tipo HTML. Ex: ``emergency_click("button", 2)``."""
        if self._debug:
            target = await self.emergency.get_by_type_index(element_type, index, timeout_ms)
            await self._dbg(target, f"click {element_type}[{index}]")
            await target.click()
            await self._dbg_end()
            return None
        return await self.emergency.click_by_type_index(element_type, index, timeout_ms=timeout_ms)

    async def emergency_read(self, element_type: str, index: int, timeout_ms: int = 7000) -> str:
        """Le o texto do N-esimo elemento do tipo HTML. Retorna string."""
        if self._debug:
            target = await self.emergency.get_by_type_index(element_type, index, timeout_ms)
            await self._dbg(target, f"read {element_type}[{index}]", is_click=False)
            result = (await target.inner_text()).strip()
            await self._dbg_end()
            return result
        return await self.emergency.read_by_type_index(element_type, index, timeout_ms=timeout_ms)

    async def emergency_fill_by_role(self, role: str, index: int, value: str, timeout_ms: int = 7000) -> Any:
        """Preenche o N-esimo elemento por role ARIA. Ex: ``emergency_fill_by_role("textbox", 0, "texto")``."""
        if self._debug:
            target = await self.emergency.get_by_role_index(role, index, timeout_ms)
            await self._dbg(target, f"fill role={role}[{index}]", is_click=False)
            await target.fill(value)
            await self._dbg_end()
            return None
        return await self.emergency.fill_by_role_index(role, index, value, timeout_ms=timeout_ms)

    async def emergency_click_by_role(self, role: str, index: int, timeout_ms: int = 7000) -> Any:
        """Clica no N-esimo elemento por role ARIA. Ex: ``emergency_click_by_role("button", 1)``."""
        if self._debug:
            target = await self.emergency.get_by_role_index(role, index, timeout_ms)
            await self._dbg(target, f"click role={role}[{index}]")
            await target.click()
            await self._dbg_end()
            return None
        return await self.emergency.click_by_role_index(role, index, timeout_ms=timeout_ms)

    async def emergency_read_by_role(self, role: str, index: int, timeout_ms: int = 7000) -> str:
        """Le texto do N-esimo elemento por role ARIA."""
        return await self.emergency.read_by_role_index(role, index, timeout_ms=timeout_ms)

    async def emergency_click_by_text(self, text: str, index: int = 0, timeout_ms: int = 7000) -> Any:
        """Clica no elemento que contem o texto visivel. Ex: ``emergency_click_by_text("Enviar")``."""
        if self._debug:
            target = await self.emergency.get_by_text_index(text, index, timeout_ms)
            await self._dbg(target, f'click "{text[:20]}"')
            await target.click()
            await self._dbg_end()
            return None
        return await self.emergency.click_by_text_index(text, index, timeout_ms=timeout_ms)

    async def emergency_read_by_text(self, text: str, index: int = 0, timeout_ms: int = 7000) -> str:
        """Le texto do elemento que contem o texto visivel."""
        return await self.emergency.read_by_text_index(text, index, timeout_ms=timeout_ms)

    async def emergency_click_first_type_containing(
        self,
        element_type: str,
        contains: str,
        timeout_ms: int = 7000,
        humanized: bool = True,
    ) -> Any:
        """Clica no primeiro elemento do tipo cujos atributos contenham o texto. Ex: ``("button", "*salvar*")``."""
        if self._debug:
            target = await self.emergency.find_first_type_containing(
                element_type, contains, timeout_ms=timeout_ms,
            )
            await self._dbg(target, f'click {element_type}~"{contains[:15]}"')
            await target.click()
            await self._dbg_end()
            return None
        return await self.emergency.click_first_type_containing(
            element_type, contains, timeout_ms=timeout_ms, humanized=humanized,
        )

    async def emergency_fill_first_type_containing(
        self,
        element_type: str,
        contains: str,
        value: str,
        timeout_ms: int = 7000,
        humanized: bool = True,
    ) -> Any:
        """Preenche o primeiro elemento do tipo cujos atributos contenham o texto."""
        if self._debug:
            target = await self.emergency.find_first_type_containing(
                element_type, contains, timeout_ms=timeout_ms,
            )
            await self._dbg(target, f'fill {element_type}~"{contains[:15]}"', is_click=False)
            if humanized:
                ps = getattr(target, "press_sequentially", None)
                if callable(ps):
                    await target.fill("")
                    await ps(value, delay=30)
                    await self._dbg_end()
                    return None
            await target.fill(value)
            await self._dbg_end()
            return None
        return await self.emergency.fill_first_type_containing(
            element_type, contains, value, timeout_ms=timeout_ms, humanized=humanized,
        )

    async def emergency_read_first_type_containing(self, element_type: str, contains: str, timeout_ms: int = 7000) -> str:
        """Le texto do primeiro elemento do tipo cujos atributos contenham o texto."""
        return await self.emergency.read_first_type_containing(element_type, contains, timeout_ms=timeout_ms)

    # ── Smart type + index + text pattern functions ────────────────────

    async def emergency_find_by_type_at_index_containing(
        self,
        element_type: str,
        index: int,
        text_pattern: str,
        timeout_ms: int = 7000,
    ) -> Any:
        """Encontra o N-esimo elemento do tipo cujo texto corresponde ao pattern glob."""
        return await self.emergency.find_by_type_at_index_containing(
            element_type, index, text_pattern, timeout_ms=timeout_ms,
        )

    async def emergency_click_by_type_at_index_containing(
        self,
        element_type: str,
        index: int,
        text_pattern: str,
        timeout_ms: int = 7000,
        humanized: bool = True,
    ) -> Any:
        """Clica no N-esimo elemento do tipo cujo texto corresponde ao pattern."""
        return await self.emergency.click_by_type_at_index_containing(
            element_type, index, text_pattern,
            timeout_ms=timeout_ms, humanized=humanized,
        )

    async def emergency_fill_by_type_at_index_containing(
        self,
        element_type: str,
        index: int,
        text_pattern: str,
        value: str,
        timeout_ms: int = 7000,
        humanized: bool = True,
    ) -> Any:
        """Preenche o N-esimo elemento do tipo cujo texto corresponde ao pattern."""
        return await self.emergency.fill_by_type_at_index_containing(
            element_type, index, text_pattern, value,
            timeout_ms=timeout_ms, humanized=humanized,
        )

    async def emergency_read_by_type_at_index_containing(
        self,
        element_type: str,
        index: int,
        text_pattern: str,
        timeout_ms: int = 7000,
    ) -> str:
        """Le texto do N-esimo elemento do tipo cujo texto corresponde ao pattern."""
        return await self.emergency.read_by_type_at_index_containing(
            element_type, index, text_pattern, timeout_ms=timeout_ms,
        )

    async def emergency_click_first_input_containing(
        self,
        contains: str,
        timeout_ms: int = 7000,
        humanized: bool = True,
    ) -> Any:
        """Atalho: clica no primeiro ``<input>`` cujos atributos contenham o texto."""
        return await self.emergency_click_first_type_containing(
            "input",
            contains,
            timeout_ms=timeout_ms,
            humanized=humanized,
        )

    async def emergency_fill_first_input_containing(
        self,
        contains: str,
        value: str,
        timeout_ms: int = 7000,
        humanized: bool = True,
    ) -> Any:
        """Atalho: preenche o primeiro ``<input>`` cujos atributos contenham o texto."""
        return await self.emergency_fill_first_type_containing(
            "input",
            contains,
            value,
            timeout_ms=timeout_ms,
            humanized=humanized,
        )

    # ── Intelligent emergency functions ──────────────────────────────────

    async def emergency_wait_for_element(self, selector: str, timeout_ms: int = 15000) -> Any:
        """Espera ate o elemento CSS aparecer no DOM. Ex: ``("div.resultado")``."""
        return await self.emergency.wait_for_element(selector, timeout_ms=timeout_ms)

    async def emergency_wait_for_url_contains(self, substring: str, timeout_ms: int = 15000) -> str:
        """Espera ate a URL conter a substring. Retorna a URL final."""
        return await self.emergency.wait_for_url_contains(substring, timeout_ms=timeout_ms)

    async def emergency_select_option(
        self, element_type: str, index: int, value: str, timeout_ms: int = 7000,
    ) -> Any:
        """Seleciona opcao num ``<select>`` pelo value."""
        if self._debug:
            target = await self.emergency.get_by_type_index(element_type, index, timeout_ms)
            await self._dbg(target, f"select {element_type}[{index}]")
            so = getattr(target, "select_option", None)
            if callable(so):
                await so(value)
            await self._dbg_end()
            return None
        return await self.emergency.select_option_by_type_index(element_type, index, value, timeout_ms=timeout_ms)

    async def emergency_check(
        self, element_type: str, index: int, checked: bool = True, timeout_ms: int = 7000,
    ) -> Any:
        """Marca/desmarca checkbox. checked=True marca, False desmarca."""
        if self._debug:
            target = await self.emergency.get_by_type_index(element_type, index, timeout_ms)
            await self._dbg(target, f"check {element_type}[{index}]")
            sc = getattr(target, "set_checked", None)
            if callable(sc):
                await sc(checked)
            elif checked:
                await target.check()
            else:
                await target.uncheck()
            await self._dbg_end()
            return None
        return await self.emergency.check_by_type_index(element_type, index, checked=checked, timeout_ms=timeout_ms)

    async def emergency_upload_file(
        self, element_type: str, index: int, file_paths: str | list[str], timeout_ms: int = 7000,
    ) -> Any:
        """Faz upload de ficheiro(s) para o N-esimo input file."""
        return await self.emergency.upload_file_by_type_index(element_type, index, file_paths, timeout_ms=timeout_ms)

    async def emergency_press_keys(self, keys: str, timeout_ms: int = 7000) -> None:
        """Pressiona teclas. Ex: ``"Enter"``, ``"Tab"``, ``"Control+a"``, ``"Shift+ArrowDown"``."""
        return await self.emergency.press_keys(keys, timeout_ms=timeout_ms)

    async def emergency_hover(
        self, element_type: str, index: int, timeout_ms: int = 7000,
    ) -> Any:
        """Hover sobre o N-esimo elemento do tipo indicado."""
        if self._debug:
            target = await self.emergency.get_by_type_index(element_type, index, timeout_ms)
            await self._dbg(target, f"hover {element_type}[{index}]", is_click=False)
            hover_fn = getattr(target, "hover", None)
            if callable(hover_fn):
                await hover_fn()
            await self._dbg_end()
            return None
        return await self.emergency.hover_by_type_index(element_type, index, timeout_ms=timeout_ms)

    async def emergency_scroll_to(self, selector: str, timeout_ms: int = 7000) -> Any:
        """Scroll ate tornar o elemento visivel (CSS selector)."""
        return await self.emergency.scroll_to_element(selector, timeout_ms=timeout_ms)

    async def emergency_get_attribute(
        self, element_type: str, index: int, attribute: str, timeout_ms: int = 7000,
    ) -> str | None:
        """Le um atributo HTML do N-esimo elemento. Retorna None se nao existir."""
        return await self.emergency.get_attribute_by_type_index(element_type, index, attribute, timeout_ms=timeout_ms)

    async def emergency_read_all(self, element_type: str, timeout_ms: int = 7000) -> list[str]:
        """Le o texto de todos os elementos do tipo. Retorna lista de strings."""
        return await self.emergency.read_all_by_type(element_type, timeout_ms=timeout_ms)

    async def emergency_screenshot_element(
        self, element_type: str, index: int, path: str, timeout_ms: int = 7000,
    ) -> str:
        """Tira screenshot so do N-esimo elemento e salva no path indicado."""
        return await self.emergency.screenshot_element_by_type_index(element_type, index, path, timeout_ms=timeout_ms)

    async def emergency_wait_for_text(self, text: str, timeout_ms: int = 15000) -> Any:
        """Espera ate o texto aparecer visivel na pagina."""
        return await self.emergency.wait_for_text_visible(text, timeout_ms=timeout_ms)

    # ── Element capture & replay ────────────────────────────────────────

    async def emergency_capture(
        self, element_type: str, index: int, timeout_ms: int = 7000,
    ) -> dict[str, Any]:
        """Captura fingerprint semantico do N-esimo elemento (para relocate posterior)."""
        return await self.emergency.capture_element(element_type, index, timeout_ms=timeout_ms)

    async def emergency_capture_by_selector(
        self, selector: str, timeout_ms: int = 7000,
    ) -> dict[str, Any]:
        """Captura fingerprint semantico via CSS selector."""
        return await self.emergency.capture_element_by_selector(selector, timeout_ms=timeout_ms)

    async def emergency_capture_containing(
        self, element_type: str, contains: str, timeout_ms: int = 7000,
    ) -> dict[str, Any]:
        """Captura fingerprint do primeiro elemento do tipo que contenha o texto."""
        return await self.emergency.capture_element_containing(element_type, contains, timeout_ms=timeout_ms)

    async def emergency_relocate(
        self, capture: dict[str, Any], timeout_ms: int = 7000,
    ) -> Any:
        """Re-encontra um elemento a partir de um capture dict anterior."""
        return await self.emergency.relocate_from_capture(capture, timeout_ms=timeout_ms)

    async def emergency_click_captured(
        self, capture: dict[str, Any], timeout_ms: int = 7000, humanized: bool = True,
    ) -> Any:
        """Clica num elemento usando capture dict (obtido via emergency_capture)."""
        return await self.emergency.click_from_capture(capture, timeout_ms=timeout_ms, humanized=humanized)

    async def emergency_fill_captured(
        self, capture: dict[str, Any], value: str, timeout_ms: int = 7000, humanized: bool = True,
    ) -> Any:
        """Preenche um campo usando capture dict."""
        return await self.emergency.fill_from_capture(capture, value, timeout_ms=timeout_ms, humanized=humanized)

    async def emergency_hover_captured(
        self, capture: dict[str, Any], timeout_ms: int = 7000,
    ) -> Any:
        """Hover sobre elemento usando capture dict."""
        return await self.emergency.hover_from_capture(capture, timeout_ms=timeout_ms)

    async def emergency_read_captured(
        self, capture: dict[str, Any], timeout_ms: int = 7000,
    ) -> str:
        """Le texto de elemento usando capture dict."""
        return await self.emergency.read_from_capture(capture, timeout_ms=timeout_ms)

    # ── Input / Form ────────────────────────────────────────────────────

    async def emergency_read_input_value(self, element_type: str, index: int, timeout_ms: int = 7000) -> str:
        """Le o value atual de um input/textarea/select."""
        return await self.emergency.read_input_value(element_type, index, timeout_ms=timeout_ms)

    async def emergency_clear_input(self, element_type: str, index: int, timeout_ms: int = 7000) -> None:
        """Limpa o conteudo do N-esimo input."""
        return await self.emergency.clear_input(element_type, index, timeout_ms=timeout_ms)

    async def emergency_fill_by_label(
        self, label_text: str, value: str, timeout_ms: int = 7000, humanized: bool = True,
    ) -> Any:
        """Preenche input associado a um ``<label>`` pelo texto do label."""
        if self._debug:
            target = self.page.get_by_label(label_text)
            count = await target.count()
            if count > 0:
                await self._dbg(target.first, f'fill label="{label_text[:15]}"', is_click=False)
                await target.first.fill(value)
                await self._dbg_end()
                return None
        return await self.emergency.fill_input_by_label(label_text, value, timeout_ms=timeout_ms, humanized=humanized)

    async def emergency_toggle_checkbox(self, element_type: str, index: int, timeout_ms: int = 7000) -> bool:
        """Inverte o estado de um checkbox. Retorna o novo estado (True=checked)."""
        return await self.emergency.toggle_checkbox(element_type, index, timeout_ms=timeout_ms)

    async def emergency_select_radio(self, name: str, value: str, timeout_ms: int = 7000) -> None:
        """Seleciona radio button pelo atributo name e value."""
        return await self.emergency.select_radio_by_name(name, value, timeout_ms=timeout_ms)

    async def emergency_submit_form(self, index: int = 0, timeout_ms: int = 7000) -> None:
        """Submete o N-esimo formulario da pagina."""
        return await self.emergency.submit_form(index, timeout_ms=timeout_ms)

    async def emergency_read_form_state(self, index: int = 0, timeout_ms: int = 7000) -> list[dict[str, Any]]:
        """Le o estado atual de todos os campos do N-esimo form."""
        return await self.emergency.read_form_state(index, timeout_ms=timeout_ms)

    async def emergency_reset_form(self, index: int = 0, timeout_ms: int = 7000) -> None:
        """Reseta o N-esimo form ao estado inicial."""
        return await self.emergency.reset_form(index, timeout_ms=timeout_ms)

    # ── Select / Dropdown ─────────────────────────────────────────────────

    async def emergency_select_option_by_label(
        self, element_type: str, index: int, label: str, timeout_ms: int = 7000,
    ) -> Any:
        """Seleciona opcao de um ``<select>`` pelo texto visivel da opcao."""
        return await self.emergency.select_option_by_label(element_type, index, label, timeout_ms=timeout_ms)

    async def emergency_read_selected_option(self, element_type: str, index: int, timeout_ms: int = 7000) -> str:
        """Le o texto da opcao atualmente selecionada num ``<select>``."""
        return await self.emergency.read_selected_option(element_type, index, timeout_ms=timeout_ms)

    async def emergency_read_all_options(
        self, element_type: str, index: int, timeout_ms: int = 7000,
    ) -> list[dict[str, str]]:
        """Lista todas as opcoes de um ``<select>`` com value e label."""
        return await self.emergency.read_all_options(element_type, index, timeout_ms=timeout_ms)

    # ── Links ─────────────────────────────────────────────────────────────

    async def emergency_click_link(self, text: str, index: int = 0, timeout_ms: int = 7000) -> Any:
        """Clica num link ``<a>`` pelo texto visivel."""
        if self._debug:
            locator = self.page.locator(f"a:has-text('{text}')")
            count = await self.emergency._wait_for_count(locator, timeout_ms)
            if count > 0:
                target = locator.nth(min(index, count - 1))
                await self._dbg(target, f'link "{text[:20]}"')
                await target.click()
                await self._dbg_end()
                return None
        return await self.emergency.click_link_by_text(text, index, timeout_ms=timeout_ms)

    async def emergency_get_link_href(self, text: str, index: int = 0, timeout_ms: int = 7000) -> str:
        """Retorna o href de um link pelo texto."""
        return await self.emergency.get_link_href(text, index, timeout_ms=timeout_ms)

    async def emergency_capture_all_links(self, timeout_ms: int = 7000) -> list[dict[str, Any]]:
        """Captura todos os links da pagina (text, href, target)."""
        return await self.emergency.capture_all_links(timeout_ms=timeout_ms)

    # ── Table ─────────────────────────────────────────────────────────────

    async def emergency_read_table_cell(
        self, table_index: int, row: int, col: int, timeout_ms: int = 7000,
    ) -> str:
        """Le o texto de uma celula especifica (table_index, row, col)."""
        return await self.emergency.read_table_cell(table_index, row, col, timeout_ms=timeout_ms)

    async def emergency_read_table_row(self, table_index: int, row: int, timeout_ms: int = 7000) -> list[str]:
        """Le todas as celulas de uma linha de tabela."""
        return await self.emergency.read_table_row(table_index, row, timeout_ms=timeout_ms)

    async def emergency_read_full_table(self, table_index: int = 0, timeout_ms: int = 7000) -> list[list[str]]:
        """Le tabela inteira como lista de listas (linhas x colunas)."""
        return await self.emergency.read_full_table(table_index, timeout_ms=timeout_ms)

    async def emergency_click_table_cell(
        self, table_index: int, row: int, col: int, timeout_ms: int = 7000,
    ) -> None:
        """Clica numa celula especifica de uma tabela."""
        return await self.emergency.click_table_cell(table_index, row, col, timeout_ms=timeout_ms)

    # ── Lists ─────────────────────────────────────────────────────────────

    async def emergency_read_list_items(
        self, list_index: int = 0, list_type: str = "ul", timeout_ms: int = 7000,
    ) -> list[str]:
        """Le todos os itens de uma lista ``<ul>`` ou ``<ol>``."""
        return await self.emergency.read_list_items(list_index, list_type, timeout_ms=timeout_ms)

    async def emergency_click_list_item(
        self, list_index: int, item_index: int, list_type: str = "ul", timeout_ms: int = 7000,
    ) -> None:
        """Clica num item especifico de uma lista."""
        return await self.emergency.click_list_item(list_index, item_index, list_type, timeout_ms=timeout_ms)

    # ── Media ─────────────────────────────────────────────────────────────

    async def emergency_control_media(
        self, element_type: str, index: int, action: str, timeout_ms: int = 7000,
    ) -> None:
        """Controla media (video/audio). action: ``"play"``, ``"pause"``, ``"mute"``."""
        return await self.emergency.control_media(element_type, index, action, timeout_ms=timeout_ms)

    async def emergency_get_media_state(
        self, element_type: str, index: int, timeout_ms: int = 7000,
    ) -> dict[str, Any]:
        """Retorna estado do media (paused, currentTime, duration, muted, volume)."""
        return await self.emergency.get_media_state(element_type, index, timeout_ms=timeout_ms)

    async def emergency_get_media_src(self, element_type: str, index: int, timeout_ms: int = 7000) -> str:
        """Retorna o src do elemento media."""
        return await self.emergency.get_media_src(element_type, index, timeout_ms=timeout_ms)

    # ── Image ─────────────────────────────────────────────────────────────

    async def emergency_get_image_info(self, index: int, timeout_ms: int = 7000) -> dict[str, Any]:
        """Info da N-esima imagem (src, alt, width, height, naturalWidth, naturalHeight)."""
        return await self.emergency.get_image_info(index, timeout_ms=timeout_ms)

    async def emergency_capture_all_images(self, timeout_ms: int = 7000) -> list[dict[str, Any]]:
        """Captura info de todas as imagens da pagina."""
        return await self.emergency.capture_all_images(timeout_ms=timeout_ms)

    # ── Iframe ────────────────────────────────────────────────────────────

    async def emergency_switch_to_iframe(
        self, index_or_selector: int | str = 0, timeout_ms: int = 7000,
    ) -> Any:
        """Entra num iframe (por indice ou selector). Acoes seguintes operam dentro dele."""
        return await self.emergency.switch_to_iframe(index_or_selector, timeout_ms=timeout_ms)

    async def emergency_switch_to_main_frame(self) -> Any:
        """Volta ao frame principal (sai do iframe)."""
        return await self.emergency.switch_to_main_frame()

    # ── Dialog ────────────────────────────────────────────────────────────

    async def emergency_handle_dialog(
        self, action: str = "accept", prompt_text: str | None = None, timeout_ms: int = 10000,
    ) -> str:
        """Lida com alert/confirm/prompt. action: ``"accept"`` ou ``"dismiss"``."""
        return await self.emergency.handle_dialog(action, prompt_text, timeout_ms=timeout_ms)

    # ── Drag & Drop ───────────────────────────────────────────────────────

    async def emergency_drag_and_drop(
        self, source_selector: str, target_selector: str, timeout_ms: int = 7000,
    ) -> None:
        """Drag & drop entre dois elementos (CSS selectors)."""
        return await self.emergency.drag_and_drop(source_selector, target_selector, timeout_ms=timeout_ms)

    # ── Scroll ────────────────────────────────────────────────────────────

    async def emergency_scroll_page(self, direction: str = "down", pixels: int = 500) -> None:
        """Scroll da pagina. direction: ``"up"`` ou ``"down"``."""
        return await self.emergency.scroll_page(direction, pixels)

    async def emergency_scroll_to_top(self) -> None:
        """Scroll ate o topo da pagina."""
        return await self.emergency.scroll_to_top()

    async def emergency_scroll_to_bottom(self) -> None:
        """Scroll ate o fim da pagina."""
        return await self.emergency.scroll_to_bottom()

    # ── Page info ─────────────────────────────────────────────────────────

    async def emergency_get_page_title(self) -> str:
        """Retorna o ``<title>`` da pagina."""
        return await self.emergency.get_page_title()

    async def emergency_get_page_url(self) -> str:
        """Retorna a URL atual da pagina."""
        return await self.emergency.get_page_url()

    async def emergency_get_computed_style(
        self, element_type: str, index: int, css_property: str, timeout_ms: int = 7000,
    ) -> str:
        """Le uma propriedade CSS computada do N-esimo elemento."""
        return await self.emergency.get_computed_style(element_type, index, css_property, timeout_ms=timeout_ms)

    # ── Bulk capture / recording ──────────────────────────────────────────

    async def emergency_capture_all_inputs(self, timeout_ms: int = 7000) -> list[dict[str, Any]]:
        """Captura metadata de todos os inputs da pagina."""
        return await self.emergency.capture_all_inputs(timeout_ms=timeout_ms)

    async def emergency_capture_all_buttons(self, timeout_ms: int = 7000) -> list[dict[str, Any]]:
        """Captura metadata de todos os botoes da pagina."""
        return await self.emergency.capture_all_buttons(timeout_ms=timeout_ms)

    async def emergency_capture_all_selects(self, timeout_ms: int = 7000) -> list[dict[str, Any]]:
        """Captura metadata de todos os ``<select>`` da pagina."""
        return await self.emergency.capture_all_selects(timeout_ms=timeout_ms)

    async def emergency_capture_all_headings(self, timeout_ms: int = 7000) -> list[dict[str, Any]]:
        """Captura todos os headings (h1-h6) da pagina."""
        return await self.emergency.capture_all_headings(timeout_ms=timeout_ms)

    async def emergency_capture_page_elements(self, timeout_ms: int = 7000) -> dict[str, Any]:
        """Captura completa da pagina: inputs, buttons, selects, links, headings, tables."""
        return await self.emergency.capture_page_elements(timeout_ms=timeout_ms)

    # ── JavaScript execution ─────────────────────────────────────────────

    async def eval_js(self, code: str, arg: Any = None) -> Any:
        """Executa JavaScript na pagina. ``arg`` fica disponivel como argumento."""
        return await self.emergency.eval_js(code, arg)

    # ── Element state checks ──────────────────────────────────────────────

    async def element_exists(self, selector: str) -> bool:
        """Verifica se existe pelo menos um elemento com o selector."""
        return await self.emergency.element_exists(selector)

    async def element_count(self, selector: str) -> int:
        """Conta quantos elementos correspondem ao selector."""
        return await self.emergency.element_count(selector)

    async def is_visible(self, element_type: str, index: int) -> bool:
        """Verifica se o N-esimo elemento esta visivel."""
        return await self.emergency.is_visible(element_type, index)

    async def is_enabled(self, element_type: str, index: int) -> bool:
        """Verifica se o N-esimo elemento esta habilitado (nao disabled)."""
        return await self.emergency.is_enabled(element_type, index)

    async def is_checked(self, element_type: str, index: int) -> bool:
        """Verifica se o N-esimo checkbox/radio esta marcado."""
        return await self.emergency.is_checked(element_type, index)

    async def has_class(self, element_type: str, index: int, class_name: str) -> bool:
        """Verifica se o N-esimo elemento tem a classe CSS indicada."""
        return await self.emergency.has_class(element_type, index, class_name)

    async def get_classes(self, element_type: str, index: int) -> list[str]:
        """Retorna lista de classes CSS do N-esimo elemento."""
        return await self.emergency.get_classes(element_type, index)

    async def get_bounding_box(self, element_type: str, index: int) -> dict[str, float] | None:
        """Retorna bounding box {x, y, width, height} do N-esimo elemento."""
        return await self.emergency.get_bounding_box(element_type, index)

    # ── Advanced click actions ─────────────────────────────────────────────

    async def double_click(self, element_type: str, index: int, timeout_ms: int = 7000) -> None:
        """Duplo-clique no N-esimo elemento."""
        return await self.emergency.double_click(element_type, index, timeout_ms=timeout_ms)

    async def right_click(self, element_type: str, index: int, timeout_ms: int = 7000) -> None:
        """Clique com botao direito no N-esimo elemento."""
        return await self.emergency.right_click(element_type, index, timeout_ms=timeout_ms)

    async def focus(self, element_type: str, index: int, timeout_ms: int = 7000) -> None:
        """Da foco ao N-esimo elemento."""
        return await self.emergency.focus(element_type, index, timeout_ms=timeout_ms)

    async def click_at_coordinates(self, x: float, y: float) -> None:
        """Clica em coordenadas absolutas (x, y) na pagina."""
        return await self.emergency.click_at_coordinates(x, y)

    async def mouse_move(self, x: float, y: float) -> None:
        """Move o mouse para as coordenadas (x, y)."""
        return await self.emergency.mouse_move(x, y)

    async def mouse_wheel(self, delta_x: float = 0, delta_y: float = -300) -> None:
        """Roda do mouse. delta_y negativo = scroll up."""
        return await self.emergency.mouse_wheel(delta_x, delta_y)

    # ── Page-level operations ──────────────────────────────────────────────

    async def page_screenshot(self, path: str = "screenshot.png", full_page: bool = False) -> str:
        """Tira screenshot da pagina. full_page=True captura a pagina inteira."""
        return await self.emergency.page_screenshot(path, full_page)

    async def page_text(self) -> str:
        """Retorna todo o texto visivel da pagina."""
        return await self.emergency.page_text()

    async def page_html(self) -> str:
        """Retorna o HTML completo da pagina."""
        return await self.emergency.page_html()

    async def page_pdf(self, path: str = "page.pdf") -> str:
        """Exporta a pagina como PDF (so headless Chromium)."""
        return await self.emergency.page_pdf(path)

    async def set_viewport(self, width: int, height: int) -> None:
        """Altera o tamanho do viewport."""
        return await self.emergency.set_viewport(width, height)

    async def go_back(self) -> None:
        """Navega para a pagina anterior (browser back)."""
        return await self.emergency.go_back()

    async def go_forward(self) -> None:
        """Navega para a pagina seguinte (browser forward)."""
        return await self.emergency.go_forward()

    async def reload(self) -> None:
        """Recarrega a pagina atual."""
        return await self.emergency.reload()

    # ── Cookie management ──────────────────────────────────────────────────

    async def get_cookies(self) -> list[dict[str, Any]]:
        """Retorna todos os cookies do contexto atual."""
        return await self.emergency.get_cookies()

    async def set_cookie(self, name: str, value: str, **kwargs: Any) -> None:
        """Define um cookie. kwargs: domain, path, expires, httpOnly, secure, sameSite."""
        return await self.emergency.set_cookie(name, value, **kwargs)

    async def clear_cookies(self) -> None:
        """Remove todos os cookies do contexto."""
        return await self.emergency.clear_cookies()

    # ── LocalStorage & SessionStorage ──────────────────────────────────────

    async def get_local_storage(self, key: str) -> str | None:
        """Le um valor do localStorage."""
        return await self.emergency.get_local_storage(key)

    async def set_local_storage(self, key: str, value: str) -> None:
        """Define um valor no localStorage."""
        return await self.emergency.set_local_storage(key, value)

    async def remove_local_storage(self, key: str) -> None:
        """Remove uma chave do localStorage."""
        return await self.emergency.remove_local_storage(key)

    async def clear_local_storage(self) -> None:
        """Limpa todo o localStorage."""
        return await self.emergency.clear_local_storage()

    async def get_all_local_storage(self) -> dict[str, str]:
        """Retorna todo o localStorage como dict."""
        return await self.emergency.get_all_local_storage()

    async def get_session_storage(self, key: str) -> str | None:
        """Le um valor do sessionStorage."""
        return await self.emergency.get_session_storage(key)

    async def set_session_storage(self, key: str, value: str) -> None:
        """Define um valor no sessionStorage."""
        return await self.emergency.set_session_storage(key, value)

    async def clear_session_storage(self) -> None:
        """Limpa todo o sessionStorage."""
        return await self.emergency.clear_session_storage()

    # ── Network / Response waiting ─────────────────────────────────────────

    async def wait_for_response(self, url_pattern: str, timeout_ms: int = 30000) -> dict[str, Any]:
        """Espera por uma resposta HTTP cujo URL contenha o pattern."""
        return await self.emergency.wait_for_response(url_pattern, timeout_ms=timeout_ms)

    async def wait_for_load(self, state: str = "load", timeout_ms: int = 30000) -> None:
        """Espera estado de load. state: ``"load"``, ``"domcontentloaded"``, ``"networkidle"``."""
        return await self.emergency.wait_for_load(state, timeout_ms=timeout_ms)

    # ── File system operations ──────────────────────────────────────────────

    @staticmethod
    async def read_file(path: str, encoding: str = "utf-8") -> dict[str, Any]:
        """Le ficheiro do disco. Retorna {content, path, size, encoding}."""
        return await EmergencyResolver.read_file(path, encoding=encoding)

    @staticmethod
    async def write_file(path: str, content: str, append: bool = False) -> dict[str, Any]:
        """Escreve ficheiro. append=True adiciona ao final."""
        return await EmergencyResolver.write_file(path, content, append=append)

    @staticmethod
    async def list_files(directory: str = ".", pattern: str = "*", recursive: bool = False) -> list[dict[str, Any]]:
        """Lista ficheiros com glob pattern. recursive=True busca subdiretorios."""
        return await EmergencyResolver.list_files(directory, pattern, recursive=recursive)

    @staticmethod
    async def file_exists(path: str) -> bool:
        """Verifica se o ficheiro existe."""
        return await EmergencyResolver.file_exists(path)

    @staticmethod
    async def delete_file(path: str) -> dict[str, Any]:
        """Apaga um ficheiro."""
        return await EmergencyResolver.delete_file(path)

    @staticmethod
    async def file_info(path: str) -> dict[str, Any]:
        """Info do ficheiro (size, modified, created, is_dir)."""
        return await EmergencyResolver.file_info(path)

    @staticmethod
    async def copy_file(src: str, dst: str) -> dict[str, Any]:
        """Copia ficheiro de src para dst."""
        return await EmergencyResolver.copy_file(src, dst)

    @staticmethod
    async def move_file(src: str, dst: str) -> dict[str, Any]:
        """Move/renomeia ficheiro de src para dst."""
        return await EmergencyResolver.move_file(src, dst)

    # ── Recording utilities (GIF, HAR) ──────────────────────────────────────

    @staticmethod
    async def generate_gif(
        screenshot_dir: str = "debug_screenshots",
        output_path: str = "recording.gif",
        duration_ms: int = 800,
        loop: int = 0,
    ) -> dict[str, Any]:
        """Generate animated GIF from debug screenshots."""
        return await EmergencyResolver.generate_gif(
            screenshot_dir, output_path, duration_ms, loop,
        )

    @staticmethod
    async def read_har(path: str) -> dict[str, Any]:
        """Read and parse a HAR file."""
        return await EmergencyResolver.read_har(path)

    @staticmethod
    async def extract_har_apis(path: str, filter_pattern: str = "/api/") -> list[dict[str, Any]]:
        """Extract API calls from a HAR file."""
        return await EmergencyResolver.extract_har_apis(path, filter_pattern)

    # ── JSON save / load / replay ─────────────────────────────────────────

    @staticmethod
    def emergency_save_actions(actions: list[dict[str, Any]], path: str) -> str:
        """Salva lista de acoes em ficheiro JSON."""
        return EmergencyResolver.save_actions_to_json(actions, path)

    @staticmethod
    def emergency_load_actions(path: str) -> list[dict[str, Any]]:
        """Carrega acoes de um ficheiro JSON."""
        return EmergencyResolver.load_actions_from_json(path)

    async def emergency_replay_actions(
        self,
        actions: list[dict[str, Any]],
        delay_ms: int = 500,
        on_step: Callable[[int, dict, dict], Any] | None = None,
        debug: bool = True,
        screenshot_dir: str = "debug_replay",
        mode: str = "padrao",
    ) -> list[dict[str, Any]]:
        """Replay de acoes gravadas. Modos: padrao, rapido, forcado, mix, adaptativo."""
        return await self.emergency.replay_actions(
            actions, delay_ms=delay_ms, on_step=on_step,
            debug=debug, screenshot_dir=screenshot_dir, mode=mode,
        )

    async def emergency_replay_json(
        self,
        path: str,
        delay_ms: int = 500,
        on_step: Callable[[int, dict, dict], Any] | None = None,
        debug: bool = True,
        screenshot_dir: str = "debug_replay",
        mode: str = "padrao",
    ) -> list[dict[str, Any]]:
        """Carrega JSON e faz replay. Atalho para load + replay_actions."""
        return await self.emergency.replay_actions_from_json(
            path, delay_ms=delay_ms, on_step=on_step,
            debug=debug, screenshot_dir=screenshot_dir, mode=mode,
        )

    # ── Manual JSON execution (tolerant) ─────────────────────────────────

    async def run_json(
        self,
        actions: list[dict[str, Any]],
        delay_ms: int = 400,
        on_step: Callable[[int, dict, dict], Any] | None = None,
        debug: bool = True,
        screenshot_dir: str = "debug_run",
        mode: str = "padrao",
        continue_on_error: bool = True,
        base_url: str = "",
    ) -> list[dict[str, Any]]:
        """Execute hand-written JSON actions with tolerance for missing fields.

        Accepts minimal JSON — only 'action' + essential fields are needed.
        Supports aliases (e.g. 'press' -> 'press_keys', 'type' -> 'fill').
        Continues on error by default.
        """
        return await self.emergency.run_json(
            actions, delay_ms=delay_ms, on_step=on_step,
            debug=debug, screenshot_dir=screenshot_dir, mode=mode,
            continue_on_error=continue_on_error, base_url=base_url,
        )

    async def run_json_file(
        self,
        path: str,
        delay_ms: int = 400,
        on_step: Callable[[int, dict, dict], Any] | None = None,
        debug: bool = True,
        screenshot_dir: str = "debug_run",
        mode: str = "padrao",
        continue_on_error: bool = True,
        base_url: str = "",
    ) -> list[dict[str, Any]]:
        """Load a hand-written JSON file and execute with tolerance."""
        return await self.emergency.run_json_file(
            path, delay_ms=delay_ms, on_step=on_step,
            debug=debug, screenshot_dir=screenshot_dir, mode=mode,
            continue_on_error=continue_on_error, base_url=base_url,
        )

    # ── Live action recorder ──────────────────────────────────────────────

    @staticmethod
    async def emergency_capture_acao(
        save_path: str = "recording.json",
        url: str | None = None,
        headless: bool = False,
        browser_args: list[str] | None = None,
        auto_wait: bool = True,
    ) -> list[dict[str, Any]]:
        """Open a browser, record all user actions, save to JSON.

        If auto_wait=True (default), blocks until the user closes the browser.
        Returns the recorded actions list.
        """
        from smartwright.recorder import ActionRecorder

        recorder = ActionRecorder(
            headless=headless,
            save_path=save_path,
            browser_args=browser_args,
        )
        await recorder.start(url=url)
        if auto_wait:
            return await recorder.wait_until_closed()
        return recorder.actions

    # ── Download & Clipboard ─────────────────────────────────────────────

    async def emergency_wait_download(
        self,
        save_dir: str = "downloads",
        timeout_ms: int = 30000,
        trigger_action: Callable[[], Awaitable[Any]] | None = None,
    ) -> dict[str, Any]:
        """Wait for a download and save the file.

        Args:
            save_dir: directory to save the downloaded file.
            timeout_ms: max wait in ms.
            trigger_action: optional awaitable that triggers the download
                            (e.g., a click coroutine).

        Returns:
            dict: filename, path, url, size, suggested_filename.
        """
        return await self.emergency.wait_download(
            save_dir=save_dir,
            timeout_ms=timeout_ms,
            trigger_action=trigger_action,
        )

    async def emergency_wait_clipboard(
        self,
        timeout_ms: int = 10000,
        poll_interval_ms: int = 300,
    ) -> dict[str, Any]:
        """Read the current clipboard content.

        Returns:
            dict: text, html, timestamp.
        """
        return await self.emergency.wait_clipboard(
            timeout_ms=timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )

    async def emergency_copy_to_clipboard(self, text: str) -> bool:
        """Write text to the page clipboard."""
        return await self.emergency.copy_to_clipboard(text)

    # ── Response extraction ───────────────────────────────────────────────

    async def wait_response_text(
        self,
        timeout_ms: int = 90000,
        stable_rounds: int = 3,
        poll_interval_ms: int = 900,
    ) -> str:
        """Espera resposta de streaming (chatbot) estabilizar e retorna o texto final."""
        return await self.emergency.wait_response_text(
            timeout_ms=timeout_ms,
            stable_rounds=stable_rounds,
            poll_interval_ms=poll_interval_ms,
        )

    async def wait_and_click_copy_button(
        self,
        timeout_ms: int = 20000,
        poll_interval_ms: int = 350,
    ) -> bool:
        """Espera e clica no botao de copiar (comum em chatbots). Retorna True se clicou."""
        return await self.emergency.wait_and_click_copy_button(
            timeout_ms=timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )

    # ── DOM Serializer ────────────────────────────────────────────────

    async def dom_snapshot(self, config: DOMSerializerConfig | None = None) -> DOMSnapshot:
        """Serialize page DOM into a DOMSnapshot with text + element metadata.

        Returns a DOMSnapshot with:
          .text     — compact string for LLM consumption
          .elements — list of ElementMeta with selectors/bbox for interaction
          .stats    — element counts by type
          .url      — page URL
          .title    — page title

        Use snapshot.to_capture(N) to get a dict for emergency_click_captured().
        """
        return await self.emergency.serialize_dom(config)

    async def dom_snapshot_text(self, config: DOMSerializerConfig | None = None) -> str:
        """Convenience: return only the serialized text (no metadata)."""
        return await self.emergency.serialize_dom_text(config)

    # ── Network Learning ──────────────────────────────────────────────

    @property
    def network_discoveries(self) -> list[dict]:
        """Lista de APIs descobertas via network learning nesta sessao."""
        return self.engine.network.discoveries

    def network_summary(self) -> dict:
        """Resumo das APIs descobertas (total, por metodo, por dominio)."""
        return self.engine.network.summary()

    def get_api_knowledge(self, intent: str) -> Any:
        """Busca API knowledge salva por intent."""
        return self.engine.store.get_api(intent)

    def network_discovery(self, intent: str) -> dict | None:
        """Busca discovery especifico por intent."""
        return self.engine.network.get_discovery(intent)

    # ── Adaptive Replay ──────────────────────────────────────────────

    async def replay_adaptive(
        self,
        actions: list[dict] | str,
        delay_ms: int = 500,
        on_step: Callable[[int, dict, dict], Any] | None = None,
        debug: bool = True,
        screenshot_dir: str = "debug_adaptive",
    ) -> list[dict]:
        """Replay autonomo sem LLM — usa fingerprint semantico.

        Resolve elementos por texto, tag, tipo, placeholder, aria-label,
        name, role e posicao visual. Ignora IDs e classes que mudam.

        actions: lista de action dicts ou path para JSON gravado.
        """
        if isinstance(actions, str):
            actions = self.emergency.load_actions_from_json(actions)
        return await self.emergency.replay_actions(
            actions,
            delay_ms=delay_ms,
            on_step=on_step,
            debug=debug,
            screenshot_dir=screenshot_dir,
            mode="adaptativo",
        )

    async def replay_adaptive_analyze(
        self,
        actions: list[dict] | str,
    ) -> list[dict]:
        """Pre-analisa matching adaptativo sem executar.

        Retorna diagnostico: para cada acao, o melhor match e score.
        Util para validar um recording antes de executar.
        """
        if isinstance(actions, str):
            actions = self.emergency.load_actions_from_json(actions)
        from smartwright.resolver.adaptive_replay import adaptive_resolve_all
        return await adaptive_resolve_all(self.page, actions)

    # ── Multi-tab / Multi-page ────────────────────────────────────────────

    @property
    def tab_count(self) -> int:
        """Numero de tabs abertas no contexto atual."""
        return self.emergency.tab_count

    async def new_tab(self, url: str | None = None) -> object:
        """Abre nova tab no contexto. Retorna o novo Page."""
        return await self.emergency.new_tab(url)

    async def list_tabs(self) -> list[dict]:
        """Lista todas as tabs: [{index, url, title}, ...]."""
        return await self.emergency.list_tabs()

    async def switch_tab(self, index: int) -> None:
        """Muda para a tab no indice indicado. Atualiza page refs."""
        await self.emergency.switch_tab(index)
        self.page = self.emergency.page
        self.engine.page = self.emergency.page

    async def close_tab(self, index: int | None = None) -> None:
        """Fecha tab pelo indice (default=atual). Atualiza page refs."""
        await self.emergency.close_tab(index)
        self.page = self.emergency.page
        self.engine.page = self.emergency.page

    async def wait_for_popup(self, trigger: Any) -> object:
        """Espera popup disparado por trigger. Retorna novo Page."""
        return await self.emergency.wait_for_popup(trigger)

    # ── Session persistence ────────────────────────────────────────────────

    async def save_session(self, path: str) -> str:
        """Exporta cookies + localStorage + sessionStorage para JSON."""
        return await self.emergency.save_session(path)

    async def load_session(self, path: str) -> dict:
        """Importa sessao de JSON, restaura cookies + storage."""
        return await self.emergency.load_session(path)

    async def clear_session(self) -> None:
        """Limpa cookies + localStorage + sessionStorage."""
        await self.emergency.clear_session()

    # ── Page Diff ──────────────────────────────────────────────────────────

    async def dom_diff_start(self, config: DOMSerializerConfig | None = None) -> tuple[DOMSnapshot, Callable[[], Awaitable[_PageDiff]]]:
        """Captura snapshot 'antes' e retorna (snapshot, finish_fn).

        Uso::

            snap, finish = await sw.dom_diff_start()
            await sw.click("button", 0)
            diff = await finish()
            print(diff.summary())
        """
        from smartwright.resolver.dom_diff import page_diff
        return await page_diff(self.page, config)

    async def dom_diff_snapshots(self, before: DOMSnapshot, after: DOMSnapshot) -> _PageDiff:
        """Compara dois DOMSnapshots e retorna PageDiff."""
        return diff_snapshots(before, after)

    # ── Captcha ────────────────────────────────────────────────────────────

    async def detect_captcha(self) -> CaptchaType | None:
        """Detecta tipo de captcha na pagina."""
        return await detect_captcha(self.page)

    async def solve_captcha(
        self,
        solver: CaptchaSolver,
        captcha_type: CaptchaType | None = None,
    ) -> Any:
        """Detecta, resolve e injeta token de captcha.

        Args:
            solver: Instancia de CaptchaSolver (ex: TwoCaptchaSolver).
            captcha_type: Tipo de captcha (auto-detecta se None).

        Returns:
            CaptchaResult com o token resolvido.
        """
        from smartwright.captcha.solver import extract_site_key, inject_captcha_token

        ct = captcha_type or await detect_captcha(self.page)
        if ct is None:
            raise CaptchaNotDetectedError("No captcha detected on page")

        site_key = await extract_site_key(self.page, ct)
        if site_key is None:
            raise CaptchaSolverError(f"Could not extract site key for {ct.value}")

        url = getattr(self.page, "url", "") or ""

        if ct == CaptchaType.RECAPTCHA_V2:
            result = await solver.solve_recaptcha_v2(site_key, url)
        elif ct == CaptchaType.RECAPTCHA_V3:
            result = await solver.solve_recaptcha_v3(site_key, url)
        elif ct == CaptchaType.HCAPTCHA:
            result = await solver.solve_hcaptcha(site_key, url)
        else:
            raise CaptchaSolverError(f"Unsupported captcha type: {ct.value}")

        if result.solved and result.token:
            await inject_captcha_token(self.page, result.token, ct)

        return result
