# Gravacao e Replay

## Visao geral

O sistema de gravacao e replay do Smartwright funciona em dois passos:

1. **Gravacao**: o `ActionRecorder` abre um browser, injeta listeners JS e captura todas as acoes do usuario (cliques, preenchimentos, selects, scroll, teclas especiais, downloads, clipboard).
2. **Replay**: o `replay_actions()` re-executa as acoes gravadas com resolucao inteligente de 6 steps, debug visual e suporte a 7 modos de execucao.

## ActionRecorder

### Uso basico

```python
import asyncio
from smartwright.recorder import ActionRecorder

async def gravar():
    recorder = ActionRecorder(
        save_path="meu_fluxo.json",
        headless=False,
    )

    # Abre o browser e comeca a gravar
    page = await recorder.start(url="https://example.com")

    # Bloqueia ate o usuario fechar o browser (ou Ctrl+C)
    actions = await recorder.wait_until_closed()

    print(f"Gravou {len(actions)} acoes")
    return actions

asyncio.run(gravar())
```

### Parametros do ActionRecorder

| Parametro | Tipo | Default | Descricao |
|-----------|------|---------|-----------|
| `headless` | bool | False | Modo headless (sem janela) |
| `save_path` | str | "recording.json" | Caminho para salvar o JSON |
| `browser_args` | list[str] | ["--start-maximized"] | Args do Chromium |
| `user_data_dir` | str | None | Diretorio de perfil persistente |
| `stealth` | bool | False | Ativar anti-deteccao |
| `stealth_config` | StealthConfig | None | Config de stealth personalizada |
| `record_video_dir` | str | None | Diretorio para gravar video |
| `record_video_size` | dict | None | Tamanho do video `{"width": 1280, "height": 720}` |
| `record_har_path` | str | None | Caminho para gravar HAR |

### Controle de gravacao

```python
recorder = ActionRecorder(save_path="fluxo.json")
page = await recorder.start(url="https://example.com")

# Pausar gravacao (acoes sao ignoradas)
recorder.pause()

# Retomar gravacao
recorder.resume()

# Parar e salvar
actions = await recorder.stop()
```

### Perfil persistente

O ActionRecorder usa um perfil de browser persistente para manter login, cookies e localStorage entre sessoes:

```python
# Perfil default: .smartwright_profile no mesmo diretorio do save_path
recorder = ActionRecorder(save_path="fluxo.json")

# Perfil customizado
recorder = ActionRecorder(
    save_path="fluxo.json",
    user_data_dir="/caminho/para/perfil",
)
```

### Gravacao com stealth

```python
from smartwright.stealth import StealthConfig

recorder = ActionRecorder(
    save_path="fluxo.json",
    stealth=True,
    stealth_config=StealthConfig(),  # todas as protecoes
)
page = await recorder.start(url="https://site-protegido.com")
```

### Gravacao com video

```python
recorder = ActionRecorder(
    save_path="fluxo.json",
    record_video_dir="videos",
    record_video_size={"width": 1280, "height": 720},
)
page = await recorder.start(url="https://example.com")
actions = await recorder.wait_until_closed()

# Acessar caminhos dos videos
for path in recorder.video_paths:
    print(f"Video salvo em: {path}")
```

## Formato das acoes gravadas

Cada acao e um dict com:

```json
{
    "step": 1,
    "action": "click",
    "element_type": "button",
    "index": 2,
    "value": "",
    "text": "Enviar",
    "url": "https://example.com/form",
    "selector": "#btn-enviar",
    "capture": {
        "tag": "button",
        "index_in_type": 2,
        "total_in_type": 5,
        "text": "Enviar",
        "attributes": {
            "id": "btn-enviar",
            "class": "btn btn-primary",
            "type": "submit",
            "aria-label": "Enviar formulario"
        },
        "bbox": {
            "x": 300, "y": 450,
            "width": 120, "height": 40,
            "cx": 360, "cy": 470
        },
        "selectors": [
            "#btn-enviar",
            "button[aria-label='Enviar formulario']",
            "button.btn.btn-primary",
            "form > button:nth-of-type(1)"
        ],
        "visible": true
    },
    "timestamp": "2025-01-15T10:30:00.000000+00:00"
}
```

