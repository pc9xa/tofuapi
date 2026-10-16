import pytest, io, inspect
from PIL import Image

from app.services.preview import (
    MAX_PREVIEW_GLYPHS,
    PREVIEW_COLS,
    STANDARD_SET,
    pick_characters,
    render_preview
)
from tests.helpers import GREEK_CAPITALS, PNG_SIGNATURE

# Minimal stand-in for TTFont. pick_characters only calls getBestCmap(), so a
# fake lets each test control exactly which characters the "font" contains.
class FakeFont:
    # Store the code points this fake font claims to support (None = no cmap at all).
    def __init__(self, codepoints):
        self.cmap = None if codepoints is None else {cp: f"glyph{cp}" for cp in codepoints}

    # Mimic TTFont.getBestCmap(): return the mapping, or None for a font without one.
    def getBestCmap(self):
        return self.cmap


# Convert a string such as "Ab5" into the list of its code points.
def cps(text: str) -> list[int]:
    return [ord(ch) for ch in text]


# ---------------------------------------------------------------------------
# Standard sample path (fonts that have Latin letters or digits)
# ---------------------------------------------------------------------------


# A font with the whole sample returns all of it, in sample order.
def test_full_latin_font_returns_whole_standard_set():
    font = FakeFont(cps(STANDARD_SET) + cps(" .,;"))
    assert pick_characters(font) == cps(STANDARD_SET)


# A partial font returns only what it supports, ordered like STANDARD_SET
# (capitals, then lowercase, then digits), not by code point.
def test_partial_latin_font_keeps_sample_order():
    font = FakeFont(cps("5bA"))
    assert pick_characters(font) == cps("Ab5")


# One Latin character is enough to stay on this path, so other scripts are ignored.
def test_standard_path_ignores_non_sample_characters():
    font = FakeFont(cps("A") + [0x0391, 0x2190])
    assert pick_characters(font) == cps("A")


# The limit parameter does not apply here: this documents the current behavior.
def test_limit_only_applies_to_fallback():
    font = FakeFont(cps(STANDARD_SET))
    assert len(pick_characters(font, limit=5)) == len(STANDARD_SET)


# ---------------------------------------------------------------------------
# Fallback path (fonts with no Latin letters or digits)
# ---------------------------------------------------------------------------


# Without Latin, the result is every usable code point in ascending order.
def test_fallback_returns_codepoints_in_ascending_order():
    font = FakeFont([0x2190, 0x05D0, 0x0391])  # arrow, Hebrew alef, Greek Alpha
    assert pick_characters(font) == [0x0391, 0x05D0, 0x2190]


# Characters that would draw as blanks or boxes must never be chosen.
@pytest.mark.parametrize(
    "codepoint, reason",
    [
        (0x0020, "space"),
        (0x00A0, "no-break space"),
        (0x0000, "control character (NUL)"),
        (0x007F, "control character (DEL)"),
        (0xE000, "private use"),
        (0xFFFF, "unassigned (noncharacter)"),
        (0x200B, "format character (zero-width space)"),
    ],
)
def test_fallback_excludes_undrawable_characters(codepoint, reason):
    font = FakeFont([codepoint, 0x0391])
    assert pick_characters(font) == [0x0391], reason


# An explicit limit caps the fallback result and keeps the lowest code points.
def test_fallback_respects_explicit_limit():
    cyrillic = list(range(0x0410, 0x0474))  # 100 characters, no Latin
    assert pick_characters(FakeFont(cyrillic), limit=10) == cyrillic[:10]


# With no limit given, the fallback stops at the number of glyphs the grid holds.
def test_fallback_defaults_to_grid_size():
    cyrillic = list(range(0x0410, 0x0474))
    assert len(pick_characters(FakeFont(cyrillic))) == MAX_PREVIEW_GLYPHS


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


# A font with an empty cmap, or none at all, gives an empty list (the router maps this to a 422).
@pytest.mark.parametrize("codepoints", [[], None], ids=["empty-cmap", "no-cmap"])
def test_font_without_usable_cmap_returns_empty_list(codepoints):
    assert pick_characters(FakeFont(codepoints)) == []


