"""Excepcoes custom do Smartwright."""
from __future__ import annotations


class SmartwrightError(Exception):
    """Erro base de todas as excepcoes do Smartwright."""


class ElementNotFoundError(SmartwrightError, LookupError):
    """Elemento nao encontrado na pagina."""

    def __init__(self, message: str = "", *, selector: str = "", element_type: str = "", index: int = -1) -> None:
        self.selector = selector
        self.element_type = element_type
        self.index = index
        super().__init__(message)


class ElementResolutionError(SmartwrightError):
    """Falha ao resolver elemento durante replay (nenhuma estrategia funcionou)."""

    def __init__(self, message: str = "", *, step: int = 0, action: str = "") -> None:
        self.step = step
        self.action = action
        super().__init__(message)


class ReplayError(SmartwrightError):
    """Erro durante replay de acoes gravadas."""

    def __init__(self, message: str = "", *, step: int = 0, action: str = "", original: Exception | None = None) -> None:
        self.step = step
        self.action = action
        self.original = original
        super().__init__(message)


class FillError(SmartwrightError):
    """Erro ao preencher campo (readonly, disabled, nao encontrado)."""


class NavigationError(SmartwrightError):
    """Erro de navegacao (timeout, URL invalida)."""


class TimeoutError(SmartwrightError):
    """Timeout ao esperar por elemento, URL ou estado de pagina."""

    def __init__(self, message: str = "", *, timeout_ms: int = 0) -> None:
        self.timeout_ms = timeout_ms
        super().__init__(message)


class CaptureError(SmartwrightError):
    """Erro ao capturar ou relocar elemento via fingerprint."""


class DialogError(SmartwrightError):
    """Erro ao lidar com alert/confirm/prompt."""


class NetworkError(SmartwrightError):
    """Erro de rede ou resposta HTTP."""


# ── Retry ────────────────────────────────────────────────────────────


class RetryExhaustedError(SmartwrightError):
    """Todas as tentativas de retry falharam."""

    def __init__(self, message: str = "", *, attempts: int = 0, last_error: Exception | None = None) -> None:
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(message)


# ── Proxy ────────────────────────────────────────────────────────────


class ProxyError(SmartwrightError):
    """Erro relacionado com proxy."""


class ProxyExhaustedError(ProxyError):
    """Todos os proxies estao indisponiveis."""


# ── Session ──────────────────────────────────────────────────────────


class SessionError(SmartwrightError):
    """Erro ao salvar, carregar ou limpar sessao."""


# ── Captcha ──────────────────────────────────────────────────────────


class CaptchaSolverError(SmartwrightError):
    """Erro ao resolver captcha."""


class CaptchaNotDetectedError(SmartwrightError):
    """Nenhum captcha detectado na pagina."""


# ── Tabs ────────────────────────────────────────────────────────────


class TabError(SmartwrightError):
    """Erro relacionado com gestao de tabs (indice invalido, etc.)."""

    def __init__(self, message: str = "", *, index: int = -1) -> None:
        self.index = index
        super().__init__(message)
