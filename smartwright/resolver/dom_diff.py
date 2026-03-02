"""Page Diff — detecta mudancas entre dois snapshots do DOM."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from smartwright.resolver.dom_serializer import DOMSerializerConfig, DOMSnapshot, ElementMeta


@dataclass(slots=True)
class ElementChange:
    """Uma mudanca detectada num elemento entre dois snapshots."""

    element: ElementMeta
    field: str
    old_value: Any
    new_value: Any


@dataclass
class PageDiff:
    """Resultado da comparacao entre dois snapshots do DOM.

    Attrs:
        added: Elementos presentes no after mas nao no before.
        removed: Elementos presentes no before mas nao no after.
        changed: Lista de mudancas em elementos que existem em ambos.
        before_url: URL da pagina antes.
        after_url: URL da pagina depois.
    """

    added: list[ElementMeta] = field(default_factory=list)
    removed: list[ElementMeta] = field(default_factory=list)
    changed: list[ElementChange] = field(default_factory=list)
    before_url: str = ""
    after_url: str = ""

    @property
    def counts(self) -> dict[str, int]:
        """Contagem resumida de mudancas."""
        return {
            "added": len(self.added),
            "removed": len(self.removed),
            "changed": len(self.changed),
        }

    @property
    def has_changes(self) -> bool:
        """Retorna True se houve qualquer mudanca."""
        return bool(self.added or self.removed or self.changed)

    def summary(self) -> str:
        """Resumo textual das mudancas."""
        parts: list[str] = []
        if self.added:
            parts.append(f"+{len(self.added)} added")
        if self.removed:
            parts.append(f"-{len(self.removed)} removed")
        if self.changed:
            parts.append(f"~{len(self.changed)} changed")
        if not parts:
            return "No changes detected"
        return ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serializa diff para dict."""
        return {
            "before_url": self.before_url,
            "after_url": self.after_url,
            "counts": self.counts,
            "added": [
                {"tag": el.tag, "role": el.role, "text": el.text, "index": el.index}
                for el in self.added
            ],
            "removed": [
                {"tag": el.tag, "role": el.role, "text": el.text, "index": el.index}
                for el in self.removed
            ],
            "changed": [
                {
                    "element": {"tag": c.element.tag, "role": c.element.role, "text": c.element.text},
                    "field": c.field,
                    "old_value": c.old_value,
                    "new_value": c.new_value,
                }
                for c in self.changed
            ],
        }


def _element_fingerprint(el: ElementMeta) -> str:
    """Gera identidade estavel de um elemento para matching entre snapshots.

    Usa tag + role + name/id/data-testid + index_in_type para criar
    uma chave unica que sobrevive a mudancas de texto/atributos.
    """
    attrs = el.attributes
    parts = [
        el.tag,
        el.role,
        attrs.get("name", ""),
        attrs.get("id", ""),
        attrs.get("data-testid", ""),
        str(el.index_in_type),
    ]
    return "|".join(parts)


def _compare_elements(before: ElementMeta, after: ElementMeta) -> list[ElementChange]:
    """Compara dois elementos matched e retorna lista de mudancas."""
    changes: list[ElementChange] = []

    # Comparar texto
    if before.text != after.text:
        changes.append(ElementChange(
            element=after, field="text",
            old_value=before.text, new_value=after.text,
        ))

    # Comparar atributos
    all_keys = set(before.attributes) | set(after.attributes)
    for key in sorted(all_keys):
        old_val = before.attributes.get(key)
        new_val = after.attributes.get(key)
        if old_val != new_val:
            changes.append(ElementChange(
                element=after, field=f"attr:{key}",
                old_value=old_val, new_value=new_val,
            ))

    # Comparar bbox (posicao visual)
    if before.bbox != after.bbox:
        changes.append(ElementChange(
            element=after, field="bbox",
            old_value=before.bbox, new_value=after.bbox,
        ))

    return changes


def diff_snapshots(before: DOMSnapshot, after: DOMSnapshot) -> PageDiff:
    """Compara dois DOMSnapshots e retorna as diferencas.

    Args:
        before: Snapshot antes da acao.
        after: Snapshot depois da acao.

    Returns:
        PageDiff com elementos added, removed e changed.
    """
    # Indexar elementos por fingerprint
    before_map: dict[str, ElementMeta] = {}
    for el in before.elements:
        fp = _element_fingerprint(el)
        before_map[fp] = el

    after_map: dict[str, ElementMeta] = {}
    for el in after.elements:
        fp = _element_fingerprint(el)
        after_map[fp] = el

    before_keys = set(before_map)
    after_keys = set(after_map)

    # Elementos adicionados (no after, nao no before)
    added = [after_map[k] for k in sorted(after_keys - before_keys)]

    # Elementos removidos (no before, nao no after)
    removed = [before_map[k] for k in sorted(before_keys - after_keys)]

    # Elementos mudados (presentes em ambos)
    changed: list[ElementChange] = []
    for k in sorted(before_keys & after_keys):
        changes = _compare_elements(before_map[k], after_map[k])
        changed.extend(changes)

    return PageDiff(
        added=added,
        removed=removed,
        changed=changed,
        before_url=before.url,
        after_url=after.url,
    )


async def page_diff(
    page: object,
    config: DOMSerializerConfig | None = None,
) -> tuple[DOMSnapshot, Callable[[], Awaitable[PageDiff]]]:
    """Captura snapshot "antes" e retorna funcao para capturar "depois" e calcular diff.

    Uso:
        before_snap, finish = await page_diff(page)
        # ... acao na pagina ...
        diff = await finish()

    Args:
        page: Playwright Page object.
        config: Configuracao do DOM serializer.

    Returns:
        Tupla (before_snapshot, finish_fn).
        finish_fn captura o snapshot "depois" e retorna PageDiff.
    """
    from smartwright.resolver.dom_serializer import serialize_dom

    before = await serialize_dom(page, config)

    async def finish() -> PageDiff:
        after = await serialize_dom(page, config)
        return diff_snapshots(before, after)

    return before, finish
