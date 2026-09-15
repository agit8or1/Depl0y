#!/usr/bin/env python3
"""Generate docs/SCREENSHOTS.md from the capture manifest.

    python3 scripts/screenshots/build_gallery.py

Keeps headings, theme labels, captions, alt text and full-size links in step
with manifest.py so the gallery cannot drift from what was actually captured.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from manifest import SHOTS, SECTION_ORDER, VIEWPORT, DEVICE_SCALE_FACTOR  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
IMG_DIR = "images/github"
OUT = os.path.join(REPO, "docs", "SCREENSHOTS.md")

present = [s for s in SHOTS
           if os.path.exists(os.path.join(REPO, "docs", IMG_DIR, s["slug"] + ".png"))]
missing = [s["slug"] for s in SHOTS if s not in present]
light = sum(1 for s in present if s["theme"] == "light")
dark = len(present) - light


def anchor(title):
    return title.lower().replace(" ", "-").replace("/", "").replace("(", "") \
        .replace(")", "").replace("—", "").replace("--", "-").strip("-")


lines = [
    "# Screenshot gallery",
    "",
    f"{len(present)} views of Depl0y — {dark} dark, {light} light — captured at "
    f"{VIEWPORT['width']}×{VIEWPORT['height']} at {DEVICE_SCALE_FACTOR}× from the "
    "running application.",
    "",
    "[← Back to the README](../README.md) · "
    "[▶ Watch the walkthrough](https://github.com/agit8or1/Depl0y/releases/download/v2.2.75/depl0y-walkthrough.mp4)",
    "",
    "> **Demo data.** Every screenshot comes from an isolated demo instance whose "
    "Proxmox and Redfish responses are synthetic fixtures served on loopback inside "
    "a private network namespace. Host names use the reserved `example.net` domain "
    "and addresses come from the RFC 5737 documentation ranges "
    "(`203.0.113.0/24`, `198.51.100.0/24`, `192.0.2.0/24`). No real infrastructure "
    "was reachable during capture, and nothing was started, stopped, migrated or "
    "deleted to stage a picture. Regenerate them with "
    "[`scripts/screenshots/`](../scripts/screenshots/README.md).",
    "",
    "## Contents",
    "",
]

for section in SECTION_ORDER:
    items = [s for s in present if s["section"] == section]
    if items:
        lines.append(f"- [{section}](#{anchor(section)})")
for section in SECTION_ORDER:
    items = [s for s in present if s["section"] == section]
    if not items:
        continue
    lines += ["", "---", "", f"## {section}", ""]
    for s in items:
        theme = "🌙 Dark" if s["theme"] == "dark" else "☀️ Light"
        img = f"{IMG_DIR}/{s['slug']}.png"
        lines += [
            f"### {s['title']}",
            "",
            f"**{theme}** · `{s['route']}`",
            "",
            f"[![{s['alt']}]({img})]({img})",
            "",
            f"{s['caption']} · [Full size]({img})",
            "",
        ]

lines += [
    "---",
    "",
    "## More tools from MSPReboot",
    "",
    "Depl0y is built and maintained alongside other operations tooling at "
    "[mspreboot.com](https://mspreboot.com).",
    "",
    "[← Back to the README](../README.md)",
    "",
]

with open(OUT, "w") as f:
    f.write("\n".join(lines))

print(f"wrote {OUT}")
print(f"  {len(present)} screenshots — {dark} dark / {light} light")
if missing:
    print("  missing images for:", ", ".join(missing))
