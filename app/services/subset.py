import io

from fontTools import subset
from fontTools.ttLib import TTFont

def to_unicode(char_list: list[str]) -> str:
    return ",".join([f"U+{ord(ch):04X}" for ch in dict.fromkeys(char_list)])

def extract_subset(text: str, font: TTFont) -> bytes:
    subsetter = subset.Subsetter(subset.Options())
    subsetter.populate(text=text)
    subsetter.subset(font)
    buffer = io.BytesIO()
    font.save(buffer)
    return buffer.getvalue()