# The two grid constants depend on each other: a partial last row means the numbers drifted.
def test_grid_constants_fill_rows_exactly():
    assert MAX_PREVIEW_GLYPHS % PREVIEW_COLS == 0


# ---------------------------------------------------------------------------
# Symbols-only font
# ---------------------------------------------------------------------------


# A symbol font should take the fallback path and return only characters it can draw.
def test_symbols_font_uses_fallback(symbols_font):
    cmap = symbols_font.getBestCmap()
    avail = [ch for ch in STANDARD_SET if ord(ch) in cmap]
    assert not avail, f"font unexpectedly contains: {avail}"  # sanity check on the fixture
    result = pick_characters(symbols_font)
    assert 0 < len(result) <= MAX_PREVIEW_GLYPHS
    assert result == GREEK_CAPITALS


# ---------------------------------------------------------------------------
# render_preview
# ---------------------------------------------------------------------------


# Decode the PNG bytes returned by render_preview back into a Pillow image.
def open_png(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


# The result must be a real PNG: right signature, format, and color mode.
def test_returns_png_image(symbols_pair):
    data, font = symbols_pair
    png = render_preview(data, font)
    assert png.startswith(PNG_SIGNATURE)
    image = open_png(png)
    assert image.format == "PNG"
    assert image.mode == "RGB"


# Image size follows the grid: width = cols x cell, height = rows x cell, where
# cell = size x 2 and rows = glyph count / cols, rounded up. The Greek-only
# font has 24 glyphs.
@pytest.mark.parametrize(
    "size, cols, expected",
    [
        (48, 8, (768, 288)),
        (32, 8, (512, 192)),
        (48, 4, (384, 576)),
        (48, 5, (480, 480)),
        (48, 6, (576, 384)),
        (48, 24, (2304, 96)),
    ],
    ids=["defaults", "smaller-size", "four-columns", "partial-last-row",
         "exact-fit", "single-row"],
)
def test_image_dimensions(symbols_pair, size, cols, expected):
    data, font = symbols_pair
    image = open_png(render_preview(data, font, size=size, cols=cols))
    assert image.size == expected


# A Latin font draws the whole 62-character sample: 8 columns x 8 rows of 96px cells.
def test_latin_font_dimensions(latin_pair):
    data, font = latin_pair
    assert len(pick_characters(font)) == len(
        STANDARD_SET)  # sanity check on the fixture
    assert open_png(render_preview(data, font)).size == (768, 768)


# Glyphs must actually be drawn: the image should contain near-black pixels,
# not only the light grid lines and grey labels.
def test_image_contains_drawn_glyphs(symbols_pair):
    data, font = symbols_pair
    image = open_png(render_preview(data, font))
    assert any(max(pixel) < 50 for pixel in image.getdata())


# The same inputs must always give identical bytes, which keeps output stable and cacheable.
def test_output_is_deterministic(symbols_pair):
    data, font = symbols_pair
    assert render_preview(data, font) == render_preview(data, font)


# A font with no drawable characters is rejected before any drawing starts
# (the router maps ValueError to a 422).
@pytest.mark.parametrize("codepoints", [[], None],
                         ids=["empty-cmap", "no-cmap"])
def test_no_drawable_characters_raises_value_error(codepoints):
    with pytest.raises(ValueError, match="no drawable characters"):
        render_preview(b"", FakeFont(codepoints))


# Bytes that Pillow cannot open as a font raise OSError (the router maps this to a 422 too).
def test_unreadable_font_bytes_raise_os_error(symbols_font):
    with pytest.raises(OSError):
        render_preview(b"not a font", symbols_font)


# The default `cols` must match PREVIEW_COLS, otherwise the two grid settings drift apart.
def test_default_cols_matches_constant():
    assert inspect.signature(render_preview).parameters[
               "cols"].default == PREVIEW_COLS
