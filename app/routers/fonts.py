import io
import struct

from fastapi import APIRouter, UploadFile, HTTPException
from fontTools.ttLib import TTLibError

from app.services.font_loader import load_font, InvalidFontError
from app.services.metadata import extract_metadata
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


# @router.post("/preview")
# def preview():
#     return {}
#

# @router.post("/subset")
# def subset():
#     return {}
#

# @router.post("/render")
# def render():
#     return {}