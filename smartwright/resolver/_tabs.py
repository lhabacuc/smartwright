"""TabsMixin — multi-tab / multi-page management."""
from __future__ import annotations

from typing import Any

from smartwright.exceptions import TabError


class TabsMixin:
    """Mixin para gestao de multiplas tabs (pages) no mesmo browser context."""

    @property
    def tab_count(self) -> int:
        """Numero de tabs abertas no contexto atual."""
        return len(self.page.context.pages)

    async def new_tab(self, url: str | None = None) -> object:
        """Abre nova tab no contexto atual.

        Args:
            url: URL opcional para navegar apos abrir.

        Returns:
            O novo Page object.
        """
        page = await self.page.context.new_page()
        if url:
            await page.goto(url)
        return page

    async def list_tabs(self) -> list[dict[str, Any]]:
        """Lista todas as tabs abertas com index, url e title.

        Returns:
            Lista de dicts ``[{index, url, title}, ...]``.
        """
        pages = self.page.context.pages
        tabs: list[dict[str, Any]] = []
        for i, p in enumerate(pages):
            title = ""
            try:
                title = await p.title()
            except Exception:
                pass
            tabs.append({
                "index": i,
                "url": p.url,
                "title": title,
            })
        return tabs

    async def switch_tab(self, index: int) -> None:
        """Muda para a tab no indice indicado.

        Args:
            index: Indice da tab (0-based).

        Raises:
            TabError: Se o indice for invalido.
        """
        pages = self.page.context.pages
        if index < 0 or index >= len(pages):
            raise TabError(
                f"Tab index {index} out of range (0-{len(pages) - 1})",
                index=index,
            )
        self.page = pages[index]

    async def close_tab(self, index: int | None = None) -> None:
        """Fecha uma tab pelo indice. Default = tab atual.

        Apos fechar, faz switch para a ultima tab que sobra.

        Args:
            index: Indice da tab a fechar (None = atual).

        Raises:
            TabError: Se o indice for invalido ou se for a unica tab.
        """
        pages = self.page.context.pages
        if len(pages) <= 1:
            raise TabError("Cannot close the only remaining tab")

        if index is None:
            target = self.page
        else:
            if index < 0 or index >= len(pages):
                raise TabError(
                    f"Tab index {index} out of range (0-{len(pages) - 1})",
                    index=index,
                )
            target = pages[index]

        await target.close()

        # Switch to last remaining page
        remaining = self.page.context.pages
        if remaining:
            self.page = remaining[-1]

    async def wait_for_popup(self, trigger: Any) -> object:
        """Espera por um popup (nova page) disparado por uma acao.

        Args:
            trigger: Coroutine que dispara a abertura do popup.
                     Ex: ``lambda: page.click("#open-popup")``

        Returns:
            O novo Page object (popup).
        """
        async with self.page.context.expect_page() as page_info:
            await trigger()
        new_page = await page_info.value
        return new_page
