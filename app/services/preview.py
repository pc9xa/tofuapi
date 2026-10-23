import io

import unicodedata
from fontTools.ttLib import TTFont
from PIL import Image, ImageFont, ImageDraw

# Grid layout size
PREVIEW_COLS = 8
MAX_PREVIEW_GLYPHS = 64

STANDARD_SET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"



def pick_characters(font: TTFont, limit: int = MAX_PREVIEW_GLYPHS) -> list[int]:
    cmap = font.getBestCmap() or {}
    std_set = [ord(ch) for ch in STANDARD_SET if ord(ch) in cmap]
    if std_set:
        return std_set

    # In case of non-Latin fonts such as a symbol font, pick out the first
    # <limit> number of characters that are neither private, control, a space,
    # or unassigned.
    def category(ch: int) -> str:
        return unicodedata.category(chr(ch))

    other_set = [ch for ch in sorted(cmap)
                 if category(ch) not in ("Cc", "Co", "Cn", "Cf")
                 and not chr(ch).isspace()]
    return other_set[:limit]


def render_preview(
        font_bytes: bytes,
        font: TTFont,
        size: int = 48, cols: int = 8
) -> bytes:
    characters = pick_characters(font)
    if not characters:
        raise ValueError("Font has no drawable characters")

    glyph_font = ImageFont.truetype(io.BytesIO(font_bytes), size)
    label_font = ImageFont.load_default(size=11)

    cell = size * 2
    rows = -(-len(characters) // cols) # ceiling division
    image = Image.new("RGB", (cols * cell, rows * cell), "white")
    draw = ImageDraw.Draw(image)

    for i, ch in enumerate(characters):
        x, y = (i % cols) * cell, (i // cols) * cell
        draw.rectangle([x, y, x + cell - 1, y + cell - 1],
                       outline=(210, 210, 210))
        draw.text((x + cell / 2, y + cell * 0.45), chr(ch), font=glyph_font, fill="black", anchor="mm")
        draw.text((x + cell / 2, y + cell - 12), f"U+{ch:04X}",
                  font=label_font, fill=(120, 120, 120), anchor="mm")

    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()