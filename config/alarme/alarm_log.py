"""CSV log of classified detections while the alarm is armed, with period export.

Usage:
    alarm_log.py append <type> <sensors>
    alarm_log.py export <start> <end>

<start>/<end> use the input_datetime format "YYYY-MM-DD HH:MM:SS" (local time),
which also sorts correctly as text. The export is written under /config/www
(served at /local/...) in a random, unguessable directory and removed after
24 hours. Prints "<url path>|<row count>" for the calling script.
"""

import csv
import datetime as dt
import pathlib
import secrets
import shutil
import sys
import time

LOG = pathlib.Path("/config/alarme/events.csv")
EXPORT_ROOT = pathlib.Path("/config/www/exports")
HEADER = ["timestamp", "type", "sensors"]
MAX_EXPORT_AGE_S = 24 * 3600


def append(kind: str, sensors: str) -> None:
    is_new = not LOG.exists()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(HEADER)
        writer.writerow([dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), kind, sensors])


def remove_old_exports() -> None:
    if not EXPORT_ROOT.exists():
        return
    for path in EXPORT_ROOT.iterdir():
        if path.is_dir() and time.time() - path.stat().st_mtime > MAX_EXPORT_AGE_S:
            shutil.rmtree(path, ignore_errors=True)


def export(start: str, end: str) -> None:
    remove_old_exports()
    rows = []
    if LOG.exists():
        with LOG.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            rows = [row for row in reader if row and start <= row[0] <= end]
    token = secrets.token_urlsafe(24)
    out_dir = EXPORT_ROOT / token
    out_dir.mkdir(parents=True)
    name = f"alarm_log_{start[:10]}_{end[:10]}.csv"
    # utf-8-sig so spreadsheet apps show accented sensor names correctly.
    with (out_dir / name).open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows)
    print(f"/local/exports/{token}/{name}|{len(rows)}")


def main(argv: list[str]) -> int:
    if len(argv) == 4 and argv[1] == "append":
        append(argv[2], argv[3])
    elif len(argv) == 4 and argv[1] == "export":
        export(argv[2], argv[3])
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
