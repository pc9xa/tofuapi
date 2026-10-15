import pytest
from fontTools.ttLib import TTFont

from app.services.metadata import extract_metadata
from tests.helpers import EXPECTED_NAMES, FIXTURES


# Structure and names (all four fonts) -----------------------------------------


def test_result_has_expected_sections(roboto_bold):
    result = extract_metadata(roboto_bold)
    assert set(result) == {"names", "style", "license", "coverage"}


@pytest.mark.parametrize("filename, expected", EXPECTED_NAMES.items())
def test_family_and_style_names(filename, expected):
    names = extract_metadata(TTFont(FIXTURES / filename))["names"]
    assert (names["family"], names["style"]) == expected


def test_full_names(roboto_italic, open_sans):
    assert extract_metadata(roboto_italic)["names"]["full_name"] == "Roboto Italic"
    assert extract_metadata(open_sans)["names"]["full_name"] == "Open Sans Regular"


# Style: each font exercises a different branch of the style logic -------------


def test_italic_font(roboto_italic):
    style = extract_metadata(roboto_italic)["style"]
    assert style["italic"] is True
    assert style["bold"] is False
    assert style["weight"] == "Regular"


def test_bold_font(roboto_bold):
    style = extract_metadata(roboto_bold)["style"]
    assert style["bold"] is True
    assert style["italic"] is False
    assert style["weight"] == "Bold"


def test_monospaced_font(source_code_pro):
    assert extract_metadata(source_code_pro)["style"]["monospaced"] is True


def test_proportional_font_is_not_monospaced(roboto_bold):
    assert extract_metadata(roboto_bold)["style"]["monospaced"] is False


def test_condensed_width(roboto_condensed):
    # Guards the WIDTHS table: usWidthClass 3, which must read "Condensed"
    assert extract_metadata(roboto_condensed)["style"]["width"] == "Condensed"


def test_normal_width(open_sans):
    assert extract_metadata(open_sans)["style"]["width"] == "Normal"


# License ----------------------------------------------------------------------


def test_embedding_permissions_installable(roboto_italic):
    lic = extract_metadata(roboto_italic)["license"]
    assert lic["embedding"] == "installable"
    assert lic["no_subsetting"] is False

def test_embedding_permissions_editable(courier_new):
    lic = extract_metadata(courier_new)["license"]
    assert lic["embedding"] == "editable"
    assert lic["no_subsetting"] is False

def test_license_text_and_url(roboto_bold):
    lic = extract_metadata(roboto_bold)["license"]
    assert lic["text"].startswith("This Font Software is licensed under the SIL Open Font License")
    assert "https://openfontlicense.org" in lic["url"]

def test_missing_license_url_is_none(courier_new):
    # Courier New has no license URL record (nameID 14)
    assert extract_metadata(courier_new)["license"]["url"] is None


# Coverage ---------------------------------------------------------------------


@pytest.mark.parametrize("filename", EXPECTED_NAMES)
def test_glyph_count_matches_maxp(filename):
    font = TTFont(FIXTURES / filename)
    coverage = extract_metadata(font)["coverage"]
    assert coverage["num_glyphs"] == font["maxp"].numGlyphs
    assert coverage["num_codepoints"] > 0


# Fonts with missing tables ----------------------------------------------------


def test_missing_os2_table(roboto_bold):
    del roboto_bold["OS/2"]
    result = extract_metadata(roboto_bold)
    assert result["style"]["weight"] is None
    assert result["style"]["width"] is None
    assert result["style"]["italic"] is False
    assert result["style"]["bold"] is False
    assert result["license"]["embedding"] is None
    assert result["license"]["no_subsetting"] is None
    assert result["names"]["family"] == "Roboto"  # unaffected sections still work


def test_missing_name_table(roboto_bold):
    del roboto_bold["name"]
    result = extract_metadata(roboto_bold)
    assert all(value is None for value in result["names"].values())
    assert result["license"]["text"] is None
    assert result["style"]["weight"] == "Bold"  # unaffected sections still work


def test_missing_post_table(source_code_pro):
    del source_code_pro["post"]
    assert extract_metadata(source_code_pro)["style"]["monospaced"] is False