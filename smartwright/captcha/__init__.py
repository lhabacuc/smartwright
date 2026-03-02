"""Captcha detection e solving."""
from smartwright.captcha.solver import (
    CaptchaResult,
    CaptchaSolver,
    CaptchaType,
    detect_captcha,
    extract_site_key,
    inject_captcha_token,
)

__all__ = [
    "CaptchaType",
    "CaptchaResult",
    "CaptchaSolver",
    "detect_captcha",
    "extract_site_key",
    "inject_captcha_token",
]
