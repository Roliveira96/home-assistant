"""Show the next random photo in the photo frame.

Picks a random photo from /config/media/fotos and its subfolders (different
from the previous one) and copies it over CURRENT, the fixed file the
local_file camera (camera.porta_retrato) always points to. Keeping the camera
on a fixed path means it never ends up pointing at a photo that was deleted.
Prints the chosen photo.
"""

import pathlib
import random
import shutil
import sys

FOLDER = pathlib.Path("/config/media/fotos")
CURRENT = pathlib.Path("/config/fotos/current.jpg")
LAST = pathlib.Path("/config/fotos/.last")
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def main() -> int:
    photos = sorted(
        str(p) for p in FOLDER.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS
    )
    if not photos:
        print("no photos found", file=sys.stderr)
        return 1
    last = LAST.read_text().strip() if LAST.exists() else ""
    choice = random.choice([p for p in photos if p != last] or photos)
    partial = CURRENT.with_suffix(".part")
    shutil.copyfile(choice, partial)
    partial.replace(CURRENT)
    LAST.write_text(choice)
    print(choice)
    return 0


if __name__ == "__main__":
    sys.exit(main())
