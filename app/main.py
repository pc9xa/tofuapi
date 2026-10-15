from fastapi import FastAPI
from app.routers import fonts

app = FastAPI(title="TofuAPI")
app.include_router(fonts.router)



