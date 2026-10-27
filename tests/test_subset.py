import io

import pytest
from fastapi.testclient import TestClient
from fontTools.ttLib import TTFont

from app.config import MAX_UPLOAD_BYTES
from app.main import app
from app.services.metadata import extract_metadata
from app.services.subset import extract_subset, format_codepoints
from app.services.utils import unsupported_characters
from tests.helpers import (
    EXPECTED_NAMES,
    FIXTURES,
    LATIN_FONT,
    corrupt_table,
    drop_table,
)

client = TestClient(app)

# Variant that answers with a 500 response instead of re-raising server errors,
# so a test can assert on the status code of a crash.
lenient_client = TestClient(app, raise_server_exceptions=False)

DAMAGE = {"corrupt": corrupt_table, "drop": drop_table}


# Return the Latin fixture font as raw .ttf bytes, ready to upload.
def latin_bytes() -> bytes:
    return LATIN_FONT.read_bytes()


# Return the set of code points that the font in `data` (.ttf bytes) maps to glyphs.
def cmap_of(data: bytes) -> set[int]:
    return set(TTFont(io.BytesIO(data)).getBestCmap() or {})


# Return the set of code points of the characters in `text`.
def cps(text: str) -> set[int]:
    return {ord(ch) for ch in text}


# Send a font and a text to /subset and return the response.
def post_subset(data: bytes, text: str = "Hello", http: TestClient = client):
    return http.post(
        "/subset",
        params={"text": text},
        files={"file": ("font.ttf", data, "font/ttf")},
    )


# ---------------------------------------------------------------------------
# extract_subset: the service function
# ---------------------------------------------------------------------------


# The result is TrueType font bytes: the right type and the TrueType signature.
def test_returns_truetype_bytes(open_sans):
    result = extract_subset("Hello", open_sans)
    assert isinstance(result, bytes)
    assert result.startswith(b"\x00\x01\x00\x00")


# Exactly the requested characters survive in the font's character map.
def test_keeps_exactly_the_requested_characters(open_sans):
    assert cmap_of(extract_subset("Hello", open_sans)) == cps("Hello")


# Repeated characters count once, and a space is kept when it is requested.
def test_repeated_characters_and_spaces(open_sans):
    assert cmap_of(extract_subset("a a a", open_sans)) == cps("a ")


# The subset is much smaller than the original font file.
def test_subset_is_smaller_than_original(open_sans):
    original_size = LATIN_FONT.stat().st_size
    assert len(extract_subset("Hello", open_sans)) < original_size / 2


# Characters the font does not have are dropped silently; the others are kept.
def test_unsupported_characters_are_dropped(open_sans):
    assert cmap_of(extract_subset("Hi日", open_sans)) == cps("Hi")


# Text made only of unsupported characters still gives a valid font, with an empty character map.
def test_only_unsupported_characters_gives_empty_cmap(open_sans):
    result = extract_subset("日本", open_sans)
    assert isinstance(result, bytes)
    assert cmap_of(result) == set()


# The family name (nameID 1) survives subsetting.
def test_family_name_is_preserved(open_sans):
    original = open_sans["name"].getDebugName(1)
    result = TTFont(io.BytesIO(extract_subset("Hello", open_sans)))
    assert result["name"].getDebugName(1) == original


# The rest of the app must be able to read a subset: metadata extraction works on it.
def test_subset_can_be_read_by_extract_metadata(open_sans):
    data = extract_subset("Hello", open_sans)
    metadata = extract_metadata(TTFont(io.BytesIO(data)))
    assert metadata["coverage"]["num_codepoints"] == len(cps("Hello"))


# Every fixture font can be subset, and keeps exactly the requested characters.
@pytest.mark.parametrize("filename", EXPECTED_NAMES)
def test_every_fixture_font_can_be_subset(filename):
    result = extract_subset("Hello", TTFont(FIXTURES / filename))
    assert cmap_of(result) == cps("Hello")


# The input TTFont is modified in place, so a caller must not reuse it as the full font.
def test_input_font_is_modified_in_place(open_sans):
    before = len(open_sans.getBestCmap())
    extract_subset("Hello", open_sans)
    assert len(open_sans.getBestCmap()) < before


# ---------------------------------------------------------------------------
# POST /subset: the endpoint, success cases
# ---------------------------------------------------------------------------


# A valid request returns 200 with a font download.
def test_endpoint_returns_font_download():
    response = post_subset(latin_bytes())
    assert response.status_code == 200
    assert response.headers["content-type"] == "font/ttf"
    assert response.headers["content-disposition"] == 'attachment; filename="subset.ttf"'


