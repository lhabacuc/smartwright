from __future__ import annotations

from typing import Any

from smartwright.core.models import ApiKnowledge


class ApiExecutor:
    async def execute(self, request_context: Any, knowledge: ApiKnowledge, payload: dict[str, Any] | None = None) -> Any:
        data = payload if payload is not None else knowledge.payload_template
        method = knowledge.method.upper()

        if method == "GET":
            return await request_context.get(knowledge.endpoint, headers=knowledge.headers)
        if method == "POST":
            return await request_context.post(knowledge.endpoint, headers=knowledge.headers, data=data)
        if method == "PUT":
            return await request_context.put(knowledge.endpoint, headers=knowledge.headers, data=data)
        if method == "DELETE":
            return await request_context.delete(knowledge.endpoint, headers=knowledge.headers, data=data)

        raise ValueError(f"Unsupported HTTP method: {knowledge.method}")
