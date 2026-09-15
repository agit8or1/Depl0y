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
    """Wait for the overview I/O tiles to show a non-zero rate.

    The tiles diff the last two status samples. The backend caches VM status
    for 10 s while the page polls every 5 s, so every other sample repeats and
    the computed rate is 0. Wait for a fresh pair, then confirm the reading is
    still non-zero — otherwise a poll firing between here and the screenshot
    puts a 0 B/s tile in the published image.
    """
    def reading():
        return page.evaluate(
            "() => (document.body.innerText.match(/In: [^\\n]*/) || [''])[0]")

    for _ in range(12):
        if "0 B/s" not in (reading() or "0 B/s"):
            time.sleep(1.2)
            if "0 B/s" not in (reading() or "0 B/s"):
                return                      # stable, safe to capture
            continue
        time.sleep(2.5)


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
    """Fill the scoping selects at the top of a page.

    Storage and Networking gate their content behind a host picker and then a
    node picker, where the node select stays disabled (and empty) until the
    host change handler has loaded the node list. Choosing only the first
    select leaves the page on its "select a host" placeholder, so walk the
    chain: pick a host, wait for the next select to populate, pick a node.
    Pages with a single picker (Backup) simply stop after the first.
    """
    def options(idx):
        return page.evaluate(
            """(i) => {
                const s = document.querySelectorAll('select')[i];
                if (!s || s.disabled) return null;
                return Array.from(s.options).map(o => o.value).filter(v => v !== '');
            }""", idx)

    try:
        page.locator("select").first.wait_for(timeout=10000)
    except Exception as e:
        print("    select chain: no picker -", repr(e)[:80], flush=True)
        return

    for idx in range(2):                      # host, then node
        vals = None
        for _ in range(16):                   # up to ~16 s for the list to load
            vals = options(idx)
            if vals:
                break
            time.sleep(1)
        if not vals:
            if idx == 0:
                print("    select chain: nothing selectable", flush=True)
            break
        page.locator("select").nth(idx).select_option(vals[0])
        print(f"    select[{idx}] = {vals[0]}", flush=True)
        time.sleep(6)

    # let the content that the selection triggered finish loading
    time.sleep(5)


def backup_schedules(page):
    """Backup opens on the PBS Servers tab; the vzdump schedules are next door."""
    select_first_host(page)
    page.get_by_text("Schedules", exact=True).first.click(timeout=20000)
    time.sleep(6)


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
    "backup_schedules": backup_schedules,
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
