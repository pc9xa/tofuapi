from fastapi import FastAPI

from app.errors import register_exception_handlers
from app.routers import fonts

app = FastAPI(
    title="TofuAPI",
    description="A small web API for inspecting, previewing, subsetting, "
                "and rendering text with font files.",
    version="1.0.0",
)

register_exception_handlers(app)
app.include_router(fonts.router)



