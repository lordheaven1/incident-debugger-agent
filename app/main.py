from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api.routes import router
from app.core.database import init_db
from app.core import models


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Autonomous Log Triage & Incident Debugger",
    version="0.2.0",
    lifespan=lifespan,
)
app.include_router(router)