from __future__ import annotations

from typing import Iterable

from smartwright.core.store import KnowledgeStore


class IntentManager:
    def __init__(self, intents: dict[str, list[str]], store: KnowledgeStore) -> None:
        self.intents = intents
        self.store = store
        self.store.record_aliases(intents)

    def hints_for(self, intent: str) -> list[str]:
        hints = self.intents.get(intent, [])
        if hints:
            return hints
        return self.store.aliases(intent)

    def all_hints(self, intent: str) -> list[str]:
        hints = self.hints_for(intent)
        normalized = [intent.replace("_", " "), *hints]
        deduped: list[str] = []
        for item in normalized:
            if item and item not in deduped:
                deduped.append(item)
        return deduped

    def suggest(self, raw_text: str) -> str | None:
        lowered = raw_text.lower()
        best_intent = None
        best_score = 0
        for intent, aliases in self.intents.items():
            variants: Iterable[str] = [intent, *aliases]
            score = sum(1 for variant in variants if variant.lower() in lowered)
            if score > best_score:
                best_score = score
                best_intent = intent
        return best_intent
