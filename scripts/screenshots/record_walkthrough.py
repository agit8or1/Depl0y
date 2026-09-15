#!/usr/bin/env python3
"""Record a walkthrough of the real application against the demo fixtures.

Produces a raw WebM plus a beat log; scripts/screenshots/build_video.sh turns
those into the MP4 deliverables, the highlight clip, the poster and the captions.

The recording is driven through the live UI — navigation, the real theme
selector, real charts — against the isolated fixture stack. Nothing is started,
stopped, migrated or deleted at any point.
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

OUT = sys.argv[1]
BASE = os.environ.get("DEMO_BASE", "http://127.0.0.1:8080")
PW = os.environ["DEMO_ADMIN_PASSWORD"]
SIZE = {"width": 1920, "height": 1080}

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

CARD = """
<!doctype html><meta charset=utf-8>
<style>
  html,body{margin:0;height:100%%;background:%(bg)s;color:%(fg)s;
    font:400 28px/1.5 'Segoe UI',Helvetica,Arial,sans-serif;
    display:flex;align-items:center;justify-content:center;text-align:center}
  .w{max-width:1200px;padding:0 60px}
  h1{font-size:76px;margin:0 0 18px;letter-spacing:-2px;font-weight:700}
  h1 .z{color:#3b82f6}
  p{margin:10px 0;color:%(muted)s}
  .big{font-size:38px;color:%(fg)s;margin-bottom:34px}
  .url{margin-top:40px;font-size:30px;color:#3b82f6}
</style>
<div class=w>%(body)s</div>
"""

BEATS = []


def beat(label, caption):
    BEATS.append({"t": round(time.time() - T0, 2), "label": label, "caption": caption})
    print(f"  [{BEATS[-1]['t']:6.1f}s] {label}", flush=True)


def card(page, body, theme="dark"):
    colours = dict(bg="#0d1117", fg="#e6edf3", muted="#9198a1") if theme == "dark" \
        else dict(bg="#ffffff", fg="#0f172a", muted="#475569")
    page.set_content(CARD % dict(body=body, **colours))
    time.sleep(0.4)


def tidy(page):
    page.evaluate(TIDY)
    time.sleep(0.3)


def glide(page, to, steps=26, pause=0.045):
    """Smooth scroll so the recording does not jump."""
    start = page.evaluate("() => window.scrollY")
    for i in range(1, steps + 1):
        page.evaluate(f"() => window.scrollTo(0, {start + (to - start) * i / steps})")
        time.sleep(pause)


def visit(page, path, settle, caption, label=None):
    page.goto(BASE + path, wait_until="commit", timeout=30000)
    time.sleep(settle)
    tidy(page)
    beat(label or path, caption)


def set_theme(page, theme):
    page.goto(BASE + "/settings", wait_until="commit", timeout=30000)
    time.sleep(6)
    tidy(page)
    page.locator("button.stab", has_text="Appearance").first.click(timeout=20000)
    time.sleep(2)
    beat("theme-selector", "Depl0y ships Light, Dark and System themes.")
    label = {"light": "Light", "dark": "Dark"}[theme]
    page.locator("button.appearance-theme-card").filter(has_text=label).first.click(
        timeout=20000)
    time.sleep(2.5)
    beat(f"theme-{theme}", f"Switching the whole panel to {label.lower()} theme.")


def main():
    global T0
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=[
            "--no-sandbox", "--disable-dev-shm-usage", "--force-color-profile=srgb",
            "--font-render-hinting=none", "--hide-scrollbars"])
        ctx = browser.new_context(viewport=SIZE, device_scale_factor=1,
                                  reduced_motion="reduce", service_workers="block",
                                  record_video_dir=OUT, record_video_size=SIZE)
        ctx.add_init_script(INIT)
        page = ctx.new_page()
        page.set_default_timeout(25000)

        page.goto(BASE + "/login", wait_until="commit")
        time.sleep(2)
        page.evaluate("""async (pw) => {
            const r = await fetch('/api/v1/auth/login', {method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: 'admin', password: pw})});
            const j = await r.json();
            localStorage.setItem('access_token', j.access_token);
            localStorage.setItem('refresh_token', j.refresh_token);
            localStorage.setItem('depl0y_theme', 'dark');
        }""", PW)

        T0 = time.time()

        # ── 1. Title (5-10 s) ────────────────────────────────────────────
        card(page, "<h1>Depl<span class=z>0</span>y</h1>"
                   "<p class=big>Proxmox infrastructure and server hardware"
                   " management in one dashboard.</p>"
                   "<p>For Proxmox administrators, homelabs and infrastructure teams."
                   "</p><p>Open source &middot; MIT licensed</p>")
        beat("title", "Depl0y — Proxmox infrastructure and server hardware "
                      "management in one dashboard.")
        time.sleep(6)

        card(page, "<p class=big>Everything that follows is the real application"
                   " running against an isolated demo instance.</p>"
                   "<p>Synthetic Proxmox and Redfish fixtures &middot; "
                   "documentation IP ranges &middot; no real infrastructure.</p>")
        beat("disclaimer", "Everything shown is the real application driven against "
                           "an isolated demo instance with synthetic data.")
        time.sleep(5)

        # ── 2. Dashboard orientation (20-30 s) ───────────────────────────
        visit(page, "/", 9,
              "One dashboard over every registered Proxmox site — guests, capacity "
              "and alerts together.", "dashboard")
        time.sleep(4)
        glide(page, 620)
        beat("dashboard-widgets",
             "Live per-node throughput, node health and the alerts Depl0y raised "
             "from its own polling.")
        time.sleep(5)
        glide(page, 0)
        time.sleep(1.5)

        # ── 3a. Workflow one: multi-site inventory ───────────────────────
        visit(page, "/proxmox", 11,
              "Two clusters and a standalone lab host, each registered with its own "
              "credentials.", "datacenters")
        time.sleep(5)
        glide(page, 780)
        beat("datacenter-nodes",
             "Per-node CPU, memory and disk, with the server model read from the BMC.")
        time.sleep(5)
        glide(page, 0)

        visit(page, "/vms", 15,
              "Every guest across every site, with the IP its guest agent reports.",
              "vm-inventory")
        time.sleep(5)

        # ── 3b. Workflow two: a guest in detail ──────────────────────────
        visit(page, "/proxmox/1/nodes/east-01/vms/103", 22,
              "Open a guest for live CPU, memory and I/O, plus an hour of history.",
              "vm-detail")
        time.sleep(6)
        glide(page, 520)
        beat("vm-charts", "CPU and memory trends come straight from the node's RRD data.")
        time.sleep(5)
        glide(page, 0)
        time.sleep(1)

        # ── 3c. Workflow three: the hardware underneath ──────────────────
        visit(page, "/idrac", 12,
              "The differentiator: iDRAC and iLO health beside the hypervisor.",
              "hardware")
        time.sleep(5)
        beat("hardware-summary",
             "Six servers, one flagged on a DIMM, with total draw across the estate.")
        time.sleep(3)
        try:
            page.get_by_role("button", name="Details").first.click(timeout=15000)
            time.sleep(6)
            glide(page, 560)
            beat("hardware-detail",
                 "Service tag, firmware, temperatures, fan speeds and current draw — "
                 "read over Redfish.")
            time.sleep(6)
            glide(page, 0)
        except Exception as e:
            print("  hardware detail skipped:", repr(e)[:120], flush=True)

        # ── 4. Theme switch + visual monitoring (20-30 s) ────────────────
        set_theme(page, "light")
        time.sleep(2)

        visit(page, "/", 9, "The same dashboard in light theme.", "dashboard-light")
        time.sleep(5)

        visit(page, "/storage-management", 10,
              "Capacity across every pool before you place the next guest.",
              "storage")
        time.sleep(4)

        visit(page, "/vms/create", 6,
              "Creating a guest: pick the site, then the node, with its load in view.",
              "create-vm")
        try:
            page.get_by_text("DC-East · Ashburn", exact=False).first.click(timeout=15000)
            time.sleep(4)
            boxes = page.get_by_placeholder("my-vm")
            boxes.first.fill("billing-api-03")
            if boxes.count() > 1:
                boxes.nth(1).fill("billing-api-03")
            time.sleep(1)
            page.get_by_text("east-03", exact=False).first.click()
            time.sleep(2)
            glide(page, 150)
            beat("create-vm-node", "Node cards show current CPU and memory load as you choose.")
            time.sleep(5)
        except Exception as e:
            print("  create-vm skipped:", repr(e)[:120], flush=True)

        visit(page, "/audit-log", 8,
              "Every action is attributable — Depl0y keeps its own audit trail.",
              "audit")
        time.sleep(4)

        # ── 5. End card (10-15 s) ────────────────────────────────────────
        card(page, "<h1>Depl<span class=z>0</span>y</h1>"
                   "<p class=big>Install it, read the docs, browse the screenshots.</p>"
                   "<p>github.com/agit8or1/Depl0y</p>"
                   "<p class=url>More tools at mspreboot.com</p>", theme="light")
        beat("endcard", "Install Depl0y and read the docs at github.com/agit8or1/Depl0y "
                        "— more tools at mspreboot.com.")
        time.sleep(8)

        total = round(time.time() - T0, 2)
        video = page.video
        ctx.close()          # flush the video file
        browser.close()
        path = video.path()

    with open(os.path.join(OUT, "beats.json"), "w") as f:
        json.dump({"duration": total, "beats": BEATS, "video": path}, f, indent=2)
    print(f"raw video: {path}")
    print(f"duration:  {total}s across {len(BEATS)} beats")


main()
