"""Bot: Grava acoes do usuario e faz replay adaptativo.

Uso:
  python gravar_e_replay.py gravar        # abre browser, grava acoes, salva JSON
  python gravar_e_replay.py replay        # replay padrao
  python gravar_e_replay.py adaptativo    # replay adaptativo (fingerprint semantico)
  python gravar_e_replay.py analisar      # analisa matching sem executar
"""
import asyncio
import json
import sys
from playwright.async_api import async_playwright

sys.path.insert(0, "..")
from smartwright import Smartwright
from smartwright.recorder import ActionRecorder

RECORDING_FILE = "test_reais/recording.json"
SCREENSHOT_DIR = "test_reais/debug_replay"


async def gravar():
    """Abre browser para o usuario gravar acoes."""
    url = sys.argv[2] if len(sys.argv) > 2 else "https://www.google.com"

    recorder = ActionRecorder(
        headless=False,
        save_path=RECORDING_FILE,
    )

    print(f"Abrindo browser em {url}")
    print("Faca as acoes que quer gravar. Feche o browser quando terminar.\n")

    await recorder.start(url=url)
    actions = await recorder.wait_until_closed()

    print(f"\n{len(actions)} acoes gravadas em {RECORDING_FILE}")
    for a in actions:
        step = a.get("step", "?")
        act = a.get("action", "?")
        text = a.get("text", "")[:40]
        val = a.get("value", "")[:30]
        print(f"  [{step}] {act} {text} {f'= {val}' if val else ''}")


async def replay(mode: str = "padrao"):
    """Replay das acoes gravadas."""
    try:
        with open(RECORDING_FILE) as f:
            data = json.load(f)
        actions = data.get("actions", data) if isinstance(data, dict) else data
    except FileNotFoundError:
        print(f"Arquivo {RECORDING_FILE} nao encontrado. Execute 'gravar' primeiro.")
        return

    print(f"Replay de {len(actions)} acoes (modo: {mode})\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()
        sw = Smartwright(page=page, request_context=context.request, debug=True)

        if mode == "adaptativo":
            results = await sw.replay_adaptive(
                actions,
                debug=True,
                screenshot_dir=SCREENSHOT_DIR,
            )
        else:
            results = await sw.emergency_replay_actions(
                actions,
                debug=True,
                screenshot_dir=SCREENSHOT_DIR,
                mode=mode,
            )

        ok = sum(1 for r in results if r["status"] == "ok")
        erros = sum(1 for r in results if r["status"] == "error")
        print(f"\nResultado: {ok} ok, {erros} erros")
        for r in results:
            status = "OK" if r["status"] == "ok" else f"ERRO: {r.get('error', '')[:60]}"
            print(f"  [{r['step']}] {r['action']} — {status}")

        await sw.page_screenshot("test_reais/replay_final.png")
        await browser.close()


async def analisar():
    """Analisa matching adaptativo sem executar."""
    try:
        with open(RECORDING_FILE) as f:
            data = json.load(f)
        actions = data.get("actions", data) if isinstance(data, dict) else data
    except FileNotFoundError:
        print(f"Arquivo {RECORDING_FILE} nao encontrado. Execute 'gravar' primeiro.")
        return

    first_url = next((a["url"] for a in actions if a.get("url")), None)
    if not first_url:
        print("Nenhuma URL encontrada nas acoes gravadas.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()
        sw = Smartwright(page=page, request_context=context.request, debug=True)

        await sw.goto(first_url)
        await sw.wait_for_load("networkidle", timeout_ms=10000)

        analysis = await sw.replay_adaptive_analyze(actions)

        print(f"\nAnalise de matching ({len(analysis)} acoes):\n")
        for a in analysis:
            if a.get("match") == "n/a":
                print(f"  [{a['step']}] {a['action']} — n/a (sem elemento)")
                continue

            fp = a.get("fingerprint", {})
            match = a.get("match", {})
            score = a.get("score", 0)
            ok = "SIM" if a.get("confident") else "NAO"

            print(f"  [{a['step']}] {a['action']} — score: {score}, match: {ok}")
            print(f"         gravado: {fp.get('tag', '?')} \"{fp.get('text', '')[:30]}\"")
            if match:
                print(f"         pagina:  {match.get('tag', '?')} \"{match.get('text', '')[:30]}\"")
            print()

        await browser.close()


async def main():
    comando = sys.argv[1] if len(sys.argv) > 1 else "gravar"

    if comando == "gravar":
        await gravar()
    elif comando in ("replay", "padrao", "rapido", "mix", "forcado"):
        mode = comando if comando != "replay" else "padrao"
        await replay(mode)
    elif comando == "adaptativo":
        await replay("adaptativo")
    elif comando == "analisar":
        await analisar()
    else:
        print(__doc__)


if __name__ == "__main__":
    asyncio.run(main())
