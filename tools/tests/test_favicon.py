"""Tests for favicon.py: rendered monogram is centered and sized as configured."""

from pathlib import Path

from PIL import Image, ImageOps

from favicon import FONT, TEXT_WIDTH, WEIGHT, build_svg, load_font, rasterize


def test_monogram_centered(tmp_path: Path) -> None:
    svg = tmp_path / "favicon.svg"
    svg.write_text(build_svg(load_font(FONT, WEIGHT)))
    rasterize(svg, tmp_path)
    icon = Image.open(tmp_path / "android-chrome-512x512.png").convert("L")
    left, top, right, bottom = ImageOps.invert(icon).point(lambda v: 255 if v > 60 else 0).getbbox()
    size = icon.width
    assert abs(left - (size - right)) <= 3
    assert abs(top - (size - bottom)) <= 3
    assert abs((right - left) - size * TEXT_WIDTH) <= 6
    assert (tmp_path / "favicon.ico").exists()
