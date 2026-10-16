import pytest, io
from fontTools import subset
from fontTools.ttLib import TTFont

from tests.helpers import FIXTURES, GREEK_CAPITALS, LATIN_FONT

# Open Source Fonts ------------------------------------------------------------

@pytest.fixture
def roboto_italic() -> TTFont:
    return TTFont(FIXTURES / "Roboto-Italic.ttf")

@pytest.fixture
def roboto_bold() -> TTFont:
    return TTFont(FIXTURES / "Roboto-Bold.ttf")

@pytest.fixture
def source_code_pro() -> TTFont:
    return TTFont(FIXTURES / "SourceCodePro-Regular.ttf")

@pytest.fixture
def roboto_condensed() -> TTFont:
    return TTFont(FIXTURES / "Roboto_Condensed-Regular.ttf")

@pytest.fixture
def open_sans() -> TTFont:
    return TTFont(FIXTURES / "OpenSans-Regular.ttf")


# Proprietary Fonts ------------------------------------------------------------

@pytest.fixture
def courier_new() -> TTFont:
    return TTFont(FIXTURES / "cour.ttf")


# Symbols-only Fonts -----------------------------------------------------------


# Build a symbols-only font that keeps only the Greek capital letters
@pytest.fixture
def symbols_font() -> TTFont:
    font = TTFont(LATIN_FONT)
    subsetter = subset.Subsetter(subset.Options())
    subsetter.populate(unicodes=GREEK_CAPITALS)
    subsetter.subset(font)
    return font


# Provide the Greek-only test font as (raw bytes, TTFont). render_preview needs
# both, and they must describe the same font.
@pytest.fixture
def symbols_pair(symbols_font):
    buffer = io.BytesIO()
    symbols_font.save(buffer)
    data = buffer.getvalue()
    return data, TTFont(io.BytesIO(data))


# Provide a full Latin font as (raw bytes, TTFont).
@pytest.fixture
def latin_pair():
    data = LATIN_FONT.read_bytes()
    return data, TTFont(io.BytesIO(data))