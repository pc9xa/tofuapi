import io

import pytest
from fontTools.ttLib import TTFont

from app.services.font_loader import InvalidFontError, load_font
from tests.helpers import FIXTURES


def test_loads_valid_font():
    with open(FIXTURES / "Roboto-Italic.ttf", "rb") as f:
        assert isinstance(load_font(f), TTFont)


@pytest.mark.parametrize(
    "data",
    [b"", b"just some text", b"\x00\x01\x00\x00" + b"junk" * 20],
    ids=["empty", "plain-text", "truetype-header-then-junk"],
)
def test_rejects_invalid_data(data):
    with pytest.raises(InvalidFontError):
        load_font(io.BytesIO(data))


def test_keeps_original_error_as_cause():
    with pytest.raises(InvalidFontError) as info:
        load_font(io.BytesIO(b"not a font"))
    assert info.value.__cause__ is not None