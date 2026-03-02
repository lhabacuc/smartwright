# Metodos Emergency

## Conceito

Os metodos `emergency_*` oferecem interacao direta com elementos por **tipo + indice ordinal**. O "tipo" e a tag HTML (`button`, `input`, `a`, `div`, etc.) e o "indice" e a posicao ordinal (0-based) entre todos os elementos daquele tipo na pagina.

```python
# O primeiro input da pagina (indice 0)
await sw.emergency_fill("input", 0, "texto")

# O terceiro botao (indice 2)
await sw.emergency_click("button", 2)

# O segundo paragrafo
texto = await sw.emergency_read("p", 1)
```

## Categorias de metodos

### Click

```python
# Por tipo + indice
await sw.emergency_click("button", 0)

# Por role + indice
await sw.emergency_click_by_role("button", 0)

# Por texto
await sw.emergency_click_by_text("Enviar")
await sw.emergency_click_by_text("Enviar", index=1)  # segundo match

# Por texto contido (busca em text + atributos)
await sw.emergency_click_first_type_containing("button", "Enviar")

# Por tipo + indice + padrao de texto
await sw.emergency_click_by_type_at_index_containing("div", 7, "*max*")

# Input especifico
await sw.emergency_click_first_input_containing("Email")

# Link por texto
await sw.emergency_click_link("Criar conta")
await sw.emergency_click_link("Criar conta", index=1)
```

### Fill

```python
# Por tipo + indice
await sw.emergency_fill("input", 0, "user@test.com")

# Por role + indice
await sw.emergency_fill_by_role("textbox", 0, "texto")

# Por texto contido
await sw.emergency_fill_first_type_containing("input", "Email", "user@test.com")

# Por tipo + indice + padrao de texto
await sw.emergency_fill_by_type_at_index_containing("textarea", 0, "*mensagem*", "Ola!")

# Input especifico
await sw.emergency_fill_first_input_containing("Email", "user@test.com")

# Por label
await sw.emergency_fill_by_label("Email", "user@test.com")
```

### Read

```python
# Por tipo + indice
texto = await sw.emergency_read("p", 0)

# Por role + indice
texto = await sw.emergency_read_by_role("heading", 0)

# Por texto
texto = await sw.emergency_read_by_text("Resultado")

# Por texto contido
texto = await sw.emergency_read_first_type_containing("div", "Preco")

# Por tipo + indice + padrao
texto = await sw.emergency_read_by_type_at_index_containing("span", 0, "*total*")

# Ler todos de um tipo
todos = await sw.emergency_read_all("li")  # lista de strings

# Valor de input
valor = await sw.emergency_read_input_value("input", 0)
```

### Busca por texto

Os metodos `_by_text` usam `page.get_by_text()` do Playwright:

```python
await sw.emergency_click_by_text("Enviar")
texto = await sw.emergency_read_by_text("Resultado")
```

### Busca por role

Os metodos `_by_role` usam `page.get_by_role()`:

```python
await sw.emergency_click_by_role("button", 0)
await sw.emergency_fill_by_role("textbox", 0, "texto")
texto = await sw.emergency_read_by_role("heading", 0)
```

### Busca por conteudo (containing)

Busca em texto + atributos (aria-label, placeholder, name, id, value, title):

```python
# Primeiro botao que contem "Enviar" em texto ou atributos
await sw.emergency_click_first_type_containing("button", "Enviar")

# Primeiro input que contem "senha" em texto ou atributos
await sw.emergency_fill_first_type_containing("input", "senha", "minha_senha")
```

### Busca por label

```python
await sw.emergency_fill_by_label("Email", "user@test.com")
```

## Formularios

### Select / Dropdown

```python
# Select nativo — por valor
await sw.emergency_select_option("select", 0, "BR")

# Select nativo — por label visivel
await sw.emergency_select_option_by_label("select", 0, "Brasil")

# Ler opcao selecionada
selecionado = await sw.emergency_read_selected_option("select", 0)

# Listar todas as opcoes
opcoes = await sw.emergency_read_all_options("select", 0)
# [{"value": "BR", "label": "Brasil"}, {"value": "US", "label": "Estados Unidos"}]
```

### Checkbox

```python
# Marcar
await sw.emergency_check("input", 3, checked=True)

# Desmarcar
await sw.emergency_check("input", 3, checked=False)

# Toggle
novo_estado = await sw.emergency_toggle_checkbox("input", 3)  # retorna bool
```

### Radio

```python
# Selecionar radio por name + value
await sw.emergency_select_radio("genero", "masculino")
```

### Upload

