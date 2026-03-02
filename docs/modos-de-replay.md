# Modos de Replay

Smartwright oferece 7 modos de execucao que controlam a estrategia de resolucao, comportamento de click, timing e retries. O modo e passado como string para `replay_actions()`, `replay_json()`, `run_json()` e via CLI.

```python
await sw.emergency_replay_json("recording.json", mode="padrao")
await sw.run_json(actions, mode="mix")
```

## Visao geral

| Modo | Velocidade | Resiliencia | Uso ideal |
|------|-----------|-------------|-----------|
| `rapido` | Maxima | Baixa | Paginas estaveis, testes rapidos |
| `padrao` | Normal | Alta | Uso geral (default) |
| `por_index` | Alta | Baixa | DOM com estrutura fixa |
| `por_id_e_class` | Normal | Media | Sites com IDs/classes estaveis |
| `forcado` | Normal | Alta | Overlays, modais, popups |
| `mix` | Lenta | Maxima | Paginas instáveis, SPAs lentas |
| `adaptativo` | Lenta | Maxima | Sites que mudam IDs/classes entre deploys |

---

## 1. rapido

Velocidade maxima. Pula verificacao de texto/bbox, usa timeouts curtos (50% do normal), sem pausa humanizada, sem delay entre steps.

**Cadeia de resolucao:**
- Step 1: Selectors CSS do capture (sem verificacao)
- Step 2: Selector da acao
- Step 5: Tag + indice ordinal
- Step 6: Coordenadas

**Configuracao:**
```
use_capture_selectors: True
verify_capture: False
use_action_selector: True
use_type_index_text: False
use_type_text: False
use_type_index: True
use_coordinates: True
timeout_factor: 0.5
click_strategy: "simple"
humanized_pause: False
humanized_typing: False
inter_step_delay: False
```

**Quando usar:** Paginas que nao mudam, testes de regressao rapidos, automacao de sites internos estaveis.

**Exemplo:**
```python
results = await sw.emergency_replay_json("login.json", mode="rapido")
```

---

## 2. padrao

Modo default. Usa todos os 6 steps da cadeia de resolucao com verificacao de texto e bounding box. Click com `_safe_click` (espera overlays, scroll, force como ultimo recurso). Pausa humanizada e digitacao sequencial.

**Cadeia de resolucao (completa):**
- Step 1: Selectors CSS do capture (com verificacao de texto/bbox)
- Step 2: Selector da acao
- Step 3: Tipo + indice + texto
- Step 4: Tipo + texto (ignorando indice)
- Step 5: Tag + indice ordinal
- Step 6: Coordenadas pixel

**Configuracao:**
```
use_capture_selectors: True
verify_capture: True
use_action_selector: True
use_type_index_text: True
use_type_text: True
use_type_index: True
use_coordinates: True
timeout_factor: 1.0
click_strategy: "safe"
humanized_pause: True
humanized_typing: True
inter_step_delay: True
delay_factor: 1.0
```

**Quando usar:** Uso geral, primeiro replay de um recording novo, sites desconhecidos.

**Exemplo:**
```python
results = await sw.emergency_replay_json("fluxo.json", mode="padrao")
# ou simplesmente (padrao e o default):
results = await sw.emergency_replay_json("fluxo.json")
```

---

## 3. por_index

Usa exclusivamente tag + indice ordinal para resolver elementos. Ignora selectors CSS, texto e coordenadas. Rapido, mas quebra se a estrutura DOM mudar.

**Cadeia de resolucao:**
- Step 5: Tag + indice ordinal (unico step ativo)

**Configuracao:**
```
use_capture_selectors: False
verify_capture: False
use_action_selector: False
use_type_index_text: False
use_type_text: False
use_type_index: True
use_coordinates: False
timeout_factor: 0.7
click_strategy: "simple"
humanized_pause: False
inter_step_delay: True
delay_factor: 0.5
```

**Quando usar:** DOM com estrutura fixa (ex: formularios internos que nunca mudam), quando voce sabe exatamente a posicao ordinal dos elementos.

**Exemplo:**
```python
results = await sw.emergency_replay_json("form_fixo.json", mode="por_index")
```

---

## 4. por_id_e_class

Usa apenas selectors CSS estaveis: `#id`, `.class`, `[data-testid]`, `[aria-label]`. Ignora indice ordinal e coordenadas. Filtra selectors instáveis automaticamente.

**Cadeia de resolucao:**
- Step 1: Selectors CSS do capture (filtrados para estaveis)
- Step 2: Selector da acao (filtrado para estaveis)

**Configuracao:**
```
use_capture_selectors: True
verify_capture: False
use_action_selector: True
use_type_index_text: False
use_type_text: False
use_type_index: False
use_coordinates: False
selector_filter_stable_only: True
timeout_factor: 0.8
click_strategy: "safe"
humanized_pause: True
humanized_typing: True
inter_step_delay: True
delay_factor: 0.8
```

