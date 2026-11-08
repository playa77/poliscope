"""Generate the Poliscope launcher icon assets (SVG source and PNG raster).

Run with a system Python that has Pillow (this is a development/rendering
convenience, not a runtime dependency of the application or the engine):

    python3 scripts/make_icon.py

It (re)writes packaging/icons/poliscope.svg and packaging/icons/poliscope-256.png
from one set of geometric constants. The committed PNG is the artifact the
packaging and installer consume; never regenerate for an existing released
candidate without a new candidate receipt.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / 'packaging/icons'

# Single source of truth for both outputs.
SIZE = 256
CORNER_RADIUS = 48
BACKGROUND = '#16140f'
RING_COLOR = '#d8a44a'
DOT_COLOR = '#efe9df'
RING_RADIUS = 74   # distance from centre to the ring centreline
RING_WIDTH = 18
DOT_RADIUS = 22


def svg() -> str:
    ring = RING_RADIUS - RING_WIDTH / 2
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{SIZE}" height="{SIZE}" viewBox="0 0 {SIZE} {SIZE}">\n'
        f'  <rect width="{SIZE}" height="{SIZE}" rx="{CORNER_RADIUS}" fill="{BACKGROUND}"/>\n'
        f'  <circle cx="{SIZE // 2}" cy="{SIZE // 2}" r="{RING_RADIUS:.0f}" '
        f'fill="none" stroke="{RING_COLOR}" stroke-width="{RING_WIDTH}"/>\n'
        f'  <circle cx="{SIZE // 2}" cy="{SIZE // 2}" r="{DOT_RADIUS}" fill="{DOT_COLOR}"/>\n'
        '</svg>\n'
    )


def png() -> Image.Image:
    image = Image.new('RGBA', (SIZE, SIZE), BACKGROUND)
    draw = ImageDraw.Draw(image)
    centre = (SIZE - 1) / 2
    draw.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=CORNER_RADIUS, fill=BACKGROUND)
    draw.ellipse([centre - RING_RADIUS + RING_WIDTH / 2, centre - RING_RADIUS + RING_WIDTH / 2,
                  centre + RING_RADIUS - RING_WIDTH / 2, centre + RING_RADIUS - RING_WIDTH / 2],
                 outline=RING_COLOR, width=RING_WIDTH)
    draw.ellipse([centre - DOT_RADIUS, centre - DOT_RADIUS,
                  centre + DOT_RADIUS, centre + DOT_RADIUS], fill=DOT_COLOR)
    return image


def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    (ICON_DIR / 'poliscope.svg').write_text(svg(), encoding='utf-8')
    png().save(ICON_DIR / 'poliscope-256.png')
    print(f'wrote {ICON_DIR / "poliscope.svg"}')
    print(f'wrote {ICON_DIR / "poliscope-256.png"}')


if __name__ == '__main__':
    main()
