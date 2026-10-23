import io
from PIL import Image, ImageFont, ImageDraw

from app.config import MAX_RENDER_IMAGE_HEIGHT


HORZ_MARGIN = 20
LINE_MARGINS = HORZ_MARGIN * 2

SPACE = ' '
LINE_SEPARATORS = [
    "\n",       # ⟨U+000A⟩ line feed (LF)
    "\v",       # ⟨U+000B⟩ line tabulation (VT)
    "\f",       # ⟨U+000C⟩ form feed (FF)
    "\r",       # ⟨U+000D⟩ carriage return (CR) not followed by LF
    "\x85",     # ⟨U+0085⟩ next line (NEL)
    "\u2028",   # ⟨U+2028⟩ line separator (LS)
    "\u2029"    # ⟨U+2029⟩ paragraph separator (PS)
]


class RenderedImageTooLargeError(ValueError):
    pass


def split_long_word(
        text: str,
        max_width: int,
        font: ImageFont.FreeTypeFont
) -> list[str]:
    breaks = []
    line = ""
    for ch in text:
        if font.getlength(line + ch) <= max_width:
            line += ch
        else:
            if line:
                breaks.append(line)
            line = ch
    if line:
        breaks.append(line)
    return breaks


def create_lines(
        text: str,
        max_width: int,
        font: ImageFont.FreeTypeFont
) -> list[str]:
    """
    First, split into paragraphs.
    If a paragraph fits into a line, append to lines.
    Otherwise, split into words, then append into lines according to the max
    width. Overlong words are broken down into separate lines as well.
    """
    lines = []
    max_width -= LINE_MARGINS

    paragraphs = text.splitlines()

    for para in paragraphs:
        if font.getlength(para) <= max_width:
            lines.append(para)
        else:
            words = para.split()
            line = ""
            temp_line = ""
            for word in words:
                temp_line = line + SPACE + word if line else line + word
                if font.getlength(temp_line) <= max_width:
                    line = temp_line
                elif font.getlength(word) > max_width:
                    line += word if not line else SPACE + word
                    bad_breaks = split_long_word(line, max_width, font)
                    for bad_break in bad_breaks[:-1]:
                        lines.append(bad_break.rstrip())
                    line = bad_breaks[-1]
                else:
                    lines.append(line.rstrip())
                    line = word
            if line:
                lines.append(line.rstrip())

    return lines


def render_text(
        font_bytes: bytes,
        image_width: int,
        font_size: int,
        text: str,
        color: str,
) -> bytes:
    glyph_font = ImageFont.truetype(io.BytesIO(font_bytes), font_size)

    text_lines = create_lines(text, image_width, glyph_font)
    line_spacing = int(font_size * 0.5)
    image_height = ((line_spacing + font_size) * len(text_lines)) + line_spacing * 2
    if image_height > MAX_RENDER_IMAGE_HEIGHT:
        raise RenderedImageTooLargeError(
            f"Rendered text would be {image_height}px tall, which exceeds the "
            f"maximum height of {MAX_RENDER_IMAGE_HEIGHT}px."
        )

    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)

    start_y = line_spacing
    for line in text_lines:
        start_xy = (HORZ_MARGIN, start_y)
        draw.text(start_xy, line, font=glyph_font, fill=color, anchor="la")
        start_y += font_size + line_spacing

    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


