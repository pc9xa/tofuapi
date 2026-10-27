import io

from fontTools import subset as ft_subset
from fontTools.ttLib import TTFont

def format_codepoints(char_list: list[str]) -> str:
    return ",".join([f"U+{ord(ch):04X}" for ch in dict.fromkeys(char_list)])

def extract_subset(text: str, font: TTFont) -> bytes:
    subsetter = ft_subset.Subsetter(ft_subset.Options())
    subsetter.populate(text=text)
    subsetter.subset(font)
    buffer = io.BytesIO()
    font.save(buffer)
    return buffer.getvalue()