```python
# Upload de arquivo
await sw.emergency_upload_file("input", 0, "/caminho/para/arquivo.pdf")

# Multiplos arquivos
await sw.emergency_upload_file("input", 0, ["/a.pdf", "/b.pdf"])
```

### Submit

```python
# Submeter o primeiro formulario
await sw.emergency_submit_form(index=0)

# Ler estado de todos os campos do formulario
estado = await sw.emergency_read_form_state(index=0)
# [{"name": "email", "value": "a@b.com", "type": "text"}, ...]

# Resetar formulario
await sw.emergency_reset_form(index=0)
```

## Tabelas

```python
# Ler celula (table_index, row, col — todos 0-based)
celula = await sw.emergency_read_table_cell(0, 1, 2)

# Ler linha inteira
linha = await sw.emergency_read_table_row(0, 0)  # ["Col1", "Col2", "Col3"]

# Ler tabela completa
tabela = await sw.emergency_read_full_table(0)
# [["Nome", "Idade"], ["Ana", "25"], ["Bruno", "30"]]

# Clicar numa celula
await sw.emergency_click_table_cell(0, 1, 0)
```

## Listas

```python
# Ler items de lista
items = await sw.emergency_read_list_items(list_index=0, list_type="ul")
# ["Item 1", "Item 2", "Item 3"]

# Clicar num item
await sw.emergency_click_list_item(list_index=0, item_index=1, list_type="ul")
```

## Links

```python
# Clicar em link por texto
await sw.emergency_click_link("Criar conta")

# Obter href
href = await sw.emergency_get_link_href("Criar conta")

# Capturar todos os links
links = await sw.emergency_capture_all_links()
# [{"text": "Home", "href": "/", "selectors": [...]}, ...]
```

## Capture e Relocate

O padrao capture/relocate permite capturar um snapshot completo de um elemento e re-encontra-lo mais tarde, mesmo apos navegacao:

### Capturar

```python
# Por tipo + indice
capture = await sw.emergency_capture("button", 0)

# Por selector CSS
capture = await sw.emergency_capture_by_selector("#btn-enviar")

# Por texto contido
capture = await sw.emergency_capture_containing("button", "Enviar")
```

O capture retorna um dict com:

```python
{
    "tag": "button",
    "index_in_type": 0,
    "total_in_type": 5,
    "text": "Enviar",
    "attributes": {"id": "btn-enviar", "class": "btn", ...},
    "bbox": {"x": 300, "y": 450, "width": 120, "height": 40, "cx": 360, "cy": 470},
    "selectors": ["#btn-enviar", "button[aria-label='Enviar']", ...],
    "visible": True,
}
```

### Relocar e interagir

```python
# Relocar (re-encontrar o elemento)
locator = await sw.emergency_relocate(capture)

# Clicar no elemento capturado
await sw.emergency_click_captured(capture)

# Preencher elemento capturado
await sw.emergency_fill_captured(capture, "texto")

# Hover no elemento capturado
await sw.emergency_hover_captured(capture)

# Ler texto do elemento capturado
texto = await sw.emergency_read_captured(capture)
```

### Cadeia de relocacao

O `relocate_from_capture` tenta multiplas estrategias em ordem:

1. Selectors CSS do capture (`#id`, `[data-testid]`, etc.)
2. Tag + index_in_type (`page.locator("button").nth(2)`)
3. Texto do elemento (`page.get_by_text(...)`)
4. Coordenadas (cx, cy) como ultimo recurso

## Bulk capture

```python
# Capturar todos os inputs
inputs = await sw.emergency_capture_all_inputs()

# Capturar todos os botoes
botoes = await sw.emergency_capture_all_buttons()

# Capturar todos os selects
selects = await sw.emergency_capture_all_selects()

# Capturar todos os headings
headings = await sw.emergency_capture_all_headings()

# Capturar sumario completo da pagina
pagina = await sw.emergency_capture_page_elements()
```

## Navegacao e estado

```python
# Scroll
await sw.emergency_scroll_page(direction="down", pixels=500)
await sw.emergency_scroll_to_top()
await sw.emergency_scroll_to_bottom()
await sw.emergency_scroll_to("#elemento")

# Hover
await sw.emergency_hover("button", 0)

# Espera
await sw.emergency_wait_for_element("#resultado")
await sw.emergency_wait_for_text("Sucesso")
url = await sw.emergency_wait_for_url_contains("/dashboard")

# Teclas
await sw.emergency_press_keys("Enter")
await sw.emergency_press_keys("Control+a")

# Pagina
titulo = await sw.emergency_get_page_title()
url = await sw.emergency_get_page_url()
```

