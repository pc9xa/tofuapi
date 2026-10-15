import io
from pathlib import Path

from fontTools.ttLib import TTFont

FIXTURES = Path(__file__).parent / "fixtures"

# filename -> (family, style), as stored in each font's name table
EXPECTED_NAMES = {
    "Roboto-Italic.ttf": ("Roboto", "Italic"),
    "Roboto-Bold.ttf": ("Roboto", "Bold"),
    "SourceCodePro-Regular.ttf": ("Source Code Pro", "Regular"),
    "Roboto_Condensed-Regular.ttf": ("Roboto Condensed", "Regular"),
    "OpenSans-Regular.ttf": ("Open Sans", "Regular"),
    "cour.ttf": ("Courier New", "Regular"),
}


def corrupt_table(font_bytes: bytes, tag: str) -> bytes:
    """Return a copy of the font with one table's bytes overwritten with 0xFF."""
    entry = TTFont(io.BytesIO(font_bytes)).reader.tables[tag]
    damaged = bytearray(font_bytes)
    damaged[entry.offset : entry.offset + entry.length] = b"\xff" * entry.length
    return bytes(damaged)


def drop_table(font_bytes: bytes, tag: str) -> bytes:
    """Return a copy of the font whose table directory no longer lists `tag`.

    Renames the tag in the directory (the first occurrence in the file),
    so the font opens normally but the table appears to be missing.
    """
    raw_tag = tag.encode().ljust(4, b" ")
    i = font_bytes.index(raw_tag)
    return font_bytes[:i] + b"zzzz" + font_bytes[i + 4 :]