import io
from fontTools.ttLib import TTFont
from PIL import Image, ImageFont, ImageDraw

from app.config import MAX_RENDER_IMAGE_HEIGHT

HORZ_MARGIN = 20
LINE_SPACING = 20 # 10 top, 10 bottom
DEFAULT_LINE_WIDTH = HORZ_MARGIN * 2

class RenderedImageTooLargeError(ValueError):
    pass

def create_lines(
        text: str,
        max_width: int,
        font: ImageFont.FreeTypeFont
) -> list[str]:
    lines = []
    total_text_width = font.getlength(text)

    # One-line only
    if total_text_width + DEFAULT_LINE_WIDTH < max_width:
        lines.append(text)
        return lines

    # Multiple lines and long words
    start = 0
    latest_word = ""
    latest_word_width = 0
    line = ""
    dash_width = font.getlength('-')
    for i, ch in enumerate(text):
        work_width = (font.getlength(line) + font.getlength(latest_word) +
                      dash_width + font.getlength(ch) + DEFAULT_LINE_WIDTH)
        if work_width > max_width:
            lines.append(line + latest_word + '-')
            line = ""
            start = i
            latest_word = ch
        else:
            latest_word += ch

        if i == len(text) - 1:
            lines.append(line + latest_word)
        elif ch == ' ' or ch == '\n':
                latest_word = text[start:i] + ch # Add space in output to avoid invalid access at the end of string

                line_width = font.getlength(line) + HORZ_MARGIN * 2
                latest_word_width = font.getlength(latest_word)

                if line_width + latest_word_width > max_width:
                    lines.append(line)
                    line = ""

                if ch == '\n':
                    line += latest_word
                    lines.append(line)
                    line = ""
                else:
                    line += latest_word
                start = i + 1
                latest_word = ""

    return lines


def render_text(
        font_bytes: bytes,
        image_width: int,
        font_size: int,
        text: str,
        color: str,
):

    glyph_font = ImageFont.truetype(io.BytesIO(font_bytes), font_size)

    text_lines = create_lines(text, image_width, glyph_font)
    image_height = int((LINE_SPACING + font_size) * len(text_lines))
    if image_height > MAX_RENDER_IMAGE_HEIGHT:
        raise RenderedImageTooLargeError(
            f"Rendered text would be {image_height}px tall, which exceeds the"
            f"maximum height of {MAX_RENDER_IMAGE_HEIGHT}."
        )

    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)


    for i, line in enumerate(text_lines):
        start_xy = (HORZ_MARGIN, (LINE_SPACING / 2) + (font_size * i))
        draw.text(start_xy, line, font=glyph_font, fill=color, anchor="la")

    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


