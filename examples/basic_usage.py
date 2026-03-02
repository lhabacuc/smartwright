import asyncio

from playwright.async_api import async_playwright

from smartwright import Smartwright


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        smart = Smartwright(page=page, request_context=context.request)
        await smart.goto("https://example.com/login")
        await smart.fill("email_field", "user@example.com")
        await smart.fill("password_field", "secret")
        await smart.click("login_button")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
