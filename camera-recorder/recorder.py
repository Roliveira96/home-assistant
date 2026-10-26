"""Continuous camera recorder with DVR-style retention.

Records the camera's RTSP stream without re-encoding into 1-minute files:

    <BASE_DIR>/continuo/YYYY-MM-DD/HH-MM-SS.mp4

Files are fragmented MP4, so they can be read while still being written
(the event clips are cut from them) and survive a power cut.

Retention: while the disk is above MAX_USAGE_PERCENT, the oldest continuous
files are deleted first; event clips (sensores/, alarme/) only go when no
continuous file is left. Nothing outside BASE_DIR is ever touched.

Safety: nothing is written unless the marker file BASE_DIR/.hd-externo
exists, so an unmounted disk never fills the notebook's SSD.
"""

import datetime as dt
import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

BASE_DIR = Path(os.environ.get("BASE_DIR", "/mnt/hd-externo/cameras"))
MARKER = BASE_DIR / ".hd-externo"
CAMERA_URL = os.environ.get("CAMERA_RTSP_URL", "").strip()
SEGMENT_SECONDS = int(os.environ.get("SEGMENT_SECONDS", "60"))
MAX_USAGE_PERCENT = float(os.environ.get("MAX_USAGE_PERCENT", "95"))
CLEANUP_INTERVAL = int(os.environ.get("CLEANUP_INTERVAL", "60"))
CONTINUOUS = "continuo"
EVENT_DIRS = ("sensores", "alarme")
VIDEO_SUFFIXES = {".mp4", ".jpg"}

log = logging.getLogger("recorder")
stop = threading.Event()


def disk_ready() -> bool:
    return MARKER.is_file()


def usage_percent() -> float:
    total, used, _free = shutil.disk_usage(BASE_DIR)
    return used * 100 / total


def oldest_file(folder: Path) -> Path | None:
    """Oldest file by name (folders are YYYY-MM-DD, files start with HH-MM-SS)."""
    if not folder.is_dir():
        return None
    for day in sorted(p for p in folder.iterdir() if p.is_dir()):
        files = sorted(f for f in day.iterdir() if f.suffix in VIDEO_SUFFIXES)
        if files:
            return files[0]
        day.rmdir()  # empty day folder left by a previous cleanup
    return None


def cleanup_once() -> None:
    deleted = 0
    while usage_percent() > MAX_USAGE_PERCENT:
        victim = oldest_file(BASE_DIR / CONTINUOUS)
        if victim is None:
            candidates = [f for f in (oldest_file(BASE_DIR / d) for d in EVENT_DIRS) if f]
            victim = min(candidates, key=lambda f: (f.parent.name, f.name), default=None)
        if victim is None:
            log.warning("disk at %.1f%% but no recordings left to delete", usage_percent())
            return
        victim.unlink()
        deleted += 1
        if not any(victim.parent.iterdir()):
            victim.parent.rmdir()
    if deleted:
        log.info("retention: deleted %d old file(s), disk at %.1f%%", deleted, usage_percent())


def cleanup_loop() -> None:
    while not stop.is_set():
        if disk_ready():
            try:
                cleanup_once()
            except OSError as exc:
                log.error("cleanup failed: %s", exc)
        stop.wait(CLEANUP_INTERVAL)


def seconds_until_midnight() -> int:
    now = dt.datetime.now()
    midnight = dt.datetime.combine(now.date() + dt.timedelta(days=1), dt.time())
    return max(int((midnight - now).total_seconds()), 1)


def record_until_midnight() -> int:
    """Runs ffmpeg into today's folder until midnight; returns its exit code."""
    day_dir = BASE_DIR / CONTINUOUS / dt.date.today().isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    for name in EVENT_DIRS:
        (BASE_DIR / name).mkdir(exist_ok=True)
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "warning", "-nostdin",
        "-rtsp_transport", "tcp", "-timeout", "15000000",
        "-i", CAMERA_URL,
        "-t", str(seconds_until_midnight()),
        "-map", "0:v", "-map", "0:a?",
        # Video is copied as is; Tapo audio (G.711) is not allowed in MP4.
        "-c:v", "copy", "-c:a", "aac", "-b:a", "32k",
        "-f", "segment", "-segment_time", str(SEGMENT_SECONDS),
        "-segment_atclocktime", "1", "-reset_timestamps", "1", "-strftime", "1",
        "-segment_format", "mp4",
        "-segment_format_options", "movflags=+frag_keyframe+empty_moov+default_base_moof",
        str(day_dir / "%H-%M-%S.mp4"),
    ]
    log.info("recording to %s", day_dir)
    proc = subprocess.Popen(cmd)
    while proc.poll() is None:
        if stop.wait(1):
            proc.send_signal(signal.SIGINT)  # lets ffmpeg close the file cleanly
            proc.wait(timeout=15)
    return proc.returncode


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=sys.stdout)
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    threading.Thread(target=cleanup_loop, daemon=True).start()
    warned = None
    while not stop.is_set():
        problem = None
        if not CAMERA_URL:
            problem = "CAMERA_RTSP_URL is empty (set it in .env)"
        elif not disk_ready():
            problem = f"external disk not mounted ({MARKER} not found)"
        if problem:
            if problem != warned:
                log.warning("not recording: %s", problem)
                warned = problem
            stop.wait(30)
            continue
        warned = None
        started = time.monotonic()
        code = record_until_midnight()
        # Code 0 at midnight is the normal day switch; anything else (or a
        # stream that ended right away) means the camera dropped.
        if not stop.is_set() and (code != 0 or time.monotonic() - started < 30):
            log.warning("ffmpeg exited with code %s, retrying in 10 s", code)
            stop.wait(10)


if __name__ == "__main__":
    main()
