"""Retry engine com backoff strategies para operacoes async."""
from __future__ import annotations

import asyncio
import enum
import functools
import math
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, TypeVar

from smartwright.constants import (
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_DELAY_S,
    MAX_RETRY_DELAY_S,
)
from smartwright._logging import logger
from smartwright.exceptions import (
    ElementNotFoundError,
    ElementResolutionError,
    RetryExhaustedError,
    TimeoutError,
)

T = TypeVar("T")


class BackoffStrategy(enum.Enum):
    """Estrategia de backoff entre tentativas."""

    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """Configuracao de retry.

    Args:
        max_attempts: Numero maximo de tentativas (incluindo a primeira).
        backoff: Estrategia de backoff entre tentativas.
        base_delay_s: Delay base em segundos.
        max_delay_s: Delay maximo em segundos (cap).
        retryable_exceptions: Tupla de excepcoes que disparam retry.
        on_retry: Callback opcional chamado antes de cada retry.
            Recebe (attempt: int, exception: Exception, delay: float).
    """

    max_attempts: int = DEFAULT_RETRY_ATTEMPTS
    backoff: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    base_delay_s: float = DEFAULT_RETRY_DELAY_S
    max_delay_s: float = MAX_RETRY_DELAY_S
    retryable_exceptions: tuple[type[BaseException], ...] = (
        TimeoutError,
        ElementNotFoundError,
        ElementResolutionError,
    )
    on_retry: Callable[[int, Exception, float], Any] | None = None


def compute_delay(config: RetryConfig, attempt: int) -> float:
    """Calcula delay em segundos para a tentativa dada (0-indexed).

    Args:
        config: Configuracao de retry.
        attempt: Numero da tentativa (0 = primeira retry apos falha inicial).

    Returns:
        Delay em segundos, capped pelo max_delay_s.
    """
    if config.backoff == BackoffStrategy.FIXED:
        delay = config.base_delay_s
    elif config.backoff == BackoffStrategy.LINEAR:
        delay = config.base_delay_s * (attempt + 1)
    else:  # EXPONENTIAL
        delay = config.base_delay_s * math.pow(2, attempt)
    return min(delay, config.max_delay_s)


async def with_retry(
    coro_factory: Callable[[], Awaitable[T]],
    config: RetryConfig | None = None,
) -> T:
    """Executa uma coroutine factory com retry.

    Args:
        coro_factory: Callable que retorna um awaitable (chamado a cada tentativa).
        config: Configuracao de retry (usa defaults se None).

    Returns:
        Resultado da coroutine factory.

    Raises:
        RetryExhaustedError: Se todas as tentativas falharem.
    """
    cfg = config or RetryConfig()
    last_error: Exception | None = None

    for attempt in range(cfg.max_attempts):
        try:
            return await coro_factory()
        except cfg.retryable_exceptions as exc:
            last_error = exc
            if attempt + 1 >= cfg.max_attempts:
                break
            delay = compute_delay(cfg, attempt)
            logger.debug(
                "Retry attempt %d/%d after %s, delay=%.1fs",
                attempt + 1, cfg.max_attempts, type(exc).__name__, delay,
            )
            if cfg.on_retry is not None:
                cfg.on_retry(attempt + 1, exc, delay)
            await asyncio.sleep(delay)

    logger.warning("All %d retry attempts exhausted", cfg.max_attempts)
    raise RetryExhaustedError(
        f"All {cfg.max_attempts} attempts failed",
        attempts=cfg.max_attempts,
        last_error=last_error,  # type: ignore[arg-type]
    )


def retry(config: RetryConfig | None = None) -> Callable:
    """Decorator para async functions com retry automatico.

    Uso:
        @retry(RetryConfig(max_attempts=5))
        async def fetch_data():
            ...
    """
    cfg = config or RetryConfig()

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await with_retry(lambda: fn(*args, **kwargs), cfg)
        return wrapper

    return decorator
