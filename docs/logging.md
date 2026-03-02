# Logging

O Smartwright usa o modulo `logging` da stdlib com o logger `"smartwright"`. Por padrao nao emite nada (NullHandler). Para ativar, use `setup_logging()`.

## Ativar logging

```python
from smartwright import setup_logging
import logging

# Nivel INFO (recomendado para uso geral)
setup_logging()

# Nivel DEBUG (verbose — mostra cada step, retry, proxy, etc.)
setup_logging(level=logging.DEBUG)

# Formato customizado
setup_logging(
    level=logging.DEBUG,
    fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
```

## O que e logado

### Retry (`retry.py`)

| Nivel | Mensagem |
|-------|----------|
| DEBUG | `Retry attempt 1/3 after TimeoutError, delay=1.0s` |
| WARNING | `All 3 retry attempts exhausted` |

### Proxy (`proxy.py`)

| Nivel | Mensagem |
|-------|----------|
| DEBUG | `Proxy rotation: selected http://proxy:8080 (strategy=round_robin)` |
| DEBUG | `Proxy recovered from cooldown: http://proxy:8080` |
| INFO | `Proxy success: http://proxy:8080` |
| WARNING | `Proxy marked unhealthy: http://proxy:8080 (failures=3)` |

### Session (`_session.py`)

| Nivel | Mensagem |
|-------|----------|
| INFO | `Session saved to /path/sessao.json` |
| INFO | `Session loaded from /path/sessao.json` |
| DEBUG | `Session cleared` |

### Captcha (`captcha/solver.py`, `captcha/twocaptcha.py`)

| Nivel | Mensagem |
|-------|----------|
| INFO | `Captcha detected: recaptcha_v2` |
| DEBUG | `Site key extracted: 6LcXyz...` |
| INFO | `Captcha token injected for recaptcha_v2` |
| INFO | `2captcha: submitting recaptcha_v2 task` |
| DEBUG | `2captcha: polling task 12345678` |
| INFO | `2captcha: solved in 15.3s` |

### run_json (`_run_json.py`)

| Nivel | Mensagem |
|-------|----------|
| DEBUG | `run_json step 1: goto` |
| WARNING | `run_json step 3 error: Element not found` |

### Replay (`_replay.py`)

| Nivel | Mensagem |
|-------|----------|
| INFO | `replay mode: padrao` |
| DEBUG | `replay step 1: goto` |

### Debug (`_debug.py`)

| Nivel | Mensagem |
|-------|----------|
| DEBUG | `debug: cursor injected` |
| DEBUG | `debug: screenshot debug_run/step_001_click.png` |

## Usar com logging padrao do Python

O logger `"smartwright"` e um logger Python normal. Pode ser configurado diretamente:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
# Todos os loggers ficam ativos, incluindo smartwright

# Ou configurar so o smartwright
logging.getLogger("smartwright").setLevel(logging.DEBUG)
```

## Desativar logging

Por padrao ja esta desativado. Se ativou e quer desativar:

```python
import logging
logging.getLogger("smartwright").handlers.clear()
logging.getLogger("smartwright").addHandler(logging.NullHandler())
```
