from __future__ import annotations

import re
from typing import Any


class AIRecovery:
    def __init__(self, advisor: Any | None = None) -> None:
        self.advisor = advisor

    async def recover(self, page: object, intent: str, hints: list[str]) -> dict[str, str] | None:
        html = await page.content()
        snippets = self._extract_relevant_snippets(html, hints)
        if not snippets:
            return None

        if self.advisor is not None:
            try:
                suggestion = await self.advisor.suggest(intent=intent, hints=hints, snippets=snippets)
                if suggestion:
                    return suggestion
            except Exception:
                # Provider failure must not block local fallback.
                pass

        for snippet in snippets:
            if "button" in snippet.lower() and any(h.lower() in snippet.lower() for h in hints):
                return {"strategy": "get_by_text", "hint": hints[0]}
        return None

    def _extract_relevant_snippets(self, html: str, hints: list[str]) -> list[str]:
        chunks = re.split(r"(?=<)", html)
        hints_low = [h.lower() for h in hints]
        relevant: list[str] = []
        for chunk in chunks:
            low = chunk.lower()
            if any(h in low for h in hints_low):
                relevant.append(chunk[:350])
            if len(relevant) >= 12:
                break
        return relevant
