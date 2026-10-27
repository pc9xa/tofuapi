import io

from fastapi import APIRouter, UploadFile, HTTPException, Query, Response

from app.services.font_loader import load_font
from app.services.metadata import extract_metadata
from app.services.preview import render_preview
from app.services.subset import extract_subset, format_codepoints
from app.services.render import render_text, RenderedImageTooLargeError
from app.routers.utils import read_upload
from app.services.utils import unsupported_characters
from app.config import (
    MAX_RENDER_IMAGE_WIDTH,
    DEFAULT_FONT_SIZE,
    FONT_READ_ERRORS
)

router = APIRouter()

@router.post("/metadata")
def metadata(file: UploadFile):
    """
    Retrieves a font's names, style, license and embedding permissions,
    and character coverage.
    """
    data = read_upload(file)
    font = load_font(io.BytesIO(data))
    try:
        return extract_metadata(font)
    except FONT_READ_ERRORS as err:
        raise HTTPException(
            status_code=422,
            detail="Error found in reading font tables."
        ) from err


@router.post("/preview")
def preview(
        file: UploadFile,
        size: int = Query(48, ge=12, le=128)
) -> Response:
    """
    Draws a grid of sample characters from the font.
    """
    data = read_upload(file)
    font = load_font(io.BytesIO(data))
    try:
        png = render_preview(data, font, size)
    except FONT_READ_ERRORS as err:
        raise HTTPException(
            status_code=422,
            detail="Could not render a preview for this font."
        ) from err
    return Response(content=png, media_type="image/png")


@router.post("/subset")
def subset(
        file: UploadFile,
        text: str = Query(min_length=1, max_length=64)
) -> Response:
    """
    Creates a smaller font that keeps only the glyphs needed for the text
    requested.
    """
    data = read_upload(file)
    font = load_font(io.BytesIO(data))
    try:
        unsupported = unsupported_characters(text, font)
        if len(unsupported) == sum(1 for ch in text if not ch.isspace()):
            raise HTTPException(
                status_code=422,
                detail="The font does not support any of the requested characters.")
        subset_ttf = extract_subset(text, font)
        headers = {"Content-Disposition": 'attachment; filename="subset.ttf"'}
        if unsupported:
            headers["Unsupported-Characters"] = format_codepoints(unsupported)
    except FONT_READ_ERRORS as err:
        raise HTTPException(
            status_code=422,
            detail="Could not create a subset for this font."
        ) from err
    return Response(
        content=subset_ttf,
        media_type="font/ttf",
        headers=headers,
    )


@router.post("/render")
def render(
        file: UploadFile,
        text: str = Query(min_length=1, max_length=1000),
        image_width: int = Query(800, ge=200, le=MAX_RENDER_IMAGE_WIDTH),
        font_size: int = Query(DEFAULT_FONT_SIZE, ge=8, le=100),
        font_color: str = Query("#000000", pattern=r"^#[0-9a-fA-F]{6}$"),
) -> Response:
    """
    Draws the text requested in the font and settings requested.
    """
    data = read_upload(file)
    load_font(io.BytesIO(data))

    try:
        png = render_text(data, image_width, font_size, text, font_color)
    except RenderedImageTooLargeError:
        raise
    except FONT_READ_ERRORS as err:
        raise HTTPException(
            status_code=422,
            detail=str("Could not render text for this font.")
        ) from err

    return Response(content=png, media_type="image/png")