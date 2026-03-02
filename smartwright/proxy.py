"""Proxy rotation com health tracking e multiplas estrategias."""
from __future__ import annotations

import enum
import random
import time
from dataclasses import dataclass, field
from typing import Any

from smartwright._logging import logger
from smartwright.constants import PROXY_COOLDOWN_SECONDS, PROXY_MAX_FAILURES
from smartwright.exceptions import ProxyExhaustedError


class RotationStrategy(enum.Enum):
    """Estrategia de rotacao de proxies."""

    ROUND_ROBIN = "round_robin"
    RANDOM = "random"


@dataclass(frozen=True, slots=True)
class ProxyConfig:
    """Configuracao de um proxy individual.

    Args:
        server: Endereco do proxy (ex: "http://proxy.example.com:8080").
        username: Username para autenticacao (opcional).
        password: Password para autenticacao (opcional).
        protocol: Protocolo do proxy.
    """

    server: str
    username: str = ""
    password: str = ""
    protocol: str = "http"

    def to_playwright_dict(self) -> dict[str, str]:
        """Converte para dict compativel com browser.launch(proxy=...)."""
        d: dict[str, str] = {"server": self.server}
        if self.username:
            d["username"] = self.username
        if self.password:
            d["password"] = self.password
        return d


@dataclass(slots=True)
class ProxyHealth:
    """Estado de saude de um proxy."""

    proxy: ProxyConfig
    failures: int = 0
    last_failure: float | None = None
    is_healthy: bool = True
    total_uses: int = 0


class ProxyRotator:
    """Gerenciador de rotacao de proxies com health tracking.

    Args:
        proxies: Lista de ProxyConfig para rotacionar.
        strategy: Estrategia de selecao (ROUND_ROBIN ou RANDOM).
        max_failures: Falhas consecutivas antes de marcar proxy como unhealthy.
        cooldown_seconds: Tempo em segundos antes de tentar um proxy unhealthy novamente.
    """

    def __init__(
        self,
        proxies: list[ProxyConfig],
        strategy: RotationStrategy = RotationStrategy.ROUND_ROBIN,
        max_failures: int = PROXY_MAX_FAILURES,
        cooldown_seconds: float = PROXY_COOLDOWN_SECONDS,
    ) -> None:
        if not proxies:
            raise ValueError("At least one proxy is required")
        self._strategy = strategy
        self._max_failures = max_failures
        self._cooldown_seconds = cooldown_seconds
        self._health: list[ProxyHealth] = [ProxyHealth(proxy=p) for p in proxies]
        self._index = 0

    @property
    def healthy_count(self) -> int:
        """Numero de proxies atualmente saudaveis (inclui recovered)."""
        self._recover_cooled()
        return sum(1 for h in self._health if h.is_healthy)

    def _recover_cooled(self) -> None:
        """Re-habilita proxies cujo cooldown expirou."""
        now = time.monotonic()
        for h in self._health:
            if not h.is_healthy and h.last_failure is not None:
                if now - h.last_failure >= self._cooldown_seconds:
                    h.is_healthy = True
                    h.failures = 0
                    logger.debug("Proxy recovered from cooldown: %s", h.proxy.server)

    def _find_health(self, proxy: ProxyConfig) -> ProxyHealth | None:
        for h in self._health:
            if h.proxy == proxy:
                return h
        return None

    def next(self) -> ProxyConfig:
        """Retorna o proximo proxy saudavel.

        Raises:
            ProxyExhaustedError: Se nenhum proxy saudavel esta disponivel.
        """
        self._recover_cooled()
        healthy = [h for h in self._health if h.is_healthy]
        if not healthy:
            raise ProxyExhaustedError(
                f"All {len(self._health)} proxies are unhealthy"
            )

        if self._strategy == RotationStrategy.RANDOM:
            chosen = random.choice(healthy)
        else:  # ROUND_ROBIN
            # Avanca ate encontrar um saudavel
            for _ in range(len(self._health)):
                idx = self._index % len(self._health)
                self._index += 1
                if self._health[idx].is_healthy:
                    chosen = self._health[idx]
                    break
            else:
                chosen = healthy[0]

        chosen.total_uses += 1
        logger.debug("Proxy rotation: selected %s (strategy=%s)", chosen.proxy.server, self._strategy.value)
        return chosen.proxy

    def mark_failed(self, proxy: ProxyConfig) -> None:
        """Regista falha num proxy. Marca unhealthy apos max_failures consecutivas."""
        h = self._find_health(proxy)
        if h is None:
            return
        h.failures += 1
        h.last_failure = time.monotonic()
        if h.failures >= self._max_failures:
            h.is_healthy = False
            logger.warning("Proxy marked unhealthy: %s (failures=%d)", proxy.server, h.failures)

    def mark_success(self, proxy: ProxyConfig) -> None:
        """Regista sucesso num proxy, resetando contador de falhas."""
        h = self._find_health(proxy)
        if h is None:
            return
        h.failures = 0
        logger.info("Proxy success: %s", proxy.server)

    def reset(self) -> None:
        """Reseta todos os proxies para estado saudavel."""
        for h in self._health:
            h.failures = 0
            h.last_failure = None
            h.is_healthy = True
            h.total_uses = 0
        self._index = 0

    @staticmethod
    def get_context_options(proxy: ProxyConfig) -> dict[str, Any]:
        """Retorna opcoes de contexto Playwright para um proxy.

        Uso: ``browser.new_context(**ProxyRotator.get_context_options(proxy))``
        """
        return {"proxy": proxy.to_playwright_dict()}
