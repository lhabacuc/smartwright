"""Constantes centrais do Smartwright."""
from __future__ import annotations

# ── Timeouts (ms) ─────────────────────────────────────────────────────
DEFAULT_TIMEOUT_MS: int = 7000
"""Timeout padrao para resolucao de elementos."""

LONG_TIMEOUT_MS: int = 15000
"""Timeout para waits (wait_for_element, wait_for_text, etc.)."""

NAVIGATION_TIMEOUT_MS: int = 30000
"""Timeout para navegacao e load de pagina."""

RESPONSE_TIMEOUT_MS: int = 90000
"""Timeout para esperar resposta de streaming (chatbot)."""

DOWNLOAD_TIMEOUT_MS: int = 30000
"""Timeout para esperar download."""

CLIPBOARD_TIMEOUT_MS: int = 10000
"""Timeout para leitura de clipboard."""

# ── Debug ─────────────────────────────────────────────────────────────
DEBUG_PAUSE_MS: int = 350
"""Pausa entre acoes no modo debug."""

DEBUG_SCREENSHOT_DIR: str = "debug_screenshots"
"""Diretorio padrao para screenshots de debug."""

# ── Replay ────────────────────────────────────────────────────────────
DEFAULT_REPLAY_DELAY_MS: int = 500
"""Delay padrao entre steps de replay."""

DEFAULT_RUN_JSON_DELAY_MS: int = 400
"""Delay padrao entre steps de run_json."""

# ── Humanization ──────────────────────────────────────────────────────
HUMANIZED_PAUSE_MIN_MS: int = 80
"""Pausa minima humanizada entre acoes."""

HUMANIZED_PAUSE_MAX_MS: int = 250
"""Pausa maxima humanizada entre acoes."""

HUMANIZED_TYPING_MIN_MS: int = 30
"""Delay minimo entre teclas (digitacao humanizada)."""

HUMANIZED_TYPING_MAX_MS: int = 90
"""Delay maximo entre teclas (digitacao humanizada)."""

# ── Adaptive Replay ───────────────────────────────────────────────────
ADAPTIVE_CONFIDENCE_THRESHOLD: float = 25.0
"""Score minimo para considerar um match confiavel no replay adaptativo."""

# ── Network Learning ──────────────────────────────────────────────────
MAX_RESPONSE_BODY_SIZE: int = 5000
"""Tamanho maximo do body de resposta capturado pelo network learning."""

# ── DOM Serializer ────────────────────────────────────────────────────
DOM_MAX_ELEMENTS: int = 500
"""Numero maximo de elementos no DOM serializado."""

DOM_MAX_TEXT_LENGTH: int = 80
"""Comprimento maximo de texto por elemento."""

# ── File paths ────────────────────────────────────────────────────────
DEFAULT_STORE_PATH: str = ".smartwright_knowledge.json"
"""Caminho padrao do ficheiro de persistencia de conhecimento."""

DEFAULT_RECORDING_PATH: str = "recording.json"
"""Caminho padrao para gravacoes."""

# ── Captcha ──────────────────────────────────────────────────────────
CAPTCHA_POLL_INTERVAL_S: float = 5.0
"""Intervalo entre polls do resultado do captcha (segundos)."""

CAPTCHA_MAX_WAIT_S: float = 180.0
"""Tempo maximo de espera pela resolucao do captcha (segundos)."""

# ── Proxy ────────────────────────────────────────────────────────────
PROXY_MAX_FAILURES: int = 3
"""Falhas consecutivas antes de marcar proxy como unhealthy."""

PROXY_COOLDOWN_SECONDS: float = 300.0
"""Tempo em segundos antes de tentar um proxy unhealthy novamente."""

# ── Retry ────────────────────────────────────────────────────────────
DEFAULT_RETRY_ATTEMPTS: int = 3
"""Numero padrao de tentativas de retry."""

DEFAULT_RETRY_DELAY_S: float = 1.0
"""Delay base padrao entre tentativas (segundos)."""

MAX_RETRY_DELAY_S: float = 30.0
"""Delay maximo entre tentativas (segundos)."""

# ── Version ───────────────────────────────────────────────────────────
VERSION: str = "0.4.0"
"""Versao atual da lib."""
