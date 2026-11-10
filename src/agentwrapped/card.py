"""Render a 1200x675 share card (the size X, LinkedIn and Slack previews use)."""
from __future__ import annotations

from importlib import resources
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1200, 675


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    with resources.as_file(resources.files(__package__) / "fonts" / name) as p:
        return ImageFont.truetype(str(p), size)


def _gradient(top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (W, H), top)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img


def _fit(draw: ImageDraw.ImageDraw, text: str, font_name: str, size: int, max_w: int) -> ImageFont.FreeTypeFont:
    f = _font(font_name, size)
    while draw.textlength(text, font=f) > max_w and size > 14:
        size -= 2
        f = _font(font_name, size)
    return f


def render(path: str | Path, *, brand: str, year_label: str, persona: str, tagline: str,
           stats: list[tuple[str, str]], bars: list[tuple[str, int]], bars_title: str, footer: str,
           accent=(255, 107, 87), top=(24, 18, 43), bottom=(10, 10, 18)) -> Path:
    img = _gradient(top, bottom)
    d = ImageDraw.Draw(img)
    ink, dim = (245, 243, 255), (160, 156, 190)

    # glow behind the title
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-260, -320, 640, 360), fill=accent + (70,))
    gd.ellipse((820, 380, 1500, 900), fill=(120, 90, 255, 40))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img = Image.alpha_composite(img.convert("RGBA"), glow)
    tiles = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(tiles)

    for i in range(min(len(stats), 4)):
        x = 64 + i * (248 + 22)
        td.rounded_rectangle((x, 300, x + 248, 432), radius=18, fill=(255, 255, 255, 14),
                             outline=(255, 255, 255, 40), width=2)
    img = Image.alpha_composite(img, tiles).convert("RGB")
    d = ImageDraw.Draw(img)

    d.text((64, 52), brand, font=_font("Inter-Bold.otf", 26), fill=accent)
    bw = d.textlength(brand, font=_font("Inter-Bold.otf", 26))
    d.text((64 + bw + 14, 52), year_label, font=_font("Inter-Regular.otf", 26), fill=dim)

    title_f = _fit(d, persona, "InterDisplay-Black.otf", 76, 1060)
    d.text((62, 96), persona, font=title_f, fill=ink)
    d.text((66, 96 + title_f.size + 14), tagline, font=_fit(d, tagline, "Inter-Regular.otf", 28, 1060), fill=dim)

    # stat tiles
    y0, tile_w, gap = 300, 248, 22
    for i, (label, value) in enumerate(stats[:4]):
        x = 64 + i * (tile_w + gap)
        vf = _fit(d, value, "InterDisplay-Black.otf", 52, tile_w - 36)
        d.text((x + 20, y0 + 18), value, font=vf, fill=ink)
        d.text((x + 20, y0 + 90), label.upper(), font=_fit(d, label.upper(), "Inter-Bold.otf", 17, tile_w - 36),
               fill=dim)

    # bar chart
    by = 470
    d.text((64, by), bars_title.upper(), font=_font("Inter-Bold.otf", 17), fill=dim)
    if bars:
        mx = max(v for _, v in bars) or 1
        name_f, val_f = _font("Inter-Bold.otf", 22), _font("Inter-Regular.otf", 20)
        for i, (name, v) in enumerate(bars[:5]):
            y = by + 36 + i * 30
            d.text((64, y), name, font=name_f, fill=ink)
            x0, x1 = 230, 230 + int(560 * v / mx)
            d.rounded_rectangle((x0, y + 6, max(x1, x0 + 8), y + 22), radius=8, fill=accent)
            d.text((max(x1, x0 + 8) + 12, y + 1), f"{v:,}", font=val_f, fill=dim)

    ff = _font("Inter-Bold.otf", 22)
    fw = d.textlength(footer, font=ff)
    d.rounded_rectangle((W - 64 - fw - 36, H - 82, W - 64, H - 40), radius=21, fill=accent)
    d.text((W - 64 - fw - 18, H - 74), footer, font=ff, fill=(20, 16, 34))

    path = Path(path)
    img.save(path, optimize=True)
    return path
