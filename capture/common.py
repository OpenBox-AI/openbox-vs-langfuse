"""Shared helpers for the screenshot scripts."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOTS = Path(os.environ.get("SCREENSHOT_DIR", ROOT / "screenshots"))
VIEWPORT = {"width": 1600, "height": 1000}


def launch(playwright):
    """Headless Chromium. CHROMIUM_PATH overrides Playwright's bundled browser."""
    path = os.environ.get("CHROMIUM_PATH")
    return playwright.chromium.launch(executable_path=path) if path else playwright.chromium.launch()


def shot(page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f"{name}.png"
    page.screenshot(path=str(path))
    print("saved", path, flush=True)
