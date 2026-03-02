# Network Learning

## Proposito

O Network Learning observa automaticamente o trafego de rede durante a navegacao e descobre endpoints de API. As APIs descobertas sao salvas como `ApiKnowledge` e podem ser reutilizadas para execucao direta (API-first), sem precisar interagir com o DOM.

## Como funciona

1. O `NetworkLearner` intercepta eventos `request` e `response` do Playwright via `page.on()`
2. Cada request e analisado: URL, metodo HTTP, headers e payload sao capturados
3. Cada response e verificado: se e uma API (por path, content-type ou padrao XHR), os dados sao extraidos
4. O endpoint e normalizado (IDs dinamicos viram `{id}`)
5. Um intent e inferido automaticamente a partir da URL
6. O resultado e salvo como `ApiKnowledge` no `KnowledgeStore`

## Ativando

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

        # Ativar network learning ANTES de navegar
        sw.attach_network_learning()

        await sw.goto("https://app.exemplo.com")

        # Navegar normalmente — APIs sao descobertas em background
        await sw.emergency_click("button", 0)  # ex: clicar em "Carregar dados"

        # Verificar APIs descobertas
        print(sw.network_summary())
        for api in sw.network_discoveries:
            print(f"  {api['method']} {api['endpoint']} -> {api['intent']}")

        await browser.close()

asyncio.run(main())
```

### attach_network_learning()

```python
sw.attach_network_learning()
```

Conecta os listeners de `request` e `response` ao page. Deve ser chamado **antes** de navegar para capturar todo o trafego.

Nota: `sw.goto()` chama `attach_network_learning()` automaticamente. Mas se voce usa `page.goto()` direto, precisa chamar manualmente.

## Deteccao de API

O sistema usa tres criterios para detectar se um response e de API:

### 1. Marcadores de path

URLs que contem esses segmentos sao consideradas APIs:

```
/api/, /v1/, /v2/, /v3/, /v4/
/rest/, /graphql, /gql
/rpc/, /services/, /endpoint/
/_api/, /ajax/, /xhr/
```

### 2. Content-Type

Responses com esses content-types sao APIs:

```
application/json
application/graphql
application/x-ndjson
text/event-stream
```

### 3. Padrao XHR

Path sem extensao de arquivo + response JSON = API.

### Filtros

Recursos estaticos sao ignorados automaticamente:

```
.js, .css, .png, .jpg, .jpeg, .gif, .svg, .ico,
.woff, .woff2, .ttf, .eot, .map, .webp, .avif,
.mp4, .webm, .ogg, .mp3, .wav
```

Responses com status < 200 ou >= 400 tambem sao ignorados.

## Normalizacao de URL

IDs dinamicos em URLs sao substituidos por `{id}` para criar templates reutilizaveis:

```
/api/users/123/posts           -> /api/users/{id}/posts
/api/orders/a1b2c3d4-e5f6...  -> /api/orders/{id}
/api/products/5f4dcc3b5aa7... -> /api/products/{id}
```

Patterns reconhecidos como IDs dinamicos:

- UUIDs: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`
- IDs numericos: `123`, `98765`
- MongoDB ObjectIds: `5f4dcc3b5aa765d61d8327de`
- Hashes MD5/SHA: 32-64 caracteres hexadecimais
- Tokens longos: 20+ caracteres alfanumericos

## Inferencia de intent

O sistema gera um intent automatico a partir da URL e metodo HTTP.

### Keywords conhecidas

| Keywords na URL | Intent gerado |
|----------------|---------------|
| `login`, `signin`, `sign-in`, `auth/login` | `api:login` |
| `logout`, `signout`, `sign-out` | `api:logout` |
| `register`, `signup`, `sign-up` | `api:register` |
| `user`, `profile`, `account`, `me` | `api:user` |
| `search`, `query`, `find` | `api:search` |
| `message`, `chat`, `conversation` | `api:messages` |
| `notification`, `alert` | `api:notifications` |
| `cart`, `basket` | `api:cart` |
| `order`, `purchase`, `checkout` | `api:order` |
| `payment`, `pay`, `billing` | `api:payment` |
| `product`, `item`, `catalog` | `api:products` |
| `upload`, `file`, `attachment` | `api:upload` |
| `settings`, `preferences`, `config` | `api:settings` |

