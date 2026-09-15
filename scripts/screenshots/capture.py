#!/usr/bin/env python3
"""Capture the documentation screenshot gallery from an isolated demo instance.

Usage (from the repository root, inside the demo namespace — see README.md here):

    python3 scripts/screenshots/capture.py OUTPUT_DIR [--only slug,slug] [--theme light]

Every capture is driven against the real frontend and the real backend; only the
Proxmox and Redfish responses are synthetic fixtures. The theme is switched with
the panel's own Settings -> Appearance selector, not by injecting CSS.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from manifest import SHOTS, VIEWPORT, DEVICE_SCALE_FACTOR  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = os.environ.get("DEMO_BASE", "http://127.0.0.1:8080")
PW = os.environ["DEMO_ADMIN_PASSWORD"]

# The demo namespace has no default route, so the PWA believes it is offline.
# That banner is an artefact of the capture rig, not of the product.
INIT = """
Object.defineProperty(navigator, 'onLine', {get: () => true, configurable: true});
window.addEventListener('DOMContentLoaded', () => window.dispatchEvent(new Event('online')));
"""

TIDY = """() => {
  document.querySelectorAll(
    '.Vue-Toastification__container, .Vue-Toastification__toast, .global-task-bar, .offline-banner'
  ).forEach(e => e.remove());
  document.querySelectorAll('div,span,p').forEach(e => {
    if (e.children.length === 0 && /You are offline/i.test(e.textContent || '')) {
      let n = e;
      for (let i = 0; i < 4 && n.parentElement && n.parentElement !== document.body; i++) n = n.parentElement;
      n.remove();
    }
  });
}"""


def tidy(page):
    page.evaluate(TIDY)
    page.evaluate("() => window.scrollTo(0, 0)")
    time.sleep(0.5)
    page.evaluate(TIDY)


def set_theme(page, theme):
    """Switch themes through Settings -> Appearance, the way a user would."""
    page.goto(BASE + "/settings", wait_until="commit", timeout=30000)
    time.sleep(6)
    tidy(page)
    # Settings is tabbed; Appearance holds the theme cards.
    page.locator("button.stab", has_text="Appearance").first.click(timeout=20000)
    time.sleep(1.5)
    label = {"light": "Light", "dark": "Dark"}[theme]
    card = page.locator("button.appearance-theme-card").filter(
        has_text=label).first
    card.scroll_into_view_if_needed(timeout=10000)
    card.click(timeout=20000)
    time.sleep(1.5)
    applied = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
    if applied != theme:
        raise RuntimeError(f"theme did not apply: wanted {theme}, got {applied}")
    return applied


# ── optional per-shot interactions ────────────────────────────────────────

def wait_for_io(page):
    """The overview I/O tiles diff two polls; the backend caches VM status for
    10 s while the page polls every 5 s, so every other sample is identical.
    Wait for a poll that lands on a fresh reading."""
    for _ in range(8):
        txt = page.evaluate("() => (document.body.innerText.match(/In: [^\\n]*/) || [''])[0]")
        if txt and "0 B/s" not in txt:
            return
        time.sleep(5.2)


def expand_bmc(page):
    page.get_by_role("button", name="Details").first.click(timeout=15000)
    time.sleep(6)
    page.evaluate("() => window.scrollTo(0, 560)")
    time.sleep(1.5)


def create_vm_walkthrough(page):
    page.get_by_text("DC-East · Ashburn", exact=False).first.click(timeout=15000)
    time.sleep(4)
    boxes = page.get_by_placeholder("my-vm")
    boxes.first.fill("billing-api-03")
    if boxes.count() > 1:
        boxes.nth(1).fill("billing-api-03")
    page.get_by_placeholder("Optional notes about this VM...").first.fill(
        "Billing API worker — replaces billing-api-01 after the Q3 migration.")
    page.get_by_text("east-03", exact=False).first.click()
    time.sleep(2.5)
    page.evaluate("() => window.scrollTo(0, 150)")
    time.sleep(1)


def create_vm_storage_step(page):
    create_vm_walkthrough(page)
    for _ in range(2):
        page.get_by_role("button", name="Next").first.click(timeout=15000)
        time.sleep(2.5)
    page.evaluate("() => window.scrollTo(0, 0)")
    time.sleep(1.5)


def all_proxmox_tasks(page):
    """The Task Log opens on Depl0y-initiated tasks; the Proxmox-wide history
    lives on the second tab."""
    page.get_by_text("All Proxmox Tasks", exact=False).first.click(timeout=20000)
    time.sleep(6)


def select_first_host(page):
    """Pages scoped to one endpoint open with an empty host picker; choose the
    first real option so the screenshot shows data instead of a prompt."""
    try:
        sel = page.locator("select").first
        sel.wait_for(timeout=8000)
        values = page.evaluate(
            "() => Array.from(document.querySelector('select').options)"
            ".map(o => o.value).filter(v => v)")
        if values:
            sel.select_option(values[0])
            time.sleep(9)
    except Exception as e:
        print("    select_first_host: no picker -", repr(e)[:80], flush=True)


def open_appearance(page):
    page.locator("button.stab", has_text="Appearance").first.click(timeout=20000)
    time.sleep(2.5)


ACTIONS = {
    "wait_for_io": wait_for_io,
    "expand_bmc": expand_bmc,
    "create_vm_walkthrough": create_vm_walkthrough,
    "create_vm_storage_step": create_vm_storage_step,
    "open_appearance": open_appearance,
    "all_proxmox_tasks": all_proxmox_tasks,
    "select_first_host": select_first_host,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--only", default="")
    ap.add_argument("--theme", default="")
    args = ap.parse_args()

    shots = SHOTS
    if args.only:
        wanted = {s.strip() for s in args.only.split(",")}
        shots = [s for s in shots if s["slug"] in wanted]
    if args.theme:
        shots = [s for s in shots if s["theme"] == args.theme]
    # Group by theme so the selector is exercised once per group, not per shot.
    shots = sorted(shots, key=lambda s: s["theme"])

    os.makedirs(args.out, exist_ok=True)
    report, external = {}, []

    with sync_playwright() as p:
        browser = p.chromium.launch(args=[
            "--no-sandbox", "--disable-dev-shm-usage", "--force-color-profile=srgb",
            "--font-render-hinting=none", "--hide-scrollbars"])
        ctx = browser.new_context(viewport=VIEWPORT,
                                  device_scale_factor=DEVICE_SCALE_FACTOR,
                                  reduced_motion="reduce", service_workers="block")
        ctx.add_init_script(INIT)
        ctx.on("request", lambda r: None if r.url.startswith(
            (BASE, "data:", "blob:", "about:")) else external.append(r.url))

        page = ctx.new_page()
        page.set_default_timeout(25000)
        page.goto(BASE + "/login", wait_until="commit")
        time.sleep(2.5)
        page.evaluate("""async (pw) => {
            const r = await fetch('/api/v1/auth/login', {method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: 'admin', password: pw})});
            const j = await r.json();
            localStorage.setItem('access_token', j.access_token);
            localStorage.setItem('refresh_token', j.refresh_token);
        }""", PW)

        current = None
        for shot in shots:
            slug = shot["slug"]
            try:
                if shot["theme"] != current:
                    current = set_theme(page, shot["theme"])
                    print(f"  -- theme now {current}", flush=True)
                t0 = time.time()
                page.goto(BASE + shot["route"], wait_until="commit", timeout=30000)
                time.sleep(shot["dwell"])
                tidy(page)
                if shot.get("action"):
                    ACTIONS[shot["action"]](page)
                    tidy(page) if shot["action"] not in (
                        "expand_bmc", "create_vm_walkthrough",
                        "create_vm_storage_step") else page.evaluate(TIDY)
                applied = page.evaluate(
                    "() => document.documentElement.getAttribute('data-theme')")
                if applied != shot["theme"]:
                    raise RuntimeError(f"theme drift: {applied} != {shot['theme']}")
                txt = page.evaluate("() => document.body.innerText")
                page.screenshot(path=os.path.join(args.out, f"{slug}.png"),
                                animations="disabled", caret="initial", timeout=25000)
                report[slug] = {"route": shot["route"], "theme": shot["theme"],
                                "chars": len(txt), "seconds": round(time.time() - t0, 1)}
                print(f"  {slug:34s} {shot['theme']:5s} chars={len(txt):6d} "
                      f"{report[slug]['seconds']:6.1f}s", flush=True)
            except Exception as e:
                report[slug] = {"route": shot["route"], "theme": shot["theme"],
                                "error": repr(e)[:200]}
                print(f"  {slug:34s} ERROR {repr(e)[:120]}", flush=True)
        browser.close()

    report["_external_requests"] = sorted(set(external))
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print("off-box requests attempted:", len(set(external)), flush=True)


main()
