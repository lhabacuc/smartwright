"""Bot: Espia APIs de qualquer site via network learning.

Navega no site e descobre automaticamente todos os endpoints de API.

Uso:
  python network_spy.py                              # espia github trending
  python network_spy.py https://github.com/trending  # espia URL especifica
"""
import asyncio
import json
import sys
from playwright.async_api import async_playwright

sys.path.insert(0, "..")
from smartwright import Smartwright


async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/trending"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()
        sw = Smartwright(page=page, request_context=context.request, debug=True)
        await sw.set_debug(screenshot_dir="test_reais/debug_network")

        # Ativar network learning ANTES de navegar
        sw.attach_network_learning()

        print(f"Navegando para {url}...")
        await sw.goto(url)
        await sw.wait_for_load("networkidle", timeout_ms=15000)

        # Scroll para forcar mais requests
        for _ in range(3):
            await sw.emergency_scroll_page("down", 500)
            await asyncio.sleep(1)

        # Clicar em alguns links para gerar mais trafego
        try:
            links = await sw.emergency_capture_all_links()
            internal = [
                lk for lk in links
                if lk.get("href", "").startswith(url.split("/")[0] + "//" + url.split("/")[2])
                and lk.get("text", "").strip()
            ]
            if internal:
                await sw.emergency_click_link(internal[0]["text"])
                await sw.wait_for_load("networkidle", timeout_ms=10000)
        except Exception:
            pass

        # Mostrar discoveries
        summary = sw.network_summary()
        discoveries = sw.network_discoveries

        print(f"\n{'=' * 60}")
        print(f"Network Learning — Resultados")
        print(f"{'=' * 60}")
        print(f"Total APIs descobertas: {summary.get('total_discovered', 0)}")
        print(f"Por metodo: {summary.get('by_method', {})}")
        print(f"Por dominio: {summary.get('by_domain', {})}")

        if discoveries:
            print(f"\nEndpoints:\n")
            for d in discoveries:
                print(f"  {d['method']:6s} {d['endpoint']}")
                print(f"         intent: {d['intent']}")
                if d.get("payload_template"):
                    keys = list(d["payload_template"].keys())[:5]
                    print(f"         payload keys: {keys}")
                if d.get("response_sample"):
                    keys = list(d["response_sample"].keys())[:5]
                    print(f"         response keys: {keys}")
                print()

            # Salvar discoveries em JSON
            output = "test_reais/api_discoveries.json"
            with open(output, "w") as f:
                json.dump(discoveries, f, indent=2, default=str)
            print(f"Discoveries salvas em {output}")
        else:
            print("\nNenhuma API descoberta neste site.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
