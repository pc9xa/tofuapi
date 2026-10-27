from typing import Any
from fontTools.ttLib import TTFont

WEIGHTS = {
    100: "Thin",
    200: "ExtraLight",
    300: "Light",
    400: "Regular",
    500: "Medium",
    600: "SemiBold",
    700: "Bold",
    800: "ExtraBold",
    900: "Black",
    950: "ExtraBlack",
}

WIDTHS = {
    1: "UltraCondensed",
    2: "ExtraCondensed",
    3: "Condensed",
    4: "SemiCondensed",
    5: "Normal",
    6: "SemiExpanded",
    7: "Expanded",
    8: "ExtraExpanded",
    9: "UltraExpanded",
}


def _embedding(fs_type: int) -> str:
    if fs_type & 0x0002:
        return "restricted"
    if fs_type & 0x0004:
        return "preview_and_print"
    if fs_type & 0x0008:
        return "editable"
    return "installable"


def extract_metadata(font: TTFont) -> dict[str, Any]:
    """
    Retrieves metadata of a given font and returns the information in JSON
    format.
    """
    name_tbl: Any = font["name"] if "name" in font else None
    os2: Any = font["OS/2"] if "OS/2" in font else None
    post: Any = font["post"] if "post" in font else None
    maxp: Any = font["maxp"] if "maxp" in font else None
    cmap = font.getBestCmap() or {}

    weight = getattr(os2, "usWeightClass", None)
    width = getattr(os2, "usWidthClass", None)
    fs_selection = getattr(os2, "fsSelection", 0)
    fs_type = getattr(os2, "fsType", None)
    is_fixed_pitch = getattr(post, "isFixedPitch", None)
    num_glyphs = getattr(maxp, "numGlyphs", None)

    def name_text(name_id):
        return name_tbl.getDebugName(name_id) if name_tbl else None

    return {
        "names": {
            "family": name_tbl.getBestFamilyName() if name_tbl else None,
            "style": name_tbl.getBestSubFamilyName() if name_tbl else None,
            "full_name": name_text(4),
            "version": name_text(5),
            "copyright": name_text(0),
        },
        "style": {
            "weight": WEIGHTS.get(weight, weight),
            "width": WIDTHS.get(width, width),
            "italic": bool(fs_selection & 0x0001),
            "bold": bool(fs_selection & 0x0020),
            "monospaced": bool(is_fixed_pitch),
        },
        "license": {
            "text": name_text(13),
            "url": name_text(14),
            "embedding": _embedding(fs_type & 0x000F) if fs_type is not None else None,
            "no_subsetting": bool(fs_type & 0x0100) if fs_type is not None else None,
        },
        "coverage": {
            "num_glyphs": num_glyphs,
            "num_codepoints": len(cmap),
        },
    }