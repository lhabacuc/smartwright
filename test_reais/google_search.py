"""Bot: Pesquisa no Google (com stealth) e extrai resultados.

Uso:
  python google_search.py                           # pesquisa default
  python google_search.py "minha pesquisa aqui"     # pesquisa custom
"""
import asyncio
import sys
from playwright.async_api import async_playwright

sys.path.insert(0, "..")
from smartwright import Smartwright
from smartwright.stealth import StealthConfig, get_stealth_args, get_context_options, apply_stealth


async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "Python playwright automation"

    cfg = StealthConfig()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=get_stealth_args(cfg),
            ignore_default_args=["--enable-automation"],
        )
        ctx_opts = get_context_options(cfg)
        ctx_opts["viewport"] = {"width": 1280, "height": 720}
        context = await browser.new_context(**ctx_opts)
        await apply_stealth(context, cfg)
        page = await context.new_page()
        sw = Smartwright(page=page, request_context=context.request, debug=True)
        await sw.set_debug(screenshot_dir="test_reais/debug_google")

        await sw.goto("https://www.google.com")

        # Aceitar cookies se aparecer
        try:
            await sw.emergency_click_by_text("Aceitar", timeout_ms=3000)
        except Exception:
            pass

        # Preencher campo de pesquisa e submeter
        await sw.emergency_fill("textarea", 0, query)
        await sw.emergency_press_keys("Enter")
        await sw.emergency_wait_for_url_contains("search", timeout_ms=10000)
        await sw.wait_for_load("networkidle", timeout_ms=10000)

        # Extrair resultados via DOM snapshot
        snapshot = await sw.dom_snapshot()
        print(f"\nPagina: {snapshot.title}")
        print(f"Elementos interativos: {snapshot.element_count}\n")

        # Capturar links dos resultados
        links = await sw.emergency_capture_all_links()
        resultados = [
            lk for lk in links
            if lk.get("href", "").startswith("http")
            and "google" not in lk.get("href", "")
            and lk.get("text", "").strip()
        ]

        print(f"Resultados encontrados: {len(resultados)}\n")
        for i, r in enumerate(resultados[:10], 1):
            print(f"  {i}. {r['text'][:80]}")
            print(f"     {r['href'][:100]}\n")

        await sw.page_screenshot("test_reais/google_results.png")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
