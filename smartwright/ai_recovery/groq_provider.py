from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from groq import Groq


class GroqAdvisor:
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile") -> None:
        self.client = Groq(api_key=api_key)
        self.model = model

    async def suggest(self, intent: str, hints: list[str], snippets: list[str]) -> dict[str, str] | None:
        prompt = self._build_prompt(intent, hints, snippets)
        content = await asyncio.to_thread(self._complete, prompt)
        return self._parse_suggestion(content)

    def _complete(self, prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0.1,
            max_tokens=180,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a web-automation recovery planner. "
                        "Return only JSON with keys: strategy, hint, reason. "
                        "Allowed strategy values: get_by_text, get_by_label, semantic."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    def _build_prompt(self, intent: str, hints: list[str], snippets: list[str]) -> str:
        clipped = "\n".join(f"- {s[:280]}" for s in snippets[:8])
        return (
            f"Intent: {intent}\n"
            f"Hints: {hints}\n"
            "Relevant DOM snippets:\n"
            f"{clipped}\n\n"
            "Select the best recovery strategy and hint."
        )

    def _parse_suggestion(self, content: str) -> dict[str, str] | None:
        if not content:
            return None

        json_candidate = self._extract_json(content)
        if json_candidate is not None:
            strategy = str(json_candidate.get("strategy", "")).strip()
            hint = str(json_candidate.get("hint", "")).strip()
            if strategy and hint:
                return {"strategy": strategy, "hint": hint}

        # Fallback parser for malformed responses.
        strategy_match = re.search(r"(get_by_text|get_by_label|semantic)", content, flags=re.IGNORECASE)
        hint_match = re.search(r'hint\\s*[:=]\\s*["\\\']?([^"\\\'\\n]+)', content, flags=re.IGNORECASE)
        if strategy_match and hint_match:
            return {"strategy": strategy_match.group(1), "hint": hint_match.group(1).strip()}
        return None

    def _extract_json(self, content: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            pass

        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
