# run_json() -- Executar JSON manual

## Proposito

`run_json()` permite executar acoes escritas manualmente em JSON, sem precisar gravar com o ActionRecorder. Aceita JSON minimo, suporta aliases de acoes e nomes de campos flexiveis, e continua em caso de erro por padrao.

## Diferenca para replay_actions()

| Aspecto | `replay_actions()` | `run_json()` |
|---------|-------------------|-------------|
| Entrada | JSON do ActionRecorder (campos completos) | JSON minimo escrito a mao |
| Campos obrigatorios | action, element_type, index, capture | Apenas `action` + campos essenciais |
| Aliases | Nao | Sim (`press` -> `press_keys`, `type` -> `fill`, etc.) |
| Erro | Para no primeiro erro | Continua por padrao (`continue_on_error=True`) |
| base_url | Nao | Sim (resolve URLs relativas) |
| Acoes extras | Nao | `go_back`, `go_forward`, `reload`, `eval_js`, operacoes de arquivo |

## Formato minimo por acao

Cada acao precisa apenas do campo `action` e dos campos relevantes para aquela acao:

```json
[
    {"action": "goto", "url": "https://example.com"},
    {"action": "fill", "selector": "#email", "value": "user@test.com"},
    {"action": "fill", "text": "Senha", "value": "123456"},
    {"action": "click", "text": "Entrar"},
    {"action": "wait", "ms": 2000},
    {"action": "screenshot", "path": "resultado.png"}
]
```

## Todas as acoes suportadas

### Navegacao

```json
{"action": "goto", "url": "https://example.com"}
{"action": "go_back"}
{"action": "go_forward"}
{"action": "reload"}
```

### Interacao com elementos

```json
{"action": "click", "selector": "#btn-enviar"}
{"action": "click", "text": "Enviar"}
{"action": "click", "tag": "button", "index": 2}

{"action": "fill", "selector": "#email", "value": "a@b.com"}
{"action": "fill", "text": "Email", "value": "a@b.com"}
{"action": "fill", "tag": "input", "index": 0, "value": "a@b.com"}

{"action": "check", "selector": "#aceito-termos", "checked": true}
{"action": "check", "text": "Aceito os termos"}

{"action": "select", "selector": "select[name='pais']", "value": "BR"}
{"action": "select", "tag": "select", "index": 0, "option": "Brasil"}

{"action": "select_custom", "text": "Brasil"}

{"action": "select_radio", "name": "genero", "value": "masculino"}

{"action": "upload", "tag": "input", "index": 0, "file": "/path/to/arquivo.pdf"}
```

### Teclado

```json
{"action": "press_keys", "value": "Enter"}
{"action": "press_keys", "value": "Control+a"}
{"action": "press_keys", "key": "Tab"}
```

### Scroll

```json
{"action": "scroll", "direction": "down", "pixels": 500}
{"action": "scroll", "direction": "up", "px": 300}
```

### Espera

```json
{"action": "wait", "ms": 2000}
{"action": "wait_text", "value": "Sucesso"}
{"action": "wait_url", "value": "/dashboard"}
{"action": "wait_element", "selector": "#resultado"}
```

### Captura

```json
{"action": "screenshot", "path": "pagina.png"}
```

### JavaScript

```json
{"action": "eval_js", "code": "document.title"}
{"action": "eval_js", "script": "window.scrollTo(0, 0)"}
```

### Download e Clipboard

```json
{"action": "wait_download", "save_dir": "downloads"}
{"action": "wait_clipboard"}
{"action": "copy_to_clipboard", "value": "texto copiado"}
```

### Dialogs

```json
{"action": "dialog", "dialog_action": "accept"}
{"action": "dialog", "dialog_action": "dismiss", "value": "resposta do prompt"}
```

### Drag and Drop

```json
{"action": "drag_drop", "source": "#item1", "target": "#zona-drop"}
```

### Operacoes de arquivo

```json
{"action": "read_file", "path": "dados.txt"}
{"action": "write_file", "path": "output.txt", "content": "resultado", "append": false}
{"action": "list_files", "dir": ".", "pattern": "*.json", "recursive": true}
{"action": "file_exists", "path": "config.json"}
{"action": "delete_file", "path": "temp.txt"}
{"action": "copy_file", "src": "a.txt", "dst": "b.txt"}
{"action": "move_file", "src": "old.txt", "dst": "new.txt"}
```

## Aliases de acoes

Voce pode usar nomes alternativos para as acoes:

| Alias | Acao real |
|-------|----------|
| `press`, `press_key`, `keys`, `key` | `press_keys` |
| `type`, `input`, `write` | `fill` |
| `navigate`, `open`, `nav`, `go` | `goto` |
| `tap` | `click` |
| `select_option` | `select` |
| `dropdown` | `select_custom` |
| `radio` | `select_radio` |
| `checkbox` | `check` |
| `file` | `upload` |
| `download` | `wait_download` |
| `clipboard` | `wait_clipboard` |
| `copy` | `copy_to_clipboard` |
| `dnd`, `drag` | `drag_drop` |
| `alert`, `confirm`, `prompt` | `dialog` |
| `sleep`, `delay`, `pause` | `wait` |
| `wait_for`, `wait_selector` | `wait_element` |
| `snap` | `screenshot` |
| `back` | `go_back` |
| `forward` | `go_forward` |
| `refresh` | `reload` |
| `eval`, `js`, `javascript` | `eval_js` |
| `ls`, `dir` | `list_files` |
| `rm`, `remove` | `delete_file` |
| `cp` | `copy_file` |
| `mv` | `move_file` |
| `save_file` | `write_file` |
| `stat` | `file_info` |
| `exists` | `file_exists` |

Exemplo com aliases:

```json
[
    {"action": "go", "url": "https://app.com"},
    {"action": "type", "text": "Email", "val": "a@b.com"},
    {"action": "type", "text": "Senha", "val": "123"},
    {"action": "tap", "text": "Entrar"},
    {"action": "sleep", "ms": 3000},
    {"action": "snap", "path": "logado.png"}
]
```

## Nomes de campos flexiveis

Cada campo aceita multiplos nomes alternativos:

| Campo | Nomes aceitos |
|-------|--------------|
| Selector CSS | `selector`, `css`, `sel` |
| Texto do elemento | `text`, `label`, `contains` |
| Tipo do elemento | `element_type`, `type`, `tag` |
| Indice | `index`, `idx`, `i` |
| Valor | `value`, `val` |
| URL | `url`, `href`, `link` |
| Tecla | `value`, `key`, `keys`, `combo` |
| Tempo de espera | `wait_ms`, `ms`, `delay`, `value` |
| Direcao de scroll | `direction`, `dir` |
| Pixels de scroll | `pixels`, `px`, `distance` |
| Opcao de select | `selected_text`, `option`, `label` |
| Arquivo de upload | `value`, `file`, `files`, `path` |
| Codigo JS | `code`, `script`, `js`, `value` |
| Caminho de screenshot | `path`, `file`, `save` |

## base_url para URLs relativas

O parametro `base_url` permite usar URLs relativas no JSON:

```python
await sw.run_json(
    [
        {"action": "goto", "url": "/login"},
        {"action": "fill", "text": "Email", "value": "a@b.com"},
        {"action": "click", "text": "Entrar"},
        {"action": "goto", "url": "/dashboard"},
    ],
    base_url="https://app.exemplo.com",
)
```

URLs que ja comecam com `http://` ou `https://` nao sao afetadas pelo `base_url`.

## continue_on_error

Por padrao, `run_json()` continua executando mesmo se uma acao falhar:

```python
results = await sw.run_json(actions, continue_on_error=True)

for r in results:
    if r["status"] == "ok":
        print(f"Step {r['step']}: OK")
    else:
        print(f"Step {r['step']}: ERRO - {r['error']}")
```

Para parar no primeiro erro, passe `continue_on_error=False` (nao disponivel diretamente, use try/except com replay_actions).

## Parametro mode

Todos os 7 modos de replay funcionam com `run_json()`:

```python
# Rapido
await sw.run_json(actions, mode="rapido")

# Forcado (para overlays)
await sw.run_json(actions, mode="forcado")

# Adaptativo (ignora IDs/classes)
await sw.run_json(actions, mode="adaptativo")
```

O modo controla a mesma `ModeConfig` documentada em [Modos de Replay](modos-de-replay.md).

## Carregar de arquivo

```python
# Direto de arquivo
results = await sw.run_json_file(
    "meu_script.json",
    base_url="https://app.exemplo.com",
    mode="padrao",
    debug=True,
)
```

## Exemplo completo

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

        actions = [
            {"action": "goto", "url": "https://app.exemplo.com/login"},
            {"action": "fill", "css": "input[name='email']", "value": "admin@test.com"},
            {"action": "fill", "css": "input[name='password']", "value": "senha123"},
            {"action": "click", "text": "Entrar"},
            {"action": "wait", "ms": 3000},
            {"action": "wait_url", "value": "/dashboard"},
            {"action": "screenshot", "path": "dashboard.png"},
        ]

        results = await sw.run_json(
            actions,
            delay_ms=400,
            debug=True,
            screenshot_dir="debug_run",
            mode="padrao",
        )

        for r in results:
            print(f"  Step {r['step']}: {r['action']} -> {r['status']}")

        await browser.close()

asyncio.run(main())
```

## Resolucao de elementos

O `run_json()` resolve elementos com flexibilidade. A ordem de prioridade:

1. **`selector`/`css`/`sel`** -- usa como CSS selector direto
2. **`text`/`label`/`contains`** -- busca por texto no elemento (get_by_text, filter(has_text))
3. **`element_type`/`type`/`tag` + `index`/`idx`/`i`** -- tipo + indice ordinal
4. **`capture`** -- usa dados de captura completos (com selectors, bbox, etc.)

Se nenhum campo de identificacao for fornecido, o `run_json()` tenta inferir: para `fill` sem elemento, assume `element_type="input"`.
