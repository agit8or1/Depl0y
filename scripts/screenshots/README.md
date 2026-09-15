# Screenshot and video capture

Regenerates the documentation gallery and the walkthrough video from the real
application, without touching any production data.

Nothing here runs as part of normal Depl0y startup. It is developer tooling.

---

## How the isolation works

`demo/inner.sh` is executed inside a private **network + mount namespace**
(`unshare -nm`). Inside that namespace:

- the only network device is loopback, so no packet can leave the machine;
- the RFC 5737 documentation addresses used by the fixtures
  (`203.0.113.x`, `198.51.100.x`, `192.0.2.x`) are added as loopback aliases,
  so they resolve to the mock servers and nothing else;
- a private `/etc/hosts` is bind-mounted so `pve-east.example.net` and friends
  resolve locally. The real `/etc/hosts` is untouched;
- `demo/mock_pve.py` and `demo/mock_redfish.py` answer the Proxmox and Redfish
  calls. **Both refuse every POST, PUT, PATCH and DELETE with HTTP 403**, so a
  capture run cannot start, stop, migrate or delete anything even by accident;
- a throwaway SQLite database and encryption key are created per run under
  `$DEMO_STATE` (default `/tmp/depl0y-demo-state`), never inside the repository.

The capture scripts also record every request the browser attempts. A run that
reaches anything off-box would report it; the published gallery was captured
with `off-box requests attempted: 0`.

## Demo data

`demo/fixtures.py` defines the synthetic estate: three Proxmox endpoints
(two clusters and a standalone lab), six BMCs (five Dell iDRAC, one HPE iLO),
45 guests and 8 containers, with mixed utilisation, one DIMM warning and one
storage alert. Host names use the reserved `example.net` domain; every address
comes from an RFC 5737 documentation range. Service tags, serial numbers and
MAC addresses are invented.

`demo/seed_db.py` adds the admin account, audit history and the cloud image and
ISO catalogue rows. `demo/seed_api.py` then registers the endpoints through
Depl0y's own REST API and attaches BMC credentials, so the captures exercise the
real code paths rather than hand-written database rows.

## Prerequisites

```
python3, the Depl0y backend virtualenv, node/npm (for a frontend build),
playwright + its chromium build, ffmpeg (video only), pngquant + ImageMagick
(optimisation)
```

Build the frontend first — captures are served from `frontend/dist`:

```bash
cd frontend && npm run build
```

## Screenshots

```bash
cd scripts/screenshots/demo
export DEMO_ADMIN_PASSWORD='<anything; it exists only for this run>'
export DEMO_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export DEMO_REPO="$(cd ../../.. && pwd)"
export PLAYWRIGHT_BROWSERS_PATH="$HOME/.cache/ms-playwright"

sudo -E unshare -nm ./inner.sh python3 -u ../capture.py /tmp/shots
```

Useful flags: `--theme light|dark`, `--only slug,slug`.

`manifest.py` is the source of truth for every capture — route, theme, dwell,
gallery section, heading, caption and alt text. Add a shot there, not in the
capture script.

Optimise and install into the repository:

```bash
for f in /tmp/shots/*.png; do
  convert "$f" -resize 1920x -strip /tmp/_r.png
  pngquant --quality=70-92 --force --output "docs/images/github/$(basename $f)" /tmp/_r.png
done
python3 scripts/screenshots/build_gallery.py     # rewrites docs/SCREENSHOTS.md
```

## Video

```bash
sudo -E unshare -nm ./inner.sh python3 -u ../record_walkthrough.py /tmp/walkthrough
python3 ../build_video.py /tmp/walkthrough /tmp/walkthrough-out
```

`record_walkthrough.py` drives the same isolated stack, logging a timestamped
beat for each step. `build_video.py` turns the raw WebM plus those beats into
the MP4, the highlight cut, the poster frame and the caption files — the caption
timings come from the beat log, so they cannot drift from what is on screen.

**Video files are deliberately not committed.** Keep them out of Git history and
attach them to a GitHub release instead.

## Secrets

No credential is stored in this directory. `DEMO_ADMIN_PASSWORD` and
`DEMO_ENCRYPTION_KEY` are supplied per run through the environment and apply
only to the throwaway database. Do not point these scripts at a real Depl0y
installation.

## Publishing the video

The MP4s are deliberately **not** committed — they are attached to a GitHub
release instead. The current set lives on **v2.2.75**:

```
https://github.com/agit8or1/Depl0y/releases/download/v2.2.75/depl0y-walkthrough.mp4
https://github.com/agit8or1/Depl0y/releases/download/v2.2.75/depl0y-highlight.mp4
https://github.com/agit8or1/Depl0y/releases/download/v2.2.75/depl0y-poster.png
https://github.com/agit8or1/Depl0y/releases/download/v2.2.75/depl0y-walkthrough.vtt
```

To publish a rebuilt set against a future release:

```bash
gh release upload vX.Y.Z \
  depl0y-walkthrough.mp4 depl0y-highlight.mp4 \
  depl0y-poster.png depl0y-walkthrough.vtt
```

Then update the release URLs in `README.md` and in `build_gallery.py` (the
gallery header link is generated, so editing `docs/SCREENSHOTS.md` by hand is
overwritten on the next build).

GitHub does not render `<video>` elements or iframes in Markdown, so the README
uses a clickable poster image plus a plain link. Only the poster is committed
(`docs/images/github/video-poster.png`); the video itself never enters Git
history.

Note that the in-app updater only treats assets ending in `.tar.gz` as update
packages (`github_updates.py`), so media assets on a release are ignored by it.
