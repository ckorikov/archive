#!/usr/bin/env python3
"""Build site favicons: 'CK' monogram in Cormorant Bold, ink on paper.

favicon.svg is drawn from the site's own font outlines (no webfont needed),
then rasterized to PNG sizes with rsvg-convert and packed into favicon.ico.
"""

import subprocess
from pathlib import Path

import click
from fontTools.pens.basePen import AbstractPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "site" / "static"
FONT = STATIC_DIR / "fonts" / "cormorant-latin.woff2"

TEXT = "CK"
WEIGHT = 700  # heavier than body text so 16-32px stays legible
SIZE = 512
TEXT_WIDTH = 0.70  # share of the square the letters span
TRACKING = -60  # font units; pulls C and K into one monogram
BG, FG = "#f3f1ec", "#2c2925"  # --c-paper, --c-ink

PNG_SIZES = {
    "favicon-16x16.png": 16,
    "favicon-32x32.png": 32,
    "apple-touch-icon.png": 180,
    "android-chrome-192x192.png": 192,
    "android-chrome-512x512.png": 512,
}

Transform = tuple[float, float, float, float, float, float]


def load_font(path: Path, weight: int) -> TTFont:
    """Open a variable font and pin its weight axis."""
    font = TTFont(path)
    return instantiateVariableFont(font, {"wght": weight})


def glyph_layout(font: TTFont, text: str) -> list[tuple[str, float]]:
    """(glyph name, x offset) per char, by advance widths plus tracking."""
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    x, out = 0.0, []
    for ch in text:
        name = cmap[ord(ch)]
        out.append((name, x))
        x += hmtx[name][0] + TRACKING
    return out


def draw(font: TTFont, layout: list[tuple[str, float]], pen: AbstractPen, t: Transform) -> None:
    """Draw laid-out glyphs into pen through affine transform t."""
    glyphs = font.getGlyphSet()
    a, b, c, d, e, f = t
    for name, x in layout:
        glyphs[name].draw(TransformPen(pen, (a, b, c, d, e + x * a, f)))


def build_svg(font: TTFont, text: str = TEXT) -> str:
    """Return the monogram as an SVG string, ink box centered in the square."""
    layout = glyph_layout(font, text)
    bounds = BoundsPen(font.getGlyphSet())
    draw(font, layout, bounds, (1, 0, 0, 1, 0, 0))
    x0, y0, x1, y1 = bounds.bounds
    scale = SIZE * TEXT_WIDTH / (x1 - x0)
    # Font Y goes up, SVG Y goes down: flip and center the ink box.
    dx = (SIZE - (x1 - x0) * scale) / 2 - x0 * scale
    dy = (SIZE + (y1 - y0) * scale) / 2 + y0 * scale
    pen = SVGPathPen(font.getGlyphSet(), ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
    draw(font, layout, pen, (scale, 0, 0, -scale, dx, dy))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}">'
        f'<rect width="{SIZE}" height="{SIZE}" fill="{BG}"/>'
        f'<path fill="{FG}" d="{pen.getCommands()}"/></svg>\n'
    )


def rasterize(svg: Path, out_dir: Path) -> None:
    """Render PNG sizes with rsvg-convert, then pack 16+32 into favicon.ico."""
    for name, px in PNG_SIZES.items():
        subprocess.run(["rsvg-convert", "-w", str(px), "-h", str(px), str(svg), "-o", str(out_dir / name)], check=True)
    small = Image.open(out_dir / "favicon-16x16.png")
    big = Image.open(out_dir / "favicon-32x32.png")
    big.save(out_dir / "favicon.ico", sizes=[(32, 32), (16, 16)], append_images=[small])


@click.command()
@click.option("-o", "--output", type=click.Path(path_type=Path), default=STATIC_DIR, help="Output directory")
def main(output: Path) -> None:
    """Write favicon.svg and its PNG/ICO renditions."""
    svg = output / "favicon.svg"
    svg.write_text(build_svg(load_font(FONT, WEIGHT)))
    rasterize(svg, output)
    click.echo(f"Favicons written to {output}")


if __name__ == "__main__":
    main()
