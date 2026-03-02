from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import ApiKnowledge, StrategyResult


class KnowledgeStore:
    def __init__(self, path: str | Path = ".smartwright_knowledge.json") -> None:
        self.path = Path(path)
        if not self.path.exists():
            self._write({"api_knowledge": {}, "history": {}, "fingerprints": {}, "intent_aliases": {}})

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    def get_api(self, intent: str) -> ApiKnowledge | None:
        data = self._read()["api_knowledge"].get(intent)
        if not data:
            return None
        return ApiKnowledge(**data)

    def save_api(self, knowledge: ApiKnowledge) -> None:
        payload = self._read()
        payload["api_knowledge"][knowledge.intent] = asdict(knowledge)
        self._write(payload)

    def save_fingerprint(self, page_key: str, dom_hash: str) -> None:
        payload = self._read()
        payload["fingerprints"][page_key] = dom_hash
        self._write(payload)

    def get_fingerprint(self, page_key: str) -> str | None:
        return self._read()["fingerprints"].get(page_key)

    def append_result(self, result: StrategyResult) -> None:
        payload = self._read()
        history = payload["history"].setdefault(result.intent, [])
        history.append(asdict(result))
        self._write(payload)

    def strategy_scores(self, intent: str) -> dict[str, float]:
        events = self._read()["history"].get(intent, [])
        if not events:
            return {}

        per_strategy: dict[str, list[bool]] = {}
        for event in events:
            per_strategy.setdefault(event["strategy"], []).append(bool(event["success"]))

        return {
            strategy: sum(1 for ok in success if ok) / len(success)
            for strategy, success in per_strategy.items()
        }

    def record_aliases(self, intent_map: dict[str, list[str]]) -> None:
        payload = self._read()
        payload["intent_aliases"].update(intent_map)
        self._write(payload)

    def aliases(self, intent: str) -> list[str]:
        return self._read()["intent_aliases"].get(intent, [])