### Acoes capturadas

| Acao | Descricao | Campos extras |
|------|-----------|---------------|
| `goto` | Navegacao | `url` |
| `click` | Clique em elemento | capture |
| `fill` | Preenchimento de campo | `value`, capture |
| `select` | Select nativo | `value`, `selected_text`, `selected_index`, `name` |
| `select_custom` | Dropdown customizado | `value`, `selected_text`, `list_capture` |
| `check` | Checkbox | `checked`, `name` |
| `select_radio` | Radio button | `value`, `name` |
| `upload` | Upload de arquivo | `value` (nomes dos arquivos) |
| `submit` | Submit de formulario | capture |
| `scroll` | Scroll da pagina | `direction`, `pixels` |
| `press_keys` | Tecla especial | `value` (ex: "Enter", "Control+a") |
| `wait_clipboard` | Copia para clipboard | `clipboard_text` |
| `wait_download` | Download de arquivo | `download_info` |

### Deduplicacao inteligente

O recorder aplica deduplicacao automatica:

- **Fills consecutivos** no mesmo elemento: mantém apenas o ultimo valor
- **Click antes de fill** no mesmo elemento (< 1.5s): remove o click (era apenas foco)
- **Eventos identicos** dentro de 0.3s: remove duplicata
- **goto duplicado** para mesma URL: ignorado
- **URLs de ruido** (analytics, trackers): filtradas automaticamente

## Replay

### replay_actions()

```python
from playwright.async_api import async_playwright
from smartwright import Smartwright

async def replay():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        sw = Smartwright(page=page, request_context=context.request)

        # Replay de lista de acoes
        actions = sw.emergency_load_actions("meu_fluxo.json")
        results = await sw.emergency_replay_actions(
            actions,
            delay_ms=500,
            debug=True,
            screenshot_dir="debug_replay",
            mode="padrao",
        )

        for r in results:
            print(f"Step {r['step']}: {r['action']} -> {r['status']}")

        await browser.close()
```

### replay_json() (de arquivo)

```python
results = await sw.emergency_replay_json(
    "meu_fluxo.json",
    delay_ms=500,
    debug=True,
    screenshot_dir="debug_replay",
    mode="padrao",
)
```

### Callback on_step

```python
async def meu_callback(step_info):
    print(f"Executando step {step_info['step']}: {step_info['action']}")

results = await sw.emergency_replay_json(
    "fluxo.json",
    on_step=meu_callback,
)
```

## Selecao de modo

Todos os 7 modos estao disponiveis para replay:

```python
# Rapido (sem verificacao)
results = await sw.emergency_replay_json("fluxo.json", mode="rapido")

# Padrao (default, todos os 6 steps)
results = await sw.emergency_replay_json("fluxo.json", mode="padrao")

# Forcado (force click para overlays)
results = await sw.emergency_replay_json("fluxo.json", mode="forcado")

# Mix (3 retries, scroll entre retries)
results = await sw.emergency_replay_json("fluxo.json", mode="mix")

# Adaptativo (fingerprint semantico)
results = await sw.replay_adaptive("fluxo.json")
```

Veja [Modos de Replay](modos-de-replay.md) para detalhes de cada modo.

## Replay adaptativo

O modo adaptativo usa **fingerprint semantico** para resolver elementos sem depender de IDs ou classes. Ideal quando o site muda entre deploys mas mantem o texto e estrutura semantica.

### replay_adaptive()

```python
# A partir de ficheiro JSON
results = await sw.replay_adaptive(
    "meu_fluxo.json",
    delay_ms=500,
    debug=True,
    screenshot_dir="debug_adaptive",
)

# A partir de lista de acoes
results = await sw.replay_adaptive(
    actions,
    delay_ms=500,
    debug=True,
    screenshot_dir="debug_adaptive",
)

for r in results:
    print(f"Step {r['step']}: {r['action']} -> {r['status']}")
```

### replay_adaptive_analyze()

Pre-analisa todos os matches sem executar. Util para validar um recording antes de rodar:

