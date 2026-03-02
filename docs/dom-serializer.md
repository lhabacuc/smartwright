# DOM Serializer

## Proposito

O DOM Serializer transforma a pagina web em texto compacto e indexado, ideal para consumo por LLMs. Cada elemento interativo recebe um indice `[N]` que mapeia para metadata completa (selectors, bbox, atributos), permitindo interacao via `to_capture()` + `emergency_click_captured()`.

## Formato de saida

```
[1] <button>Login</button>
[2] <input type="email" placeholder="Email"/>
[3] <input type="password" placeholder="Senha"/>
[4] <a href="/register">Criar conta</a>
[5] <select name="idioma"> [PT-BR, *EN, ES] </select>
```

- `[N]` -- indice numerico (1-based) que mapeia para metadata
- Tags com atributos relevantes (type, name, placeholder, aria-label, role, href)
- Texto do elemento entre tags
- Inputs e imagens usam formato self-closing (`<input .../>`)
- Selects mostram opcoes inline com `*` indicando a opcao selecionada
- Estados: `checked`, `disabled`, `readonly`, `contenteditable`
- Landmarks como prefixo: `  nav > [1] <a href="/">Home</a>`

## Presets de configuracao

### DOMSerializerConfig

```python
from smartwright.resolver.dom_serializer import DOMSerializerConfig
```

| Opcao | Tipo | Default | Descricao |
|-------|------|---------|-----------|
| `include_headings` | bool | False | Inclui h1-h6 na saida |
| `include_images` | bool | False | Inclui img com alt |
| `include_text` | bool | False | Inclui p, li, label, figcaption |
| `viewport_only` | bool | False | So elementos visiveis no viewport |
| `include_landmarks` | bool | False | Prefixo nav/main/footer/aside |
| `max_elements` | int | 500 | Limite de elementos |
| `max_text_length` | int | 80 | Trunca texto de elementos |
| `max_option_count` | int | 15 | Max opcoes de select |
| `max_href_length` | int | 80 | Trunca URLs |
| `skip_disabled` | bool | False | Ignora elementos disabled |
| `skip_hidden_inputs` | bool | True | Ignora input[type=hidden] |

### Preset compact

Minimo de tokens, ideal para contextos com limite de tokens:

```python
config = DOMSerializerConfig.compact()
# max_elements=200, max_text_length=50, max_option_count=8
```

### Preset verbose

Rico em informacoes, com headings, imagens e landmarks:

```python
config = DOMSerializerConfig.verbose()
# include_headings=True, include_images=True, include_landmarks=True
# max_elements=500, max_text_length=120
```

## DOMSnapshot

O resultado da serializacao e um objeto `DOMSnapshot` com:

| Atributo | Tipo | Descricao |
|----------|------|-----------|
| `.text` | str | Texto formatado com todos os elementos indexados |
| `.elements` | list[ElementMeta] | Lista de metadados por elemento |
| `.stats` | dict[str, int] | Contagem por tipo (button, input, a, etc.) |
| `.url` | str | URL da pagina |
| `.title` | str | Titulo da pagina |
| `.element_count` | int | Total de elementos |

### Metodos do DOMSnapshot

```python
# Buscar metadata por indice [N] (1-based)
el = snapshot.get_element(3)
# ElementMeta(index=3, tag='input', role='', selectors=[...], bbox={...}, ...)

# Converter para formato capture (compativel com relocate_from_capture)
capture = snapshot.to_capture(3)
# dict com tag, index_in_type, total_in_type, text, attributes, bbox, selectors, visible
```

### ElementMeta

Cada elemento no `snapshot.elements` tem:

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `index` | int | Indice 1-based |
| `tag` | str | Tag HTML (button, input, a, etc.) |
| `role` | str | Role ARIA |
| `selectors` | list[str] | CSS selectors para relocacao |
| `bbox` | dict[str, int] | Posicao e tamanho (x, y, w, h, cx, cy) |
| `index_in_type` | int | Indice ordinal entre elementos do mesmo tipo |
| `total_in_type` | int | Total de elementos do mesmo tipo na pagina |
| `text` | str | Texto do elemento |
| `attributes` | dict[str, str] | Atributos relevantes |
| `landmark` | str | Landmark ancestral (nav, main, footer, etc.) |

