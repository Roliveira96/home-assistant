"""Sync resized copies of the notebook photos into the photo frame folder.

Reads /pictures (the host's ~/Pictures, mounted read-only; subfolders such as
Screenshots are ignored) and writes JPEGs of at most MAX_SIDE px, with the
EXIF orientation applied, to /config/media/fotos/otimizadas. Copies whose
source no longer exists are removed. Photos uploaded through the media browser
to /config/media/fotos are not touched. A lock file prevents concurrent runs.
"""

import fcntl
import pathlib
import sys

from PIL import Image, ImageOps

SOURCE = pathlib.Path("/pictures")
TARGET = pathlib.Path("/config/media/fotos/otimizadas")
LOCK = pathlib.Path("/config/fotos/.sync.lock")
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_SIDE = 1600
QUALITY = 85


def target_for(source: pathlib.Path) -> pathlib.Path:
    return TARGET / f"{source.stem}.jpg"


def main() -> int:
    with LOCK.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("another sync is already running")
            return 0
        return sync()


def sync() -> int:
    if not SOURCE.is_dir():
        print(f"source folder not found: {SOURCE}", file=sys.stderr)
        return 1
    TARGET.mkdir(parents=True, exist_ok=True)
    sources = [p for p in SOURCE.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS]
    created = removed = failed = 0
    wanted = set()
    for source in sources:
        target = target_for(source)
        wanted.add(target.name)
        if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
            continue
        try:
            with Image.open(source) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((MAX_SIDE, MAX_SIDE))
                # Write to a temp file first: an interrupted run (shell_command
                # times out after 60 s) must not leave a truncated photo behind.
                partial = target.with_suffix(".part")
                image.save(partial, "JPEG", quality=QUALITY, optimize=True)
                partial.replace(target)
            created += 1
        except OSError as err:
            failed += 1
            print(f"failed to convert {source.name}: {err}", file=sys.stderr)
    for stale in TARGET.glob("*.jpg"):
        if stale.name not in wanted:
            stale.unlink()
            removed += 1
    print(f"sources={len(sources)} created={created} removed={removed} failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
