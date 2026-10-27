from fontTools.ttLib import TTFont

def unsupported_characters(text: str, font: TTFont) -> list[str]:
    cmap = font.getBestCmap() or {}
    return [ch for ch in text if ord(ch) not in cmap and not ch.isspace()]