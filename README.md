# Smartwright

Motor de automacao web adaptativo com gravacao ao vivo, replay inteligente e 290+ funcoes para qualquer tarefa.

## Instalacao

```bash
pip install smartwright
playwright install chromium
```

## CLI

```bash
smartwright version                                   # versao instalada
smartwright run flow.json                             # executa JSON manual
smartwright run flow.json --mode mix --no-headless    # modo mix com browser visivel
smartwright run flow.json --debug --screenshot-dir ss # debug visual + screenshots
smartwright run flow.json --base-url https://app.com  # URLs relativas
smartwright run flow.json --stop-on-error             # para no primeiro erro
smartwright record                                    # grava acoes em recording.json
smartwright record --output meu_fluxo.json --url https://example.com
smartwright replay recording.json                     # replay com modo padrao
smartwright replay recording.json --mode mix          # replay resiliente
smartwright replay recording.json --no-headless       # browser visivel
```

## Modos de execucao

| Modo | Descricao | Uso ideal |
|---|---|---|
| `rapido` | Sem verificacao, timeouts curtos, sem delay | Paginas estaveis, testes rapidos |
| `padrao` | Todos os 6 steps de resolucao (default) | Uso geral |
| `por_index` | So usa tag + indice ordinal | DOM fixo |
| `por_id_e_class` | So CSS com #id, .class, [data-testid] | Sites com bons IDs |
| `forcado` | Resolucao completa + force click | Overlays, modais |
| `mix` | Todos os steps + 3 retries + scroll | Maximo resiliencia |

## Uso como biblioteca — exemplos rapidos

```python
from smartwright import Smartwright
from smartwright.recorder import ActionRecorder
```

### Gravacao e Replay

```python
# Gravar acoes do usuario
recorder = ActionRecorder(save_path="acoes.json")
page = await recorder.start(url="https://example.com")
actions = await recorder.wait_until_closed()

# Replay com modo
smart = Smartwright(page=page, request_context=context.request)
results = await smart.emergency_replay_actions(actions, mode="mix")

# Replay direto do JSON
results = await smart.emergency_replay_json("acoes.json", mode="padrao")
```

### Executar JSON manual (run_json)

Executa JSONs escritos a mao, tolerante com campos em falta. So precisa de `action` + os campos essenciais.

```python
# ── Inline (lista de dicts) ──
results = await smart.run_json([
    {"action": "goto", "url": "https://example.com"},
    {"action": "fill", "selector": "#email", "value": "user@test.com"},
    {"action": "fill", "text": "Password", "value": "123456"},
    {"action": "click", "text": "Login"},
    {"action": "wait", "ms": 2000},
    {"action": "screenshot", "path": "resultado.png"},
])

# ── De arquivo JSON ──
results = await smart.run_json_file("meu_fluxo.json", mode="mix")

# ── Com base_url (URLs relativas) ──
results = await smart.run_json([
    {"action": "goto", "url": "/login"},
    {"action": "fill", "selector": "input[name=user]", "value": "admin"},
], base_url="https://meusite.com")

# ── Parar no primeiro erro ──
results = await smart.run_json(actions, continue_on_error=False)
```

**JSON minimo por acao:**

```json
[
  {"action": "goto", "url": "https://example.com"},
  {"action": "click", "selector": "#btn"},
  {"action": "click", "text": "Enviar"},
  {"action": "fill", "selector": "#email", "value": "a@b.com"},
  {"action": "fill", "text": "Senha", "value": "123"},
  {"action": "select", "selector": "#pais", "value": "BR"},
  {"action": "select", "selector": "#pais", "option": "Brasil"},
  {"action": "check", "selector": "#aceito", "checked": true},
  {"action": "press", "key": "Enter"},
  {"action": "scroll", "dir": "down", "px": 500},
  {"action": "wait", "ms": 3000},
  {"action": "wait_text", "text": "Sucesso"},
  {"action": "wait_element", "selector": "div.resultado"},
  {"action": "screenshot", "path": "captura.png"},
  {"action": "back"},
  {"action": "js", "code": "document.title"},
  {"action": "drag", "from": "#item", "to": "#destino"},
  {"action": "upload", "selector": "input[type=file]", "file": "/path/doc.pdf"},
  {"action": "download", "dir": "downloads"},
  {"action": "copy", "value": "texto copiado"}
]
```

