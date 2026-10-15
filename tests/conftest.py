from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

FIXTURES = Path(__file__).parent / "fixtures"

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