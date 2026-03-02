from __future__ import annotations

from typing import Any


class SemanticFinder:
    def __init__(self, semantic_map: dict[str, dict[str, list[str]]] | None = None) -> None:
        self.semantic_map = semantic_map or {
            "chat_list_msg": {
                "roles": ["listitem", "row", "article"],
                "patterns": ["message", "chat", "conversation"],
            }
        }

    async def find(self, page: object, intent: str, hints: list[str]) -> Any | None:
        profile = self.semantic_map.get(intent, {})
        roles = profile.get("roles", [])
        patterns = [p.lower() for p in profile.get("patterns", [])]
        hints_low = [h.lower() for h in hints]

        for role in roles:
            locator = page.get_by_role(role)
            count = await locator.count()
            for idx in range(count):
                candidate = locator.nth(idx)
                text = (await candidate.inner_text()).lower()
                if any(pattern in text for pattern in patterns) or any(h in text for h in hints_low):
                    return candidate

        for hint in hints:
            by_text = page.get_by_text(hint)
            if await by_text.count() > 0:
                return by_text.first

        return None
