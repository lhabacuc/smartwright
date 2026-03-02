# Replay Adaptativo

## O problema

Sites modernos com frameworks CSS-in-JS (Tailwind, Styled Components, CSS Modules) geram classes e IDs dinamicos que mudam a cada build:

```html
<!-- Deploy v1 -->
<button class="sc-1a2b3c4 kJHfds">Entrar</button>

<!-- Deploy v2 — mesmo botao, classes novas -->
<button class="sc-9x8y7z qWerty">Entrar</button>
```

Selectors CSS tradicionais (`button.sc-1a2b3c4`) quebram imediatamente. O replay adaptativo resolve isso ignorando IDs e classes e usando **fingerprint semantico**: texto, tag, tipo de input, placeholder, aria-label, name, role e posicao visual.

## A solucao: fingerprint semantico

O fingerprint semantico captura a **identidade funcional** de um elemento, nao sua identidade CSS. Dois elementos sao o "mesmo" se fazem a mesma coisa, nao se tem a mesma classe.

### SemanticFingerprint

Dataclass que armazena a identidade semantica:

```python
@dataclass(frozen=True, slots=True)
class SemanticFingerprint:
    tag: str              # button, input, a, select, textarea
    text: str             # innerText (ate 200 chars)
    input_type: str       # text, email, password, checkbox...
    placeholder: str      # placeholder do input
    aria_label: str       # aria-label do elemento
    name: str             # atributo name
    role: str             # role ARIA (button, link, checkbox...)
    href_pattern: str     # href normalizado (IDs dinamicos -> {id})
    value: str            # valor pre-preenchido
    region: str           # quadrante visual: top-left, mid-center...
    action_type: str      # click, fill, select, etc.
```

### Extracao do fingerprint

O fingerprint e extraido automaticamente de cada acao gravada:

```python
from smartwright.resolver.adaptive_replay import extract_fingerprint

action = {
    "action": "fill",
    "capture": {
        "tag": "input",
        "text": "",
        "attributes": {
            "type": "email",
            "placeholder": "Digite seu email",
            "name": "user_email",
            "aria-label": "Campo de email",
        },
        "bbox": {"cx": 640, "cy": 200},
    },
}

fp = extract_fingerprint(action)
# SemanticFingerprint(
#     tag='input',
#     input_type='email',
#     placeholder='Digite seu email',
#     aria_label='Campo de email',
#     name='user_email',
#     region='top-center',
#     action_type='fill',
# )
```

## Algoritmo de scoring

Cada candidato na pagina atual e pontuado contra o fingerprint. O algoritmo segue esta tabela de pesos:

| Atributo | Peso | Tipo de match |
|----------|------|---------------|
| **Texto** | 40 pts | Fuzzy (token Jaccard + substring + bigrams) |
| **Tipo de input** | 25 pts | Exato. Penalidade de -15 se tipo errado |
| **Placeholder** | 20 pts | Fuzzy |
| **aria-label** | 20 pts | Fuzzy |
| **name** | 15 pts | Exato |
| **href pattern** | 15 pts | Fuzzy (URL normalizada) |
| **Role** | 10 pts | Exato |
| **Regiao visual** | 10 pts | Exato (10) ou adjacente (4) |

**Score maximo teorico:** 155 pts (todos os atributos com match perfeito).

**Threshold minimo:** 15 pts. Candidatos abaixo disso sao rejeitados.

### Filtro de tag

Antes do scoring, o algoritmo verifica se a tag e compativel. Tags equivalentes sao aceitas:

- `button` aceita: `button`, `div`, `span`, `a` (role=button)
- `a` aceita: `a`, `button`
- `input`, `textarea`, `select`: match exato apenas

Se a tag nao e compativel, o candidato recebe score `-1` e e descartado.

### Similaridade de texto

A funcao de similaridade usa tres niveis:

1. **Token Jaccard**: intersecao/uniao de palavras
2. **Substring**: se um texto contem o outro
3. **Bigram**: similaridade de pares de caracteres (fallback)

```python
# Exemplo interno
_text_similarity("Entrar na conta", "Entrar")  # ~0.5 (Jaccard)
_text_similarity("Email", "E-mail")             # ~0.8 (substring)
_text_similarity("Login", "Logn")               # ~0.5 (bigrams)
```

### Regiao visual

O viewport e dividido em grid 3x3:

```
top-left     | top-center    | top-right
mid-left     | mid-center    | mid-right
bottom-left  | bottom-center | bottom-right
```