**Quando usar:** Sites com bons IDs (ex: `data-testid`, IDs semanticos), quando voce quer ignorar resolucao por texto/indice.

**Exemplo:**
```python
results = await sw.emergency_replay_json("app_react.json", mode="por_id_e_class")
```

---

## 5. forcado

Todos os 6 steps de resolucao ativos com click forcado (`force=True`). Ignora visibilidade e overlays -- clica diretamente no elemento mesmo que esteja coberto.

**Cadeia de resolucao:**
- Steps 1-6: Todos ativos (igual ao padrao)

**Configuracao:**
```
use_capture_selectors: True
verify_capture: True
use_action_selector: True
use_type_index_text: True
use_type_text: True
use_type_index: True
use_coordinates: True
timeout_factor: 1.0
click_strategy: "force"
humanized_pause: False
humanized_typing: False
inter_step_delay: True
delay_factor: 0.7
```

**Quando usar:** Paginas com overlays, modais, cookie banners, popups de newsletter que bloqueiam cliques normais.

**Exemplo:**
```python
results = await sw.emergency_replay_json("fluxo_com_modal.json", mode="forcado")
```

---

## 6. mix

Modo mais resiliente. Todos os steps ativos, timeouts dobrados (200% do normal), 3 retries com scroll entre tentativas, delay aumentado entre steps.

**Cadeia de resolucao:**
- Steps 1-6: Todos ativos
- Retry: 3 tentativas por step
- Scroll entre retries para revelar elementos

**Configuracao:**
```
use_capture_selectors: True
verify_capture: True
use_action_selector: True
use_type_index_text: True
use_type_text: True
use_type_index: True
use_coordinates: True
timeout_factor: 2.0
click_strategy: "safe"
humanized_pause: True
humanized_typing: True
inter_step_delay: True
delay_factor: 1.5
retry_on_failure: True
max_retries: 3
scroll_between_retries: True
```

**Quando usar:** Paginas com lazy loading, SPAs lentas, elementos que demoram a renderizar, situacoes onde resiliencia e mais importante que velocidade.

**Exemplo:**
```python
results = await sw.emergency_replay_json("spa_lenta.json", mode="mix")
```

---

## 7. adaptativo

Modo que usa fingerprint semantico para resolver elementos. Ignora completamente IDs e classes CSS. Compara texto, tag, tipo de input, placeholder, aria-label, name, role e posicao visual. Nao precisa de LLM.

**Cadeia de resolucao:**
- Fingerprint semantico: pontua candidatos por similaridade
- Fallback interno: selectors estaveis -> tag+texto -> get_by_text -> nth-of-type -> coordenadas

**Configuracao:**
```
use_capture_selectors: False
verify_capture: False
use_action_selector: False
use_type_index_text: False
use_type_text: False
use_type_index: False
use_coordinates: False
timeout_factor: 1.5
click_strategy: "safe"
humanized_pause: True
humanized_typing: True
inter_step_delay: True
delay_factor: 1.0
retry_on_failure: True
max_retries: 2
scroll_between_retries: True
use_adaptive: True
```

**Quando usar:** Sites que mudam IDs e classes entre deploys (frameworks CSS-in-JS, builds com hash), quando voce quer um replay robusto que sobrevive a redesigns parciais.

**Exemplo:**
```python
# Via replay_actions com modo
results = await sw.emergency_replay_json("recording.json", mode="adaptativo")

# Via metodo dedicado
results = await sw.replay_adaptive("recording.json")

# Pre-analise sem executar
diagnostico = await sw.replay_adaptive_analyze("recording.json")
for item in diagnostico:
    print(f"Step {item['step']}: score={item['score']} confident={item.get('confident')}")
```

Para detalhes sobre o algoritmo de fingerprint semantico, veja [Replay Adaptativo](replay-adaptativo.md).

---

## Usando via CLI

```bash
python qwen-cap.py replay --mode rapido
python qwen-cap.py replay --mode padrao
python qwen-cap.py replay --mode por_index
python qwen-cap.py replay --mode por_id_e_class
python qwen-cap.py replay --mode forcado
python qwen-cap.py replay --mode mix
python qwen-cap.py replay --mode adaptativo
```

## Usando via codigo

```python
from smartwright.resolver.replay_mode import ReplayMode, get_mode_config

# Converter string para enum
modo = ReplayMode.from_str("mix")

# Obter configuracao
config = get_mode_config(modo)
print(config.timeout_factor)     # 2.0
print(config.max_retries)        # 3
print(config.click_strategy)     # "safe"
```

## Comparacao de performance

| Cenario | Modo recomendado |
|---------|-----------------|
| CI/CD rapido | `rapido` |
| Primeiro teste de um recording | `padrao` |
| Formulario interno fixo | `por_index` |
| App React com data-testid | `por_id_e_class` |
| Pagina com cookie banner | `forcado` |
| SPA com lazy loading | `mix` |
| Site que muda CSS a cada deploy | `adaptativo` |
