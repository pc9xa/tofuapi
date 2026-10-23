from app.config import MAX_UPLOAD_BYTES
from fastapi import UploadFile, HTTPException
from fontTools.ttLib import TTFont

def read_upload(file: UploadFile) -> bytes:
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        mb_limit = MAX_UPLOAD_BYTES // (1024 * 1024) # readability
        raise HTTPException(status_code=413, detail=f"File too large (max {mb_limit} MB)")
    return data


def unsupported_characters(text: str, font: TTFont) -> list[str]:
    cmap = font.getBestCmap() or {}
    return [ch for ch in text if ord(ch) not in cmap]