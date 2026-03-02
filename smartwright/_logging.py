"""Logging configuration for Smartwright."""
from __future__ import annotations

import logging

# Root logger for the library
logger = logging.getLogger("smartwright")

# Null handler by default (library best practice — let users configure)
logger.addHandler(logging.NullHandler())


def setup_logging(level: int = logging.INFO, fmt: str | None = None) -> None:
    """Ativa logging do Smartwright no console.

    Chamada opcional — se o usuario nao chamar, nenhum log e emitido.

    Args:
        level: Nivel minimo (DEBUG, INFO, WARNING, ERROR).
        fmt: Formato customizado. Default: ``"%(levelname)s %(name)s: %(message)s"``.
    """
    if fmt is None:
        fmt = "%(levelname)s %(name)s: %(message)s"
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)
    logger.setLevel(level)
