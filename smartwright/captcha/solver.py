"""Captcha solver — deteccao, extracao de sitekey e injecao de token."""
from __future__ import annotations

import abc
import enum
from dataclasses import dataclass, field
from typing import Any

from smartwright._logging import logger
from smartwright.exceptions import CaptchaNotDetectedError, CaptchaSolverError


class CaptchaType(enum.Enum):
    """Tipos de captcha suportados."""

    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    IMAGE = "image"


@dataclass(slots=True)
class CaptchaResult:
    """Resultado de um solve de captcha."""

    captcha_type: CaptchaType
    token: str = ""
    solved: bool = False
    elapsed_seconds: float = 0.0
    error: str = ""


class CaptchaSolver(abc.ABC):
    """Interface abstrata para solvers de captcha."""

    @abc.abstractmethod
    async def solve_recaptcha_v2(self, site_key: str, page_url: str) -> CaptchaResult:
        """Resolve reCAPTCHA v2."""
        ...

    @abc.abstractmethod
    async def solve_recaptcha_v3(self, site_key: str, page_url: str, action: str = "verify") -> CaptchaResult:
        """Resolve reCAPTCHA v3."""
        ...

    @abc.abstractmethod
    async def solve_hcaptcha(self, site_key: str, page_url: str) -> CaptchaResult:
        """Resolve hCaptcha."""
        ...

    @abc.abstractmethod
    async def solve_image(self, image_base64: str) -> CaptchaResult:
        """Resolve captcha de imagem."""
        ...


async def detect_captcha(page: object) -> CaptchaType | None:
    """Detecta tipo de captcha na pagina via iframes e elementos.

    Args:
        page: Playwright Page object.

    Returns:
        CaptchaType detectado ou None se nenhum captcha presente.
    """
    evaluate = getattr(page, "evaluate", None)
    if not callable(evaluate):
        return None

    result = await evaluate(
        """() => {
            // reCAPTCHA v2 - iframe
            const recaptchaFrame = document.querySelector(
                'iframe[src*="google.com/recaptcha"], iframe[src*="recaptcha/api2"]'
            );
            if (recaptchaFrame) {
                const src = recaptchaFrame.src || '';
                if (src.includes('anchor') || src.includes('bframe')) return 'recaptcha_v2';
            }

            // reCAPTCHA v2 - div
            const recaptchaDiv = document.querySelector('.g-recaptcha');
            if (recaptchaDiv) return 'recaptcha_v2';

            // reCAPTCHA v3 - badge
            const recaptchaBadge = document.querySelector('.grecaptcha-badge');
            if (recaptchaBadge) return 'recaptcha_v3';

            // reCAPTCHA v3 - script
            const recaptchaScript = document.querySelector(
                'script[src*="recaptcha/api.js?render="]'
            );
            if (recaptchaScript) return 'recaptcha_v3';

            // hCaptcha - iframe
            const hcaptchaFrame = document.querySelector(
                'iframe[src*="hcaptcha.com"], iframe[data-hcaptcha-widget-id]'
            );
            if (hcaptchaFrame) return 'hcaptcha';

            // hCaptcha - div
            const hcaptchaDiv = document.querySelector('.h-captcha');
            if (hcaptchaDiv) return 'hcaptcha';

            return null;
        }"""
    )

    if result is None:
        return None

    type_map = {
        "recaptcha_v2": CaptchaType.RECAPTCHA_V2,
        "recaptcha_v3": CaptchaType.RECAPTCHA_V3,
        "hcaptcha": CaptchaType.HCAPTCHA,
    }
    detected = type_map.get(result)
    if detected:
        logger.info("Captcha detected: %s", detected.value)
    return detected


