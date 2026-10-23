import io
import math

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageFont

from app.config import MAX_RENDER_IMAGE_WIDTH, MAX_UPLOAD_BYTES
from app.main import app
from app.services.render import (
    HORZ_MARGIN,
    LINE_MARGINS,
    RenderedImageTooLargeError,
    create_lines,
    render_text,
    split_long_word,
)
from tests.helpers import (
    EXPECTED_NAMES,
    FIXTURES,
    LATIN_FONT,
    PNG_SIGNATURE,
    corrupt_table,
    drop_table,
)

client = TestClient(app)

# Variant that answers with a 500 response instead of re-raising server errors,
# so a test can assert on the status code of a crash.
lenient_client = TestClient(app, raise_server_exceptions=False)

PROPORTIONAL = "OpenSans-Regular.ttf"
MONOSPACED = "SourceCodePro-Regular.ttf"
FONT_FILES = [PROPORTIONAL, MONOSPACED]
FONT_IDS = ["proportional", "monospaced"]

SENTENCE = "Trying again and again and again and again and again, and yet again."
SHORT_WORDS = "Short words only here to wrap around a few times in this paragraph"
LONG_WORD = "Pneumonoultramicroscopicsilicovolcanoconiosis"
WITH_LONG_WORD = f"Hello there {LONG_WORD} and more words after it"

# Characters that end a line, as str.splitlines() understands them.
LINE_BREAKS = ["\n", "\v", "\f", "\r", "\x85", "\u2028", "\u2029"]

SIZE = 30
WIDTHS = (220, 300, 400, 600)
TEXTS = [SENTENCE, SHORT_WORDS, WITH_LONG_WORD]
SHORT_TEXTS = [SENTENCE, SHORT_WORDS]  # no word is wider than a line

# Every combination of font, image width and text, with readable ids.
LAYOUT_CASES = [(f, w, t) for f in FONT_FILES for w in WIDTHS for t in TEXTS]
LAYOUT_IDS = [f"{kind}-{w}-text{n}" for kind in FONT_IDS for w in WIDTHS for n in range(len(TEXTS))]
SHORT_CASES = [(f, w, t) for f in FONT_FILES for w in WIDTHS for t in SHORT_TEXTS]
SHORT_IDS = [f"{kind}-{w}-text{n}" for kind in FONT_IDS for w in WIDTHS for n in range(len(SHORT_TEXTS))]

# Every combination of font and word-breaking width.
BREAK_CASES = [(f, w) for f in FONT_FILES for w in (60, 90, 150, 240)]
BREAK_IDS = [f"{kind}-{w}" for kind in FONT_IDS for w in (60, 90, 150, 240)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Load a fixture font as a Pillow font object at the given size.
def pil_font(filename: str, size: int = SIZE) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FIXTURES / filename), size)


# Return the widest line in pixels, ignoring trailing spaces (they draw nothing).
def widest(lines: list[str], font: ImageFont.FreeTypeFont) -> float:
    return max((font.getlength(line.rstrip()) for line in lines), default=0)


# Return the Latin fixture font as raw .ttf bytes.
def latin_bytes() -> bytes:
    return LATIN_FONT.read_bytes()