```python
await sw.goto("https://example.com")
await sw.wait_for_load("networkidle", timeout_ms=10000)

analysis = await sw.replay_adaptive_analyze("meu_fluxo.json")

for a in analysis:
    if a.get("match") == "n/a":
        print(f"  [{a['step']}] {a['action']} — sem elemento")
        continue

    fp = a.get("fingerprint", {})
    match = a.get("match", {})
    score = a.get("score", 0)
    ok = "SIM" if a.get("confident") else "NAO"

    print(f"  [{a['step']}] {a['action']} — score: {score}, match: {ok}")
    print(f"         gravado: {fp.get('tag', '?')} \"{fp.get('text', '')[:30]}\"")
    if match:
        print(f"         pagina:  {match.get('tag', '?')} \"{match.get('text', '')[:30]}\"")
```

Veja [Replay Adaptativo](replay-adaptativo.md) para detalhes completos do algoritmo.

## A cadeia de resolucao de 6 steps

No modo `padrao`, cada acao e resolvida tentando 6 estrategias em sequencia. A primeira que encontra o elemento encerra a cadeia:

### Step 1: Selectors CSS do capture

Usa os selectors gerados durante a gravacao (`#id`, `[data-testid]`, `[aria-label]`, etc.). Se `verify_capture` esta ativo, verifica que o texto e bounding box do elemento encontrado correspondem ao gravado.

### Step 2: Selector da acao

Usa o campo `selector` da acao (primeiro selector dos selectors do capture).

### Step 3: Tipo + indice + texto

Combina `element_type` + `index` + verifica se o texto do elemento contem `text`. Exemplo: o 3o botao que contem "Enviar".

### Step 4: Tipo + texto (ignorando indice)

Busca qualquer elemento do tipo que contenha o texto, ignorando o indice ordinal. Util quando elementos foram adicionados/removidos, mudando os indices.

### Step 5: Tag + indice ordinal

Usa `page.locator(tag).nth(index)`. Simples mas fragil se a estrutura muda.

### Step 6: Coordenadas pixel

Ultimo recurso: clica nas coordenadas `(cx, cy)` salvas no bounding box do capture. Funciona mesmo sem selectors, mas e sensivel a mudancas de layout.

## Debug no replay

Com `debug=True`, cada step gera:

1. **Cursor virtual** -- animacao de cursor movendo para o elemento
2. **Highlight colorido** -- borda colorida no elemento alvo
3. **Efeito ripple** -- animacao de clique
4. **Screenshot automatico** -- salvo em `screenshot_dir/step_NNN_action.png`

```python
results = await sw.emergency_replay_json(
    "fluxo.json",
    debug=True,
    screenshot_dir="debug_replay",
)

# Screenshots ficam em:
# debug_replay/step_001_goto.png
# debug_replay/step_002_fill.png
# debug_replay/step_003_click.png
```

## Gravacao via Smartwright

Atalho que encapsula o ActionRecorder:

```python
sw = Smartwright(page=page, request_context=context.request)

# Abre browser, grava, salva e retorna acoes
actions = await Smartwright.emergency_capture_acao(
    save_path="meu_fluxo.json",
    url="https://example.com",
    headless=False,
)
```

## CLI

```bash
# Gravar
python qwen-cap.py record
python qwen-cap.py record meu_fluxo.json

# Replay
python qwen-cap.py replay
python qwen-cap.py replay --mode rapido
python qwen-cap.py replay --no-debug
python qwen-cap.py replay meu_fluxo.json --mode mix

# Gravar + replay sequencial
python qwen-cap.py full
python qwen-cap.py full --mode forcado
```

## Formato do arquivo JSON

```json
{
    "version": 1,
    "recorded_at": "2025-01-15T10:30:00.000000+00:00",
    "actions": [
        {"step": 1, "action": "goto", "url": "https://example.com", ...},
        {"step": 2, "action": "fill", "element_type": "input", ...},
        {"step": 3, "action": "click", "element_type": "button", ...}
    ]
}
```

Apos `stop()`, o recorder tambem salva o storage state (cookies/localStorage) em `recording.state.json` para portabilidade.
