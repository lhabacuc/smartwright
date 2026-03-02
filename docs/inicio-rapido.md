# Inicio Rapido

## Instalacao

```bash
pip install smartwright
playwright install chromium
```

## Padrao minimo de uso

O fluxo basico com Smartwright segue 4 passos: abrir browser, criar instancia, executar acoes, fechar.

```python
import asyncio
from playwright.async_api import async_playwright
from smartwright import Smartwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Criar instancia do Smartwright
        sw = Smartwright(page=page, request_context=context.request)

        # Navegar
        await sw.goto("https://example.com")

        # Interagir com elementos por tipo + indice
        await sw.emergency_fill("input", 0, "usuario@email.com")
        await sw.emergency_fill("input", 1, "minha_senha")
        await sw.emergency_click("button", 0)

        await browser.close()

asyncio.run(main())
```

## Tres modos de interacao

### 1. Semantico (intent-driven)

Define intencoes e o Smartwright resolve automaticamente usando get_by_role, get_by_label, get_by_text e heuristicas:

```python
sw = Smartwright(
    page=page,
    request_context=context.request,
    intents={
        "login_button": ["Entrar", "Login", "Sign in"],
        "email_field": ["Email", "E-mail", "Username"],
        "password_field": ["Senha", "Password"],
    },
)

await sw.fill("email_field", "user@test.com")
await sw.fill("password_field", "123456")
await sw.click("login_button")
```

### 2. Emergency (tipo + indice)

Acesso direto por tipo de elemento e posicao ordinal na pagina:

```python
# Preencher o primeiro input da pagina
await sw.emergency_fill("input", 0, "texto aqui")

# Clicar no terceiro botao
await sw.emergency_click("button", 2)

# Ler texto do segundo paragrafo
texto = await sw.emergency_read("p", 1)

# Buscar por texto contido
await sw.emergency_click_first_type_containing("button", "Enviar")
```

### 3. Gravacao e Replay

Grava acoes do usuario no browser e reproduz automaticamente:

```python
from smartwright.recorder import ActionRecorder

# Gravar
recorder = ActionRecorder(save_path="meu_fluxo.json")
page = await recorder.start(url="https://example.com")
actions = await recorder.wait_until_closed()

# Reproduzir
sw = Smartwright(page=page, request_context=context.request)
results = await sw.emergency_replay_json("meu_fluxo.json", mode="padrao")
```

## Ativando debug visual

```python
sw = Smartwright(page=page, request_context=context.request, debug=True)
await sw.set_debug(
    enabled=True,
    screenshot_dir="debug_screenshots",
    pause_ms=350,
)
```

Com debug ativo, cada acao mostra um cursor virtual animado, highlight colorido no elemento alvo, efeito ripple nos clicks e screenshots automaticos salvos no diretorio configurado.

## Ativando network learning

```python
sw.attach_network_learning()
await sw.goto("https://app.exemplo.com")

# Apos navegar, verificar APIs descobertas
print(sw.network_summary())
for api in sw.network_discoveries:
    print(f"{api['method']} {api['endpoint']} -> {api['intent']}")
```

## Usando com stealth (anti-deteccao)

```python
from smartwright.stealth import StealthConfig, get_stealth_args, get_context_options, apply_stealth

cfg = StealthConfig()  # todas as protecoes ativas

browser = await p.chromium.launch(
    headless=False,
    args=get_stealth_args(cfg),
    ignore_default_args=["--enable-automation"],
)
context = await browser.new_context(**get_context_options(cfg))
await apply_stealth(context, cfg)

page = await context.new_page()
sw = Smartwright(page=page, request_context=context.request)
```

## CLI rapido

O Smartwright inclui um CLI para uso direto no terminal:

```bash
smartwright version                             # versao
smartwright run flow.json --mode mix            # executa JSON manual
smartwright record --output meu_fluxo.json      # grava acoes do browser
smartwright replay meu_fluxo.json --mode padrao # reproduz gravacao
```

## Logging

```python
from smartwright import setup_logging
import logging

setup_logging(level=logging.DEBUG)  # ativa logs detalhados
```

## Multi-tab

```python
await sw.new_tab("https://example.com/other")
print(sw.tab_count)  # 2
await sw.switch_tab(1)
await sw.close_tab(1)
```

## Proximos passos

- [CLI](cli.md) -- ferramenta de linha de comando
- [Multi-tab](multi-tab.md) -- gestao de multiplas tabs
- [Modos de Replay](modos-de-replay.md) -- entenda os 7 modos de execucao
- [Emergency API](emergency-api.md) -- todos os 290+ metodos de acesso direto
- [run_json()](run-json.md) -- execute acoes escritas manualmente em JSON
- [Logging](logging.md) -- configuracao de logging integrado