### Sufixos por metodo HTTP

- `POST` -> `:create`
- `PUT` -> `:update`
- `DELETE` -> `:delete`
- `GET` -> sem sufixo

Exemplos:

```
POST /api/v1/users         -> api:user:create
GET  /api/v1/users/123     -> api:user
PUT  /api/v1/settings      -> api:settings:update
DELETE /api/v1/cart/items/5 -> api:cart:delete
```

### Fallback

Se nenhuma keyword e reconhecida, o intent e gerado a partir dos ultimos segmentos do path:

```
GET /api/v1/custom/widgets -> api:custom:widgets
POST /api/v1/analytics/events -> api:analytics:events:create
```

## Acessando as descobertas

### Lista completa

```python
for api in sw.network_discoveries:
    print(f"Intent:   {api['intent']}")
    print(f"Metodo:   {api['method']}")
    print(f"Endpoint: {api['endpoint']}")
    print(f"Original: {api['original_url']}")
    print(f"Status:   {api['status']}")
    print(f"Payload:  {api['payload_template']}")
    print(f"Headers:  {api['headers']}")
    print(f"Response: {api['response_sample']}")
    print("---")
```

### Resumo

```python
resumo = sw.network_summary()
print(f"Total de APIs: {resumo['total_discovered']}")
print(f"Por metodo: {resumo['by_method']}")
print(f"Por dominio: {resumo['by_domain']}")
print(f"Intents: {resumo['intents']}")
```

Saida tipica:

```python
{
    'total_discovered': 5,
    'by_method': {'GET': 3, 'POST': 2},
    'by_domain': {'api.exemplo.com': 5},
    'intents': ['api:user', 'api:products', 'api:cart', 'api:order:create', 'api:search'],
}
```

### Buscar por intent

```python
# Buscar discovery com metadata completa
discovery = sw.network_discovery("api:user")
if discovery:
    print(f"Endpoint: {discovery['endpoint']}")
    print(f"Response sample: {discovery['response_sample']}")

# Buscar ApiKnowledge salva (para execucao API-first)
knowledge = sw.get_api_knowledge("api:user")
if knowledge:
    print(f"Endpoint: {knowledge.endpoint}")
    print(f"Metodo: {knowledge.method}")
    print(f"Confianca: {knowledge.confidence}")
```

## Headers capturados

Apenas headers relevantes para replay sao salvos:

```
authorization, content-type, accept, x-api-key,
x-csrf-token, x-xsrf-token, x-requested-with
```

Headers de browser, cache e encoding sao ignorados.

## Response body

O body do response e capturado como sample truncado para evitar memoria excessiva:

- Profundidade maxima: 3 niveis
- Maximo de keys por objeto: 20
- Arrays: apenas o primeiro item como sample
- Strings: truncadas em 200 caracteres

## Uso direto do NetworkLearner

```python
from smartwright.network_learning.observer import NetworkLearner
from smartwright.core.store import KnowledgeStore

store = KnowledgeStore(".knowledge.json")
learner = NetworkLearner(store)

# Conectar ao page
learner.attach(page)

# Navegar normalmente...
await page.goto("https://api.exemplo.com")

# Consultar
print(learner.discoveries)
print(learner.summary())

# Limpar
learner.clear()
```

## Execucao API-first

Quando o `DecisionEngine` detecta que existe `ApiKnowledge` para um intent, ele executa via API diretamente (sem tocar no DOM):

```python
sw = Smartwright(page=page, request_context=context.request, intents={
    "user_data": ["Perfil", "Meus dados"],
})

# Primeira vez: resolve via DOM
await sw.goto("https://app.exemplo.com/perfil")
# Network learning descobre: GET /api/v1/user -> api:user

# Proximas vezes: se houver ApiKnowledge salva, o engine pode usar
# a API diretamente, sem precisar clicar em botoes
```

A execucao API-first e automatica e transparente. O `DecisionEngine` verifica primeiro se existe API knowledge antes de tentar resolucao DOM.
