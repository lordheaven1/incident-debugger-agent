import os

import certifi
from arq import create_pool
from arq.connections import RedisSettings
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import IncidentDetailResponse, LogIngestRequest, LogIngestResponse
from app.core.database import get_db
from app.core.fingerprint import generate_fingerprint
from app.core.models import Incident

load_dotenv()


def _normalize_redis_url(raw_url: str) -> str:
    url = raw_url.strip().strip('"').strip("'")
    if "upstash.io" in url and url.startswith("redis://"):
        url = url.replace("redis://", "rediss://", 1)
    return url


REDIS_URL = _normalize_redis_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
redis_kwargs = {"decode_responses": True}
if REDIS_URL.startswith("rediss://"):
    redis_kwargs["ssl_ca_certs"] = certifi.where()

router = APIRouter()
redis_client = Redis.from_url(REDIS_URL, **redis_kwargs)
arq_redis_settings = RedisSettings.from_dsn(REDIS_URL)


@router.get("/health")
async def health_check():
    try:
        await redis_client.ping()
        return {"status": "ok", "redis": "connected"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {exc}")


@router.post("/ingest", response_model=LogIngestResponse)
async def ingest_log(payload: LogIngestRequest, db: AsyncSession = Depends(get_db)):
    fingerprint = generate_fingerprint(payload.service_name, payload.raw_log)
    count_key = f"incident:count:{fingerprint}"
    occurrence_count = await redis_client.incr(count_key)

    result = await db.execute(
        select(Incident).where(Incident.fingerprint == fingerprint)
    )
    incident = result.scalar_one_or_none()

    if incident is None:
        incident = Incident(
            fingerprint=fingerprint,
            service_name=payload.service_name,
            environment=payload.environment,
            raw_log=payload.raw_log,
            occurrence_count=occurrence_count,
            status="queued",
        )
        db.add(incident)
    else:
        incident.occurrence_count = occurrence_count

    await db.commit()

    queued = False
    if occurrence_count == 1:
        await redis_client.expire(count_key, 3600)
        arq_pool = await create_pool(arq_redis_settings)
        await arq_pool.enqueue_job("triage_incident", fingerprint)
        await arq_pool.aclose()
        queued = True

    return LogIngestResponse(
        status="accepted",
        fingerprint=fingerprint,
        occurrence_count=occurrence_count,
        queued_for_triage=queued,
    )


@router.get("/incidents/{fingerprint}", response_model=IncidentDetailResponse)
async def get_incident(fingerprint: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Incident).where(Incident.fingerprint == fingerprint)
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident