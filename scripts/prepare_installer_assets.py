"""Generate WiX UI PNGs from resources/background.png (requires Pillow).

Application / MSI icon: resources/xplane_mcp_icon.ico (committed; not generated here).
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Install Pillow: pip install pillow", file=sys.stderr)
    sys.exit(1)

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "resources" / "background.png"
OUT = REPO / "artifacts" / "installer-assets"


def cover_resize(im: Image.Image, w: int, h: int) -> Image.Image:
    src_w, src_h = im.size
    scale = max(w / src_w, h / src_h)
    nw, nh = int(src_w * scale), int(src_h * scale)
    resized = im.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return resized.crop((left, top, left + w, top + h))


def main() -> None:
    if not SRC.is_file():
        print(f"Missing source image: {SRC}", file=sys.stderr)
        sys.exit(1)

    OUT.mkdir(parents=True, exist_ok=True)

    im = Image.open(SRC).convert("RGBA")
    cover_resize(im, 493, 312).save(OUT / "WixUIDialogBmp.png", "PNG")
    cover_resize(im, 493, 58).save(OUT / "WixUIBannerBmp.png", "PNG")
    print(f"Installer UI bitmaps -> {OUT}")


if __name__ == "__main__":
    main()
