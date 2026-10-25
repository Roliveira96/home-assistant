"""Print a random photo path from /config/media/fotos and its subfolders
(different from the current one).

Usage: next_photo.py [current_path]
Used by the photo frame automation to rotate the local_file camera.
"""

import pathlib
import random
import sys

FOLDER = pathlib.Path("/config/media/fotos")
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def main(argv: list[str]) -> int:
    current = argv[1] if len(argv) > 1 else ""
    photos = sorted(
        str(p) for p in FOLDER.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS
    )
    # Hide the placeholder once real photos exist.
    real = [p for p in photos if not pathlib.Path(p).name.startswith("00-placeholder")]
    photos = real or photos
    if not photos:
        return 1
    choices = [p for p in photos if p != current] or photos
    print(random.choice(choices))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
