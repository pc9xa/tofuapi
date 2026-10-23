import io
import struct

from fastapi import APIRouter, UploadFile, HTTPException, Query, Response
from fontTools.ttLib import TTLibError

from app.services.font_loader import load_font, InvalidFontError
from app.services.metadata import extract_metadata
from app.services.preview import render_preview
from app.services.subset import extract_subset, to_unicode
from app.services.render import render_text, RenderedImageTooLargeError
from app.utils import read_upload, unsupported_characters
from app.config import MAX_RENDER_IMAGE_WIDTH, DEFAULT_FONT_SIZE

router = APIRouter()

@router.post("/metadata")
def metadata(file: UploadFile):
    data = read_upload(file)
    try:
        font = load_font(io.BytesIO(data))
    except InvalidFontError as err:
        raise HTTPException(status_code=400, detail=str(err))
    try:
        return extract_metadata(font)
    except (TTLibError, struct.error, EOFError, IndexError, KeyError) as err:
        raise HTTPException(status_code=422, detail="Error found in reading font tables") from err


@router.post("/preview")
def preview(file: UploadFile, size: int = Query(48, ge=12, le=128)) -> Response:
    data = read_upload(file)
    try:
        font = load_font(io.BytesIO(data))
        png = render_preview(data, font, size)
    except InvalidFontError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except (ValueError, OSError, TTLibError, struct.error, KeyError) as err:
        raise HTTPException(status_code=422,
                            detail="Could not render a preview for this font.") from err
    return Response(content=png, media_type="image/png")


@router.post("/subset")
def subset(file: UploadFile, text: str = Query(min_length=1, max_length=64)) -> Response:
    data = read_upload(file)
    try:
        font = load_font(io.BytesIO(data))
    except InvalidFontError as err:
        raise HTTPException(status_code=400, detail=str(err))
    try:
        unsupported = unsupported_characters(text, font)
        if len(unsupported) == len(text):
            raise HTTPException(status_code=422,
                                detail="The font does not support any of the requested characters.")

        subset_ttf = extract_subset(text, font)
        headers = {"Content-Disposition": 'attachment; filename="subset.ttf"'}
        if unsupported:
            headers["Unsupported-Characters"] = to_unicode(unsupported)
    except (ValueError, OSError, TTLibError, struct.error, KeyError, IndexError) as err:
        raise HTTPException(status_code=422,
                            detail="Could not create a subset for this font.") from err
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
):
    data = read_upload(file)
    try:
        font = load_font(io.BytesIO(data))
        unsupported = unsupported_characters(text, font)
        if len(unsupported) == len(text):
            raise HTTPException(status_code=422,
                                detail="The font does not support any of the requested characters")
        png = render_text(data, image_width, font_size, text, font_color)
    except InvalidFontError as err:
        raise HTTPException(status_code=400, detail=str(err))
    except RenderedImageTooLargeError as err:
        raise HTTPException(status_code=422, detail=str(err))
    except (OSError, TTLibError, struct.error, KeyError, IndexError) as err:
        raise HTTPException(status_code=422, detail=str("Could not render text for this font."))

    return Response(content=png, media_type="image/png")