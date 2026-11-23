from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import delete

from app.api.routes import router
from app.core.database import AsyncSessionLocal, init_db
from app.core.models import CodeChunk
from scripts.index_repo import index_directory


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with AsyncSessionLocal() as session:
        await session.execute(delete(CodeChunk))
        await session.commit()
    await index_directory("sample_service")
    yield


app = FastAPI(
    title="Autonomous Log Triage & Incident Debugger",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(router)