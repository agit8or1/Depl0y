#!/usr/bin/env python3
"""Regenerate docs/images/github/social-preview.png from the dashboard capture.

    python3 scripts/screenshots/build_social_preview.py

GitHub's social card is 1280x640 (2:1) and capped at 1 MB. It is cropped from
the canonical dashboard screenshot rather than captured separately, so it can
never drift from the gallery: regenerate the gallery, run this, and the card
tracks it.

The field itself has no API — see docs/github-about.md. This only produces the
file; a maintainer uploads it through Settings -> General -> Social preview.
"""
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(REPO, "docs/images/github/infrastructure-dashboard-dark.png")
OUT = os.path.join(REPO, "docs/images/github/social-preview.png")
TMP = "/tmp/_social-preview.png"
LIMIT = 1024 * 1024

if not os.path.exists(SRC):
    sys.exit(f"missing source capture: {SRC}")

# Width-fit to 1280, then take the top 640 — the header, the summary tiles and
# the first row of panels, which is what reads at social-card size.
subprocess.run(["convert", SRC, "-resize", "1280x", "-gravity", "north",
                "-crop", "1280x640+0+0", "+repage", "-strip", TMP], check=True)
subprocess.run(["pngquant", "--quality=70-92", "--force", "--output", OUT, TMP],
               check=True)
os.remove(TMP)

size = os.path.getsize(OUT)
dims = subprocess.run(["identify", "-format", "%wx%h", OUT],
                      capture_output=True, text=True, check=True).stdout
print(f"wrote {OUT}")
print(f"  {dims}, {size / 1024:.1f} KB", "OK" if size < LIMIT else "OVER 1 MB LIMIT")
if dims != "1280x640" or size >= LIMIT:
    sys.exit("social preview does not meet GitHub's requirements")
