# Changelog

## [0.4.0] - 2026-03-01

### Added
- **Multi-tab / Multi-page** — TabsMixin: new_tab(), list_tabs(), switch_tab(), close_tab(), wait_for_popup(), tab_count property
- **CLI Tool** — `smartwright run|record|replay|version` via argparse (zero extra deps), entry point in pyproject.toml
- **Integrated Logging** — logger.debug/info/warning em retry, proxy, session, captcha, run_json, replay, debug modules; setup_logging() exportado
- **Complete Type Stubs** — TYPE_CHECKING imports para Page, BrowserContext, DOMSnapshot, CaptchaSolver, Callable; on_step, solver, config tipados
- Nova excepcao: TabError
- Facades no Smartwright: new_tab, list_tabs, switch_tab, close_tab, wait_for_popup, tab_count

## [0.3.0] - 2026-03-01

### Added
- **Retry Engine** — BackoffStrategy (fixed, exponential, linear), RetryConfig, with_retry(), @retry decorator
- **Proxy Rotation** — ProxyConfig, ProxyRotator com round-robin/random, health tracking e cooldown
- **Session Persistence** — save_session/load_session/clear_session (cookies + localStorage + sessionStorage em JSON)
- **Page Diff** — diff_snapshots() compara dois DOMSnapshot, page_diff() captura antes/depois automaticamente
- **Captcha Solver** — detect_captcha(), extract_site_key(), inject_captcha_token(), TwoCaptchaSolver (2captcha.com via stdlib)
- Novas excepcoes: RetryExhaustedError, ProxyError, ProxyExhaustedError, SessionError, CaptchaSolverError, CaptchaNotDetectedError
- SessionMixin adicionado ao EmergencyResolver
- Facades no Smartwright: save_session, load_session, clear_session, dom_diff_start, dom_diff_snapshots, detect_captcha, solve_captcha
- Novas constantes: retry, proxy, captcha

## [0.2.0] - 2026-03-01

### Added
- Modo de replay adaptativo (fingerprint semantico sem LLM)
- DOM Serializer para integracao com LLMs
- Debug visual (cursor, highlight, ripple, screenshots)
- Network learning (descoberta automatica de APIs)
- 8 bots de exemplo em test_reais/
- Docstrings em todos os 152 metodos publicos
- 11 guias de documentacao em docs/
- Excepcoes custom (SmartwrightError, ElementNotFoundError, etc.)
- Constantes centrais (constants.py)
- Licenca MIT
- py.typed marker para PEP 561
- Stealth/anti-deteccao (StealthConfig, fingerprint profiles)
- run_json() com aliases e campos flexiveis

### Changed
- emergency.py refatorado em 9 sub-modulos (_base, _interact, _capture, _form, _content, _page, _response, _replay, _run_json, _debug, _helpers)
- __init__.py refatorado com facade mais fina
- pyproject.toml completo com metadata, linting, testes
- Logging Python substituiu prints

### Fixed
- google_search.py usa stealth para evitar bloqueio do Google
- Viewport duplicado no contexto com stealth

## [0.1.0] - 2025-12-01

### Added
- Classe Smartwright com 290+ metodos
- EmergencyResolver (tipo + indice)
- DecisionEngine com resolucao semantica
- ActionRecorder (gravacao ao vivo)
- 7 modos de replay (rapido, padrao, por_index, por_id_e_class, forcado, mix, adaptativo)
- Capture/relocate pattern
- File system operations
- GIF generation, HAR parsing
- Knowledge persistence (JSON)
