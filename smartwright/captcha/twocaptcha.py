"""2Captcha solver — resolve captchas via api 2captcha.com usando stdlib."""
from __future__ import annotations

import asyncio
import json
import time
import urllib.parse
import urllib.request
from typing import Any

from smartwright._logging import logger
from smartwright.captcha.solver import CaptchaResult, CaptchaSolver, CaptchaType
from smartwright.constants import CAPTCHA_MAX_WAIT_S, CAPTCHA_POLL_INTERVAL_S
from smartwright.exceptions import CaptchaSolverError


class TwoCaptchaSolver(CaptchaSolver):
    """Solver usando api 2captcha.com.

    Usa urllib.request (stdlib) para nao adicionar dependencias.
    Todas as chamadas HTTP sao feitas em threads via asyncio.to_thread.

    Args:
        api_key: Chave da API 2captcha.
        poll_interval: Intervalo em segundos entre polls do resultado.
        max_wait: Tempo maximo de espera em segundos.
    """

    BASE_URL = "https://2captcha.com"

    def __init__(
        self,
        api_key: str,
        poll_interval: float = CAPTCHA_POLL_INTERVAL_S,
        max_wait: float = CAPTCHA_MAX_WAIT_S,
    ) -> None:
        self._api_key = api_key
        self._poll_interval = poll_interval
        self._max_wait = max_wait

    def _post_task(self, params: dict[str, str]) -> str:
        """Submete task para 2captcha e retorna task ID (sync, roda em thread)."""
        params["key"] = self._api_key
        params["json"] = "1"
        data = urllib.parse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(
            f"{self.BASE_URL}/in.php",
            data=data,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        if body.get("status") != 1:
            raise CaptchaSolverError(f"2captcha submit failed: {body.get('request', 'unknown')}")
        return body["request"]

    def _poll_result(self, task_id: str) -> str:
        """Poll resultado de um task (sync, roda em thread)."""
        params = {
            "key": self._api_key,
            "action": "get",
            "id": task_id,
            "json": "1",
        }
        url = f"{self.BASE_URL}/res.php?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        if body.get("status") == 1:
            return body["request"]
        if body.get("request") == "CAPCHA_NOT_READY":
            return ""
        raise CaptchaSolverError(f"2captcha error: {body.get('request', 'unknown')}")

    async def _submit_and_wait(self, params: dict[str, str], captcha_type: CaptchaType) -> CaptchaResult:
        """Submete task, faz polling e retorna resultado."""
        start = time.monotonic()
        logger.info("2captcha: submitting %s task", captcha_type.value)
        try:
            task_id = await asyncio.to_thread(self._post_task, params)
        except CaptchaSolverError:
            raise
        except Exception as exc:
            return CaptchaResult(
                captcha_type=captcha_type,
                error=str(exc),
                elapsed_seconds=time.monotonic() - start,
            )

        # Esperar processamento inicial
        await asyncio.sleep(self._poll_interval)

        deadline = start + self._max_wait
        while time.monotonic() < deadline:
            logger.debug("2captcha: polling task %s", task_id)
            try:
                token = await asyncio.to_thread(self._poll_result, task_id)
            except CaptchaSolverError as exc:
                return CaptchaResult(
                    captcha_type=captcha_type,
                    error=str(exc),
                    elapsed_seconds=time.monotonic() - start,
                )

            if token:
                elapsed = time.monotonic() - start
                logger.info("2captcha: solved in %.1fs", elapsed)
                return CaptchaResult(
                    captcha_type=captcha_type,
                    token=token,
                    solved=True,
                    elapsed_seconds=elapsed,
                )

            await asyncio.sleep(self._poll_interval)

        return CaptchaResult(
            captcha_type=captcha_type,
            error=f"Timeout after {self._max_wait}s",
            elapsed_seconds=time.monotonic() - start,
        )

    async def solve_recaptcha_v2(self, site_key: str, page_url: str) -> CaptchaResult:
        """Resolve reCAPTCHA v2 via 2captcha."""
        return await self._submit_and_wait(
            {
                "method": "userrecaptcha",
                "googlekey": site_key,
                "pageurl": page_url,
            },
            CaptchaType.RECAPTCHA_V2,
        )

    async def solve_recaptcha_v3(self, site_key: str, page_url: str, action: str = "verify") -> CaptchaResult:
        """Resolve reCAPTCHA v3 via 2captcha."""
        return await self._submit_and_wait(
            {
                "method": "userrecaptcha",
                "googlekey": site_key,
                "pageurl": page_url,
                "version": "v3",
                "action": action,
                "min_score": "0.3",
            },
            CaptchaType.RECAPTCHA_V3,
        )

    async def solve_hcaptcha(self, site_key: str, page_url: str) -> CaptchaResult:
        """Resolve hCaptcha via 2captcha."""
        return await self._submit_and_wait(
            {
                "method": "hcaptcha",
                "sitekey": site_key,
                "pageurl": page_url,
            },
            CaptchaType.HCAPTCHA,
        )

    async def solve_image(self, image_base64: str) -> CaptchaResult:
        """Resolve captcha de imagem via 2captcha."""
        return await self._submit_and_wait(
            {
                "method": "base64",
                "body": image_base64,
            },
            CaptchaType.IMAGE,
        )
