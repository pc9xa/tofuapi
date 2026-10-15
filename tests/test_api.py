import pytest
from fastapi.testclient import TestClient

from app.config import MAX_UPLOAD_BYTES
from app.main import app
from tests.helpers import EXPECTED_NAMES, FIXTURES, corrupt_table, drop_table

client = TestClient(app)


def post_font(data: bytes, filename: str = "font.ttf"):
    return client.post("/metadata", files={"file": (filename, data, "font/ttf")})


def open_sans_bytes() -> bytes:
    return (FIXTURES / "OpenSans-Regular.ttf").read_bytes()


# Happy path -------------------------------------------------------------------


@pytest.mark.parametrize("filename, expected", EXPECTED_NAMES.items())
def test_valid_fonts_return_metadata(filename, expected):
    response = post_font((FIXTURES / filename).read_bytes(), filename)
    assert response.status_code == 200
    names = response.json()["names"]
    assert (names["family"], names["style"]) == expected


def test_response_has_expected_sections():
    body = post_font(open_sans_bytes()).json()
    assert set(body) == {"names", "style", "license", "coverage"}


# Client errors ----------------------------------------------------------------


def test_missing_file_returns_422():
    assert client.post("/metadata").status_code == 422


@pytest.mark.parametrize(
    "data",
    [b"", b"not a font", b"\x00\x01\x00\x00" + b"junk" * 20],
    ids=["empty", "plain-text", "truetype-header-then-junk"],
)
def test_non_fonts_return_400(data):
    response = post_font(data)
    assert response.status_code == 400
    assert "detail" in response.json()


def test_oversized_upload_returns_413():
    too_big = b"\x00\x01\x00\x00" + b"0" * MAX_UPLOAD_BYTES
    assert post_font(too_big).status_code == 413


# Damaged tables (see ADR-0001) ------------------------------------------------


@pytest.mark.parametrize("tag", ["OS/2", "post", "cmap"])
def test_unreadable_table_returns_422(tag):
    # fontTools raises TTLibError / struct.error for these, so the router maps them to 422
    assert post_font(corrupt_table(open_sans_bytes(), tag)).status_code == 422


@pytest.mark.parametrize("tag", ["maxp", "cmap"])
def test_missing_required_table_returns_422(tag):
    # maxp and cmap are required by the spec, and loading the cmap raises KeyError without them
    assert post_font(drop_table(open_sans_bytes(), tag)).status_code == 422


@pytest.mark.parametrize("tag", ["name", "maxp", "head"])
def test_tolerated_table_damage_never_returns_500(tag):
    # fontTools tolerates damage to these tables, so the response is 200 with degraded data
    assert post_font(corrupt_table(open_sans_bytes(), tag)).status_code in (200, 422)