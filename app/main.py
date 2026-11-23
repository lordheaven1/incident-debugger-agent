from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from app.api.routes import router
from app.core.database import AsyncSessionLocal, init_db
from app.core.models import CodeChunk
from scripts.index_repo import index_directory


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with AsyncSessionLocal() as session:
        count = await session.scalar(select(func.count()).select_from(CodeChunk))
        if not count:
            await index_directory("sample_service")
    yield


app = FastAPI(
    title="Autonomous Log Triage & Incident Debugger",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


app.include_router(router)