# The downloaded bytes are a real font holding exactly the requested characters.
def test_endpoint_download_has_requested_characters():
    response = post_subset(latin_bytes(), "Hello")
    assert cmap_of(response.content) == cps("Hello")


# The download is smaller than the font that was uploaded.
def test_endpoint_download_is_smaller_than_upload():
    data = latin_bytes()
    assert len(post_subset(data).content) < len(data)


# Every fixture font works through the endpoint.
@pytest.mark.parametrize("filename", EXPECTED_NAMES)
def test_endpoint_works_for_every_fixture_font(filename):
    response = post_subset((FIXTURES / filename).read_bytes(), "Hello")
    assert response.status_code == 200
    assert cmap_of(response.content) == cps("Hello")


# Unsupported characters are dropped silently, so a mixed request still returns 200.
def test_endpoint_drops_unsupported_characters():
    response = post_subset(latin_bytes(), "Hi日")
    assert response.status_code == 200
    assert cmap_of(response.content) == cps("Hi")


# Round trip: a subset produced by /subset is accepted by /metadata.
def test_endpoint_output_is_accepted_by_metadata_endpoint():
    subset_bytes = post_subset(latin_bytes(), "Hello").content
    response = client.post(
        "/metadata", files={"file": ("subset.ttf", subset_bytes, "font/ttf")}
    )
    assert response.status_code == 200
    assert response.json()["coverage"]["num_codepoints"] == len(cps("Hello"))


# ---------------------------------------------------------------------------
# POST /subset: input validation
# ---------------------------------------------------------------------------


# The text parameter is required.
def test_endpoint_missing_text_returns_422():
    response = client.post(
        "/subset", files={"file": ("font.ttf", latin_bytes(), "font/ttf")}
    )
    assert response.status_code == 422


# Empty text is rejected (min_length=1).
def test_endpoint_empty_text_returns_422():
    assert post_subset(latin_bytes(), "").status_code == 422


# Text of exactly 64 characters is the longest accepted.
def test_endpoint_text_at_limit_is_accepted():
    assert post_subset(latin_bytes(), "a" * 64).status_code == 200


# Text of 65 characters is rejected (max_length=64).
def test_endpoint_text_over_limit_returns_422():
    assert post_subset(latin_bytes(), "a" * 65).status_code == 422


# The file is required.
def test_endpoint_missing_file_returns_422():
    assert client.post("/subset", params={"text": "Hello"}).status_code == 422


# Data that is not a font is rejected with a 400.
@pytest.mark.parametrize(
    "data",
    [b"", b"not a font", b"\x00\x01\x00\x00" + b"junk" * 20],
    ids=["empty", "plain-text", "truetype-header-then-junk"],
)
def test_endpoint_non_fonts_return_400(data):
    assert post_subset(data).status_code == 400


# Uploads over the size limit are rejected with a 413.
def test_endpoint_oversized_upload_returns_413():
    too_big = b"\x00\x01\x00\x00" + b"0" * MAX_UPLOAD_BYTES
    assert post_subset(too_big).status_code == 413


# ---------------------------------------------------------------------------
# POST /subset: damaged fonts (see ADR-0001)
# ---------------------------------------------------------------------------


# Damage that makes subsetting raise must come back as a 422, not a crash.
@pytest.mark.parametrize(
    "damage, tag",
    [("corrupt", "OS/2"), ("corrupt", "post"), ("corrupt", "cmap"),
     ("drop", "cmap"), ("drop", "head")],
)
def test_endpoint_unsubsettable_font_returns_422(damage, tag):
    data = DAMAGE[damage](latin_bytes(), tag)
    assert post_subset(data, http=lenient_client).status_code == 422


# Whatever table is damaged or missing, the endpoint must never answer 500.
@pytest.mark.parametrize(
    "damage, tag",
    [("corrupt", "name"), ("corrupt", "head"), ("corrupt", "loca"),
     ("corrupt", "hmtx"), ("corrupt", "glyf"), ("corrupt", "maxp"),
     ("corrupt", "hhea"), ("drop", "OS/2"), ("drop", "post"),
     ("drop", "name"), ("drop", "glyf"), ("drop", "maxp"),
     ("drop", "hmtx"), ("drop", "loca")],
)
def test_endpoint_table_damage_never_returns_500(damage, tag):
    data = DAMAGE[damage](latin_bytes(), tag)
    assert post_subset(data, http=lenient_client).status_code in (200, 400, 422)


# ---------------------------------------------------------------------------
# unsupported_characters: which requested characters the font cannot draw
# ---------------------------------------------------------------------------


# When the font has every requested character, nothing is reported.
def test_unsupported_none_when_all_supported(open_sans):
    assert unsupported_characters("Hello", open_sans) == []


