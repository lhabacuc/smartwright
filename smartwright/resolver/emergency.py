"""EmergencyResolver — classe composta a partir de mixins modulares.

Cada mixin vive no seu proprio ficheiro dentro de smartwright/resolver/:

  _base.py      — __init__, get_by_type_index, get_by_role_index, etc.
  _interact.py  — find/click/fill/read *_first_type_containing, waits, hover, scroll_to
  _capture.py   — capture, relocate, _build_capture, click/fill/read_from_capture
  _form.py      — input value, label, checkbox, radio, form state, select options
  _content.py   — links, tables, lists, media, images, iframes, dialogs, drag, scroll
  _page.py      — page info, bulk capture, JS, element state, clicks, page ops, cookies, storage, files, GIF/HAR
  _response.py  — wait_response_text, clipboard, download, copy button heuristics
  _replay.py    — replay_actions, _resolve_element (6-step chain), save/load JSON
  _run_json.py  — run_json, _normalize_action (aliases), _resolve_manual_element
  _debug.py     — virtual cursor, highlight, ripple, screenshots
  _helpers.py   — _safe_click, _humanized_pause, _verify_resolved, _find_fillable_input
"""
from __future__ import annotations

from smartwright.resolver._base import BaseMixin, _CoordinateHandle
from smartwright.resolver._interact import InteractMixin
from smartwright.resolver._capture import CaptureMixin
from smartwright.resolver._form import FormMixin
from smartwright.resolver._content import ContentMixin
from smartwright.resolver._page import PageMixin
from smartwright.resolver._response import ResponseMixin
from smartwright.resolver._replay import ReplayMixin
from smartwright.resolver._run_json import RunJsonMixin
from smartwright.resolver._debug import DebugMixin
from smartwright.resolver._helpers import HelpersMixin
from smartwright.resolver._session import SessionMixin
from smartwright.resolver._tabs import TabsMixin


class EmergencyResolver(
    BaseMixin,
    InteractMixin,
    CaptureMixin,
    FormMixin,
    ContentMixin,
    PageMixin,
    ResponseMixin,
    ReplayMixin,
    RunJsonMixin,
    DebugMixin,
    HelpersMixin,
    SessionMixin,
    TabsMixin,
):
    """Motor de resolucao de elementos por tipo + indice com 290+ metodos.

    Composto por mixins modulares — cada um num ficheiro separado.
    Veja docstring do modulo para a lista completa.
    """

    def __init__(self, page: object) -> None:
        self.page = page


# Re-export for backwards compat
__all__ = ["EmergencyResolver", "_CoordinateHandle"]