async def extract_site_key(page: object, captcha_type: CaptchaType) -> str | None:
    """Extrai site key (data-sitekey) do captcha detectado.

    Args:
        page: Playwright Page object.
        captcha_type: Tipo de captcha a procurar.

    Returns:
        Site key string ou None se nao encontrado.
    """
    evaluate = getattr(page, "evaluate", None)
    if not callable(evaluate):
        return None

    if captcha_type in (CaptchaType.RECAPTCHA_V2, CaptchaType.RECAPTCHA_V3):
        result = await evaluate(
            """() => {
                // Tentar div com data-sitekey
                const div = document.querySelector('.g-recaptcha[data-sitekey]');
                if (div) return div.getAttribute('data-sitekey');

                // Tentar script render param
                const script = document.querySelector('script[src*="recaptcha/api.js?render="]');
                if (script) {
                    const match = script.src.match(/render=([^&]+)/);
                    if (match) return match[1];
                }

                // Tentar iframe src
                const frame = document.querySelector('iframe[src*="google.com/recaptcha"]');
                if (frame) {
                    const match = frame.src.match(/[?&]k=([^&]+)/);
                    if (match) return match[1];
                }

                return null;
            }"""
        )
        if result:
            logger.debug("Site key extracted: %s...", result[:8])
        return result

    if captcha_type == CaptchaType.HCAPTCHA:
        result = await evaluate(
            """() => {
                const div = document.querySelector('.h-captcha[data-sitekey]');
                if (div) return div.getAttribute('data-sitekey');

                const frame = document.querySelector('iframe[src*="hcaptcha.com"]');
                if (frame) {
                    const match = frame.src.match(/sitekey=([^&]+)/);
                    if (match) return match[1];
                }

                return null;
            }"""
        )
        if result:
            logger.debug("Site key extracted: %s...", result[:8])
        return result

    return None


async def inject_captcha_token(page: object, token: str, captcha_type: CaptchaType) -> None:
    """Injeta token resolvido no campo correto e dispara callback.

    Args:
        page: Playwright Page object.
        token: Token resolvido pelo solver.
        captcha_type: Tipo de captcha para injecao correta.

    Raises:
        CaptchaSolverError: Se falhar ao injetar token.
    """
    evaluate = getattr(page, "evaluate", None)
    if not callable(evaluate):
        raise CaptchaSolverError("Page does not support evaluate")

    logger.info("Captcha token injected for %s", captcha_type.value)

    if captcha_type in (CaptchaType.RECAPTCHA_V2, CaptchaType.RECAPTCHA_V3):
        success = await evaluate(
            """(token) => {
                // Injetar no textarea padrao do reCAPTCHA
                const textarea = document.getElementById('g-recaptcha-response');
                if (textarea) {
                    textarea.value = token;
                    textarea.style.display = 'block';
                }

                // Tambem injetar em textareas hidden (v3 pode ter multiplos)
                document.querySelectorAll('[name="g-recaptcha-response"]').forEach(el => {
                    el.value = token;
                });

                // Disparar callback se existir
                if (typeof window.___grecaptcha_cfg !== 'undefined') {
                    const clients = window.___grecaptcha_cfg.clients;
                    if (clients) {
                        for (const cid of Object.keys(clients)) {
                            const client = clients[cid];
                            // Procurar callback recursivamente
                            const findCallback = (obj, depth) => {
                                if (depth > 5 || !obj) return;
                                for (const key of Object.keys(obj)) {
                                    if (typeof obj[key] === 'function') {
                                        try { obj[key](token); } catch {}
                                    } else if (typeof obj[key] === 'object') {
                                        findCallback(obj[key], depth + 1);
                                    }
                                }
                            };
                            findCallback(client, 0);
                        }
                    }
                }

                return true;
            }""",
            token,
        )
        return

    if captcha_type == CaptchaType.HCAPTCHA:
        await evaluate(
            """(token) => {
                // Injetar no textarea do hCaptcha
                const textareas = document.querySelectorAll(
                    '[name="h-captcha-response"], [name="g-recaptcha-response"]'
                );
                textareas.forEach(el => { el.value = token; });

                // Disparar callback do hCaptcha
                const iframes = document.querySelectorAll('iframe[data-hcaptcha-widget-id]');
                iframes.forEach(frame => {
                    const widgetId = frame.getAttribute('data-hcaptcha-widget-id');
                    if (widgetId && window.hcaptcha) {
                        try {
                            // Tentar submit via API
                            window.hcaptcha.execute(widgetId);
                        } catch {}
                    }
                });
            }""",
            token,
        )
        return

    raise CaptchaSolverError(f"Unsupported captcha type for token injection: {captcha_type}")
