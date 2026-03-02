"""DOM Serializer — transforma pagina em texto compacto para LLM.

Extrai elementos interativos da pagina com uma unica page.evaluate() call
e formata como texto indexado:

    [1] <button>Login</button>
    [2] <input type="email" placeholder="Email"/>
    [3] <input type="password" placeholder="Senha"/>
    [4] <a href="/register">Criar conta</a>
    [5] <select name="idioma"> [PT-BR, *EN, ES] </select>

Cada indice [N] mapeia para metadata (selectors, bbox, tag, index_in_type)
que permite interacao via relocate_from_capture() existente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Config ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DOMSerializerConfig:
    """Configuracao do DOM Serializer."""

    # Elementos extras alem dos interativos
    include_headings: bool = False
    include_images: bool = False
    include_text: bool = False
    viewport_only: bool = False
    include_landmarks: bool = False

    # Limites
    max_elements: int = 500
    max_text_length: int = 80
    max_option_count: int = 15
    max_href_length: int = 80

    # Filtros
    skip_disabled: bool = False
    skip_hidden_inputs: bool = True

    @classmethod
    def compact(cls) -> DOMSerializerConfig:
        """Preset minimo para contextos com poucos tokens."""
        return cls(max_elements=200, max_text_length=50, max_option_count=8)

    @classmethod
    def verbose(cls) -> DOMSerializerConfig:
        """Preset rico com headings, imagens e landmarks."""
        return cls(
            include_headings=True,
            include_images=True,
            include_landmarks=True,
            max_elements=500,
            max_text_length=120,
        )


# ── Metadata ──────────────────────────────────────────────────────────


@dataclass(slots=True)
class ElementMeta:
    """Metadata de um elemento serializado, permite interacao por indice."""

    index: int
    tag: str
    role: str
    selectors: list[str]
    bbox: dict[str, int]
    index_in_type: int
    total_in_type: int
    text: str
    attributes: dict[str, str]
    landmark: str = ""


@dataclass
class DOMSnapshot:
    """Resultado completo da serializacao do DOM."""

    text: str
    elements: list[ElementMeta]
    stats: dict[str, int]
    url: str
    title: str
    element_count: int = 0

    def get_element(self, index: int) -> ElementMeta | None:
        """Busca metadata pelo indice [N] (1-based)."""
        if 1 <= index <= len(self.elements):
            return self.elements[index - 1]
        return None

    def to_capture(self, index: int) -> dict[str, Any]:
        """Converte [N] em dict compativel com relocate_from_capture()."""
        el = self.get_element(index)
        if el is None:
            raise IndexError(f"Nenhum elemento no indice [{index}]")
        return {
            "tag": el.tag,
            "index_in_type": el.index_in_type,
            "total_in_type": el.total_in_type,
            "text": el.text,
            "attributes": el.attributes,
            "bbox": el.bbox,
            "selectors": el.selectors,
            "visible": True,
        }


# ── JavaScript — single-pass DOM traversal ────────────────────────────

_JS_SERIALIZE_DOM = """
(config) => {
  const {
    includeHeadings, includeImages, includeText, viewportOnly,
    includeLandmarks, maxElements, maxTextLength, maxOptionCount,
    maxHrefLength, skipDisabled, skipHiddenInputs
  } = config;

  const vw = window.innerWidth;
  const vh = window.innerHeight;

  const INTERACTIVE_ROLES = new Set([
    'button', 'link', 'checkbox', 'tab', 'menuitem',
    'radio', 'switch', 'slider', 'spinbutton', 'combobox',
    'searchbox', 'option', 'menuitemcheckbox', 'menuitemradio'
  ]);

  const LANDMARK_TAGS = new Set([
    'NAV', 'MAIN', 'FOOTER', 'ASIDE', 'HEADER', 'FORM', 'SECTION'
  ]);

  const LANDMARK_ROLES = new Set([
    'navigation', 'main', 'contentinfo', 'complementary',
    'banner', 'form', 'region', 'search'
  ]);

  function findLandmark(el) {
    if (!includeLandmarks) return '';
    let node = el.parentElement;
    while (node && node !== document.body) {
      if (LANDMARK_TAGS.has(node.tagName)) {
        const label = node.getAttribute('aria-label') || node.id || '';
        const tag = node.tagName.toLowerCase();
        return label ? tag + '[' + label + ']' : tag;
      }
      const role = node.getAttribute('role');
      if (role && LANDMARK_ROLES.has(role)) {
        const label = node.getAttribute('aria-label') || node.id || '';
        return role + (label ? '[' + label + ']' : '');
      }
      node = node.parentElement;
    }
    return '';
  }

  function isVisible(el) {
    if (el.offsetWidth === 0 && el.offsetHeight === 0) return false;
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    if (style.opacity === '0') return false;
    return true;
  }

  function isInViewport(rect) {
    return rect.bottom > 0 && rect.top < vh && rect.right > 0 && rect.left < vw;
  }

  function buildSelectors(el, tag) {
    const sels = [];
    if (el.id) sels.push('#' + CSS.escape(el.id));

    const testId = el.getAttribute('data-testid');
    if (testId) sels.push("[data-testid='" + testId.replace(/'/g, "\\\\'") + "']");

    const ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel) sels.push(tag + "[aria-label='" + ariaLabel.replace(/'/g, "\\\\'") + "']");

    const name = el.getAttribute('name');
    if (name) sels.push(tag + "[name='" + name.replace(/'/g, "\\\\'") + "']");

    const placeholder = el.getAttribute('placeholder');
    if (placeholder) sels.push(tag + "[placeholder='" + placeholder.replace(/'/g, "\\\\'") + "']");

    const classes = Array.from(el.classList || [])
      .filter(c => c.length > 1 && !/^[0-9]/.test(c))
      .slice(0, 3);
    if (classes.length > 0) {
      sels.push(tag + '.' + classes.map(c => CSS.escape(c)).join('.'));
    }

    const parent = el.parentElement;
    if (parent) {
      const siblings = Array.from(parent.children).filter(s => s.tagName === el.tagName);
      const idx = siblings.indexOf(el);
      if (idx >= 0) {
        const prefix = parent.id
          ? '#' + CSS.escape(parent.id) + ' > '
          : parent.tagName.toLowerCase() + ' > ';
        sels.push(prefix + tag + ':nth-of-type(' + (idx + 1) + ')');
      }
    }
    return sels;
  }

  function getSelectOptions(el) {
    const opts = Array.from(el.options).slice(0, maxOptionCount);
    const total = el.options.length;
    return {
      items: opts.map(o => ({
        text: o.text.trim().slice(0, 40),
        value: o.value,
        selected: o.selected,
      })),
      total: total,
    };
  }

  // Cache tag counters para evitar O(N^2)
  const tagCounters = {};

  function getTypeIndex(el, tag) {
    if (!tagCounters[tag]) {
      const all = document.querySelectorAll(tag);
      const map = new Map();
      all.forEach((e, i) => map.set(e, i));
      tagCounters[tag] = { map, total: all.length };
    }
    const entry = tagCounters[tag];
    return {
      index_in_type: entry.map.get(el) ?? -1,
      total_in_type: entry.total,
    };
  }

  // Selector combinado
  let selector = 'button, input, textarea, select, a, ' +
    '[role="button"], [role="link"], [role="checkbox"], [role="tab"], ' +
    '[role="menuitem"], [role="radio"], [role="switch"], [role="combobox"], ' +
    '[role="searchbox"], [contenteditable="true"]';

  if (includeHeadings) selector += ', h1, h2, h3, h4, h5, h6';
  if (includeImages) selector += ', img[alt]';
  if (includeText) selector += ', p, li, label, figcaption';

  const elements = document.querySelectorAll(selector);
  const results = [];

  for (let i = 0; i < elements.length && results.length < maxElements; i++) {
    const el = elements[i];
    const tn = el.tagName;

    // Skip containers proibidos
    if (el.closest('template, script, style, noscript')) continue;

    // Skip hidden inputs
    if (skipHiddenInputs && tn === 'INPUT' && el.type === 'hidden') continue;

    // Skip disabled
    if (skipDisabled && el.disabled) continue;

    // Visibilidade
    if (!isVisible(el)) continue;

    const rect = el.getBoundingClientRect();

    // Viewport filter
    if (viewportOnly && !isInViewport(rect)) continue;

    const tag = tn.toLowerCase();
    const role = el.getAttribute('role') || '';
    const typeInfo = getTypeIndex(el, tag);

    const text = (el.innerText || el.textContent || '').trim().slice(0, maxTextLength);

    const item = {
      tag,
      role,
      type: el.type || '',
      text,
      value: (tn === 'INPUT' || tn === 'TEXTAREA') ? (el.value || '').slice(0, maxTextLength) : '',
      name: el.name || '',
      id: el.id || '',
      href: (el.href || '').slice(0, maxHrefLength),
      src: (el.src || '').slice(0, maxHrefLength),
      alt: (el.alt || '').slice(0, maxTextLength),
      placeholder: el.placeholder || '',
      'aria-label': el.getAttribute('aria-label') || '',
      checked: !!el.checked,
      disabled: !!el.disabled,
      readOnly: !!el.readOnly,
      contentEditable: el.contentEditable === 'true',
      bbox: {
        x: Math.round(rect.x), y: Math.round(rect.y),
        w: Math.round(rect.width), h: Math.round(rect.height),
        cx: Math.round(rect.x + rect.width / 2),
        cy: Math.round(rect.y + rect.height / 2),
      },
      index_in_type: typeInfo.index_in_type,
      total_in_type: typeInfo.total_in_type,
      selectors: buildSelectors(el, tag),
      landmark: findLandmark(el),
    };

    // Select: opcoes inline
    if (tn === 'SELECT') {
      item.options = getSelectOptions(el);
    }

    results.push(item);
  }

  return {
    elements: results,
    url: location.href,
    title: document.title,
  };
}
"""


# ── Formatacao ─────────────────────────────────────────────────────────


def _format_element_line(index: int, el: dict[str, Any]) -> str:
    """Formata um elemento como [N] <tag attrs>text</tag>."""
    tag = el["tag"]

    # Landmark prefix
    landmark = el.get("landmark", "")
    prefix = f"  {landmark} > " if landmark else ""

    # Atributos relevantes
    attrs: list[str] = []

    el_type = el.get("type", "")
    if tag == "input" and el_type and el_type != "text":
        attrs.append(f'type="{el_type}"')

    name = el.get("name", "")
    if name:
        attrs.append(f'name="{name}"')

    el_id = el.get("id", "")
    if el_id:
        attrs.append(f'id="{el_id}"')

    placeholder = el.get("placeholder", "")
    if placeholder:
        attrs.append(f'placeholder="{placeholder}"')

    aria_label = el.get("aria-label", "")
    if aria_label:
        attrs.append(f'aria-label="{aria_label}"')

    role = el.get("role", "")
    if role and tag not in ("button", "a", "input", "select", "textarea"):
        attrs.append(f'role="{role}"')

    href = el.get("href", "")
    if href and tag == "a":
        attrs.append(f'href="{href}"')

    alt = el.get("alt", "")
    if alt and tag == "img":
        attrs.append(f'alt="{alt}"')

    src = el.get("src", "")
    if src and tag == "img":
        attrs.append(f'src="{src}"')

    # Estados
    if el.get("checked"):
        attrs.append("checked")
    if el.get("disabled"):
        attrs.append("disabled")
    if el.get("readOnly"):
        attrs.append("readonly")
    if el.get("contentEditable"):
        attrs.append("contenteditable")

    # Valor atual de inputs/textareas
    value = el.get("value", "")
    if value and tag in ("input", "textarea"):
        attrs.append(f'value="{value}"')

    attr_str = " " + " ".join(attrs) if attrs else ""

    text = el.get("text", "")

    # Select: opcoes inline
    if tag == "select" and el.get("options"):
        opt_info = el["options"]
        items = opt_info.get("items", []) if isinstance(opt_info, dict) else opt_info
        total = opt_info.get("total", len(items)) if isinstance(opt_info, dict) else len(items)
        opt_strs = []
        for o in items:
            t = o.get("text", o.get("value", ""))
            if o.get("selected"):
                opt_strs.append(f"*{t}")
            else:
                opt_strs.append(t)
        content = " [" + ", ".join(opt_strs)
        if total > len(items):
            content += f", ...+{total - len(items)}"
        content += "] "
        return f"{prefix}[{index}] <{tag}{attr_str}>{content}</{tag}>"

    # Self-closing: input, img
    if tag in ("input", "img"):
        return f"{prefix}[{index}] <{tag}{attr_str}/>"

    # Elementos com texto
    if text:
        return f"{prefix}[{index}] <{tag}{attr_str}>{text}</{tag}>"

    # Sem texto: self-closing style
    return f"{prefix}[{index}] <{tag}{attr_str}/>"


# ── Serialize ──────────────────────────────────────────────────────────


async def serialize_dom(
    page: object,
    config: DOMSerializerConfig | None = None,
) -> DOMSnapshot:
    """Serializa o DOM da pagina num formato compacto para LLM.

    Executa uma unica page.evaluate() para extrair todos os elementos
    interativos e formata como texto indexado com metadata de relocacao.
    """
    if config is None:
        config = DOMSerializerConfig()

    evaluate = getattr(page, "evaluate", None)
    if not callable(evaluate):
        return DOMSnapshot(text="", elements=[], stats={}, url="", title="")

    js_config = {
        "includeHeadings": config.include_headings,
        "includeImages": config.include_images,
        "includeText": config.include_text,
        "viewportOnly": config.viewport_only,
        "includeLandmarks": config.include_landmarks,
        "maxElements": config.max_elements,
        "maxTextLength": config.max_text_length,
        "maxOptionCount": config.max_option_count,
        "maxHrefLength": config.max_href_length,
        "skipDisabled": config.skip_disabled,
        "skipHiddenInputs": config.skip_hidden_inputs,
    }

    try:
        raw = await evaluate(_JS_SERIALIZE_DOM, js_config)
    except Exception:
        return DOMSnapshot(text="", elements=[], stats={}, url="", title="")

    if not raw or not raw.get("elements"):
        return DOMSnapshot(
            text="",
            elements=[],
            stats={},
            url=raw.get("url", "") if raw else "",
            title=raw.get("title", "") if raw else "",
        )

    lines: list[str] = []
    elements: list[ElementMeta] = []
    stats: dict[str, int] = {}

    for i, el in enumerate(raw["elements"], start=1):
        # Atributos relevantes para metadata
        meta_attrs: dict[str, str] = {}
        for k in ("type", "name", "id", "href", "placeholder", "aria-label", "alt", "src", "value"):
            v = el.get(k, "")
            if v:
                meta_attrs[k] = v

        meta = ElementMeta(
            index=i,
            tag=el["tag"],
            role=el.get("role", ""),
            selectors=el.get("selectors", []),
            bbox=el.get("bbox", {}),
            index_in_type=el.get("index_in_type", -1),
            total_in_type=el.get("total_in_type", 0),
            text=el.get("text", ""),
            attributes=meta_attrs,
            landmark=el.get("landmark", ""),
        )
        elements.append(meta)

        # Stats por categoria
        cat = el["tag"]
        if cat in ("h1", "h2", "h3", "h4", "h5", "h6"):
            cat = "heading"
        elif cat == "img":
            cat = "image"
        stats[cat] = stats.get(cat, 0) + 1

        # Formata linha de texto
        lines.append(_format_element_line(i, el))

    text = "\n".join(lines)

    return DOMSnapshot(
        text=text,
        elements=elements,
        stats=stats,
        url=raw.get("url", ""),
        title=raw.get("title", ""),
        element_count=len(elements),
    )


async def serialize_dom_text(
    page: object,
    config: DOMSerializerConfig | None = None,
) -> str:
    """Conveniencia: retorna apenas o texto formatado."""
    snapshot = await serialize_dom(page, config)
    return snapshot.text
