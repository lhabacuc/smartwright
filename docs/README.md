# Smartwright -- Documentacao

Motor de automacao web adaptativo com gravacao ao vivo, replay inteligente e 290+ metodos para qualquer tarefa de automacao.

Smartwright resolve elementos por **intencao semantica**, **tipo + indice**, **fingerprint adaptativo** ou **selectors CSS** -- sem depender de IDs frageis que mudam entre deploys.

## Indice

| Guia | Descricao |
|------|-----------|
| [Inicio Rapido](inicio-rapido.md) | Instalacao e primeiro uso em 5 minutos |
| [CLI](cli.md) | Ferramenta de linha de comando: run, record, replay |
| [Multi-tab](multi-tab.md) | Gestao de multiplas tabs e popups |
| [Modos de Replay](modos-de-replay.md) | Os 7 modos de execucao: rapido, padrao, por_index, por_id_e_class, forcado, mix, adaptativo |
| [Replay Adaptativo](replay-adaptativo.md) | Guia completo do modo adaptativo com fingerprint semantico |
| [run_json()](run-json.md) | Executar acoes escritas manualmente em JSON |
| [DOM Serializer](dom-serializer.md) | Representacao compacta do DOM para LLMs |
| [Network Learning](network-learning.md) | Descoberta automatica de APIs via observacao de trafego |
| [Gravacao e Replay](gravacao-e-replay.md) | Gravar acoes do usuario e reproduzir com resolucao inteligente |
| [Metodos Emergency](emergency-api.md) | Interacao direta por tipo + indice (290+ metodos) |
| [Debug Visual](debug-visual.md) | Cursor, highlight, ripple e screenshots automaticos |
| [Stealth / Anti-deteccao](stealth.md) | Configuracao anti-bot: WebGL, canvas, webdriver, etc. |
| [Logging](logging.md) | Configuracao de logging integrado |

## Requisitos

- Python >= 3.10
- Playwright >= 1.45

## Instalacao rapida

```bash
pip install smartwright
playwright install chromium
```

## Arquitetura

```
smartwright/
  __init__.py          # Classe principal Smartwright (290+ metodos, type stubs)
  cli.py               # CLI: run, record, replay, version
  _logging.py          # Logger + setup_logging()
  retry.py             # Retry engine com backoff
  proxy.py             # Proxy rotation com health tracking
  constants.py         # Configuracao central
  exceptions.py        # Hierarquia de excepcoes
  core/
    engine.py          # DecisionEngine (orquestra resolucao)
    models.py          # Dataclasses: ApiKnowledge, StrategyResult
    store.py           # Persistencia de conhecimento (JSON)
  resolver/
    emergency.py       # EmergencyResolver (12 mixins compostos)
    _tabs.py           # TabsMixin (multi-tab / multi-page)
    _session.py        # SessionMixin (persistencia de sessao)
    _replay.py         # ReplayMixin (replay com 6-step resolution)
    _run_json.py       # RunJsonMixin (execucao JSON manual)
    _debug.py          # DebugMixin (cursor, highlight, screenshots)
    dom_serializer.py  # Serializa DOM para texto indexado
    dom_diff.py        # Comparacao de snapshots
    replay_mode.py     # ReplayMode enum + ModeConfig
  captcha/
    solver.py          # Deteccao + extracao + injecao de captcha
    twocaptcha.py      # 2Captcha.com solver
  recorder/
    __init__.py        # ActionRecorder (gravacao ao vivo)
  network_learning/
    observer.py        # NetworkLearner (descobre APIs)
  stealth/
    __init__.py        # StealthConfig, apply_stealth, fingerprint profiles
```
