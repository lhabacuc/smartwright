"""Bot: Navega na Wikipedia, extrai info de um artigo e segue links."""
import asyncio
import sys
from playwright.async_api import async_playwright

sys.path.insert(0, "..")
from smartwright import Smartwright


async def main():
    tema = sys.argv[1] if len(sys.argv) > 1 else "Python (programming language)"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()
        sw = Smartwright(page=page, request_context=context.request, debug=True)
        await sw.set_debug(screenshot_dir="test_reais/debug_wiki")

        await sw.goto(f"https://en.wikipedia.org/wiki/{tema.replace(' ', '_')}")

        # Info basica
        titulo = await sw.emergency_get_page_title()
        print(f"\nArtigo: {titulo}")

        # Primeiro paragrafo
        try:
            intro = await sw.emergency_read("p", 0)
            print(f"\nIntro: {intro[:300]}...\n")
        except Exception:
            pass

        # Headings do artigo
        headings = await sw.emergency_capture_all_headings()
        seccoes = [h["text"] for h in headings if h.get("text")]
        print(f"Seccoes ({len(seccoes)}):")
        for s in seccoes[:15]:
            print(f"  - {s}")

        # DOM snapshot compacto
        from smartwright.resolver.dom_serializer import DOMSerializerConfig
        snapshot = await sw.dom_snapshot(DOMSerializerConfig.compact())
        print(f"\nDOM compacto: {snapshot.element_count} elementos")

        # Links internos
        links = await sw.emergency_capture_all_links()
        wiki_links = [
            lk for lk in links
            if "/wiki/" in lk.get("href", "")
            and ":" not in lk.get("href", "").split("/wiki/")[-1]
            and lk.get("text", "").strip()
        ]
        print(f"Links internos: {len(wiki_links)}")

        # Seguir primeiro link relevante
        if wiki_links:
            primeiro = wiki_links[0]
            print(f"\nSeguindo link: {primeiro['text']}")
            await sw.emergency_click_link(primeiro["text"])
            await sw.wait_for_load("networkidle", timeout_ms=10000)
            novo_titulo = await sw.emergency_get_page_title()
            print(f"Novo artigo: {novo_titulo}")

        await sw.page_screenshot("test_reais/wikipedia.png")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