**Aliases aceitos:** `press`/`key`/`keys` → press_keys, `type`/`write`/`input` → fill, `go`/`open`/`nav` → goto, `tap` → click, `sleep`/`delay`/`pause` → wait, `snap` → screenshot, `back` → go_back, `forward` → go_forward, `refresh` → reload, `js`/`eval` → eval_js, `drag`/`dnd` → drag_drop, `checkbox` → check, `radio` → select_radio, `dropdown` → select_custom, `download` → wait_download, `clipboard` → wait_clipboard, `copy` → copy_to_clipboard, `alert`/`confirm`/`prompt` → dialog.

**Campos flexiveis:** `selector`/`css`/`sel`, `element_type`/`type`/`tag`, `index`/`idx`/`i`, `text`/`label`/`contains`, `value`/`val`, `url`/`href`/`link`, `timeout_ms`/`timeout`.

### Clicks

```python
await smart.emergency_click("button", 0)                                        # por tipo + indice
await smart.emergency_click_by_text("Enviar")                                   # por texto visivel
await smart.emergency_click_by_role("button", 2)                                # por role ARIA
await smart.emergency_click_first_type_containing("button", "*salvar*")          # glob pattern
await smart.emergency_click_by_type_at_index_containing("a", 0, "*download*")   # tipo + pos + texto
await smart.emergency_click_link("Ver mais")                                     # link por texto
await smart.double_click("div", 3)                                               # duplo click
await smart.right_click("tr", 0)                                                 # click direito
await smart.click_at_coordinates(500, 300)                                       # x, y absoluto
```

### Fill / Input

```python
await smart.emergency_fill("input", 0, "user@test.com")                          # por tipo + indice
await smart.emergency_fill_first_type_containing("input", "*email*", "a@b.com")  # glob pattern
await smart.emergency_fill_by_type_at_index_containing("input", 2, "*senha*", "123")
await smart.emergency_fill_by_label("Email", "user@test.com")                    # por label do campo
await smart.emergency_clear_input("input", 0)                                    # limpar campo
val = await smart.emergency_read_input_value("input", 0)                         # ler valor atual
```

### Read / Extrair texto

```python
text = await smart.emergency_read("span", 5)                                     # texto por tipo + indice
text = await smart.emergency_read_by_text("Total:", 0)                           # por texto visivel
text = await smart.emergency_read_first_type_containing("div", "*preco*")        # glob pattern
text = await smart.emergency_read_by_type_at_index_containing("p", 0, "*desc*")  # tipo + pos + texto
texts = await smart.emergency_read_all("li")                                     # todos os textos de um tipo
```

### Formularios

```python
await smart.emergency_select_option("select", 0, "opcao_valor")                 # select por value
await smart.emergency_select_option_by_label("select", 0, "Opcao visivel")      # select por label
sel = await smart.emergency_read_selected_option("select", 0)                    # ler selecionado
opts = await smart.emergency_read_all_options("select", 0)                       # listar opcoes

await smart.emergency_check("input", 3, checked=True)                           # marcar checkbox
await smart.emergency_toggle_checkbox("input", 3)                                # alternar checkbox
await smart.emergency_select_radio("genero", "masculino")                        # radio por name+value
await smart.emergency_upload_file("input", 0, "/path/file.pdf")                  # upload arquivo

state = await smart.emergency_read_form_state(0)                                 # estado de todos os campos
await smart.emergency_submit_form(0)                                             # submit form
await smart.emergency_reset_form(0)                                              # reset form
```

### Tabelas

```python
cell = await smart.emergency_read_table_cell(0, 2, 3)                           # tabela[0] linha 2 col 3
row  = await smart.emergency_read_table_row(0, 1)                                # linha inteira
data = await smart.emergency_read_full_table(0)                                  # tabela completa -> [[str]]
await smart.emergency_click_table_cell(0, 1, 2)                                  # clicar na celula
```

### Listas

```python
items = await smart.emergency_read_list_items(0, list_type="ul")                 # textos de uma <ul>
await smart.emergency_click_list_item(0, 2, list_type="ul")                      # clicar no 3o item
```

### Links

```python
await smart.emergency_click_link("Saiba mais", index=0)                          # clicar link por texto
href = await smart.emergency_get_link_href("Download")                           # pegar href
links = await smart.emergency_capture_all_links()                                # todos os links da pagina
```

