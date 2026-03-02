# CLI — Ferramenta de Linha de Comando

O Smartwright inclui um CLI para executar, gravar e reproduzir fluxos de automacao diretamente do terminal.

## Instalacao

Apos instalar o package, o comando `smartwright` fica disponivel:

```bash
pip install smartwright
playwright install chromium
```

Ou execute via modulo Python:

```bash
python -m smartwright.cli <command>
```

## Comandos

### `smartwright version`

Imprime a versao instalada.

```bash
smartwright version
# smartwright 0.4.0
```

### `smartwright run <flow.json>`

Executa um ficheiro JSON de acoes escritas manualmente. Usa `run_json_file()` internamente.

```bash
smartwright run flow.json
smartwright run flow.json --mode mix
smartwright run flow.json --no-headless --debug
smartwright run flow.json --base-url https://app.com
smartwright run flow.json --stop-on-error
smartwright run flow.json --delay 200 --screenshot-dir capturas
```

**Flags:**

| Flag | Default | Descricao |
|------|---------|-----------|
| `--delay` | 400 | Delay entre steps (ms) |
| `--mode` | padrao | Modo de execucao (rapido, padrao, forcado, mix) |
| `--headless` / `--no-headless` | headless | Browser visivel ou nao |
| `--base-url` | (vazio) | Prefixo para URLs relativas |
| `--debug` | off | Ativa debug visual (cursor, highlight, screenshots) |
| `--screenshot-dir` | debug_run | Diretorio para screenshots |
| `--continue-on-error` / `--stop-on-error` | continue | Continuar ou parar no primeiro erro |

### `smartwright record`

Abre browser, grava acoes do usuario e salva em JSON. Bloqueia ate o browser ser fechado.

```bash
smartwright record
smartwright record --output meu_fluxo.json
smartwright record --url https://example.com
smartwright record --headless  # gravar headless (raro, mas possivel)
```

**Flags:**

| Flag | Default | Descricao |
|------|---------|-----------|
| `--output` | recording.json | Caminho do ficheiro de saida |
| `--url` | (nenhum) | URL inicial para navegar |
| `--headless` | off (visivel) | Executar headless |

### `smartwright replay <recording.json>`

Reproduz acoes gravadas usando o motor de resolucao de 6 steps.

```bash
smartwright replay recording.json
smartwright replay recording.json --mode mix
smartwright replay recording.json --no-headless --debug
smartwright replay recording.json --delay 1000
```

**Flags:**

| Flag | Default | Descricao |
|------|---------|-----------|
| `--delay` | 500 | Delay entre steps (ms) |
| `--mode` | padrao | Modo de replay |
| `--headless` / `--no-headless` | headless | Browser visivel ou nao |
| `--debug` | off | Debug visual |
| `--screenshot-dir` | debug_replay | Diretorio para screenshots |

## Formato JSON

O ficheiro JSON aceito por `run` segue o formato do `run_json()`:

```json
[
  {"action": "goto", "url": "https://example.com"},
  {"action": "fill", "selector": "#email", "value": "user@test.com"},
  {"action": "click", "text": "Login"},
  {"action": "wait", "ms": 2000},
  {"action": "screenshot", "path": "resultado.png"}
]
```

O ficheiro JSON aceito por `replay` segue o formato do `ActionRecorder`:

```json
{
  "version": 1,
  "recorded_at": "2026-03-01T...",
  "actions": [...]
}
```

## Codigo de saida

- `0` — sucesso (todos os steps OK)
- `1` — erros (pelo menos um step falhou)
