"""Bot: Executa acoes escritas em JSON (sem gravar antes).

Demonstra o run_json() que aceita JSON simplificado com aliases.
"""
import asyncio
import sys
from playwright.async_api import async_playwright

sys.path.insert(0, "..")
from smartwright import Smartwright


# Acoes escritas a mao — formato simplificado
ACOES_GOOGLE = [
    {"action": "goto", "url": "https://www.google.com"},
    {"action": "fill", "selector": "textarea[name='q']", "value": "smartwright playwright python"},
    {"action": "press", "key": "Enter"},
    {"action": "wait", "ms": 2000},
    {"action": "screenshot", "path": "test_reais/multi_search.png"},
]

ACOES_WIKIPEDIA = [
    {"action": "goto", "url": "https://en.wikipedia.org/wiki/Web_scraping"},
    {"action": "wait", "ms": 1500},
    {"action": "screenshot", "path": "test_reais/multi_wiki.png"},
    {"action": "click", "text": "Techniques"},
    {"action": "wait", "ms": 1000},
    {"action": "scroll", "direction": "down", "pixels": 400},
    {"action": "screenshot", "path": "test_reais/multi_wiki_section.png"},
]

CENARIOS = {
    "google": ACOES_GOOGLE,
    "wikipedia": ACOES_WIKIPEDIA,
}


async def main():
    cenario = sys.argv[1] if len(sys.argv) > 1 else "google"
    acoes = CENARIOS.get(cenario)

    if not acoes:
        print(f"Cenarios disponiveis: {', '.join(CENARIOS.keys())}")
        return

    print(f"Executando cenario '{cenario}' ({len(acoes)} acoes)\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()
        sw = Smartwright(page=page, request_context=context.request, debug=True)

        results = await sw.run_json(
            acoes,
            delay_ms=300,
            debug=True,
            screenshot_dir="test_reais/debug_multi",
            mode="padrao",
        )

        ok = sum(1 for r in results if r["status"] == "ok")
        erros = sum(1 for r in results if r["status"] == "error")
        print(f"\nResultado: {ok} ok, {erros} erros")
        for r in results:
            status = "OK" if r["status"] == "ok" else f"ERRO: {r.get('error', '')[:60]}"
            print(f"  [{r['step']}] {r['action']} — {status}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