### Hover / Scroll / Teclas

```python
await smart.emergency_hover("div", 0)                                            # hover no elemento
await smart.emergency_scroll_page("down", 500)                                   # scroll direcional
await smart.emergency_scroll_to_top()                                            # topo da pagina
await smart.emergency_scroll_to_bottom()                                         # final da pagina
await smart.emergency_scroll_to("div.footer")                                    # scroll ate elemento
await smart.mouse_move(400, 200)                                                 # mover mouse
await smart.mouse_wheel(0, -500)                                                 # scroll por mouse wheel
await smart.emergency_press_keys("Enter")                                        # teclas especiais
await smart.emergency_press_keys("Control+a")                                    # atalhos
```

### Waits / Esperas

```python
el = await smart.emergency_wait_for_element("div.resultado", timeout_ms=15000)   # esperar elemento
await smart.emergency_wait_for_text("Sucesso!", timeout_ms=10000)                # esperar texto visivel
url = await smart.emergency_wait_for_url_contains("/dashboard")                  # esperar URL mudar
await smart.wait_for_load("networkidle", timeout_ms=30000)                       # esperar pagina carregar
resp = await smart.wait_for_response("*/api/data*", timeout_ms=30000)            # esperar resposta HTTP
```

### Download e Clipboard

```python
dl = await smart.emergency_wait_download(save_dir="downloads", timeout_ms=30000)
print(dl["filename"], dl["path"], dl["size"])

clip = await smart.emergency_wait_clipboard(timeout_ms=10000)
print(clip["text"])

await smart.emergency_copy_to_clipboard("texto copiado")
```

### Estado dos elementos

```python
exists = await smart.element_exists("div.modal")                                 # existe no DOM?
count  = await smart.element_count("li.item")                                    # quantos existem?
vis    = await smart.is_visible("button", 0)                                     # visivel?
ena    = await smart.is_enabled("input", 1)                                      # habilitado?
chk    = await smart.is_checked("input", 3)                                      # marcado?
has    = await smart.has_class("div", 0, "active")                               # tem classe?
cls    = await smart.get_classes("div", 0)                                       # listar classes
box    = await smart.get_bounding_box("img", 0)                                  # x, y, width, height
```

### Pagina

```python
title = await smart.emergency_get_page_title()                                   # titulo da pagina
url   = await smart.emergency_get_page_url()                                     # URL atual
await smart.page_screenshot("captura.png", full_page=True)                       # screenshot
text  = await smart.page_text()                                                  # todo texto visivel
html  = await smart.page_html()                                                  # HTML completo
await smart.page_pdf("relatorio.pdf")                                            # exportar PDF
await smart.set_viewport(1920, 1080)                                             # mudar tamanho
await smart.go_back()                                                            # voltar
await smart.go_forward()                                                         # avancar
await smart.reload()                                                             # recarregar
```

### CSS / Estilo

```python
style = await smart.emergency_get_computed_style("div", 0, "background-color")
attr  = await smart.emergency_get_attribute("a", 0, "href")
```

### Cookies

```python
cookies = await smart.get_cookies()                                              # listar cookies
await smart.set_cookie("token", "abc123", domain=".example.com")                 # criar cookie
await smart.clear_cookies()                                                      # limpar tudo
```

### LocalStorage e SessionStorage

```python
val = await smart.get_local_storage("user_id")                                   # ler
await smart.set_local_storage("theme", "dark")                                   # salvar
await smart.remove_local_storage("temp")                                         # remover chave
all_data = await smart.get_all_local_storage()                                   # tudo
await smart.clear_local_storage()                                                # limpar tudo

val = await smart.get_session_storage("cart")                                    # session storage
await smart.set_session_storage("step", "2")
await smart.clear_session_storage()
```

### JavaScript

```python
result = await smart.eval_js("document.title")                                   # executar JS
result = await smart.eval_js("el => el.dataset.id", element)                     # JS com argumento
```

### Iframes

```python
frame = await smart.emergency_switch_to_iframe(0)                                # por indice
frame = await smart.emergency_switch_to_iframe("#meu-iframe")                    # por selector
await smart.emergency_switch_to_main_frame()                                     # voltar ao principal
```

### Dialogs (alert, confirm, prompt)