- Match exato da regiao: +10 pts
- Regiao adjacente (1 celula de distancia): +4 pts

### Normalizacao de href

URLs com IDs dinamicos sao normalizados:

```
/api/users/123/posts       -> /api/users/{id}/posts
/product/a1b2c3d4-e5f6     -> /product/{id}
/order/5f4dcc3b5aa765d61d8 -> /order/{id}
```

## Usando o replay adaptativo

### Replay direto

```python
import asyncio
from playwright.async_api import async_playwright
from smartwright import Smartwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        sw = Smartwright(page=page, request_context=context.request)
        await page.goto("https://app.exemplo.com")

        # Replay adaptativo a partir de arquivo JSON
        results = await sw.replay_adaptive("recording.json")

        for r in results:
            print(f"Step {r['step']}: {r['status']}")

        await browser.close()

asyncio.run(main())
```

### Replay via modo

```python
results = await sw.emergency_replay_json(
    "recording.json",
    mode="adaptativo",
    debug=True,
    screenshot_dir="debug_adaptive",
)
```

### Pre-analise sem executar

`replay_adaptive_analyze()` analisa todos os matches sem executar nenhuma acao. Util para validar um recording antes do replay:

```python
diagnostico = await sw.replay_adaptive_analyze("recording.json")

for item in diagnostico:
    step = item["step"]
    action = item["action"]
    score = item["score"]
    confident = item.get("confident", False)

    if action in ("goto", "scroll", "press_keys", "wait"):
        print(f"  Step {step}: {action} (n/a)")
        continue

    fp = item.get("fingerprint", {})
    match = item.get("match", {})

    status = "OK" if confident else "RISCO"
    print(f"  Step {step}: {action} -> score={score} [{status}]")
    print(f"    Fingerprint: tag={fp.get('tag')} text='{fp.get('text', '')[:30]}'")
    if match:
        print(f"    Match:       tag={match.get('tag')} text='{match.get('text', '')[:30]}'")
```

## Cadeia de fallback interna

Quando o fingerprint identifica o melhor candidato, a resolucao para Playwright locator segue esta cadeia:

1. **Selectors estaveis** -- `[name="..."]`, `[aria-label="..."]`, `[placeholder="..."]`, `[data-testid="..."]` (pula `nth-of-type`)
2. **Tag + texto** -- `page.locator("button").filter(has_text="Login")`
3. **get_by_text** -- `page.get_by_text("Login", exact=False)`
4. **nth-of-type** -- `parent > tag:nth-of-type(N)` (selector estrutural)
5. **Coordenadas** -- `page.mouse.click(cx, cy)` (ultimo recurso)

## to_capture(): integracao com sistema de captura

O resultado do matching adaptativo pode ser convertido de volta para o formato `capture` usado pelo `relocate_from_capture()`:

```python
from smartwright.resolver.adaptive_replay import adaptive_resolve

# Resolve elemento adaptativo
locator = await adaptive_resolve(page, action_dict)

# Interagir
await locator.click()
```

## Coleta de candidatos

A coleta de elementos interativos e feita com uma unica `page.evaluate()` que retorna todos os elementos visiveis do tipo:

- `button`, `input`, `textarea`, `select`, `a[href]`
- `[role="button"]`, `[role="link"]`, `[role="checkbox"]`
- `[role="tab"]`, `[role="menuitem"]`, `[role="radio"]`
- `[role="switch"]`, `[role="combobox"]`, `[contenteditable="true"]`

Elementos ocultos (display:none, visibility:hidden, opacity:0, width/height 0) e inputs hidden sao filtrados automaticamente.

Cada candidato retorna: tag, index_in_type, text, type, name, placeholder, aria_label, role, href, value, checked, disabled, bbox e selectors estaveis.

## Dicas praticas

1. **O replay adaptativo funciona melhor com recordings que tem `capture` rico** -- acoes gravadas pelo ActionRecorder ja incluem todos os atributos necessarios.

2. **Use `replay_adaptive_analyze()` antes de executar** -- identifica steps com score baixo antes de rodar o fluxo inteiro.

3. **Se um step falha no adaptativo, tente `mix`** -- o modo mix usa a cadeia de resolucao completa com 3 retries e e mais tolerante.

4. **Threshold 15 e conservador** -- na pratica, matches bons ficam acima de 40 pts. Scores entre 15-30 indicam match possivel mas impreciso.

5. **Nao precisa de LLM** -- todo o matching e feito por heuristicas locais. Zero custo de API, zero latencia de rede.
