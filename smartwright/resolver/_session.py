"""SessionMixin — persistencia de sessao (cookies + localStorage + sessionStorage)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from smartwright._logging import logger
from smartwright.exceptions import SessionError


class SessionMixin:
    """Mixin para save/load de sessao completa (cookies + storage)."""

    async def get_all_session_storage(self) -> dict[str, str]:
        """Retorna todos os pares chave-valor do sessionStorage."""
        return await self.page.evaluate(
            """() => {
                const o = {};
                for (let i = 0; i < sessionStorage.length; i++) {
                    const k = sessionStorage.key(i);
                    o[k] = sessionStorage.getItem(k);
                }
                return o;
            }"""
        )

    async def save_session(self, path: str | Path) -> str:
        """Exporta cookies + localStorage + sessionStorage para JSON.

        Args:
            path: Caminho do ficheiro de destino.

        Returns:
            Caminho absoluto do ficheiro salvo.

        Raises:
            SessionError: Se falhar ao exportar sessao.
        """
        try:
            context = self.page.context
            cookies = await context.cookies()

            local_storage = await self.page.evaluate(
                """() => {
                    const o = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        const k = localStorage.key(i);
                        o[k] = localStorage.getItem(k);
                    }
                    return o;
                }"""
            )

            session_storage = await self.get_all_session_storage()

            url = getattr(self.page, "url", "") or ""

            data = {
                "version": 1,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "url": url,
                "cookies": cookies,
                "local_storage": local_storage,
                "session_storage": session_storage,
            }

            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("Session saved to %s", p.resolve())
            return str(p.resolve())

        except SessionError:
            raise
        except Exception as exc:
            raise SessionError(f"Failed to save session: {exc}") from exc

    async def load_session(self, path: str | Path) -> dict[str, Any]:
        """Importa sessao de JSON, restaura cookies + localStorage + sessionStorage.

        Args:
            path: Caminho do ficheiro de sessao.

        Returns:
            Dict com os dados carregados.

        Raises:
            SessionError: Se falhar ao importar sessao.
        """
        try:
            p = Path(path)
            if not p.exists():
                raise SessionError(f"Session file not found: {path}")

            data = json.loads(p.read_text(encoding="utf-8"))
            context = self.page.context

            # Restaurar cookies
            cookies = data.get("cookies", [])
            if cookies:
                await context.add_cookies(cookies)

            # Restaurar localStorage
            local_storage = data.get("local_storage", {})
            if local_storage:
                await self.page.evaluate(
                    """(items) => {
                        for (const [k, v] of Object.entries(items)) {
                            localStorage.setItem(k, v);
                        }
                    }""",
                    local_storage,
                )

            # Restaurar sessionStorage
            session_storage = data.get("session_storage", {})
            if session_storage:
                await self.page.evaluate(
                    """(items) => {
                        for (const [k, v] of Object.entries(items)) {
                            sessionStorage.setItem(k, v);
                        }
                    }""",
                    session_storage,
                )

            logger.info("Session loaded from %s", path)
            return data

        except SessionError:
            raise
        except Exception as exc:
            raise SessionError(f"Failed to load session: {exc}") from exc

    async def clear_session(self) -> None:
        """Limpa cookies + localStorage + sessionStorage.

        Raises:
            SessionError: Se falhar ao limpar sessao.
        """
        try:
            context = self.page.context
            await context.clear_cookies()
            await self.page.evaluate("() => localStorage.clear()")
            await self.page.evaluate("() => sessionStorage.clear()")
            logger.debug("Session cleared")
        except Exception as exc:
            raise SessionError(f"Failed to clear session: {exc}") from exc
