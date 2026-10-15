from typing import BinaryIO
from fontTools.ttLib import TTFont

class InvalidFontError(Exception):
    pass

def load_font(font_data: BinaryIO) -> TTFont:
    try:
        return TTFont(font_data)
    except Exception as err:
        raise InvalidFontError(f"Could not parse font: {err}") from err