from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReplayMode(str, Enum):
    """Execution mode for replay_actions().

    Controls resolution strategy, click behavior, and timing.
    """

    RAPIDO = "rapido"
    PADRAO = "padrao"
    POR_INDEX = "por_index"
    POR_ID_E_CLASS = "por_id_e_class"
    FORCADO = "forcado"
    MIX = "mix"
    ADAPTATIVO = "adaptativo"

    @classmethod
    def from_str(cls, value: str) -> ReplayMode:
        """Parse from CLI string, case-insensitive."""
        try:
            return cls(value.lower().strip())
        except ValueError:
            valid = ", ".join(m.value for m in cls)
            raise ValueError(
                f"Modo invalido '{value}'. Modos validos: {valid}"
            ) from None


@dataclass(frozen=True, slots=True)
class ModeConfig:
    """Pre-computed behavioral parameters for a ReplayMode."""

    # Resolution chain — which steps are active
    use_capture_selectors: bool = True    # Step 1: capture CSS selectors
    verify_capture: bool = True           # Text/bbox verification on step 1
    use_action_selector: bool = True      # Step 2: action-level CSS selector
    use_type_index_text: bool = True      # Step 3: type + index + text pattern
    use_type_text: bool = True            # Step 4: type + text (ignoring index)
    use_type_index: bool = True           # Step 5/5b: type + index ordinal
    use_coordinates: bool = True          # Step 6: bbox pixel coordinates

    # Filter selectors to stable identifiers only (#id, .class, [data-testid], [aria-label])
    selector_filter_stable_only: bool = False

    # Timeout multiplier (1.0 = normal, 0.5 = halved, 2.0 = doubled)
    timeout_factor: float = 1.0

    # Click strategy: "safe" | "force" | "simple"
    #   safe   = _safe_click (overlay wait, scroll, force as last resort)
    #   force  = always force=True, skip visibility
    #   simple = target.click() directly, no retry
    click_strategy: str = "safe"

    # Timing
    humanized_pause: bool = True          # Random micro-pause before interactions
    humanized_typing: bool = True         # Use press_sequentially for fill
    inter_step_delay: bool = True         # Apply delay_ms between steps
    delay_factor: float = 1.0             # Multiplier on delay_ms

    # Retry (for mix mode)
    retry_on_failure: bool = False
    max_retries: int = 1
    scroll_between_retries: bool = False

    # Adaptive semantic matching (for adaptativo mode)
    use_adaptive: bool = False


def get_mode_config(mode: ReplayMode) -> ModeConfig:
    """Return the ModeConfig for a given ReplayMode."""
    return _MODE_CONFIGS[mode]


_MODE_CONFIGS: dict[ReplayMode, ModeConfig] = {
    # ── rapido: velocidade maxima, sem verificacao ──
    ReplayMode.RAPIDO: ModeConfig(
        use_capture_selectors=True,
        verify_capture=False,
        use_action_selector=True,
        use_type_index_text=False,
        use_type_text=False,
        use_type_index=True,
        use_coordinates=True,
        timeout_factor=0.5,
        click_strategy="simple",
        humanized_pause=False,
        humanized_typing=False,
        inter_step_delay=False,
        delay_factor=0.0,
    ),
    # ── padrao: comportamento atual (default) ──
    ReplayMode.PADRAO: ModeConfig(),
    # ── por_index: so usa tag + indice ordinal ──
    ReplayMode.POR_INDEX: ModeConfig(
        use_capture_selectors=False,
        verify_capture=False,
        use_action_selector=False,
        use_type_index_text=False,
        use_type_text=False,
        use_type_index=True,
        use_coordinates=False,
        timeout_factor=0.7,
        click_strategy="simple",
        humanized_pause=False,
        humanized_typing=False,
        inter_step_delay=True,
        delay_factor=0.5,
    ),
    # ── por_id_e_class: so CSS com id/class/testid/aria-label ──
    ReplayMode.POR_ID_E_CLASS: ModeConfig(
        use_capture_selectors=True,
        verify_capture=False,
        use_action_selector=True,
        use_type_index_text=False,
        use_type_text=False,
        use_type_index=False,
        use_coordinates=False,
        selector_filter_stable_only=True,
        timeout_factor=0.8,
        click_strategy="safe",
        humanized_pause=True,
        humanized_typing=True,
        inter_step_delay=True,
        delay_factor=0.8,
    ),
    # ── forcado: todos os steps + force click sempre ──
    ReplayMode.FORCADO: ModeConfig(
        use_capture_selectors=True,
        verify_capture=True,
        use_action_selector=True,
        use_type_index_text=True,
        use_type_text=True,
        use_type_index=True,
        use_coordinates=True,
        timeout_factor=1.0,
        click_strategy="force",
        humanized_pause=False,
        humanized_typing=False,
        inter_step_delay=True,
        delay_factor=0.7,
    ),
    # ── mix: mais resiliente, retries, timeouts longos ──
    ReplayMode.MIX: ModeConfig(
        use_capture_selectors=True,
        verify_capture=True,
        use_action_selector=True,
        use_type_index_text=True,
        use_type_text=True,
        use_type_index=True,
        use_coordinates=True,
        timeout_factor=2.0,
        click_strategy="safe",
        humanized_pause=True,
        humanized_typing=True,
        inter_step_delay=True,
        delay_factor=1.5,
        retry_on_failure=True,
        max_retries=3,
        scroll_between_retries=True,
    ),
    # ── adaptativo: fingerprint semantico, ignora id/class ──
    ReplayMode.ADAPTATIVO: ModeConfig(
        use_capture_selectors=False,       # ignora CSS selectors gravados
        verify_capture=False,
        use_action_selector=False,         # ignora selector da acao
        use_type_index_text=False,
        use_type_text=False,
        use_type_index=False,
        use_coordinates=False,             # coordenadas so como ultimo recurso interno
        timeout_factor=1.5,
        click_strategy="safe",
        humanized_pause=True,
        humanized_typing=True,
        inter_step_delay=True,
        delay_factor=1.0,
        retry_on_failure=True,
        max_retries=2,
        scroll_between_retries=True,
        use_adaptive=True,                 # ativa matching semantico
    ),
}
