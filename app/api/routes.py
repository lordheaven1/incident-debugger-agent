from fastapi import APIRouter, HTTPException
from redis.asyncio import Redis

from app.api.schemas import LogIngestRequest, LogIngestResponse
from app.core.fingerprint import generate_fingerprint

router = APIRouter()
redis_client = Redis(host="localhost", port=6379, db=0, decode_responses=True)


@router.get("/health")
async def health_check():
    try:
        await redis_client.ping()
        return {"status": "ok", "redis": "connected"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {exc}")


@router.post("/ingest", response_model=LogIngestResponse)
async def ingest_log(payload: LogIngestRequest):
    fingerprint = generate_fingerprint(payload.service_name, payload.raw_log)
    count_key = f"incident:count:{fingerprint}"
    occurrence_count = await redis_client.incr(count_key)

    queued = False
    if occurrence_count == 1:
        await redis_client.expire(count_key, 3600)
        queued = True

    return LogIngestResponse(
        status="accepted",
        fingerprint=fingerprint,
        occurrence_count=occurrence_count,
        queued_for_triage=queued,
    )