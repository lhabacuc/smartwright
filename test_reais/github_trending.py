"""Bot: Scraping de repositorios trending no GitHub."""
import asyncio
import sys
from playwright.async_api import async_playwright

sys.path.insert(0, "..")
from smartwright import Smartwright


async def main():
    lang = sys.argv[1] if len(sys.argv) > 1 else ""
    url = "https://github.com/trending"
    if lang:
        url += f"/{lang}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        sw = Smartwright(page=page, request_context=context.request, debug=True)
        await sw.set_debug(screenshot_dir="test_reais/debug_github")

        sw.attach_network_learning()
        await sw.goto(url)
        await sw.wait_for_load("networkidle", timeout_ms=15000)

        titulo = await sw.emergency_get_page_title()
        print(f"\n{titulo}\n{'=' * 60}")

        # Extrair repos via JS direto
        repos = await sw.eval_js("""() => {
            const articles = document.querySelectorAll('article.Box-row');
            return Array.from(articles).map((el, i) => {
                const nameEl = el.querySelector('h2 a');
                const descEl = el.querySelector('p');
                const langEl = el.querySelector('[itemprop="programmingLanguage"]');
                const starsEl = el.querySelector('a[href*="/stargazers"]');
                return {
                    rank: i + 1,
                    name: nameEl ? nameEl.textContent.trim().replace(/\\s+/g, '') : '',
                    url: nameEl ? nameEl.href : '',
                    description: descEl ? descEl.textContent.trim() : '',
                    language: langEl ? langEl.textContent.trim() : '',
                    stars: starsEl ? starsEl.textContent.trim() : '',
                };
            });
        }""")

        for repo in repos[:20]:
            print(f"\n  #{repo['rank']} {repo['name']}")
            if repo["language"]:
                print(f"     Lang: {repo['language']}  Stars: {repo['stars']}")
            if repo["description"]:
                print(f"     {repo['description'][:100]}")

        print(f"\n\nTotal: {len(repos)} repos trending")

        # Network discoveries
        discoveries = sw.network_discoveries
        if discoveries:
            print(f"\nAPIs descobertas: {len(discoveries)}")
            for d in discoveries[:5]:
                print(f"  {d['method']} {d['endpoint']}")

        await sw.page_screenshot("test_reais/github_trending.png")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