```python
msg = await smart.emergency_handle_dialog("accept")                              # aceitar alert
msg = await smart.emergency_handle_dialog("dismiss")                             # cancelar
msg = await smart.emergency_handle_dialog("accept", prompt_text="resposta")      # prompt com texto
```

### Drag and Drop

```python
await smart.emergency_drag_and_drop("#item", "#destino")
```

### Media (audio/video)

```python
await smart.emergency_control_media("video", 0, "play")                          # play/pause/mute
state = await smart.emergency_get_media_state("video", 0)                        # currentTime, paused, etc.
src   = await smart.emergency_get_media_src("video", 0)                          # URL do media
```

### Imagens

```python
info   = await smart.emergency_get_image_info(0)                                 # src, alt, naturalWidth...
images = await smart.emergency_capture_all_images()                              # todas as imagens
```

### Captura em massa

```python
inputs  = await smart.emergency_capture_all_inputs()                             # todos os inputs
buttons = await smart.emergency_capture_all_buttons()                            # todos os botoes
selects = await smart.emergency_capture_all_selects()                            # todos os selects
heads   = await smart.emergency_capture_all_headings()                           # todos os h1-h6
full    = await smart.emergency_capture_page_elements()                          # mapa completo da pagina
```

### Capture e Relocate (persistir referencia a elementos)

```python
cap = await smart.emergency_capture("button", 0)                                # captura snapshot
cap = await smart.emergency_capture_by_selector("#btn-enviar")                   # por selector
cap = await smart.emergency_capture_containing("button", "*enviar*")             # por glob

# Mais tarde, relocar o mesmo elemento (mesmo se DOM mudou)
el = await smart.emergency_relocate(cap)
await smart.emergency_click_captured(cap)
await smart.emergency_fill_captured(cap, "novo valor")
text = await smart.emergency_read_captured(cap)
await smart.emergency_hover_captured(cap)
```

### Intent-driven (modo avancado)

```python
smart = Smartwright(page=page, request_context=context.request)
await smart.goto("https://example.com")
await smart.fill("email_field", "user@test.com")
await smart.fill("password_field", "senha123")
await smart.click("login_button")
```

### Resposta de assistente (chat bots)

```python
answer = await smart.wait_response_text(timeout_ms=60000, stable_rounds=3)
await smart.wait_and_click_copy_button()
```

### File system

```python
data = await smart.read_file("config.json")                                     # ler arquivo
await smart.write_file("output.txt", "resultado")                               # escrever
await smart.write_file("log.txt", "nova linha\n", append=True)                  # append
files = await smart.list_files("downloads", "*.pdf", recursive=True)            # listar
exists = await smart.file_exists("data.csv")                                    # existe?
info = await smart.file_info("report.pdf")                                      # metadata
await smart.copy_file("a.txt", "backup/a.txt")                                  # copiar
await smart.move_file("temp.txt", "final.txt")                                  # mover
await smart.delete_file("temp.txt")                                             # deletar
```

### Anti-deteccao (stealth)

```python
from smartwright.stealth import StealthConfig, apply_stealth, get_stealth_args

# Config com todas protecoes (default)
cfg = StealthConfig()

# Ou config minima (so webdriver + automation flags)
cfg = StealthConfig.minimal()

# Usar no recorder
recorder = ActionRecorder(save_path="acoes.json", stealth=True)

# Usar manualmente
browser = await p.chromium.launch(
    args=get_stealth_args(cfg),
    ignore_default_args=["--enable-automation"],
)
context = await browser.new_context(**get_context_options(cfg))
await apply_stealth(context, cfg)
```

Protecoes: navigator.webdriver, plugins, chrome object, permissions, hardware (concurrency/memory/platform), WebGL vendor/renderer, canvas noise, audio noise, connection rtt, WebRTC IP leak. 6 fingerprint profiles (Windows/Mac/Linux com GPUs realistas).

### Multi-tab / Multi-page

```python
# Abrir nova tab
new_page = await smart.new_tab("https://example.com/other")

# Listar tabs abertas
tabs = await smart.list_tabs()  # [{index, url, title}, ...]
print(f"{smart.tab_count} tabs abertas")

# Mudar para tab
await smart.switch_tab(1)

# Fechar tab (default = atual)
await smart.close_tab(1)
await smart.close_tab()  # fecha a tab atual

# Esperar popup
popup = await smart.wait_for_popup(lambda: smart.emergency_click("a", 0))
```

