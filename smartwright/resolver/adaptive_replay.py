"""Adaptive Replay — replay autonomo sem LLM.

Resolve elementos por fingerprint semantico (texto, tag, tipo, atributos
estaveis), ignorando IDs e classes que mudam constantemente entre deploys.

Algoritmo:
1. Extrai fingerprint semantico de cada acao gravada (tag, text, type,
   placeholder, aria-label, name, role, href pattern, regiao visual).
2. No replay, coleta todos os elementos interativos da pagina atual.
3. Pontua cada candidato contra o fingerprint usando pesos:
   - Texto: 40 pts (fuzzy match por tokens)
   - Tipo de input: 25 pts (exact match)
   - Placeholder: 20 pts
   - aria-label: 20 pts
   - name: 15 pts
   - href pattern: 15 pts
   - Regiao visual: 10 pts
   - Role: 10 pts
4. Seleciona o candidato com maior score (minimo 15 pts).
5. Resolve para Playwright locator via selectors estaveis ou coordenadas.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse


# ── Semantic Fingerprint ──────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SemanticFingerprint:
    """Identidade semantica de um elemento, independente de ID/class."""

    tag: str                          # button, input, a, select, textarea
    text: str = ""                    # innerText
    input_type: str = ""              # text, email, password, checkbox...
    placeholder: str = ""
    aria_label: str = ""
    name: str = ""
    role: str = ""
    href_pattern: str = ""            # href normalizado (sem IDs dinamicos)
    value: str = ""                   # valor pre-preenchido
    region: str = ""                  # quadrante visual: top-left, mid-center...
    action_type: str = ""             # click, fill, select, etc.


def extract_fingerprint(action: dict[str, Any]) -> SemanticFingerprint:
    """Extrai fingerprint semantico de uma acao gravada."""
    capture = action.get("capture") or {}
    attrs = capture.get("attributes") or {}
    bbox = capture.get("bbox") or {}

    tag = capture.get("tag", action.get("element_type", "")).lower()
    text = capture.get("text", action.get("text", "")).strip()[:200]

    # Tipo de input
    input_type = attrs.get("type", "").lower()
    if tag == "input" and not input_type:
        input_type = "text"

    # Normalizar href para links
    href = attrs.get("href", "")
    href_pattern = _normalize_href(href) if href else ""

    # Regiao do viewport
    region = ""
    if bbox.get("cx") is not None and bbox.get("cy") is not None:
        region = _bbox_to_region(bbox["cx"], bbox["cy"])

    return SemanticFingerprint(
        tag=tag,
        text=text,
        input_type=input_type,
        placeholder=attrs.get("placeholder", ""),
        aria_label=attrs.get("aria-label", ""),
        name=attrs.get("name", ""),
        role=attrs.get("role", ""),
        href_pattern=href_pattern,
        value=attrs.get("value", ""),
        region=region,
        action_type=action.get("action", ""),
    )


# ── Text Similarity ──────────────────────────────────────────────────


def _text_similarity(a: str, b: str) -> float:
    """Similaridade entre dois textos (0.0 a 1.0).

    Usa token Jaccard + fallback para substring.
    Sem dependencias externas.
    """
    a, b = a.lower().strip(), b.lower().strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    # Token Jaccard
    ta = set(a.split())
    tb = set(b.split())
    if ta and tb:
        intersection = ta & tb
        union = ta | tb
        jaccard = len(intersection) / len(union) if union else 0.0
        if jaccard > 0:
            return jaccard

    # Substring containment
    if a in b or b in a:
        return min(len(a), len(b)) / max(len(a), len(b))

    # Character bigram similarity (fallback para palavras unicas)
    bigrams_a = {a[i:i + 2] for i in range(len(a) - 1)}
    bigrams_b = {b[i:i + 2] for i in range(len(b) - 1)}
    if bigrams_a and bigrams_b:
        intersection = bigrams_a & bigrams_b
        union = bigrams_a | bigrams_b
        return len(intersection) / len(union) if union else 0.0

    return 0.0


# ── URL Normalization ─────────────────────────────────────────────────

_DYNAMIC_SEG = re.compile(
    r"^("
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"  # UUID
    r"|[0-9]+$"                                                         # Numeric ID
    r"|[0-9a-f]{24}"                                                    # MongoDB ObjectId
    r"|[0-9a-f]{32,64}"                                                 # Hash
    r"|[A-Za-z0-9_-]{20,}"                                              # Long tokens
    r")$",
    re.IGNORECASE,
)


def _normalize_href(href: str) -> str:
    """Normaliza href substituindo IDs dinamicos por {id}."""
    if not href:
        return ""
    try:
        parsed = urlparse(href)
        segments = parsed.path.split("/")
        normalized = []
        for seg in segments:
            if not seg:
                normalized.append(seg)
            elif _DYNAMIC_SEG.match(seg):
                normalized.append("{id}")
            else:
                normalized.append(seg)
        return "/".join(normalized)
    except Exception:
        return href


# ── Region Detection ──────────────────────────────────────────────────

# Viewport padrao para calculo de regiao (ajustavel)
_VP_WIDTH = 1280
_VP_HEIGHT = 720


def _bbox_to_region(cx: int | float, cy: int | float) -> str:
    """Converte coordenadas centrais em regiao do viewport.

    Grid 3x3: top/mid/bottom x left/center/right.
    """
    # Vertical
    if cy < _VP_HEIGHT * 0.33:
        v = "top"
    elif cy < _VP_HEIGHT * 0.66:
        v = "mid"
    else:
        v = "bottom"

    # Horizontal
    if cx < _VP_WIDTH * 0.33:
        h = "left"
    elif cx < _VP_WIDTH * 0.66:
        h = "center"
    else:
        h = "right"

    return f"{v}-{h}"


def _regions_adjacent(r1: str, r2: str) -> bool:
    """Verifica se duas regioes sao adjacentes no grid 3x3."""
    if not r1 or not r2:
        return False
    parts1 = r1.split("-")
    parts2 = r2.split("-")
    if len(parts1) != 2 or len(parts2) != 2:
        return False

    v_order = {"top": 0, "mid": 1, "bottom": 2}
    h_order = {"left": 0, "center": 1, "right": 2}

    v1 = v_order.get(parts1[0], -1)
    v2 = v_order.get(parts2[0], -1)
    h1 = h_order.get(parts1[1], -1)
    h2 = h_order.get(parts2[1], -1)

    return abs(v1 - v2) <= 1 and abs(h1 - h2) <= 1


# ── Scoring ───────────────────────────────────────────────────────────

# Tags equivalentes para matching
_TAG_EQUIVALENTS: dict[str, set[str]] = {
    "button": {"button", "div", "span", "a"},      # role=button em div/span/a
    "a": {"a", "button"},                            # links que viram botoes
    "input": {"input"},
    "textarea": {"textarea"},
    "select": {"select"},
}


def score_candidate(fp: SemanticFingerprint, candidate: dict[str, Any]) -> float:
    """Pontua um candidato contra o fingerprint. Maior = melhor match."""
    score = 0.0

    # ── Tag match (hard filter com tolerancia para role=button) ──
    c_tag = candidate.get("tag", "").lower()
    c_role = candidate.get("role", "").lower()

    tag_ok = False
    if c_tag == fp.tag:
        tag_ok = True
    elif fp.tag in _TAG_EQUIVALENTS:
        if c_tag in _TAG_EQUIVALENTS[fp.tag]:
            tag_ok = True
    # role=button/link em qualquer tag
    if not tag_ok:
        if fp.tag == "button" and c_role == "button":
            tag_ok = True
        elif fp.tag == "a" and c_role == "link":
            tag_ok = True
        elif fp.role and c_role == fp.role:
            tag_ok = True

    if not tag_ok:
        return -1.0

    # ── Texto (peso: 40) ──
    if fp.text:
        c_text = candidate.get("text", "")
        sim = _text_similarity(fp.text, c_text)
        score += sim * 40

    # ── Tipo de input (peso: 25) ──
    if fp.input_type:
        c_type = candidate.get("type", "").lower()
        if not c_type and c_tag == "input":
            c_type = "text"
        if c_type == fp.input_type:
            score += 25
        elif c_type and c_type != fp.input_type:
            score -= 15  # tipo errado e sinal forte negativo

    # ── Placeholder (peso: 20) ──
    if fp.placeholder:
        c_ph = candidate.get("placeholder", "")
        if c_ph:
            sim = _text_similarity(fp.placeholder, c_ph)
            score += sim * 20

    # ── aria-label (peso: 20) ──
    if fp.aria_label:
        c_al = candidate.get("aria_label", "")
        if c_al:
            sim = _text_similarity(fp.aria_label, c_al)
            score += sim * 20

    # ── name (peso: 15, exact match) ──
    if fp.name:
        c_name = candidate.get("name", "")
        if c_name == fp.name:
            score += 15

    # ── href pattern (peso: 15) ──
    if fp.href_pattern:
        c_href = _normalize_href(candidate.get("href", ""))
        if c_href:
            sim = _text_similarity(fp.href_pattern, c_href)
            score += sim * 15

    # ── role (peso: 10) ──
    if fp.role:
        if c_role == fp.role:
            score += 10

    # ── Regiao visual (peso: 10) ──
    if fp.region:
        c_bbox = candidate.get("bbox") or {}
        if c_bbox.get("cx") is not None:
            c_region = _bbox_to_region(c_bbox["cx"], c_bbox["cy"])
            if c_region == fp.region:
                score += 10
            elif _regions_adjacent(fp.region, c_region):
                score += 4

    return score


# ── JS: Collect Interactive Elements ──────────────────────────────────

_JS_COLLECT_INTERACTIVE = """() => {
    const sel = 'button, input, textarea, select, a[href], ' +
        '[role="button"], [role="link"], [role="checkbox"], ' +
        '[role="tab"], [role="menuitem"], [role="radio"], ' +
        '[role="switch"], [role="combobox"], [contenteditable="true"]';
    const els = document.querySelectorAll(sel);
    const results = [];
    const tagCounters = new Map();

    for (const el of els) {
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' ||
            parseFloat(style.opacity) === 0) continue;

        const rect = el.getBoundingClientRect();
        if (rect.width === 0 && rect.height === 0) continue;

        if (el.tagName === 'INPUT' && el.type === 'hidden') continue;
        if (el.closest('template, script, style, noscript')) continue;

        const tag = el.tagName.toLowerCase();

        if (!tagCounters.has(tag)) tagCounters.set(tag, 0);
        const idx = tagCounters.get(tag);
        tagCounters.set(tag, idx + 1);

        // Selectors estaveis para relocacao (SEM id/class)
        const sels = [];
        const name = el.getAttribute('name');
        if (name) sels.push(tag + '[name="' + name.replace(/"/g, '\\\\"') + '"]');
        const ariaLabel = el.getAttribute('aria-label');
        if (ariaLabel) sels.push(tag + '[aria-label="' + ariaLabel.replace(/"/g, '\\\\"') + '"]');
        const ph = el.placeholder;
        if (ph) sels.push(tag + '[placeholder="' + ph.replace(/"/g, '\\\\"') + '"]');
        const role = el.getAttribute('role');
        if (role) sels.push('[role="' + role + '"]');
        const testId = el.getAttribute('data-testid');
        if (testId) sels.push('[data-testid="' + testId + '"]');

        // Parent structural selector (fallback)
        const parent = el.parentElement;
        if (parent) {
            try {
                const siblings = parent.querySelectorAll(':scope > ' + tag);
                const nthIdx = Array.from(siblings).indexOf(el) + 1;
                let pSel = parent.tagName.toLowerCase();
                if (parent.id) pSel = '#' + CSS.escape(parent.id);
                sels.push(pSel + ' > ' + tag + ':nth-of-type(' + nthIdx + ')');
            } catch (_) {}
        }

        results.push({
            tag,
            index_in_type: idx,
            text: (el.innerText || '').trim().slice(0, 200),
            type: (el.type || '').toLowerCase(),
            name: name || '',
            placeholder: ph || '',
            aria_label: ariaLabel || '',
            role: role || '',
            href: el.href || '',
            value: (el.value || '').slice(0, 100),
            checked: !!el.checked,
            disabled: !!el.disabled,
            alt: el.alt || '',
            bbox: {
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                width: Math.round(rect.width),
                height: Math.round(rect.height),
                cx: Math.round(rect.x + rect.width / 2),
                cy: Math.round(rect.y + rect.height / 2),
            },
            selectors: sels,
        });
    }

    return results;
}"""


# ── Adaptive Resolve ──────────────────────────────────────────────────


async def adaptive_resolve(
    page: Any,
    action: dict[str, Any],
    timeout_ms: int = 7000,
) -> Any:
    """Resolve elemento usando fingerprint semantico.

    1. Extrai fingerprint da acao gravada
    2. Coleta todos os elementos interativos da pagina
    3. Pontua cada candidato
    4. Resolve o melhor match para Playwright locator

    Raises LookupError se nenhum match com score >= 15.
    """
    fp = extract_fingerprint(action)

    # Coletar elementos interativos da pagina atual
    candidates = await page.evaluate(_JS_COLLECT_INTERACTIVE)

    if not candidates:
        raise LookupError(
            f"Nenhum elemento interativo na pagina para "
            f"acao '{fp.action_type}' tag='{fp.tag}'"
        )

    # Pontuar cada candidato
    scored: list[tuple[float, dict[str, Any]]] = []
    for c in candidates:
        s = score_candidate(fp, c)
        if s > 0:
            scored.append((s, c))

    if not scored:
        raise LookupError(
            f"Nenhum candidato compativel: tag='{fp.tag}', "
            f"text='{fp.text[:50]}', type='{fp.input_type}'"
        )

    # Ordenar por score descrescente
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]

    # Threshold minimo
    if best_score < 15:
        raise LookupError(
            f"Score muito baixo ({best_score:.1f}) para "
            f"tag='{fp.tag}', text='{fp.text[:50]}'"
        )

    # Resolver para Playwright locator
    return await _resolve_to_locator(page, best, timeout_ms)


async def adaptive_resolve_all(
    page: Any,
    actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pre-analisa todas as acoes contra a pagina atual.

    Retorna diagnostico: para cada acao, o melhor match e score.
    Util para validar um recording antes de executar.
    """
    candidates = await page.evaluate(_JS_COLLECT_INTERACTIVE)
    results = []

    for i, action in enumerate(actions):
        act_type = action.get("action", "")
        if act_type in ("goto", "scroll", "press_keys", "wait", "wait_text", "wait_url"):
            results.append({
                "step": action.get("step", i + 1),
                "action": act_type,
                "match": "n/a",
                "score": 0,
            })
            continue

        fp = extract_fingerprint(action)
        best_score = 0.0
        best_match = None
        for c in candidates:
            s = score_candidate(fp, c)
            if s > best_score:
                best_score = s
                best_match = c

        results.append({
            "step": action.get("step", i + 1),
            "action": act_type,
            "fingerprint": {
                "tag": fp.tag,
                "text": fp.text[:60],
                "type": fp.input_type,
                "placeholder": fp.placeholder,
                "name": fp.name,
            },
            "match": {
                "tag": best_match.get("tag", "") if best_match else "",
                "text": best_match.get("text", "")[:60] if best_match else "",
                "type": best_match.get("type", "") if best_match else "",
            } if best_match else None,
            "score": round(best_score, 1),
            "confident": best_score >= 15,
        })

    return results


# ── Locator Resolution ────────────────────────────────────────────────


async def _resolve_to_locator(
    page: Any,
    candidate: dict[str, Any],
    timeout_ms: int,
) -> Any:
    """Converte candidato matched em Playwright locator."""
    # 1. Selectors estaveis (name, aria-label, placeholder)
    for sel in candidate.get("selectors", []):
        # Pular selectors estruturais nth-of-type (podem mudar)
        if ":nth-of-type" in sel:
            continue
        try:
            loc = page.locator(sel)
            count = await loc.count()
            if count == 1:
                return loc.first
            elif count > 1:
                # Multiplos matches — filtrar por texto se possivel
                text = candidate.get("text", "")
                if text and len(text) >= 3:
                    filtered = loc.filter(has_text=text[:80])
                    fc = await filtered.count()
                    if fc > 0:
                        return filtered.first
                return loc.first
        except Exception:
            continue

    # 2. Tag + texto (locator semantico)
    text = candidate.get("text", "")
    tag = candidate.get("tag", "")
    if text and len(text) >= 3 and tag:
        try:
            loc = page.locator(tag).filter(has_text=text[:80])
            count = await loc.count()
            if count > 0:
                return loc.first
        except Exception:
            pass

    # 3. get_by_text (ultimo recurso antes de coordenadas)
    if text and len(text) >= 4:
        try:
            loc = page.get_by_text(text[:80], exact=False)
            count = await loc.count()
            if count > 0:
                return loc.first
        except Exception:
            pass

    # 4. Selector estrutural nth-of-type (tentamos por ultimo)
    for sel in candidate.get("selectors", []):
        if ":nth-of-type" in sel:
            try:
                loc = page.locator(sel)
                count = await loc.count()
                if count > 0:
                    return loc.first
            except Exception:
                continue

    # 5. Coordenadas (ultimo recurso absoluto)
    bbox = candidate.get("bbox") or {}
    if bbox.get("cx") is not None:
        from smartwright.resolver.emergency import _CoordinateHandle
        return _CoordinateHandle(page, bbox["cx"], bbox["cy"])

    raise LookupError(
        f"Nao consegui criar locator para: "
        f"tag='{candidate.get('tag')}', text='{candidate.get('text', '')[:40]}'"
    )
