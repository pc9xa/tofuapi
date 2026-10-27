from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.font_loader import InvalidFontError
from app.services.render import RenderedImageTooLargeError


def error_response(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail})

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidFontError)
    def invalid_font(request: Request, err: InvalidFontError) -> JSONResponse:
        return error_response(400, str(err))

    @app.exception_handler(RenderedImageTooLargeError)
    def image_too_large(
            request: Request,
            err: RenderedImageTooLargeError
    ) -> JSONResponse:
        return error_response(422, str(err))