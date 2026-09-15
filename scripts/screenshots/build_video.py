#!/usr/bin/env python3
"""Turn a raw walkthrough recording into the published video deliverables.

    python3 scripts/screenshots/build_video.py RAW_DIR OUT_DIR

RAW_DIR must contain the WebM written by record_walkthrough.py and its
beats.json. Produces, in OUT_DIR:

    depl0y-walkthrough.mp4      full walkthrough, 1080p30 H.264, burned captions
    depl0y-highlight.mp4        30-60 s highlight cut
    depl0y-poster.png           thumbnail frame
    depl0y-walkthrough.vtt      caption sidecar
    depl0y-walkthrough.srt      caption source
    narration-script.md         narration-ready script keyed to the timeline

Requires ffmpeg with libx264.
"""
import glob
import json
import os
import subprocess
import sys

RAW, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)

beats_file = os.path.join(RAW, "beats.json")
meta = json.load(open(beats_file))
beats, duration = meta["beats"], meta["duration"]

webm = meta.get("video")
if not webm or not os.path.exists(webm):
    cands = sorted(glob.glob(os.path.join(RAW, "*.webm")), key=os.path.getsize)
    if not cands:
        sys.exit("no .webm found in " + RAW)
    webm = cands[-1]
print("raw:", webm, os.path.getsize(webm) // 1024, "KiB")


def run(cmd):
    print("  $", " ".join(cmd[:8]), "...")
    subprocess.run(cmd, check=True, capture_output=True)


def ts(seconds, comma=True):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    sep = "," if comma else "."
    return f"{h:02d}:{m:02d}:{int(s):02d}{sep}{int(round((s % 1) * 1000)):03d}"


# ── captions ──────────────────────────────────────────────────────────────
cues = []
for i, b in enumerate(beats):
    start = b["t"]
    end = beats[i + 1]["t"] if i + 1 < len(beats) else duration
    end = min(end - 0.15, start + 7.5)
    if end > start + 0.8:
        cues.append((start, end, b["caption"]))

with open(os.path.join(OUT, "depl0y-walkthrough.srt"), "w") as f:
    for i, (a, b_, text) in enumerate(cues, 1):
        f.write(f"{i}\n{ts(a)} --> {ts(b_)}\n{text}\n\n")

with open(os.path.join(OUT, "depl0y-walkthrough.vtt"), "w") as f:
    f.write("WEBVTT\n\n")
    for a, b_, text in cues:
        f.write(f"{ts(a, False)} --> {ts(b_, False)}\n{text}\n\n")

srt = os.path.join(OUT, "depl0y-walkthrough.srt")
style = ("FontName=DejaVu Sans,FontSize=19,PrimaryColour=&H00FFFFFF,"
         "BackColour=&HB0000000,BorderStyle=4,Outline=0,Shadow=0,"
         "MarginV=42,Alignment=2")

# ── full walkthrough ──────────────────────────────────────────────────────
full = os.path.join(OUT, "depl0y-walkthrough.mp4")
run(["ffmpeg", "-y", "-loglevel", "error", "-i", webm,
     "-vf", f"fps=30,scale=1920:1080:flags=lanczos,subtitles={srt}:force_style='{style}'",
     "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-pix_fmt", "yuv420p",
     "-movflags", "+faststart", "-an", full])

# ── highlight cut ─────────────────────────────────────────────────────────
by_label = {b["label"]: b["t"] for b in beats}


def seg(label, length, fallback=0.0):
    return (by_label.get(label, fallback), length)


wanted = [seg("title", 5), seg("dashboard", 8), seg("datacenters", 7),
          seg("vm-detail", 7), seg("hardware", 7), seg("hardware-detail", 8),
          seg("theme-light", 6), seg("endcard", 7)]
parts = []
for i, (start, length) in enumerate(wanted):
    if start <= 0 and i not in (0,):
        continue
    part = os.path.join(OUT, f".hl{i}.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{length}",
         "-i", full, "-c:v", "libx264", "-preset", "slow", "-crf", "23",
         "-pix_fmt", "yuv420p", "-an", part])
    parts.append(part)

listfile = os.path.join(OUT, ".concat.txt")
with open(listfile, "w") as f:
    for p in parts:
        f.write(f"file '{os.path.abspath(p)}'\n")
highlight = os.path.join(OUT, "depl0y-highlight.mp4")
run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
     "-i", listfile, "-c", "copy", "-movflags", "+faststart", highlight])
for p in parts + [listfile]:
    os.remove(p)

# ── poster ────────────────────────────────────────────────────────────────
poster_at = by_label.get("dashboard", 12) + 4
run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{poster_at:.2f}", "-i", full,
     "-frames:v", "1", os.path.join(OUT, "depl0y-poster.png")])

# ── narration script ──────────────────────────────────────────────────────
with open(os.path.join(OUT, "narration-script.md"), "w") as f:
    f.write("# Depl0y walkthrough — narration script\n\n")
    f.write("Timings match `depl0y-walkthrough.mp4`. The published video is "
            "caption-led; no narration audio was recorded.\n\n")
    f.write("| Time | Beat | Line to read |\n|---|---|---|\n")
    for b in beats:
        f.write(f"| {ts(b['t'], False)[3:]} | `{b['label']}` | {b['caption']} |\n")


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "format=duration:stream=width,height,avg_frame_rate",
         "-of", "json", path], capture_output=True, text=True).stdout
    d = json.loads(out)
    st = d["streams"][0]
    return (f"{st['width']}x{st['height']} @{st['avg_frame_rate']} "
            f"{float(d['format']['duration']):.1f}s "
            f"{os.path.getsize(path) // 1024} KiB")


print("full     :", probe(full))
print("highlight:", probe(highlight))
print("poster   :", os.path.getsize(os.path.join(OUT, 'depl0y-poster.png')) // 1024, "KiB")
print("cues     :", len(cues))
