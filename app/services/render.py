import io
from PIL import Image, ImageFont, ImageDraw

from app.config import MAX_RENDER_IMAGE_HEIGHT


HORIZONTAL_MARGIN = 20
LINE_MARGINS = HORIZONTAL_MARGIN * 2

SPACE = ' '


class RenderedImageTooLargeError(ValueError):
    pass


def split_long_word(
        text: str,
        max_width: float,
        font: ImageFont.FreeTypeFont
) -> list[str]:
    """
    Breaks a long word whose rendered width exceeds the maximum into pieces
    that can fit.
    """
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


def wrap_paragraph(
        para: str,
        max_width: float,
        font: ImageFont.FreeTypeFont,
) -> list[str]:
    """
    Wraps a paragraph into lines that fit within the max width.
    """
    lines = []
    words = para.split()
    line = ""

    for word in words:
        temp_line = line + SPACE + word if line else line + word
        if font.getlength(temp_line) <= max_width:
            line = temp_line
        elif font.getlength(word) > max_width:
            line += word if not line else SPACE + word
            pieces = split_long_word(line, max_width, font)
            for piece in pieces[:-1]:
                lines.append(piece.strip())
            line = pieces[-1]
        else:
            lines.append(line.strip())
            line = word
    if line:
        lines.append(line.strip())

    return lines


def create_lines(
        text: str,
        max_width: float,
        font: ImageFont.FreeTypeFont
) -> list[str]:
    """
    First, splits the text into paragraphs.
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
            lines.extend(wrap_paragraph(para, max_width, font))

    return lines


def render_text(
        font_bytes: bytes,
        image_width: int,
        font_size: int,
        text: str,
        color: str,
) -> bytes:
    """
    Renders the PNG image out of the text and settings requested.
    """
    glyph_font = ImageFont.truetype(io.BytesIO(font_bytes), font_size)

    text_lines = create_lines(text, image_width, glyph_font)
    line_spacing = int(font_size * 0.5)
    image_height = (((line_spacing + font_size) * len(text_lines)) +
                    line_spacing * 2)
    if image_height > MAX_RENDER_IMAGE_HEIGHT:
        raise RenderedImageTooLargeError(
            f"Rendered text would be {image_height}px tall, which exceeds the "
            f"maximum height of {MAX_RENDER_IMAGE_HEIGHT}px."
        )

    image = Image.new(
        mode="RGB",
        size=(image_width, image_height),
        color="white"
    )
    draw = ImageDraw.Draw(image)

    start_y = line_spacing
    for line in text_lines:
        start_xy = (HORIZONTAL_MARGIN, start_y)
        draw.text(start_xy, line, font=glyph_font, fill=color, anchor="la")
        start_y += font_size + line_spacing

    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