## Uso basico

```python
import asyncio
from playwright.async_api import async_playwright
from smartwright import Smartwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://example.com/login")

        sw = Smartwright(page=page, request_context=context.request)

        # Serializar DOM completo
        snapshot = await sw.dom_snapshot()
        print(snapshot.text)
        print(f"Total: {snapshot.element_count} elementos")
        print(f"Stats: {snapshot.stats}")

        await browser.close()

asyncio.run(main())
```

Saida tipica:

```
[1] <input type="email" name="email" placeholder="Email"/>
[2] <input type="password" name="password" placeholder="Senha"/>
[3] <button>Entrar</button>
[4] <a href="/register">Criar conta</a>
[5] <a href="/forgot-password">Esqueci minha senha</a>
Total: 5 elementos
Stats: {'input': 2, 'button': 1, 'a': 2}
```

## Com configuracao personalizada

```python
from smartwright.resolver.dom_serializer import DOMSerializerConfig

# So elementos no viewport, com headings e landmarks
config = DOMSerializerConfig(
    viewport_only=True,
    include_headings=True,
    include_landmarks=True,
    max_elements=100,
)

snapshot = await sw.dom_snapshot(config)
print(snapshot.text)
```

## Apenas o texto (sem metadata)

```python
# Retorna apenas a string formatada
texto = await sw.dom_snapshot_text()
print(texto)
```

## Integracao com capture/relocate

O principal uso do DOMSnapshot e conectar a saida do LLM com acoes reais. O LLM escolhe um indice `[N]` e voce usa `to_capture()` para interagir:

```python
# 1. Serializar DOM para o LLM
snapshot = await sw.dom_snapshot()

# 2. Enviar para o LLM
resposta_llm = await chamar_llm(f"Escolha o elemento para clicar:\n{snapshot.text}")
# LLM responde: "Clique no elemento [3]"

# 3. Extrair indice e converter para capture
indice = 3
capture = snapshot.to_capture(indice)

# 4. Clicar usando o sistema de captura existente
await sw.emergency_click_captured(capture)
```

### Exemplo com fill

```python
snapshot = await sw.dom_snapshot()

# LLM decide: preencher elemento [2] com "user@test.com"
capture = snapshot.to_capture(2)
await sw.emergency_fill_captured(capture, "user@test.com")
```

### Exemplo com relocate

```python
snapshot = await sw.dom_snapshot()
capture = snapshot.to_capture(5)

# Relocar e interagir diretamente
locator = await sw.emergency_relocate(capture)
texto = await locator.inner_text()
print(f"Texto do elemento [5]: {texto}")
```

## Uso direto (sem Smartwright)

```python
from smartwright.resolver.dom_serializer import serialize_dom, serialize_dom_text, DOMSerializerConfig

# Texto apenas
texto = await serialize_dom_text(page)

# Snapshot completo
config = DOMSerializerConfig.verbose()
snapshot = await serialize_dom(page, config)

# Iterar elementos
for el in snapshot.elements:
    print(f"[{el.index}] {el.tag} text='{el.text}' selectors={el.selectors}")
```

## Selectors gerados

Para cada elemento, o serializer gera multiplos selectors para relocacao:

1. `#id` -- se o elemento tem id
2. `[data-testid='...']` -- se tem data-testid
3. `tag[aria-label='...']` -- se tem aria-label
4. `tag[name='...']` -- se tem name
5. `tag[placeholder='...']` -- se tem placeholder
6. `tag.class1.class2` -- ate 3 classes (filtra numeros)
7. `parent > tag:nth-of-type(N)` -- selector estrutural