# Decode PNG bytes into a Pillow image.
def open_png(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


# Return the bounding box (left, top, right, bottom) of the dark pixels in a PNG, or None if blank.
def ink_bbox(png: bytes):
    gray = open_png(png).convert("L")
    return gray.point(lambda value: 255 if value < 128 else 0).getbbox()


# Render text with the Latin fixture font, using defaults that keep expected sizes easy to calculate.
def render_png(text: str, width: int = 400, size: int = 40, color: str = "#000000") -> bytes:
    return render_text(latin_bytes(), width, size, text, color)


# Send a font and a text to /render and return the response. Extra query parameters can be passed.
def post_render(data: bytes, text: str = "Hello world", http: TestClient = client, **params):
    return http.post(
        "/render",
        params={"text": text, **params},
        files={"file": ("font.ttf", data, "font/ttf")},
    )


# ---------------------------------------------------------------------------
# split_long_word
# ---------------------------------------------------------------------------


# Joining the pieces gives back the original word: nothing is lost or added.
@pytest.mark.parametrize("filename, width", BREAK_CASES, ids=BREAK_IDS)
def test_pieces_rejoin_to_the_original_word(filename, width):
    assert "".join(split_long_word(LONG_WORD, width, pil_font(filename))) == LONG_WORD


# Every piece is no wider than the width it was asked to fit.
@pytest.mark.parametrize("filename, width", BREAK_CASES, ids=BREAK_IDS)
def test_every_piece_fits_the_width(filename, width):
    font = pil_font(filename)
    assert all(font.getlength(piece) <= width for piece in split_long_word(LONG_WORD, width, font))


# No piece is empty.
@pytest.mark.parametrize("filename, width", BREAK_CASES, ids=BREAK_IDS)
def test_no_piece_is_empty(filename, width):
    assert all(split_long_word(LONG_WORD, width, pil_font(filename)))


# Pieces are as long as they can be: the next character would not have fit on the previous piece.
@pytest.mark.parametrize("filename, width", BREAK_CASES, ids=BREAK_IDS)
def test_pieces_are_as_long_as_they_can_be(filename, width):
    font = pil_font(filename)
    pieces = split_long_word(LONG_WORD, width, font)
    for piece, following in zip(pieces, pieces[1:]):
        assert font.getlength(piece + following[0]) >= width


# A word that fits comfortably comes back whole.
def test_word_that_fits_is_not_broken():
    assert split_long_word("Hello", 2000, pil_font(PROPORTIONAL)) == ["Hello"]


# split_long_word receives the width available for text (create_lines has already
# subtracted the margins), so no margins are added here. A word exactly that wide still fits.
@pytest.mark.parametrize("filename", FONT_FILES, ids=FONT_IDS)
def test_word_that_fits_the_available_width_exactly_is_not_broken(filename):
    font = pil_font(filename)
    assert split_long_word("Hello", font.getlength("Hello"), font) == ["Hello"]


# A width narrower than any character still terminates, with one character per piece.
def test_width_narrower_than_one_character_gives_single_characters():
    assert split_long_word("abc", 1, pil_font(PROPORTIONAL)) == ["a", "b", "c"]


# An empty word has no pieces.
def test_empty_word_has_no_pieces():
    assert split_long_word("", 200, pil_font(PROPORTIONAL)) == []


# ---------------------------------------------------------------------------
# create_lines
# ---------------------------------------------------------------------------


# No line is wider than the width left after the margins (the right-margin check).
@pytest.mark.parametrize("filename, width, text", LAYOUT_CASES, ids=LAYOUT_IDS)
def test_no_line_is_wider_than_the_available_width(filename, width, text):
    font = pil_font(filename)
    assert widest(create_lines(text, width, font), font) <= width - LINE_MARGINS


# No characters are lost or reordered when text is wrapped (spaces aside).
@pytest.mark.parametrize("filename, width, text", LAYOUT_CASES, ids=LAYOUT_IDS)
def test_no_characters_are_lost(filename, width, text):
    lines = create_lines(text, width, pil_font(filename))
    assert "".join(lines).replace(" ", "") == text.replace(" ", "")


# Lines carry no trailing spaces.
@pytest.mark.parametrize("filename, width, text", LAYOUT_CASES, ids=LAYOUT_IDS)
def test_lines_have_no_trailing_spaces(filename, width, text):
    lines = create_lines(text, width, pil_font(filename))
    assert all(line == line.rstrip() for line in lines)


# When no word is wider than a line, every word stays whole and in order.
@pytest.mark.parametrize("filename, width, text", SHORT_CASES, ids=SHORT_IDS)
def test_words_are_not_split_when_they_fit(filename, width, text):
    lines = create_lines(text, width, pil_font(filename))
    assert " ".join(lines).split() == text.split()


# Text that fits is a single line, unchanged.
def test_short_text_is_one_line():
    assert create_lines("Hello world", 800, pil_font(PROPORTIONAL)) == ["Hello world"]


# Wrapping uses more lines when the text is longer than one line.
def test_long_text_wraps_onto_several_lines():
    assert len(create_lines(SENTENCE, 300, pil_font(PROPORTIONAL))) > 1


# An explicit line break starts a new line even when everything would fit on one.
def test_explicit_line_break():
    assert create_lines("Hello\nworld", 800, pil_font(PROPORTIONAL)) == ["Hello", "world"]


# Every line-ending character starts a new line.
@pytest.mark.parametrize("separator", LINE_BREAKS, ids=[repr(s) for s in LINE_BREAKS])
def test_every_separator_starts_a_new_line(separator):
    assert create_lines(f"Hello{separator}world", 800, pil_font(PROPORTIONAL)) == ["Hello", "world"]


# Windows line endings (CR LF) give clean lines, without a stray carriage return.
def test_crlf_gives_clean_lines():
    assert create_lines("Hello\r\nworld", 800, pil_font(PROPORTIONAL)) == ["Hello", "world"]


# A blank line between paragraphs is kept as an empty line.
def test_blank_paragraph_is_kept():
    assert create_lines("a\n\nb", 800, pil_font(PROPORTIONAL)) == ["a", "", "b"]


# A newline at the very end does not add an empty line.
def test_trailing_newline_adds_no_line():
    assert create_lines("a\n", 800, pil_font(PROPORTIONAL)) == ["a"]


# Empty text gives no lines.
def test_empty_text_gives_no_lines():
    assert create_lines("", 800, pil_font(PROPORTIONAL)) == []


# A word wider than the line is broken into several lines that rejoin to the original word.
@pytest.mark.parametrize("filename", FONT_FILES, ids=FONT_IDS)
def test_long_word_alone_breaks_into_fitting_pieces(filename):
    font = pil_font(filename)
    lines = create_lines(LONG_WORD, 400, font)
    assert len(lines) > 1
    assert "".join(lines) == LONG_WORD
    assert widest(lines, font) <= 400 - LINE_MARGINS


# Margin-aware boundary: a word whose width plus both margins equals the image width fits on
# one line, unbroken. (Pillow measures in 1/64 pixel steps, so the arithmetic is exact.)
@pytest.mark.parametrize("filename", FONT_FILES, ids=FONT_IDS)
def test_word_that_fits_with_margins_exactly_is_not_broken(filename):
    font = pil_font(filename)
    assert create_lines("Hello", font.getlength("Hello") + LINE_MARGINS, font) == ["Hello"]


# One pixel less room than that exact fit forces a break, and every piece still fits.
@pytest.mark.parametrize("filename", FONT_FILES, ids=FONT_IDS)
def test_word_one_pixel_too_wide_for_the_margins_is_broken(filename):
    font = pil_font(filename)
    width = font.getlength("Hello") + LINE_MARGINS - 1
    lines = create_lines("Hello", width, font)
    assert len(lines) > 1
    assert "".join(lines) == "Hello"
    assert widest(lines, font) <= width - LINE_MARGINS


# A whole paragraph whose width plus margins equals the image width stays on one line.
@pytest.mark.parametrize("filename", FONT_FILES, ids=FONT_IDS)
def test_paragraph_that_fits_with_margins_exactly_is_one_line(filename):
    font = pil_font(filename)
    assert create_lines("Hello world", font.getlength("Hello world") + LINE_MARGINS, font) == ["Hello world"]


# Words that come before a too-long word are not cut up.
def test_words_before_a_long_word_stay_intact():
    lines = create_lines(WITH_LONG_WORD, 400, pil_font(PROPORTIONAL))
    assert lines[0].startswith("Hello there")


# A narrower image never needs fewer lines than a wider one.
def test_narrower_width_never_gives_fewer_lines():
    font = pil_font(PROPORTIONAL)
    counts = [len(create_lines(SENTENCE, width, font)) for width in (800, 600, 400, 300, 220)]
    assert counts == sorted(counts)


# ---------------------------------------------------------------------------
# render_text: the image
# ---------------------------------------------------------------------------


# The result is a real RGB PNG.
def test_returns_rgb_png():
    png = render_png("Hello")
    assert png.startswith(PNG_SIGNATURE)
    image = open_png(png)
    assert image.format == "PNG"
    assert image.mode == "RGB"


# The image is exactly as wide as requested.
@pytest.mark.parametrize("width", [200, 400, 800])
def test_image_width_matches_the_request(width):
    assert open_png(render_png("Hello", width=width)).width == width


# One line at size 40: line spacing is 20, so height = (20 + 40) x 1 + 2 x 20 = 100.
def test_height_for_one_line():
    assert open_png(render_png("Hi", width=400, size=40)).size == (400, 100)


# An image just wide enough for the word plus both margins keeps the word on one line (height 100),
# while an image two pixels narrower than that has to break it (taller image).
def test_image_width_just_fitting_the_word_with_margins():
    font = ImageFont.truetype(io.BytesIO(latin_bytes()), 40)
    just_enough = math.ceil(font.getlength("Hello")) + LINE_MARGINS
    assert open_png(render_text(latin_bytes(), just_enough, 40, "Hello", "#000000")).height == 100
    assert open_png(render_text(latin_bytes(), just_enough - 2, 40, "Hello", "#000000")).height > 100


# Two lines at size 40: height = (20 + 40) x 2 + 2 x 20 = 160.
def test_height_for_two_lines():
    assert open_png(render_png("a\nb", width=400, size=40)).size == (400, 160)


# Spacing scales with the font size: at size 20 the line spacing is 10, so height = 30 + 20 = 50.
def test_height_scales_with_font_size():
    assert open_png(render_png("Hi", width=400, size=20)).size == (400, 50)


# Each extra line adds exactly one line pitch (font size + line spacing = 60 at size 40).
def test_each_extra_line_adds_one_line_pitch():
    one = open_png(render_png("a", size=40)).height
    three = open_png(render_png("a\nb\nc", size=40)).height
    assert three - one == 2 * 60


# Any line-ending character gives the same image height as a plain newline.
@pytest.mark.parametrize("separator", LINE_BREAKS, ids=[repr(s) for s in LINE_BREAKS])
def test_every_separator_gives_the_height_of_a_newline(separator):
    expected = open_png(render_png("a\nb")).height
    assert open_png(render_png(f"a{separator}b")).height == expected


# The drawn text stays inside the margins on all four sides, including after wrapping and breaking a long word.
@pytest.mark.parametrize("width", [220, 400, 800])
@pytest.mark.parametrize("size", [16, 40])
def test_ink_stays_inside_the_margins(width, size):
    png = render_png(f"{SENTENCE} {LONG_WORD}", width=width, size=size)
    image = open_png(png)
    left, top, right, bottom = ink_bbox(png)
    line_spacing = int(size * 0.5)
    assert left >= HORZ_MARGIN // 2
    assert right <= image.width - HORZ_MARGIN // 2
    assert top >= line_spacing
    assert bottom <= image.height - line_spacing


# Both kinds of font render and keep inside the margins.
@pytest.mark.parametrize("filename", FONT_FILES, ids=FONT_IDS)
def test_both_font_kinds_render_inside_the_margins(filename):
    png = render_text((FIXTURES / filename).read_bytes(), 300, 30, SENTENCE, "#000000")
    left, _top, right, _bottom = ink_bbox(png)
    assert left >= HORZ_MARGIN // 2
    assert right <= 300 - HORZ_MARGIN // 2


# The requested color is used for the text.
def test_text_color_is_applied():
    image = open_png(render_png("HHH", size=60, color="#ff0000")).convert("RGB")
    assert any(r > 200 and g < 80 and b < 80 for r, g, b in image.getdata())


# The background is white.
def test_background_is_white():
    assert open_png(render_png("Hello")).getpixel((0, 0)) == (255, 255, 255)


# The same inputs always give identical bytes.
def test_output_is_deterministic():
    assert render_png(SENTENCE) == render_png(SENTENCE)


# ---------------------------------------------------------------------------
# render_text: limits and errors
# ---------------------------------------------------------------------------


# An image exactly as tall as the maximum is allowed (the limit is inclusive).
def test_height_exactly_at_the_limit_is_allowed(monkeypatch):
    monkeypatch.setattr("app.services.render.MAX_RENDER_IMAGE_HEIGHT", 100)
    assert open_png(render_png("Hi", size=40)).height == 100


# One pixel over the maximum raises an error whose message names the limit.
def test_height_over_the_limit_raises(monkeypatch):
    monkeypatch.setattr("app.services.render.MAX_RENDER_IMAGE_HEIGHT", 99)
    with pytest.raises(RenderedImageTooLargeError, match="99"):
        render_png("Hi", size=40)


# The too-large error is a ValueError, so a generic ValueError handler also catches it.
def test_too_large_error_is_a_value_error():
    assert issubclass(RenderedImageTooLargeError, ValueError)


# Bytes that are not a font raise OSError (the router needs to handle this).
def test_unreadable_font_bytes_raise_os_error():
    with pytest.raises(OSError):
        render_text(b"not a font", 400, 40, "Hi", "#000000")


# A color Pillow cannot understand raises ValueError.
def test_invalid_color_raises_value_error():
    with pytest.raises(ValueError):
        render_png("Hi", color="notacolor")


# ---------------------------------------------------------------------------
# POST /render: success cases
# ---------------------------------------------------------------------------


# A valid request returns a PNG.
def test_endpoint_returns_png():
    response = post_render(latin_bytes())
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(PNG_SIGNATURE)


# Without image_width, the image is 800 pixels wide.
def test_endpoint_default_width_is_800():
    assert open_png(post_render(latin_bytes()).content).width == 800


# The requested image_width is used.
def test_endpoint_uses_requested_width():
    assert open_png(post_render(latin_bytes(), image_width=400).content).width == 400


# Text with a line break gives a taller image than the same text on one line.
def test_endpoint_multiline_text_is_taller():
    one = open_png(post_render(latin_bytes(), "Hello world").content).height
    two = open_png(post_render(latin_bytes(), "Hello\nworld").content).height
    assert two > one


# Text too long for one line wraps and makes a taller image.
def test_endpoint_long_text_wraps_into_a_taller_image():
    short = open_png(post_render(latin_bytes(), "Hello", image_width=300).content).height
    long = open_png(post_render(latin_bytes(), SENTENCE, image_width=300).content).height
    assert long > short


# Every fixture font works through the endpoint.
@pytest.mark.parametrize("filename", EXPECTED_NAMES)
def test_endpoint_works_for_every_fixture_font(filename):
    response = post_render((FIXTURES / filename).read_bytes(), "Hello")
    assert response.status_code == 200
    assert response.content.startswith(PNG_SIGNATURE)


# ---------------------------------------------------------------------------
# POST /render: input validation
# ---------------------------------------------------------------------------


# The text parameter is required.
def test_endpoint_missing_text_returns_422():
    response = client.post("/render", files={"file": ("font.ttf", latin_bytes(), "font/ttf")})
    assert response.status_code == 422


# Empty text and text over 1000 characters are rejected.
@pytest.mark.parametrize("text", ["", "a" * 1001], ids=["empty", "too-long"])
def test_endpoint_text_length_limits(text):
    assert post_render(latin_bytes(), text).status_code == 422


# image_width must be between 200 and the configured maximum.
@pytest.mark.parametrize(
    "width, expected",
    [(199, 422), (200, 200), (MAX_RENDER_IMAGE_WIDTH, 200), (MAX_RENDER_IMAGE_WIDTH + 1, 422)],
    ids=["below-min", "min", "max", "above-max"],
)
def test_endpoint_image_width_bounds(width, expected):
    assert post_render(latin_bytes(), "Hi", image_width=width).status_code == expected


# font_size must be between 8 and 100.
@pytest.mark.parametrize(
    "size, expected",
    [(7, 422), (8, 200), (100, 200), (101, 422)],
    ids=["below-min", "min", "max", "above-max"],
)
def test_endpoint_font_size_bounds(size, expected):
    assert post_render(latin_bytes(), "Hi", font_size=size).status_code == expected


# font_color must be a # followed by exactly six hex digits.
@pytest.mark.parametrize(
    "color, expected",
    [("#000000", 200), ("#FFFFFF", 200), ("#1a2B3c", 200), ("#fff", 422), ("000000", 422),
     ("#GGGGGG", 422), ("red", 422), ("", 422), ("#ffffff\n", 422)],
    ids=["black", "white", "mixed-case", "short", "no-hash", "not-hex", "name", "empty", "trailing-newline"],
)
def test_endpoint_font_color_format(color, expected):
    assert post_render(latin_bytes(), "Hi", font_color=color).status_code == expected


# The file is required.
def test_endpoint_missing_file_returns_422():
    assert client.post("/render", params={"text": "Hello"}).status_code == 422


# Data that is not a font is rejected with a 400.
@pytest.mark.parametrize(
    "data",
    [b"", b"not a font", b"\x00\x01\x00\x00" + b"junk" * 20],
    ids=["empty", "plain-text", "truetype-header-then-junk"],
)
def test_endpoint_non_fonts_return_400(data):
    assert post_render(data).status_code == 400


# Uploads over the size limit are rejected with a 413.
def test_endpoint_oversized_upload_returns_413():
    too_big = b"\x00\x01\x00\x00" + b"0" * MAX_UPLOAD_BYTES
    assert post_render(too_big).status_code == 413


# ---------------------------------------------------------------------------
# POST /render: unsupported characters
# ---------------------------------------------------------------------------


# Text with no supported characters is rejected with a 422 and a JSON error, not an image.
@pytest.mark.parametrize("text", ["日", "日本", "日日日", "日本語"])
def test_endpoint_text_with_no_supported_characters_returns_422(text):
    response = post_render(latin_bytes(), text)
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"]


# One supported character is enough: the request succeeds.
def test_endpoint_one_supported_character_is_enough():
    assert post_render(latin_bytes(), "日本a").status_code == 200


# ---------------------------------------------------------------------------
# POST /render: size limit and damaged fonts
# ---------------------------------------------------------------------------


# Text that would make the image too tall returns a 422 whose message names the maximum.
def test_endpoint_too_tall_returns_422(monkeypatch):
    monkeypatch.setattr("app.services.render.MAX_RENDER_IMAGE_HEIGHT", 200)
    response = post_render(latin_bytes(), "a\nb\nc", font_size=100)
    assert response.status_code == 422
    assert "200" in response.json()["detail"]


# Whatever table is damaged or missing, the endpoint must never answer 500.
@pytest.mark.parametrize(
    "damage, tag",
    [("corrupt", "cmap"), ("corrupt", "glyf"), ("corrupt", "head"), ("drop", "cmap"),
     ("drop", "head"), ("drop", "glyf")],
)
def test_endpoint_table_damage_never_returns_500(damage, tag):
    data = {"corrupt": corrupt_table, "drop": drop_table}[damage](latin_bytes(), tag)
    assert post_render(data, http=lenient_client).status_code in (200, 400, 422)