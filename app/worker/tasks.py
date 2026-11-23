from arq.connections import RedisSettings
from sqlalchemy import select

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

        incident.diagnosis = (
            f"Placeholder diagnosis for {incident.service_name} ({fingerprint}). "
            "Ready for LangGraph agent in Phase 3."
        )
        incident.status = "diagnosed"
        await session.commit()
        return f"diagnosed:{fingerprint}"


class WorkerSettings:
    functions = [triage_incident]
    redis_settings = RedisSettings(host="localhost", port=6379, database=0)