## Acoes avancadas

```python
# Double click
await sw.double_click("div", 0)

# Right click
await sw.right_click("div", 0)

# Focus
await sw.focus("input", 0)

# Click por coordenadas
await sw.click_at_coordinates(360, 470)

# Mouse
await sw.mouse_move(100, 200)
await sw.mouse_wheel(delta_y=-300)

# Dialog
mensagem = await sw.emergency_handle_dialog(action="accept", prompt_text="resposta")

# Drag and drop
await sw.emergency_drag_and_drop("#source", "#target")

# Iframe
frame = await sw.emergency_switch_to_iframe(0)
await sw.emergency_switch_to_main_frame()
```

## Informacoes de elementos

```python
# Atributo
valor = await sw.emergency_get_attribute("input", 0, "name")

# Estado
visivel = await sw.is_visible("button", 0)
habilitado = await sw.is_enabled("button", 0)
marcado = await sw.is_checked("input", 3)

# Classes
tem_classe = await sw.has_class("div", 0, "ativo")
classes = await sw.get_classes("div", 0)

# Bounding box
bbox = await sw.get_bounding_box("button", 0)

# Estilo computado
cor = await sw.emergency_get_computed_style("button", 0, "background-color")

# Contagem
existe = await sw.element_exists("#btn")
total = await sw.element_count("button")
```

## Media (video/audio)

```python
# Controlar media: "play", "pause", "mute"
await sw.emergency_control_media("video", 0, "play")
await sw.emergency_control_media("video", 0, "pause")
await sw.emergency_control_media("audio", 0, "mute")

# Estado do media (paused, currentTime, duration, muted, volume)
estado = await sw.emergency_get_media_state("video", 0)

# Src do media
src = await sw.emergency_get_media_src("video", 0)
```

## Imagem

```python
# Info da N-esima imagem (src, alt, width, height, naturalWidth, naturalHeight)
info = await sw.emergency_get_image_info(0)

# Capturar info de todas as imagens
imagens = await sw.emergency_capture_all_images()
```

## Iframe

```python
# Entrar num iframe (por indice ou selector)
frame = await sw.emergency_switch_to_iframe(0)
frame = await sw.emergency_switch_to_iframe("#meu-iframe")

# Voltar ao frame principal
await sw.emergency_switch_to_main_frame()
```

## Dialog (alert/confirm/prompt)

```python
# Aceitar dialog
mensagem = await sw.emergency_handle_dialog(action="accept")

# Recusar dialog
mensagem = await sw.emergency_handle_dialog(action="dismiss")

# Responder prompt
mensagem = await sw.emergency_handle_dialog(action="accept", prompt_text="minha resposta")
```

## Drag and Drop

```python
# Arrastar de um elemento para outro (CSS selectors)
await sw.emergency_drag_and_drop("#item-origem", "#zona-destino")
```

## Scroll

```python
# Scroll da pagina
await sw.emergency_scroll_page("down", 500)
await sw.emergency_scroll_page("up", 300)

# Topo e fundo
await sw.emergency_scroll_to_top()
await sw.emergency_scroll_to_bottom()

# Scroll ate elemento (CSS selector)
await sw.emergency_scroll_to("#elemento-alvo")
```

## Pagina

```python
# Titulo e URL
titulo = await sw.emergency_get_page_title()
url = await sw.emergency_get_page_url()

# Screenshot
await sw.page_screenshot("pagina.png")
await sw.page_screenshot("pagina_full.png", full_page=True)

# Texto e HTML
texto = await sw.page_text()
html = await sw.page_html()

# PDF (so headless Chromium)
await sw.page_pdf("pagina.pdf")

# Viewport
await sw.set_viewport(1920, 1080)

# Navegacao
await sw.go_back()
await sw.go_forward()
await sw.reload()

# Espera por estado de load
await sw.wait_for_load("networkidle", timeout_ms=15000)
# Opcoes: "load", "domcontentloaded", "networkidle"

# Espera por resposta HTTP
response = await sw.wait_for_response("/api/data", timeout_ms=30000)

# Estilo computado
cor = await sw.emergency_get_computed_style("button", 0, "background-color")
```

## Cookies

```python
# Obter todos os cookies
cookies = await sw.get_cookies()

# Definir cookie
await sw.set_cookie("session", "abc123", domain="example.com", path="/")

# Limpar todos os cookies
await sw.clear_cookies()
```

## LocalStorage e SessionStorage

