"""Resolver — resolucao de elementos por tipo+indice, capture, replay, run_json."""
from smartwright.resolver.dom_diff import PageDiff, diff_snapshots
from smartwright.resolver.emergency import EmergencyResolver

__all__ = ["EmergencyResolver", "PageDiff", "diff_snapshots"]
