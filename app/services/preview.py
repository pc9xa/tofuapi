import io

import unicodedata
from fontTools.ttLib import TTFont
from PIL import Image, ImageFont, ImageDraw
from app.config import MAX_PREVIEW_GLYPHS

PREVIEW_COLS = 8
GLYPH_CENTER_Y_RATIO = 0.45
LABEL_FONT_SIZE = 11            # for the "U+XXXX" caption
LABEL_BOTTOM_OFFSET = 12
LIGHT_GRAY = (210, 210, 210)
DARK_GRAY = (120, 120, 120)

STANDARD_SET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"



def pick_characters(font: TTFont, limit: int = MAX_PREVIEW_GLYPHS) -> list[int]:
    """
    Selects the set of characters to preview for the given font.
    Returns the standard set for fonts that support latin characters;
    otherwise picks out the first <limit> number of characters that are
    neither private, control, a whitespace, or unassigned.
    """
    cmap = font.getBestCmap() or {}
    std_set = [ord(ch) for ch in STANDARD_SET if ord(ch) in cmap]
    if std_set:
        return std_set

    def category(ch: int) -> str:
        return unicodedata.category(chr(ch))

    other_set = [ch for ch in sorted(cmap)
                 if category(ch) not in ("Cc", "Co", "Cn", "Cf")
                 and not chr(ch).isspace()]
    return other_set[:limit]


def render_preview(
        font_bytes: bytes,
        font: TTFont,
        size: int = 48,
        cols: int = PREVIEW_COLS
) -> bytes:
    """
    Renders a PNG image that shows a preview of what a preset of characters
    would look like using the given font.
    """
    characters = pick_characters(font)
    if not characters:
        raise ValueError("Font has no drawable characters")

    glyph_font = ImageFont.truetype(io.BytesIO(font_bytes), size)
    label_font = ImageFont.load_default(size=LABEL_FONT_SIZE)

    cell = size * 2
    rows = -(-len(characters) // cols)
    image = Image.new(
        mode="RGB",
        size=(cols * cell, rows * cell),
        color="white"
    )
    draw = ImageDraw.Draw(image)

    for i, ch in enumerate(characters):
        x, y = (i % cols) * cell, (i // cols) * cell
        draw.rectangle(
            xy=[x, y, x + cell - 1, y + cell - 1],
            outline=LIGHT_GRAY
        )
        draw.text(
            xy=(x + cell / 2, y + cell * GLYPH_CENTER_Y_RATIO),
            text=chr(ch),
            font=glyph_font,
            fill="black",
            anchor="mm"
        )
        draw.text(
            xy=(x + cell / 2, y + cell - LABEL_BOTTOM_OFFSET),
            text=f"U+{ch:04X}",
            font=label_font,
            fill=DARK_GRAY,
            anchor="mm"
        )

    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()