# A mixed request reports only the characters the font lacks.
def test_unsupported_reports_missing_characters(open_sans):
    assert unsupported_characters("Hi日", open_sans) == ["日"]


# Text made only of unsupported characters reports all of them, in the order typed.
def test_unsupported_all_missing_in_order(open_sans):
    assert unsupported_characters("日本語", open_sans) == ["日", "本", "語"]


# Each character is reported once, in the order it first appears.
def test_unsupported_lists_each_character_once_in_first_seen_order(open_sans):
    result = unsupported_characters("本a日本日a", open_sans)
    assert format_codepoints(result) == "U+672C,U+65E5"

# Empty text has nothing to report.
def test_unsupported_empty_text(open_sans):
    assert unsupported_characters("", open_sans) == []


# Support is decided per font: Latin "A" is missing from a Greek-only font, Greek Alpha is not.
def test_unsupported_depends_on_the_font(symbols_font):
    assert unsupported_characters("A\u0391", symbols_font) == ["A"]


# Checking support must not change the font, because extract_subset runs on it afterwards.
def test_unsupported_does_not_modify_the_font(open_sans):
    before = set(open_sans.getBestCmap())
    unsupported_characters("Hi日", open_sans)
    assert set(open_sans.getBestCmap()) == before


# ---------------------------------------------------------------------------
# format_codepoints: the value of the X-Dropped-Characters header
# ---------------------------------------------------------------------------


# Characters become comma-separated U+ code points, padded to at least four hex digits.
@pytest.mark.parametrize(
    "characters, expected",
    [
        (["日"], "U+65E5"),
        (["日", "本"], "U+65E5,U+672C"),
        (["A"], "U+0041"),
        (["\U0001F600"], "U+1F600"),
        ([], ""),
    ],
    ids=["one", "two", "padded-to-four-digits", "beyond-bmp", "empty"],
)
def test_format_codepoints(characters, expected):
    assert format_codepoints(characters) == expected


# ---------------------------------------------------------------------------
# POST /subset: reporting dropped characters (X-Dropped-Characters header)
# ---------------------------------------------------------------------------


# Characters the font lacks are reported in the header as U+ code points.
def test_endpoint_reports_dropped_characters_in_header():
    response = post_subset(latin_bytes(), "Hi日")
    assert response.status_code == 200
    assert response.headers["Unsupported-Characters"] == "U+65E5"
    assert cmap_of(response.content) == cps("Hi")


# Several dropped characters are listed once each, in the order they first appear.
def test_endpoint_header_lists_each_dropped_character_once():
    response = post_subset(latin_bytes(), "H日本日i")
    assert response.headers["Unsupported-Characters"] == "U+65E5,U+672C"


# The header value is plain ASCII, so any HTTP client can carry it.
def test_endpoint_dropped_header_is_ascii():
    response = post_subset(latin_bytes(), "Hi日本")
    assert response.headers["Unsupported-Characters"].isascii()


# When every requested character is supported, the header is left out entirely.
def test_endpoint_no_header_when_nothing_is_dropped():
    response = post_subset(latin_bytes(), "Hello")
    assert response.status_code == 200
    assert "Unsupported-Characters" not in response.headers


# Adding the header must not disturb the normal download headers.
def test_endpoint_dropped_header_keeps_download_headers():
    response = post_subset(latin_bytes(), "Hi日")
    assert response.headers["content-type"] == "font/ttf"
    assert response.headers[
               "content-disposition"] == 'attachment; filename="subset.ttf"'


# ---------------------------------------------------------------------------
# POST /subset: text with no supported characters
# ---------------------------------------------------------------------------


# Text with no characters the font supports is rejected with a 422 and a JSON error, not a download.
@pytest.mark.parametrize("text", ["日", "日本", "日日日", "日本語"])
def test_endpoint_text_with_no_supported_characters_returns_422(text):
    response = post_subset(latin_bytes(), text)
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"]
    assert "content-disposition" not in response.headers


# One supported character is enough: the request succeeds and the rest is reported.
def test_endpoint_one_supported_character_is_enough():
    response = post_subset(latin_bytes(), "日本a")
    assert response.status_code == 200
    assert cmap_of(response.content) == cps("a")
    assert response.headers["Unsupported-Characters"] == "U+65E5,U+672C"


# Support is judged per font: a Greek-only font rejects Latin-only text but accepts Greek.
def test_endpoint_judges_support_per_font(symbols_pair):
    data, _font = symbols_pair
    assert post_subset(data, "ABC").status_code == 422
    mixed = post_subset(data, "A\u0391")
    assert mixed.status_code == 200
    assert mixed.headers["Unsupported-Characters"] == "U+0041"
    assert cmap_of(mixed.content) == cps("\u0391")
