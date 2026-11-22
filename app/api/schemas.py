from datetime import datetime, timezone
from pydantic import BaseModel, Field


class LogIngestRequest(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=100)
    environment: str = Field(default="production")
    raw_log: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LogIngestResponse(BaseModel):
    status: str
    fingerprint: str
    occurrence_count: int
    queued_for_triage: bool