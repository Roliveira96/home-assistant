"""Cuts a 60-second event clip out of the continuous recording.

Usage: make_clip.py <kind> <label> <event_epoch> [snapshot]

    kind      folder on the external disk: "sensores" or "alarme"
    label     what fired (sensor name), used in the file name
    snapshot  optional JPEG (taken by HA at event time) copied next to the clip

The clip covers PRE_ROLL seconds before the event and the rest after it, and
is saved as <BASE_DIR>/<kind>/YYYY-MM-DD/HH-MM-SS_<label>.mp4. HA calls this
~55 s after the event, when the continuous files already hold that minute.

Also prunes HA's notification snapshots (/config/media/camera) older than
SNAPSHOT_DAYS days; the copies on the external disk follow its retention.
Prints the clip path; exits non-zero when it cannot make the clip.
"""

import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

BASE_DIR = Path(os.environ.get("CAMERA_BASE_DIR", "/mnt/hd-externo/cameras"))
MARKER = BASE_DIR / ".hd-externo"
CONTINUOUS = BASE_DIR / "continuo"
KINDS = ("sensores", "alarme")
CLIP_SECONDS = 60
PRE_ROLL = 10
SEGMENT_SECONDS = 60
HA_SNAPSHOTS = Path("/config/media/camera")
SNAPSHOT_DAYS = 30


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower() or "event"


def segments_between(start: dt.datetime, end: dt.datetime) -> list[tuple[dt.datetime, Path]]:
    """Continuous files whose minute overlaps [start, end], oldest first."""
    found = []
    day = start.date() - dt.timedelta(days=1)
    while day <= end.date():
        folder = CONTINUOUS / day.isoformat()
        if folder.is_dir():
            for f in folder.glob("*.mp4"):
                try:
                    t = dt.datetime.combine(day, dt.datetime.strptime(f.stem, "%H-%M-%S").time())
                except ValueError:
                    continue
                if t <= end and t + dt.timedelta(seconds=SEGMENT_SECONDS) >= start:
                    found.append((t, f))
        day += dt.timedelta(days=1)
    return sorted(found)


def prune_ha_snapshots() -> None:
    if not HA_SNAPSHOTS.is_dir():
        return
    limit = time.time() - SNAPSHOT_DAYS * 86400
    for f in HA_SNAPSHOTS.rglob("*.jpg"):
        if f.stat().st_mtime < limit:
            f.unlink()
    for d in sorted(HA_SNAPSHOTS.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()


def main() -> int:
    if len(sys.argv) < 4 or sys.argv[1] not in KINDS:
        print(__doc__, file=sys.stderr)
        return 2
    kind, label, epoch = sys.argv[1], sys.argv[2], float(sys.argv[3])
    snapshot = Path(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else None
    prune_ha_snapshots()
    if not MARKER.is_file():
        print(f"external disk not mounted ({MARKER} not found)", file=sys.stderr)
        return 1

    event = dt.datetime.fromtimestamp(epoch)
    start = event - dt.timedelta(seconds=PRE_ROLL)
    end = start + dt.timedelta(seconds=CLIP_SECONDS)
    out_dir = BASE_DIR / kind / event.date().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{event:%H-%M-%S}_{slug(label)}"
    if snapshot and snapshot.is_file():
        shutil.copyfile(snapshot, out_dir / f"{name}.jpg")

    segments = segments_between(start, end)
    if not segments:
        print("no continuous recording for this time (is the camera recording?)",
              file=sys.stderr)
        return 1
    offset = max((start - segments[0][0]).total_seconds(), 0)
    clip = out_dir / f"{name}.mp4"
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as lst:
        for _t, f in segments:
            lst.write(f"file '{f}'\n")
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-f", "concat", "-safe", "0", "-i", lst.name,
             "-ss", f"{offset:.2f}", "-t", str(CLIP_SECONDS),
             "-c", "copy", "-movflags", "+faststart", str(clip)],
            capture_output=True, text=True, timeout=50, check=False)
    finally:
        Path(lst.name).unlink(missing_ok=True)
    if result.returncode != 0:
        print(f"ffmpeg failed: {result.stderr.strip()[-300:]}", file=sys.stderr)
        return 1
    print(clip)
    return 0


if __name__ == "__main__":
    sys.exit(main())
