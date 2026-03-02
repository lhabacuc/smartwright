# Stealth / Anti-deteccao

## Proposito

O modulo stealth aplica tecnicas de anti-deteccao para fazer o Playwright parecer um browser real, evitando bloqueios por sistemas anti-bot (Cloudflare, DataDome, PerimeterX, etc.).

## StealthConfig

```python
from smartwright.stealth import StealthConfig
```

### Protecoes disponiveis

| Protecao | Default | O que faz |
|----------|---------|-----------|
| `webdriver` | True | Spoofa `navigator.webdriver` para `undefined` |
| `plugins` | True | Faz `navigator.plugins` e `mimeTypes` com plugins realistas |
| `chrome_object` | True | Cria `window.chrome.app` e `window.chrome.runtime` |
| `permissions` | True | Corrige `navigator.permissions.query` para notifications |
| `hardware` | True | Spoofa `hardwareConcurrency`, `deviceMemory`, `platform`, `languages` |
| `webgl` | True | Spoofa vendor/renderer do WebGL (parametros 37445/37446) |
| `canvas` | True | Adiciona ruido ao canvas fingerprint (toDataURL/toBlob) |
| `audio` | True | Adiciona ruido ao audio fingerprint (AnalyserNode/AudioBuffer) |
| `connection` | True | Faz `navigator.connection` com dados realistas (4g, 50ms RTT) |
| `webrtc` | True | Previne vazamento de IP via WebRTC (limpa iceServers) |

### Opcoes de lancamento do browser

| Opcao | Default | O que faz |
|-------|---------|-----------|
| `disable_automation` | True | Remove flag `--enable-automation` |
| `disable_blink_features` | True | `--disable-blink-features=AutomationControlled` |
| `disable_infobars` | True | Esconde barra "controlado por automacao" |
| `no_sandbox` | False | `--no-sandbox` (necessario em alguns ambientes) |

### Outros

| Opcao | Default | Descricao |
|-------|---------|-----------|
| `profile` | None | Perfil de fingerprint especifico (None = aleatorio) |
| `user_agent` | None | User-Agent customizado (None = do perfil) |
| `extra_args` | [] | Args extras do Chromium |

## Presets

### Full (default)

Todas as protecoes ativas com perfil aleatorio:

```python
cfg = StealthConfig()
# ou
cfg = StealthConfig.maximum()
```

### Minimal

Apenas o essencial: webdriver + flags de automacao. Mais rapido e menos intrusivo:

```python
cfg = StealthConfig.minimal()
# plugins=False, chrome_object=False, permissions=False,
# hardware=False, webgl=False, canvas=False, audio=False,
# connection=False, webrtc=False
```

### Personalizado

```python
cfg = StealthConfig(
    webdriver=True,
    plugins=True,
    chrome_object=True,
    permissions=True,
    hardware=True,
    webgl=False,       # desativar WebGL spoofing
    canvas=False,       # desativar canvas noise
    audio=False,        # desativar audio noise
    connection=True,
    webrtc=True,
    no_sandbox=True,    # necessario em containers Docker
)
```

## Uso completo

### Setup manual (controle total)

```python
import asyncio
from playwright.async_api import async_playwright
from smartwright import Smartwright
from smartwright.stealth import (
    StealthConfig,
    get_stealth_args,
    get_ignored_default_args,
    get_context_options,
    apply_stealth,
)

async def main():
    cfg = StealthConfig()

    async with async_playwright() as p:
        # 1. Lancar browser com args de stealth
        browser = await p.chromium.launch(
            headless=False,
            args=get_stealth_args(cfg),
            ignore_default_args=get_ignored_default_args(cfg),
        )

        # 2. Criar context com opcoes de fingerprint
        context = await browser.new_context(**get_context_options(cfg))

        # 3. Aplicar injecoes JS (ANTES de navegar)
        await apply_stealth(context, cfg)

        # 4. Criar page e usar normalmente
        page = await context.new_page()
        sw = Smartwright(page=page, request_context=context.request)

        await sw.goto("https://bot.sannysoft.com")
        await asyncio.sleep(5)  # ver resultados

        await browser.close()

asyncio.run(main())
```

### Com ActionRecorder

O recorder tem suporte integrado para stealth:

```python
from smartwright.recorder import ActionRecorder
from smartwright.stealth import StealthConfig

recorder = ActionRecorder(
    save_path="fluxo.json",
    stealth=True,
    stealth_config=StealthConfig(),
)

page = await recorder.start(url="https://site-protegido.com")
actions = await recorder.wait_until_closed()
```

Quando `stealth=True`, o recorder automaticamente:
- Usa `get_stealth_args()` para os args do browser
- Usa `get_ignored_default_args()` para remover `--enable-automation`
- Aplica `apply_stealth()` ao contexto antes de navegar

### Aplicar a pagina ja aberta

Se voce nao controla a criacao do contexto (ex: persistent context), use `apply_stealth_to_page()`:

```python
from smartwright.stealth import apply_stealth_to_page, StealthConfig

cfg = StealthConfig()
await apply_stealth_to_page(page, cfg)
```

Nota: esta abordagem e menos confiavel que `apply_stealth()` no contexto, pois o JS roda depois dos scripts da pagina.

## Fingerprint profiles

O modulo inclui 6 perfis realistas pre-configurados com User-Agent, platform, viewport, timezone, locale, hardware e WebGL consistentes entre si:

### Perfil 1 -- Windows Chrome (New York)