```python
# LocalStorage
valor = await sw.get_local_storage("chave")
await sw.set_local_storage("chave", "valor")
await sw.remove_local_storage("chave")
await sw.clear_local_storage()
todos = await sw.get_all_local_storage()  # dict

# SessionStorage
valor = await sw.get_session_storage("chave")
await sw.set_session_storage("chave", "valor")
await sw.clear_session_storage()
```

## Operacoes de ficheiro

```python
# Ler
dados = await sw.read_file("dados.txt")
# {"content": "...", "path": "dados.txt", "size": 1234, "encoding": "utf-8"}

# Escrever
await sw.write_file("output.txt", "conteudo")
await sw.write_file("log.txt", "linha extra\n", append=True)

# Listar
ficheiros = await sw.list_files(".", pattern="*.json", recursive=False)

# Verificar
existe = await sw.file_exists("config.json")

# Info
info = await sw.file_info("dados.txt")
# {"size": 1234, "modified": "...", "created": "...", "is_dir": False}

# Copiar, mover, apagar
await sw.copy_file("src.txt", "dst.txt")
await sw.move_file("old.txt", "new.txt")
await sw.delete_file("temp.txt")
```

## Download e Clipboard

```python
# Esperar download (opcionalmente com trigger)
resultado = await sw.emergency_wait_download(
    save_dir="downloads",
    timeout_ms=30000,
    trigger_action=sw.emergency_click("a", 0),
)
# {"filename": "...", "path": "...", "url": "...", "size": 1234}

# Ler clipboard
clipboard = await sw.emergency_wait_clipboard()
# {"text": "...", "html": "...", "timestamp": "..."}

# Escrever no clipboard
await sw.emergency_copy_to_clipboard("texto copiado")
```

## JavaScript

```python
# Executar JS na pagina
titulo = await sw.eval_js("document.title")
await sw.eval_js("window.scrollTo(0, 0)")

# Com argumento
resultado = await sw.eval_js("(x) => x * 2", 21)  # → 42
```

## Resposta de streaming (chatbots)

```python
# Esperar resposta estabilizar
texto = await sw.wait_response_text(
    timeout_ms=90000,
    stable_rounds=3,
    poll_interval_ms=900,
)

# Clicar no botao de copiar (heuristica automatica)
clicou = await sw.wait_and_click_copy_button(timeout_ms=20000)
```

## Debug visual na API Emergency

Com `debug=True`, os metodos `emergency_click`, `emergency_fill`, `emergency_click_by_text`, `emergency_fill_by_label`, `emergency_hover`, `emergency_select_option`, `emergency_check`, `emergency_click_link` e `emergency_click_first_type_containing` mostram automaticamente:

1. Cursor virtual animado movendo ate o elemento
2. Highlight colorido com label da acao
3. Efeito ripple (nos clicks)
4. Screenshot automatico (se `set_debug(screenshot_dir=...)` configurado)

```python
sw = Smartwright(page=page, request_context=context.request, debug=True)
await sw.set_debug(screenshot_dir="debug")

# Cada chamada mostra debug visual
await sw.emergency_fill("input", 0, "user@test.com")
await sw.emergency_click("button", 0)
```

## Multi-tab

```python
# Abrir nova tab
page = await sw.new_tab("https://example.com")

# Listar tabs
tabs = await sw.list_tabs()  # [{index, url, title}, ...]
count = sw.tab_count

# Mudar de tab
await sw.switch_tab(1)

# Fechar tab (default = atual)
await sw.close_tab(1)

# Esperar popup
popup = await sw.wait_for_popup(lambda: sw.emergency_click("a", 0))
```

## Session Persistence

```python
# Salvar sessao (cookies + localStorage + sessionStorage)
path = await sw.save_session("sessao.json")

# Restaurar sessao
data = await sw.load_session("sessao.json")

# Limpar sessao
await sw.clear_session()
```

## Captcha

```python
from smartwright.captcha.twocaptcha import TwoCaptchaSolver

# Detectar
captcha_type = await sw.detect_captcha()

# Resolver e injetar automaticamente
solver = TwoCaptchaSolver(api_key="KEY")
result = await sw.solve_captcha(solver)
```

## Quando usar emergency vs semantico

| Cenario | Usar |
|---------|------|
| Automacao geral, scripts rapidos | `emergency_*` |
| Aplicacao com intencoes definidas | `click()`, `fill()`, `read()` (semantico) |
| Pagina desconhecida, exploracao | `emergency_*` |
| Fluxo com self-healing | semantico (intents) |
| Replay de gravacao | `replay_actions()` / `run_json()` |
| Integracao com LLM | `dom_snapshot()` + `emergency_click_captured()` |
