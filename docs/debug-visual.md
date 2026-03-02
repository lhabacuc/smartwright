# Debug Visual

## O que e

O debug visual injeta elementos CSS/JS na pagina para mostrar visualmente o que o Smartwright esta fazendo. Cada acao mostra:

- **Cursor virtual animado** -- circulo que se move ate o elemento alvo
- **Highlight do elemento** -- borda colorida ao redor do elemento
- **Efeito ripple** -- animacao de clique (onda expandindo)
- **Screenshots automaticos** -- PNG salvo por step no diretorio configurado

## Configuracao com set_debug()

```python
import asyncio
from playwright.async_api import async_playwright
from smartwright import Smartwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        sw = Smartwright(page=page, request_context=context.request, debug=True)

        # Configurar debug
        await sw.set_debug(
            enabled=True,
            screenshot_dir="debug_screenshots",
            pause_ms=350,
        )

        # Cada acao agora mostra debug visual
        await sw.goto("https://example.com")
        await sw.emergency_fill("input", 0, "user@test.com")
        await sw.emergency_click("button", 0)

        await browser.close()

asyncio.run(main())
```

### Parametros de set_debug()

| Parametro | Tipo | Default | Descricao |
|-----------|------|---------|-----------|
| `enabled` | bool | True | Ativa/desativa debug visual |
| `screenshot_dir` | str | "debug_screenshots" | Diretorio para screenshots |
| `pause_ms` | int | 350 | Pausa entre highlight e acao (ms) |

### Ativar no construtor

```python
# Ativa debug diretamente no construtor
sw = Smartwright(page=page, request_context=context.request, debug=True)
```

### Desativar

```python
await sw.set_debug(enabled=False)
```

## O que voce ve

### Cursor virtual

Um circulo vermelho semi-transparente que se move suavemente ate o centro do elemento alvo. Criado via CSS e injetado na pagina.

### Highlight

Uma borda colorida (tipicamente verde ou azul) ao redor do elemento alvo, com label indicando a acao e step number. O highlight permanece visivel durante `pause_ms` antes da acao ser executada.

### Ripple

Nos clicks, uma animacao de onda expandindo a partir do ponto de clique, simulando visualmente o impacto.

### Screenshots

Um PNG e salvo automaticamente para cada step no diretorio configurado:

```
debug_screenshots/
  step_001_goto.png
  step_002_fill.png
  step_003_click.png
  step_004_fill=admin@test.com.png
```

## Debug no replay_actions e run_json

O parametro `debug=True` ativa debug visual durante replay:

```python
# replay_actions
results = await sw.emergency_replay_actions(
    actions,
    debug=True,
    screenshot_dir="debug_replay",
)

# replay_json (de arquivo)
results = await sw.emergency_replay_json(
    "fluxo.json",
    debug=True,
    screenshot_dir="debug_replay",
)

# run_json
results = await sw.run_json(
    actions,
    debug=True,
    screenshot_dir="debug_run",
)
```

Por padrao, `debug=True` em todos esses metodos. Para desativar:

```python
results = await sw.emergency_replay_json("fluxo.json", debug=False)
```

## Debug nos metodos emergency

Quando o Smartwright e criado com `debug=True`, todos os metodos `emergency_*` mostram debug visual automaticamente:

```python
sw = Smartwright(page=page, request_context=context.request, debug=True)
await sw.set_debug(screenshot_dir="debug")

# Cada chamada mostra cursor -> highlight -> ripple -> screenshot
await sw.emergency_fill("input", 0, "user@test.com")
await sw.emergency_click("button", 0)
await sw.emergency_click_by_text("Enviar")
await sw.emergency_fill_by_label("Senha", "123456")
await sw.emergency_hover("button", 1)
await sw.emergency_select_option("select", 0, "BR")
await sw.emergency_check("input", 3, checked=True)
await sw.emergency_click_link("Criar conta")
```

Metodos que nao interagem com elementos visiveis (como `emergency_press_keys`, `emergency_get_page_title`) nao mostram debug visual.

## Diretorios de screenshot

Cada metodo de replay/run tem seu diretorio default:

| Metodo | Diretorio default |
|--------|-------------------|
| `set_debug()` | `debug_screenshots` |
| `emergency_replay_actions()` | `debug_replay` |
| `emergency_replay_json()` | `debug_replay` |
| `run_json()` | `debug_run` |
| `replay_adaptive()` | `debug_adaptive` |

O diretorio e criado automaticamente se nao existir.

## Gerando GIF das screenshots

Apos a execucao, voce pode gerar um GIF animado das screenshots:

```python
result = await Smartwright.generate_gif(
    screenshot_dir="debug_replay",
    output_path="replay.gif",
    duration_ms=800,  # tempo por frame
    loop=0,           # 0 = loop infinito
)
print(f"GIF gerado: {result['path']}")
print(f"Frames: {result['frame_count']}")
```

Requer `Pillow` instalado (`pip install Pillow`).

## Exemplo completo com debug

```python
import asyncio
from playwright.async_api import async_playwright
from smartwright import Smartwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        sw = Smartwright(page=page, request_context=context.request, debug=True)
        await sw.set_debug(
            screenshot_dir="meu_debug",
            pause_ms=500,  # pausa maior para ver melhor
        )

        await sw.goto("https://example.com/login")

        # Cada passo mostra: cursor -> highlight -> (ripple) -> screenshot
        await sw.emergency_fill("input", 0, "admin@test.com")
        await sw.emergency_fill("input", 1, "senha123")
        await sw.emergency_click("button", 0)

        # Gerar GIF
        await Smartwright.generate_gif(
            screenshot_dir="meu_debug",
            output_path="login_debug.gif",
        )

        await browser.close()

asyncio.run(main())
```

## Dicas

1. **Use headless=False** -- debug visual so faz sentido com browser visivel.
2. **Aumente pause_ms para demonstracoes** -- `pause_ms=1000` da tempo de ver cada step.
3. **Use GIF para compartilhar** -- o `generate_gif()` e util para documentacao e reports.
4. **Debug desacelera a execucao** -- desative em producao com `debug=False`.
5. **Screenshots ocupam espaco** -- limpe `debug_screenshots/` periodicamente.
