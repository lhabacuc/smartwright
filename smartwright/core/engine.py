from __future__ import annotations

import time
from typing import Any

from smartwright.ai_recovery.recovery import AIRecovery
from smartwright.api_executor.executor import ApiExecutor
from smartwright.fingerprint.tracker import FingerprintTracker
from smartwright.healing.layer import HealingLayer
from smartwright.intent.manager import IntentManager
from smartwright.network_learning.observer import NetworkLearner
from smartwright.resolver.adaptive import AdaptiveResolver
from smartwright.semantic_finder.finder import SemanticFinder

from .models import StrategyResult
from .store import KnowledgeStore


class DecisionEngine:
    def __init__(
        self,
        page: object,
        request_context: object,
        intents: dict[str, list[str]],
        semantic_map: dict[str, dict[str, list[str]]] | None = None,
        store_path: str = ".smartwright_knowledge.json",
        ai_advisor: object | None = None,
    ) -> None:
        self.page = page
        self.request_context = request_context
        self.store = KnowledgeStore(store_path)
        self.intent_manager = IntentManager(intents, self.store)
        self.semantic_finder = SemanticFinder(semantic_map=semantic_map)
        self.resolver = AdaptiveResolver(self.store, self.semantic_finder)
        self.api_executor = ApiExecutor()
        self.healing = HealingLayer()
        self.fingerprint = FingerprintTracker(self.store)
        self.network = NetworkLearner(self.store)
        self.ai_recovery = AIRecovery(advisor=ai_advisor)

    def attach_network_learning(self) -> None:
        self.network.attach(self.page)

    async def run(self, action: str, intent: str, value: Any | None = None) -> Any:
        hints = self.intent_manager.all_hints(intent)
        if not hints:
            raise KeyError(f"Unknown intent: {intent}")

        page_key = await self._page_key()
        dom_changed = await self.fingerprint.detect_change(self.page, page_key)
        if dom_changed:
            # Layout drift detected: strategy cache becomes less trustworthy.
            self.store.append_result(
                StrategyResult(
                    intent=intent,
                    strategy="fingerprint_change",
                    success=True,
                    elapsed_ms=0,
                    details={"page": page_key},
                )
            )

        api_knowledge = self.store.get_api(intent)
        if api_knowledge is not None:
            start = time.perf_counter()
            response = await self.api_executor.execute(
                self.request_context,
                api_knowledge,
                payload=value if isinstance(value, dict) else None,
            )
            self.store.append_result(
                StrategyResult(
                    intent=intent,
                    strategy="api_executor",
                    success=True,
                    elapsed_ms=(time.perf_counter() - start) * 1000,
                    details={"endpoint": api_knowledge.endpoint},
                )
            )
            return response

        async def dom_action() -> Any:
            locator = await self.resolver.resolve(self.page, intent, hints)
            return await self._apply_action(locator, action, value)

        try:
            return await self.healing.run_with_healing(
                action=dom_action,
                reload_state=self._reload_state,
                relearn=self._relearn,
            )
        except Exception:
            suggestion = await self.ai_recovery.recover(self.page, intent, hints)
            if suggestion is None:
                raise
            return await self._execute_ai_suggestion(suggestion, action, value, intent)

    async def _apply_action(self, locator: Any, action: str, value: Any | None = None) -> Any:
        if action == "click":
            return await locator.click()
        if action == "fill":
            return await locator.fill(str(value or ""))
        if action == "read":
            return await locator.inner_text()
        raise ValueError(f"Unsupported action: {action}")

    async def _reload_state(self) -> None:
        await self.page.wait_for_load_state("domcontentloaded")

    async def _relearn(self) -> None:
        page_key = await self._page_key()
        await self.fingerprint.detect_change(self.page, page_key)

    async def _page_key(self) -> str:
        url = getattr(self.page, "url", "unknown://page")
        return url or "unknown://page"

    async def _execute_ai_suggestion(self, suggestion: dict[str, str], action: str, value: Any | None, intent: str) -> Any:
        strategy = suggestion.get("strategy")
        hint = suggestion.get("hint", "")
        start = time.perf_counter()

        if strategy == "get_by_text":
            locator = self.page.get_by_text(hint)
            if await locator.count() > 0:
                result = await self._apply_action(locator.first, action, value)
                self.store.append_result(
                    StrategyResult(
                        intent=intent,
                        strategy="ai_recovery:get_by_text",
                        success=True,
                        elapsed_ms=(time.perf_counter() - start) * 1000,
                    )
                )
                return result

        self.store.append_result(
            StrategyResult(
                intent=intent,
                strategy="ai_recovery",
                success=False,
                elapsed_ms=(time.perf_counter() - start) * 1000,
                details={"suggestion": suggestion},
            )
        )
        raise LookupError(f"AI recovery failed for intent: {intent}")
