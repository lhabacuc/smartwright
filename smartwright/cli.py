"""Smartwright CLI — run, record, replay and inspect flows from the terminal."""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smartwright",
        description="Smartwright — adaptive web automation engine CLI",
    )
    sub = parser.add_subparsers(dest="command")

    # ── run ──────────────────────────────────────────────────────
    run_p = sub.add_parser("run", help="Execute a hand-written JSON flow")
    run_p.add_argument("flow", help="Path to JSON flow file")
    run_p.add_argument("--delay", type=int, default=400, help="Delay between steps (ms)")
    run_p.add_argument("--mode", default="padrao", help="Replay mode (rapido, padrao, forcado, mix)")
    run_p.add_argument("--headless", action="store_true", default=True, help="Run in headless mode (default)")
    run_p.add_argument("--no-headless", dest="headless", action="store_false", help="Run with visible browser")
    run_p.add_argument("--base-url", default="", help="Base URL prefix for relative paths")
    run_p.add_argument("--debug", action="store_true", default=False, help="Enable visual debug (cursor, screenshots)")
    run_p.add_argument("--screenshot-dir", default="debug_run", help="Screenshot directory for debug mode")
    run_p.add_argument("--continue-on-error", dest="continue_on_error", action="store_true", default=True)
    run_p.add_argument("--stop-on-error", dest="continue_on_error", action="store_false")

    # ── record ──────────────────────────────────────────────────
    rec_p = sub.add_parser("record", help="Record browser actions to JSON")
    rec_p.add_argument("--output", default="recording.json", help="Output JSON file path")
    rec_p.add_argument("--url", default=None, help="Initial URL to navigate to")
    rec_p.add_argument("--headless", action="store_true", default=False, help="Run headless (default: visible)")

    # ── replay ──────────────────────────────────────────────────
    rep_p = sub.add_parser("replay", help="Replay recorded actions from JSON")
    rep_p.add_argument("recording", help="Path to recording JSON file")
    rep_p.add_argument("--delay", type=int, default=500, help="Delay between steps (ms)")
    rep_p.add_argument("--mode", default="padrao", help="Replay mode")
    rep_p.add_argument("--headless", action="store_true", default=True, help="Run headless (default)")
    rep_p.add_argument("--no-headless", dest="headless", action="store_false")
    rep_p.add_argument("--debug", action="store_true", default=False, help="Enable visual debug")
    rep_p.add_argument("--screenshot-dir", default="debug_replay", help="Screenshot directory")

    # ── version ─────────────────────────────────────────────────
    sub.add_parser("version", help="Print Smartwright version")

    return parser


async def _cmd_run(args: argparse.Namespace) -> int:
    from playwright.async_api import async_playwright

    from smartwright import Smartwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=args.headless)
        context = await browser.new_context()
        page = await context.new_page()
        sw = Smartwright(page=page, request_context=context.request)
        results = await sw.emergency.run_json_file(
            args.flow,
            delay_ms=args.delay,
            debug=args.debug,
            screenshot_dir=args.screenshot_dir,
            mode=args.mode,
            continue_on_error=args.continue_on_error,
            base_url=args.base_url,
        )
        await browser.close()

    errors = [r for r in results if r.get("status") == "error"]
    total = len(results)
    ok = total - len(errors)
    print(f"Done: {ok}/{total} steps OK", end="")
    if errors:
        print(f", {len(errors)} errors")
        for e in errors:
            print(f"  step {e.get('step')}: {e.get('error')}")
        return 1
    print()
    return 0


async def _cmd_record(args: argparse.Namespace) -> int:
    from smartwright.recorder import ActionRecorder

    recorder = ActionRecorder(
        headless=args.headless,
        save_path=args.output,
    )
    await recorder.start(url=args.url)
    actions = await recorder.wait_until_closed()
    print(f"Recorded {len(actions)} actions -> {args.output}")
    return 0


async def _cmd_replay(args: argparse.Namespace) -> int:
    from playwright.async_api import async_playwright

    from smartwright import Smartwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=args.headless)
        context = await browser.new_context()
        page = await context.new_page()
        sw = Smartwright(page=page, request_context=context.request)
        results = await sw.emergency.replay_actions_from_json(
            args.recording,
            delay_ms=args.delay,
            debug=args.debug,
            screenshot_dir=args.screenshot_dir,
            mode=args.mode,
        )
        await browser.close()

    errors = [r for r in results if r.get("status") == "error"]
    total = len(results)
    ok = total - len(errors)
    print(f"Done: {ok}/{total} steps OK", end="")
    if errors:
        print(f", {len(errors)} errors")
        for e in errors:
            print(f"  step {e.get('step')}: {e.get('error')}")
        return 1
    print()
    return 0


def _cmd_version() -> int:
    from smartwright.constants import VERSION
    print(f"smartwright {VERSION}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "version":
        return _cmd_version()

    if args.command == "run":
        return asyncio.run(_cmd_run(args))

    if args.command == "record":
        return asyncio.run(_cmd_record(args))

    if args.command == "replay":
        return asyncio.run(_cmd_replay(args))

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