```python
{
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ... Chrome/131.0.0.0 Safari/537.36",
    "platform": "Win32",
    "languages": ["en-US", "en"],
    "viewport": {"width": 1920, "height": 1080},
    "device_scale_factor": 1,
    "timezone": "America/New_York",
    "locale": "en-US",
    "hardware_concurrency": 8,
    "device_memory": 8,
    "webgl_vendor": "Google Inc. (NVIDIA)",
    "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
}
```

### Perfil 2 -- Windows Chrome (Chicago)

```python
{
    "platform": "Win32",
    "viewport": {"width": 1366, "height": 768},
    "timezone": "America/Chicago",
    "hardware_concurrency": 4,
    "webgl_renderer": "ANGLE (Intel, Intel(R) UHD Graphics 630 ...)",
}
```

### Perfil 3 -- macOS Chrome (Los Angeles)

```python
{
    "platform": "MacIntel",
    "viewport": {"width": 1440, "height": 900},
    "device_scale_factor": 2,
    "timezone": "America/Los_Angeles",
    "hardware_concurrency": 10,
    "device_memory": 16,
    "webgl_renderer": "Apple M1 Pro",
}
```

### Perfil 4 -- Linux Chrome (London)

```python
{
    "platform": "Linux x86_64",
    "viewport": {"width": 1920, "height": 1080},
    "timezone": "Europe/London",
    "locale": "en-GB",
    "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 Ti, OpenGL 4.5)",
}
```

### Perfil 5 -- Windows Edge (Sao Paulo) -- PT-BR

```python
{
    "user_agent": "... Chrome/131.0.0.0 ... Edg/131.0.0.0",
    "platform": "Win32",
    "languages": ["pt-BR", "pt", "en"],
    "timezone": "America/Sao_Paulo",
    "locale": "pt-BR",
    "webgl_renderer": "ANGLE (AMD, AMD Radeon RX 580, ...)",
}
```

### Perfil 6 -- macOS Chrome (Madrid) -- ES

```python
{
    "platform": "MacIntel",
    "viewport": {"width": 2560, "height": 1440},
    "device_scale_factor": 2,
    "timezone": "Europe/Madrid",
    "locale": "es-ES",
    "hardware_concurrency": 12,
    "device_memory": 32,
    "webgl_renderer": "Apple M2 Max",
}
```

### Usar perfil especifico

```python
from smartwright.stealth import StealthConfig, PROFILES

# Usar o perfil PT-BR (indice 4)
cfg = StealthConfig(profile=PROFILES[4])

# Usar perfil aleatorio (default)
cfg = StealthConfig()  # profile=None seleciona aleatorio

# Perfil customizado
cfg = StealthConfig(profile={
    "user_agent": "Mozilla/5.0 ...",
    "platform": "Win32",
    "languages": ["pt-BR", "pt"],
    "viewport": {"width": 1920, "height": 1080},
    "timezone": "America/Sao_Paulo",
    "locale": "pt-BR",
    "hardware_concurrency": 8,
    "device_memory": 16,
    "webgl_vendor": "Google Inc. (NVIDIA)",
    "webgl_renderer": "ANGLE (NVIDIA, ...)",
})
```

### Override de User-Agent

```python
cfg = StealthConfig(
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/132.0.0.0 Safari/537.36"
)
```

O `user_agent` do config tem prioridade sobre o do perfil.

## O que cada injecao faz

### navigator.webdriver

```javascript
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
```

Bots sao detectados por `navigator.webdriver === true`. A injecao faz retornar `undefined`.

### navigator.plugins

Cria 3 plugins realistas: Chrome PDF Plugin, Chrome PDF Viewer, Native Client. Browsers automatizados normalmente tem `plugins.length === 0`.

### window.chrome

Cria o objeto `window.chrome` com `app` e `runtime` consistentes com Chrome real. Muitos sites verificam `window.chrome.runtime`.

### navigator.permissions

Corrige `navigator.permissions.query({name:'notifications'})` para retornar o estado real de `Notification.permission`.

### Hardware

Spoofa `platform`, `languages`, `hardwareConcurrency` e `deviceMemory` com valores do perfil.

### WebGL

Intercepta `getParameter(37445)` (vendor) e `getParameter(37446)` (renderer) para retornar valores do perfil.

### Canvas

Adiciona ruido minimo (1 bit flip aleatorio por pixel a cada 4) ao `toDataURL()` e `toBlob()` para gerar fingerprints unicos.

### Audio

Adiciona ruido flutuante minimo ao `getFloatFrequencyData` e `getChannelData` para variar o audio fingerprint.

### WebRTC

Limpa `iceServers` na criacao de `RTCPeerConnection` para prevenir vazamento do IP real.

## Funcoes utilitarias

```python
from smartwright.stealth import (
    get_stealth_args,          # Args do Chromium
    get_ignored_default_args,  # Args a ignorar
    get_context_options,       # Opcoes do context (viewport, UA, etc.)
    apply_stealth,             # Injecoes JS no contexto
    apply_stealth_to_page,     # Injecoes JS direto na pagina
    build_stealth_js,          # Gerar JS combinado (sem aplicar)
)

# Gerar JS para uso customizado
js = build_stealth_js(cfg)
print(js)  # todo o JavaScript de injecao
```

## Verificacao

Use sites de teste para verificar se o stealth esta funcionando:

```python
await sw.goto("https://bot.sannysoft.com")        # Teste geral
await sw.goto("https://arh.antoinevastel.com/bots/areyouheadless")  # Headless check
await sw.goto("https://browserleaks.com/webgl")   # WebGL fingerprint
await sw.goto("https://browserleaks.com/canvas")  # Canvas fingerprint
```

No `bot.sannysoft.com`, todos os testes devem aparecer verdes com stealth ativo.
