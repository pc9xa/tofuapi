import io
import struct

from fastapi import APIRouter, UploadFile, HTTPException, Query, Response
from fontTools.ttLib import TTLibError

from app.services.font_loader import load_font, InvalidFontError
from app.services.metadata import extract_metadata
from app.services.preview import render_preview
from app.utils import read_upload

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


# @router.post("/subset")
# def subset():
#     return {}
#

# @router.post("/render")
# def render():
#     return {}