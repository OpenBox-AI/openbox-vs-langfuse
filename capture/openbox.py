"""Screenshot the OpenBox views of the `openbox` run.

    ./capture/open_chrome.sh                      # sign in, leave the window open
    uv run --with playwright python capture/openbox.py \\
        --agent-id <agent uuid> --session-id <session uuid>

Attaches to the Chrome window on :9333 and waits until you are past the login
page. scripts/find_openbox_ids.sh prints both ids for the latest run on a
local stack; on a hosted environment copy them from the dashboard URL
(Agents -> the agent -> Sessions -> Details).
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request

from playwright.sync_api import sync_playwright

from common import VIEWPORT, shot

DASHBOARD = os.environ.get("OPENBOX_DASHBOARD_URL", "http://localhost:3233")
CDP = "http://localhost:9333"


def wait_for_sign_in() -> None:
    """Poll Chrome's tab list (not a page handle: the login redirect replaces the tab)."""
    print("waiting for sign-in in the Chrome window ...", flush=True)
    while True:
        try:
            tabs = json.load(urllib.request.urlopen(f"{CDP}/json", timeout=3))
        except OSError:
            tabs = []
        for tab in tabs:
            url = tab.get("url", "")
            if tab.get("type") == "page" and url.startswith(DASHBOARD) and "/login" not in url and "/sso" not in url:
                return
        time.sleep(2)


def event_modal(page, activity: str, name: str, page_no: int) -> None:
    """Open one ActivityStarted row of the Verify event log and capture its three tabs."""
    if page_no > 1:
        page.get_by_role("button", name=str(page_no), exact=True).click()
        page.wait_for_timeout(2500)
    row = page.locator("tr").filter(has_text="ActivityStarted").filter(has_text=activity).last
    row.scroll_into_view_if_needed()
    row.locator("td").last.click()
    page.wait_for_timeout(3000)
    shot(page, f"openbox-{name}-proof")
    for tab in ("Overview", "Input"):
        page.locator("button", has_text=tab).last.click()
        page.wait_for_timeout(2000)
        shot(page, f"openbox-{name}-{tab.lower()}")
    page.get_by_role("button", name="Close").last.click()
    page.wait_for_timeout(1000)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--session-id", required=True)
    args = parser.parse_args()
    agent = f"{DASHBOARD}/agents/{args.agent_id}"
    verify = f"{agent}?tab=verify&sessionId={args.session_id}"

    wait_for_sign_in()
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        page = [pg for pg in browser.contexts[0].pages if pg.url.startswith(DASHBOARD)][-1]
        page.set_viewport_size(VIEWPORT)

        # Agent overview and session list.
        page.goto(agent)
        page.wait_for_timeout(7000)
        shot(page, "openbox-1-agent-overview")
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(2000)
        shot(page, "openbox-1b-agent-overview-lower")
        page.mouse.wheel(0, 1400)
        page.wait_for_timeout(2000)
        shot(page, "openbox-1c-agent-overview-bottom")
        page.get_by_text("Sessions", exact=True).first.click()
        page.wait_for_timeout(4000)
        shot(page, "openbox-2-sessions")

        # Session replay, paused on the LLM call.
        page.goto(f"{agent}/sessions/{args.session_id}/replay")
        page.wait_for_timeout(6000)
        player = page.get_by_text("0.5x", exact=True).locator("xpath=ancestor::div[.//button][2]")
        player.locator("button").first.click()
        page.wait_for_timeout(1000)
        page.get_by_text("llm_call", exact=True).first.click()
        page.wait_for_timeout(2500)
        shot(page, "openbox-3-llm-call")

        # Verify tab: integrity panel, event log, and per-event detail.
        page.goto(verify)
        page.wait_for_timeout(7000)
        shot(page, "openbox-7-verify")
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(1500)
        shot(page, "openbox-7b-verify-log")
        event_modal(page, "upload_document", "10-upload-spans", 1)
        event_modal(page, "llm_call", "8-llm-span", 3)
        event_modal(page, "read_document", "9-read-span", 3)

        # Execution tree, expanded: raw HTTP and file spans.
        page.goto(verify)
        page.wait_for_timeout(6000)
        page.get_by_text("Tree View", exact=True).first.click()
        page.wait_for_timeout(2500)
        page.get_by_text("Expand All", exact=True).first.click()
        page.wait_for_timeout(3000)
        page.get_by_text('"HTTP POST"', exact=False).first.scroll_into_view_if_needed()
        page.mouse.wheel(0, -250)
        page.wait_for_timeout(1200)
        shot(page, "openbox-12-http-span")
        # Amy's first read is the Coca-Cola brief; its file span is the second mention.
        page.get_by_text("Coca_Cola_MA.docx", exact=False).nth(1).scroll_into_view_if_needed()
        page.mouse.wheel(0, -300)
        page.wait_for_timeout(1200)
        shot(page, "openbox-13-file-span")


if __name__ == "__main__":
    main()