### Session Persistence

```python
# Salvar sessao completa (cookies + localStorage + sessionStorage)
path = await smart.save_session("sessao.json")

# Restaurar sessao
data = await smart.load_session("sessao.json")

# Limpar sessao
await smart.clear_session()
```

### Captcha Solving

```python
from smartwright.captcha.twocaptcha import TwoCaptchaSolver

solver = TwoCaptchaSolver(api_key="YOUR_KEY")
result = await smart.solve_captcha(solver)
# Auto-detecta tipo, resolve e injeta token
```

### Logging

```python
from smartwright import setup_logging
import logging

# Ativar logging (por default nao emite nada)
setup_logging(level=logging.DEBUG)

# Agora todas as operacoes logam:
# DEBUG smartwright: Retry attempt 1/3 after TimeoutError, delay=1.0s
# INFO smartwright: Session saved to /path/sessao.json
# WARNING smartwright: Proxy marked unhealthy: http://proxy:8080 (failures=3)
```

### Gravacao de video e HAR

```python
# Gravar com video
recorder = ActionRecorder(
    save_path="acoes.json",
    record_video_dir="videos/",
    record_har_path="network.har",
)
page = await recorder.start(url="https://example.com")
actions = await recorder.wait_until_closed()
print(recorder.video_paths)                                                      # paths dos videos

# Ler HAR
har = await smart.read_har("network.har")                                        # parse HAR
print(har["total_entries"])

# Extrair APIs do HAR
apis = await smart.extract_har_apis("network.har", "/api/")                      # so endpoints API
for api in apis:
    print(api["method"], api["url"], api["status"])

# Gerar GIF dos screenshots de debug
gif = await smart.generate_gif("debug_screenshots/", "replay.gif", duration_ms=600)
print(gif["frames"], "frames,", gif["size"], "bytes")
```

CLI:
```bash
smartwright record --url https://example.com             # record com URL inicial
smartwright replay recording.json --mode mix             # replay resiliente
smartwright run flow.json --debug                        # executa com debug visual
```

## Resolucao de elementos (6 steps)

O replay busca cada elemento nesta ordem:

1. **Capture CSS selectors** — selectors gravados (#id, .class, [data-testid])
2. **Action selector** — selector do JSON com proximidade de bbox
3. **Type + index + text** — N-esimo elemento com texto correspondente
4. **Type + text** — primeiro match por texto (resiliente a mudancas de DOM)
5. **Type + index** — lookup ordinal por tag
6. **Coordenadas** — click por posicao x/y (ultimo recurso)

## Arquitetura

```
smartwright/
  __init__.py              Facade (Smartwright class, 290+ metodos)
  cli.py                   CLI entry point (run, record, replay, version)
  _logging.py              Logger + setup_logging()
  retry.py                 Retry engine com backoff strategies
  proxy.py                 Proxy rotation com health tracking
  constants.py             Timeouts, versao, configuracao central
  exceptions.py            Hierarquia de excepcoes
  recorder/
    __init__.py            ActionRecorder — gravacao ao vivo com JS injection
  resolver/
    emergency.py           EmergencyResolver — 12 mixins compostos
    _tabs.py               TabsMixin — multi-tab / multi-page
    _session.py            SessionMixin — persistencia de sessao
    _replay.py             ReplayMixin — replay com 6-step resolution
    _run_json.py           RunJsonMixin — execucao de JSON manual
    _debug.py              DebugMixin — cursor, highlight, screenshots
    replay_mode.py         ReplayMode enum + ModeConfig
    dom_serializer.py      Serializa DOM para LLMs
    dom_diff.py            Comparacao de snapshots
  captcha/
    solver.py              Deteccao + extracao + injecao de captcha
    twocaptcha.py          2Captcha.com solver
  stealth/
    __init__.py            StealthConfig, apply_stealth — anti-deteccao
  core/                    Decision engine, modelos, knowledge store
  network_learning/        Descoberta automatica de APIs
```

## Persistencia

- `.smartwright_profile/` — perfil do Chromium (login, cookies, sessao)
- `.smartwright_knowledge.json` — historico de estrategias, APIs, scores
- `recording.json` — acoes gravadas
- `debug_screenshots/` — screenshots de debug por step
