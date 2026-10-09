"""Screenshot the Langfuse views of the `langfuse` run.

    uv run --with playwright python capture/langfuse.py

Reads the trace id from runs/langfuse.json. Signs in with the demo user from
langfuse/.env.example unless LANGFUSE_UI_EMAIL / LANGFUSE_UI_PASSWORD are set.
"""

from __future__ import annotations

import json
import os

from playwright.sync_api import sync_playwright

from common import ROOT, VIEWPORT, launch, shot

BASE = os.environ.get("LANGFUSE_HOST", "http://localhost:3100")
PROJECT = os.environ.get("LANGFUSE_PROJECT_ID", "policy-studio")
EMAIL = os.environ.get("LANGFUSE_UI_EMAIL", "demo@openbox.local")
PASSWORD = os.environ.get("LANGFUSE_UI_PASSWORD", "compare-demo-123")


def pick(page, name: str, nth: int = 0) -> None:
    """Filter the trace tree to one span name and open the nth match."""
    page.get_by_placeholder("Search").first.fill(name)
    page.wait_for_timeout(1500)
    page.get_by_text(name, exact=True).nth(nth).click()
    page.wait_for_timeout(2500)


def main() -> None:
    run = json.loads((ROOT / "runs/langfuse.json").read_text())
    trace = f"{BASE}/project/{PROJECT}/traces/{run['langfuse_trace_id']}"
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=2)
        page.goto(f"{BASE}/auth/sign-in")
        page.fill("input[name=email]", EMAIL)
        page.fill("input[type=password]", PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_url("**/", timeout=30000)

        page.goto(trace)
        page.wait_for_timeout(6000)
        shot(page, "langfuse-1-trace-tree")
        pick(page, "ChatOpenAI")
        shot(page, "langfuse-2-ChatOpenAI")
        pick(page, "read_document", 1)  # chain span, then tool span: index 1 is the first tool call
        shot(page, "langfuse-3-tool-read")
        page.get_by_placeholder("Search").first.fill("")
        for view in ("Timeline", "Graph"):
            page.get_by_text(view, exact=True).first.click()
            page.wait_for_timeout(3000)
            shot(page, f"langfuse-4-{view.lower()}")
        page.goto(f"{BASE}/project/{PROJECT}/sessions")
        page.wait_for_timeout(5000)
        shot(page, "langfuse-5-sessions")
        page.goto(f"{BASE}/project/{PROJECT}")
        page.wait_for_timeout(8000)
        shot(page, "langfuse-6-home")
        browser.close()


if __name__ == "__main__":
    main()
