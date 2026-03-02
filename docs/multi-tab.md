# Multi-tab / Multi-page

O Smartwright permite gerir multiplas tabs (pages) dentro do mesmo browser context.

## API

### `tab_count` (property)

Numero de tabs abertas.

```python
print(sw.tab_count)  # 1
```

### `new_tab(url=None)`

Abre nova tab. Opcionalmente navega para URL.

```python
page = await sw.new_tab()  # tab em branco
page = await sw.new_tab("https://example.com")  # tab com URL
```

### `list_tabs()`

Lista todas as tabs com indice, URL e titulo.

```python
tabs = await sw.list_tabs()
# [
#   {"index": 0, "url": "https://example.com", "title": "Example"},
#   {"index": 1, "url": "https://other.com", "title": "Other"},
# ]
```

### `switch_tab(index)`

Muda para a tab no indice indicado. Atualiza automaticamente `sw.page` e `sw.engine.page`.

```python
await sw.switch_tab(1)
# Agora todas as operacoes operam na tab 1
await sw.emergency_click("button", 0)
```

### `close_tab(index=None)`

Fecha uma tab. Se `index` nao for dado, fecha a tab atual. Faz switch automatico para a ultima tab restante.

```python
await sw.close_tab(1)  # fecha tab 1
await sw.close_tab()   # fecha tab atual
```

Levanta `TabError` se tentar fechar a unica tab restante.

### `wait_for_popup(trigger)`

Espera por um popup (nova page) disparado por uma acao.

```python
popup = await sw.wait_for_popup(
    lambda: sw.emergency_click("a", 0)
)
# popup e o novo Page object
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

        # Abrir site na tab 0
        await sw.goto("https://example.com")

        # Abrir segunda tab
        await sw.new_tab("https://other-site.com")
        print(f"Tabs: {sw.tab_count}")  # 2

        # Listar
        for tab in await sw.list_tabs():
            print(f"  [{tab['index']}] {tab['url']}")

        # Interagir na tab 1
        await sw.switch_tab(1)
        await sw.emergency_fill("input", 0, "busca")

        # Voltar para tab 0
        await sw.switch_tab(0)

        # Fechar tab 1
        await sw.close_tab(1)
        print(f"Tabs: {sw.tab_count}")  # 1

        await browser.close()

asyncio.run(main())
```

## Excepcoes

- `TabError` — indice invalido, fechar unica tab restante
