"""Network Learning — descobre APIs automaticamente via observacao de trafego.

Intercepta requests/responses do Playwright, identifica endpoints de API,
normaliza URLs dinamicas, captura payloads e response bodies, e salva
como ApiKnowledge para reutilizacao futura (API-first execution).
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse, parse_qs

from smartwright.core.models import ApiKnowledge
from smartwright.core.store import KnowledgeStore


# ── Patterns para detectar URLs de API ────────────────────────────────

# Segmentos de path que indicam API
_API_PATH_MARKERS = (
    "/api/", "/v1/", "/v2/", "/v3/", "/v4/",
    "/rest/", "/graphql", "/gql",
    "/rpc/", "/services/", "/endpoint/",
    "/_api/", "/ajax/", "/xhr/",
)

# Content-types que indicam resposta de API
_API_CONTENT_TYPES = (
    "application/json",
    "application/graphql",
    "application/x-ndjson",
    "text/event-stream",
)

# Extensoes de recurso estatico a ignorar
_STATIC_EXTENSIONS = (
    ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".map", ".webp", ".avif",
    ".mp4", ".webm", ".ogg", ".mp3", ".wav",
)

# Regex para detectar segmentos dinamicos (IDs, UUIDs, hashes)
_DYNAMIC_SEGMENT = re.compile(
    r"^("
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"  # UUID
    r"|[0-9]+$"                                                         # Numeric ID
    r"|[0-9a-f]{24}"                                                    # MongoDB ObjectId
    r"|[0-9a-f]{32,64}"                                                 # Hash (MD5/SHA)
    r"|[A-Za-z0-9_-]{20,}"                                              # Long tokens
    r")$",
    re.IGNORECASE,
)

# Headers relevantes para replay de API
_KEEP_HEADERS = {
    "authorization", "content-type", "accept", "x-api-key",
    "x-csrf-token", "x-xsrf-token", "x-requested-with",
}

# Palavras-chave para inferencia de intent (URL path → intent)
_INTENT_KEYWORDS: list[tuple[list[str], str]] = [
    # Auth
    (["login", "signin", "sign-in", "auth/login"], "api:login"),
    (["logout", "signout", "sign-out"], "api:logout"),
    (["register", "signup", "sign-up"], "api:register"),
    (["password", "reset-password", "forgot"], "api:password"),
    (["token", "refresh", "oauth"], "api:token"),
    # User
    (["user", "profile", "account", "me"], "api:user"),
    (["settings", "preferences", "config"], "api:settings"),
    # Content
    (["message", "chat", "conversation"], "api:messages"),
    (["comment", "reply"], "api:comments"),
    (["post", "article", "blog"], "api:posts"),
    (["notification", "alert"], "api:notifications"),
    # Data
    (["search", "query", "find"], "api:search"),
    (["list", "index", "feed"], "api:list"),
    (["upload", "file", "attachment", "media"], "api:upload"),
    (["download", "export"], "api:download"),
    # Commerce
    (["cart", "basket"], "api:cart"),
    (["order", "purchase", "checkout"], "api:order"),
    (["payment", "pay", "billing"], "api:payment"),
    (["product", "item", "catalog"], "api:products"),
]


class NetworkLearner:
    """Observa trafego de rede e descobre APIs automaticamente."""

    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store
        self._buffer: dict[str, dict[str, Any]] = {}
        self._attached = False
        self._seen_endpoints: set[str] = set()
        self._discoveries: list[dict[str, Any]] = []

    # ── Attach/Detach ─────────────────────────────────────────────────

    def attach(self, page: object) -> None:
        """Conecta listeners de request/response ao page."""
        if self._attached:
            return
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        self._attached = True

    # ── Request capture ───────────────────────────────────────────────

    def _on_request(self, request: Any) -> None:
        """Captura metadata de cada request (sync, nunca falha)."""
        try:
            url = request.url

            # Skip recursos estaticos
            parsed = urlparse(url)
            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in _STATIC_EXTENSIONS):
                return

            method = request.method

            # Extrair payload
            payload = self._extract_payload(request)

            # Extrair headers relevantes
            raw_headers = {}
            try:
                h = request.headers
                raw_headers = h if isinstance(h, dict) else {}
            except Exception:
                pass

            self._buffer[url] = {
                "method": method,
                "headers": raw_headers,
                "payload": payload,
            }
        except Exception:
            pass

    @staticmethod
    def _extract_payload(request: Any) -> dict[str, Any]:
        """Extrai payload JSON do request."""
        # Tentar post_data_json (property no Playwright real)
        try:
            pdj = request.post_data_json
            data = pdj() if callable(pdj) else pdj
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        # Fallback: parse post_data como texto JSON
        try:
            raw = request.post_data
            if isinstance(raw, str) and raw.strip().startswith(("{", "[")):
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
        except Exception:
            pass

        return {}

    # ── Response capture ──────────────────────────────────────────────

    async def _on_response(self, response: Any) -> None:
        """Analisa response e salva API descoberta (async, nunca falha)."""
        try:
            url = response.url
            status = 0
            try:
                status = response.status
            except Exception:
                pass

            # Ignorar erros de rede e redirects
            if status < 200 or status >= 400:
                return

            # Detectar se e uma API
            if not self._is_api_response(url, response):
                return

            # Normalizar endpoint (substituir IDs dinamicos)
            norm_endpoint = self._normalize_url(url)

            # Deduplicar
            method = "GET"
            try:
                method = response.request.method
            except Exception:
                pass
            dedup_key = f"{method}:{norm_endpoint}"
            if dedup_key in self._seen_endpoints:
                return
            self._seen_endpoints.add(dedup_key)

            # Inferir intent
            intent = self._infer_intent(url, method)

            # Buscar request info do buffer
            base = self._buffer.get(url, {})
            if not base:
                # Tentar buffer com URL sem query
                base_url = url.split("?")[0]
                base = self._buffer.get(base_url, {})

            # Filtrar headers relevantes
            filtered_headers = {
                k: v
                for k, v in base.get("headers", {}).items()
                if k.lower() in _KEEP_HEADERS
            }

            # Capturar response body (para analise de schema)
            response_sample = await self._safe_response_body(response)

            # Salvar discovery
            knowledge = ApiKnowledge(
                intent=intent,
                endpoint=norm_endpoint,
                method=method,
                payload_template=base.get("payload", {}),
                headers=filtered_headers,
                confidence=0.7,
            )
            self.store.save_api(knowledge)

            # Guardar em memoria para consulta
            discovery = {
                "intent": intent,
                "endpoint": norm_endpoint,
                "original_url": url,
                "method": method,
                "status": status,
                "payload_template": base.get("payload", {}),
                "headers": filtered_headers,
                "response_sample": response_sample,
            }
            self._discoveries.append(discovery)

        except Exception:
            pass

    # ── API detection ─────────────────────────────────────────────────

    @staticmethod
    def _is_api_response(url: str, response: Any) -> bool:
        """Detecta se um response e de uma API (nao recurso estatico)."""
        url_lower = url.lower()

        # Check 1: path contem marcador de API
        if any(marker in url_lower for marker in _API_PATH_MARKERS):
            return True

        # Check 2: content-type indica API
        try:
            content_type = ""
            try:
                # Playwright Response.headers é dict
                headers = response.headers
                if isinstance(headers, dict):
                    content_type = headers.get("content-type", "")
                else:
                    content_type = response.headers.get("content-type", "")
            except Exception:
                pass

            if any(ct in content_type.lower() for ct in _API_CONTENT_TYPES):
                return True
        except Exception:
            pass

        # Check 3: XHR pattern — path sem extensao + JSON response
        parsed = urlparse(url)
        path = parsed.path
        if not any(path.lower().endswith(ext) for ext in _STATIC_EXTENSIONS):
            if "." not in path.split("/")[-1]:  # Sem extensao no ultimo segmento
                try:
                    content_type = ""
                    headers = response.headers
                    if isinstance(headers, dict):
                        content_type = headers.get("content-type", "")
                    if "json" in content_type.lower():
                        return True
                except Exception:
                    pass

        return False

    # ── URL normalization ─────────────────────────────────────────────

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normaliza URL substituindo segmentos dinamicos por {id}.

        /api/users/123/posts/abc-def-ghi → /api/users/{id}/posts/{id}
        """
        parsed = urlparse(url)
        segments = parsed.path.split("/")
        normalized = []
        for seg in segments:
            if not seg:
                normalized.append(seg)
                continue
            if _DYNAMIC_SEGMENT.match(seg):
                normalized.append("{id}")
            else:
                normalized.append(seg)

        norm_path = "/".join(normalized)
        # Reconstruir sem query string (template limpo)
        return f"{parsed.scheme}://{parsed.netloc}{norm_path}"

    # ── Intent inference ──────────────────────────────────────────────

    @staticmethod
    def _infer_intent(url: str, method: str = "GET") -> str:
        """Gera intent a partir da URL e metodo HTTP.

        Tenta match com keywords conhecidas (por segmento de path).
        Fallback: gera intent a partir dos ultimos segmentos do path.
        """
        parsed = urlparse(url)
        path = parsed.path.lower()
        path_segments = [s for s in path.split("/") if s and s != "{id}"]

        # Sufixo de metodo HTTP
        method_suffix = ""
        if method == "POST":
            method_suffix = ":create"
        elif method == "PUT":
            method_suffix = ":update"
        elif method == "DELETE":
            method_suffix = ":delete"

        # Tentar match com keywords conhecidas (match por segmento, nao substring)
        for keywords, intent in _INTENT_KEYWORDS:
            for kw in keywords:
                # Keywords com "/" fazem match de path (ex: "auth/login")
                if "/" in kw:
                    if kw in path:
                        return intent + method_suffix
                else:
                    # Match por segmento para evitar "me" matchando "messages"
                    for seg in path_segments:
                        if seg == kw or seg.rstrip("s") == kw or kw.rstrip("s") == seg:
                            return intent + method_suffix

        # Fallback: gerar intent a partir do path
        # /api/v1/users/settings → api:users:settings
        meaningful = [
            s for s in path_segments
            if s not in ("api", "v1", "v2", "v3", "v4", "rest", "graphql")
        ]
        if meaningful:
            slug = ":".join(meaningful[-3:])
            return f"api:{slug}{method_suffix}"

        # Ultimo fallback
        return f"api:{parsed.netloc}:{method.lower()}"

    # ── Response body ─────────────────────────────────────────────────

    @staticmethod
    async def _safe_response_body(response: Any) -> dict[str, Any] | None:
        """Extrai body do response como dict (truncado para nao explodir memoria)."""
        try:
            body_fn = getattr(response, "json", None)
            if callable(body_fn):
                data = await body_fn()
                if isinstance(data, dict):
                    # Truncar para evitar armazenar payloads gigantes
                    return _truncate_dict(data, max_depth=3, max_keys=20)
                if isinstance(data, list) and data:
                    # Guardar apenas o primeiro item como sample
                    first = data[0] if isinstance(data[0], dict) else {"_sample": str(data[0])[:100]}
                    return {"_type": "array", "_length": len(data), "_sample": _truncate_dict(first, max_depth=2, max_keys=10)}
        except Exception:
            pass

        try:
            text_fn = getattr(response, "text", None)
            if callable(text_fn):
                text = await text_fn()
                if isinstance(text, str) and text.strip().startswith(("{", "[")):
                    parsed = json.loads(text[:10000])  # Cap em 10KB
                    if isinstance(parsed, dict):
                        return _truncate_dict(parsed, max_depth=3, max_keys=20)
        except Exception:
            pass

        return None

    # ── Public API ────────────────────────────────────────────────────

    @property
    def discoveries(self) -> list[dict[str, Any]]:
        """Retorna lista de todas as APIs descobertas nesta sessao."""
        return list(self._discoveries)

    def get_discovery(self, intent: str) -> dict[str, Any] | None:
        """Busca discovery por intent."""
        for d in self._discoveries:
            if d["intent"] == intent:
                return d
        return None

    def summary(self) -> dict[str, Any]:
        """Resumo das APIs descobertas."""
        by_method: dict[str, int] = {}
        by_domain: dict[str, int] = {}
        for d in self._discoveries:
            m = d.get("method", "?")
            by_method[m] = by_method.get(m, 0) + 1
            try:
                domain = urlparse(d["endpoint"]).netloc
                by_domain[domain] = by_domain.get(domain, 0) + 1
            except Exception:
                pass
        return {
            "total_discovered": len(self._discoveries),
            "by_method": by_method,
            "by_domain": by_domain,
            "intents": [d["intent"] for d in self._discoveries],
        }

    def clear(self) -> None:
        """Limpa buffer e discoveries da sessao."""
        self._buffer.clear()
        self._discoveries.clear()
        self._seen_endpoints.clear()


# ── Helpers ───────────────────────────────────────────────────────────


def _truncate_dict(d: dict, max_depth: int = 3, max_keys: int = 20, _depth: int = 0) -> dict:
    """Trunca dict recursivamente para evitar payloads gigantes."""
    if _depth >= max_depth:
        return {"_truncated": True}
    result = {}
    for i, (k, v) in enumerate(d.items()):
        if i >= max_keys:
            result["_more_keys"] = len(d) - max_keys
            break
        if isinstance(v, dict):
            result[k] = _truncate_dict(v, max_depth, max_keys, _depth + 1)
        elif isinstance(v, list):
            if v and isinstance(v[0], dict):
                result[k] = [_truncate_dict(v[0], max_depth, max_keys, _depth + 1)]
                if len(v) > 1:
                    result[k].append({"_more_items": len(v) - 1})
            else:
                result[k] = v[:5]
                if len(v) > 5:
                    result[k].append(f"...+{len(v) - 5}")
        elif isinstance(v, str) and len(v) > 200:
            result[k] = v[:200] + "..."
        else:
            result[k] = v
    return result
