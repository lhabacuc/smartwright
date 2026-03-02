from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from smartwright.core.models import StrategyResult
from smartwright.core.store import KnowledgeStore
from smartwright.semantic_finder.finder import SemanticFinder

ResolverCallable = Callable[[object, str, list[str]], Awaitable[Any | None]]


class AdaptiveResolver:
    def __init__(self, store: KnowledgeStore, semantic_finder: SemanticFinder) -> None:
        self.store = store
        self.semantic_finder = semantic_finder

    async def resolve(self, page: object, intent: str, hints: list[str]) -> Any:
        strategies: list[tuple[str, ResolverCallable]] = [
            ("get_by_role", self._by_role),
            ("get_by_label", self._by_label),
            ("get_by_text", self._by_text),
            ("structural_heuristic", self._heuristic),
            ("semantic", self._semantic),
        ]

        scores = self.store.strategy_scores(intent)
        strategies = sorted(strategies, key=lambda item: scores.get(item[0], 0), reverse=True)

        last_error: Exception | None = None
        for strategy_name, strategy in strategies:
            start = time.perf_counter()
            try:
                locator = await strategy(page, intent, hints)
                elapsed = (time.perf_counter() - start) * 1000
                success = locator is not None
                self.store.append_result(
                    StrategyResult(
                        intent=intent,
                        strategy=strategy_name,
                        success=success,
                        elapsed_ms=elapsed,
                    )
                )
                if locator is not None:
                    return locator
            except Exception as exc:
                last_error = exc
                elapsed = (time.perf_counter() - start) * 1000
                self.store.append_result(
                    StrategyResult(
                        intent=intent,
                        strategy=strategy_name,
                        success=False,
                        elapsed_ms=elapsed,
                        details={"error": str(exc)},
                    )
                )

        if last_error is not None:
            raise last_error
        raise LookupError(f"Unable to resolve intent: {intent}")

    async def _by_role(self, page: object, _intent: str, hints: list[str]) -> Any | None:
        common_roles = ["button", "textbox", "link", "checkbox"]
        for hint in hints:
            for role in common_roles:
                locator = page.get_by_role(role, name=hint)
                if await locator.count() > 0:
                    return locator.first
        return None

    async def _by_label(self, page: object, _intent: str, hints: list[str]) -> Any | None:
        for hint in hints:
            locator = page.get_by_label(hint)
            if await locator.count() > 0:
                return locator.first
        return None

    async def _by_text(self, page: object, _intent: str, hints: list[str]) -> Any | None:
        for hint in hints:
            locator = page.get_by_text(hint)
            if await locator.count() > 0:
                return locator.first
        return None

    async def _heuristic(self, page: object, intent: str, hints: list[str]) -> Any | None:
        tag_priority = ["button", "input", "textarea", "a"]
        for tag in tag_priority:
            locator = page.locator(tag)
            count = await locator.count()
            for idx in range(min(count, 30)):
                candidate = locator.nth(idx)
                text = ((await candidate.inner_text()) if tag != "input" else "") or ""
                attrs = (
                    (await candidate.get_attribute("aria-label")) or "",
                    (await candidate.get_attribute("placeholder")) or "",
                    (await candidate.get_attribute("name")) or "",
                    (await candidate.get_attribute("id")) or "",
                )
                haystack = f"{intent} {text} {' '.join(attrs)}".lower()
                if any(h.lower() in haystack for h in hints):
                    return candidate
        return None

    async def _semantic(self, page: object, intent: str, hints: list[str]) -> Any | None:
        return await self.semantic_finder.find(page, intent, hints)
