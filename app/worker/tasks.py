import json
import os
import ssl
import certifi
from arq.connections import RedisSettings
from dotenv import load_dotenv
from sqlalchemy import select
from app.agent.graph import run_triage_agent
from app.core.database import AsyncSessionLocal
from app.core.models import Incident

async def triage_incident(ctx, fingerprint: str) -> str:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Incident).where(Incident.fingerprint == fingerprint)
        )
        incident = result.scalar_one_or_none()
        if not incident:
            return f"not_found:{fingerprint}"

        incident.status = "investigating"
        await session.commit()

        try:
            report = await run_triage_agent(
                fingerprint=incident.fingerprint,
                service_name=incident.service_name,
                environment=incident.environment,
                raw_log=incident.raw_log,
            )
            incident.diagnosis = json.dumps(report, indent=2)
            incident.status = "diagnosed"
        except Exception as exc:
            incident.diagnosis = json.dumps({"error": str(exc)}, indent=2)
            incident.status = "failed"

        await session.commit()
        return f"{incident.status}:{fingerprint}"

load_dotenv()

import os
from arq.connections import RedisSettings
from dotenv import load_dotenv

load_dotenv()

raw_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip().strip('"').strip("'")
if "upstash.io" in raw_redis_url and raw_redis_url.startswith("redis://"):
    raw_redis_url = raw_redis_url.replace("redis://", "rediss://", 1)


class WorkerSettings:
    functions = [triage_incident]
    redis_settings = RedisSettings.from_dsn(raw_redis_url)