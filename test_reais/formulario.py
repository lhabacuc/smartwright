"""Bot: Preenche formulario de pratica no demoqa.com."""
import asyncio
from playwright.async_api import async_playwright
import sys

sys.path.insert(0, "..")
from smartwright import Smartwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        sw = Smartwright(page=page, request_context=context.request, debug=True)
        await sw.set_debug(screenshot_dir="test_reais/debug_form")

        await sw.goto("https://demoqa.com/automation-practice-form")
        await sw.wait_for_load("networkidle", timeout_ms=10000)

        print("\nPreenchendo formulario...\n")

        # Nome
        await sw.emergency_fill_first_input_containing("First Name", "Maria")
        await sw.emergency_fill_first_input_containing("Last Name", "Silva")

        # Email
        await sw.emergency_fill_first_input_containing("name@example", "maria@test.com")

        # Genero (radio)
        try:
            await sw.emergency_click_by_text("Female", timeout_ms=3000)
        except Exception:
            pass

        # Telefone
        await sw.emergency_fill_first_input_containing("Mobile", "1234567890")

        # Morada
        await sw.emergency_fill("textarea", 0, "Rua das Flores, 123\nLisboa, Portugal")

        # Scroll para ver mais campos
        await sw.emergency_scroll_page("down", 300)

        # DOM snapshot para ver estado do form
        snapshot = await sw.dom_snapshot()
        print(f"Elementos na pagina: {snapshot.element_count}")

        # Ler estado do formulario
        try:
            inputs = await sw.emergency_capture_all_inputs()
            preenchidos = [i for i in inputs if i.get("value")]
            print(f"Campos preenchidos: {len(preenchidos)}/{len(inputs)}")
            for inp in preenchidos:
                label = inp.get("placeholder") or inp.get("name") or inp.get("type", "?")
                print(f"  {label}: {inp['value'][:50]}")
        except Exception:
            pass

        await sw.page_screenshot("test_reais/formulario.png")
        print("\nFormulario preenchido com sucesso!")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
