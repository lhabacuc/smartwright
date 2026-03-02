"""Bot: Explora o DOM de qualquer site com o serializer.

Mostra todos os elementos interativos no formato indexado [N].

Uso:
  python dom_explorer.py                          # explora google.com
  python dom_explorer.py https://github.com       # explora URL especifica
  python dom_explorer.py https://example.com -v   # modo verbose
"""
import asyncio
import sys
from playwright.async_api import async_playwright

sys.path.insert(0, "..")
from smartwright import Smartwright
from smartwright.resolver.dom_serializer import DOMSerializerConfig


async def main():
    url = "https://www.google.com"
    verbose = False

    for arg in sys.argv[1:]:
        if arg in ("-v", "--verbose"):
            verbose = True
        elif arg.startswith("http"):
            url = arg

    config = DOMSerializerConfig.verbose() if verbose else DOMSerializerConfig.compact()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()
        sw = Smartwright(page=page, request_context=context.request, debug=True)
        await sw.set_debug(screenshot_dir="test_reais/debug_dom")

        await sw.goto(url)
        await sw.wait_for_load("networkidle", timeout_ms=10000)

        # Snapshot
        snapshot = await sw.dom_snapshot(config)

        print(f"\n{'=' * 60}")
        print(f"URL:    {snapshot.url}")
        print(f"Titulo: {snapshot.title}")
        print(f"Elementos: {snapshot.element_count}")
        print(f"Stats: {snapshot.stats}")
        print(f"{'=' * 60}\n")

        # DOM serializado
        print(snapshot.text)

        # Demonstrar to_capture
        if snapshot.element_count > 0:
            print(f"\n{'=' * 60}")
            print("Exemplo: converter [1] em capture dict para interacao:")
            el = snapshot.get_element(1)
            if el:
                print(f"  Tag: {el.tag}")
                print(f"  Text: {el.text[:60]}")
                print(f"  Selectors: {el.selectors[:3]}")
                capture = snapshot.to_capture(1)
                print(f"  Capture keys: {list(capture.keys())}")

        await sw.page_screenshot("test_reais/dom_explorer.png")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
