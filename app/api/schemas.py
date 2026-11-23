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


class IncidentDetailResponse(BaseModel):
    fingerprint: str
    service_name: str
    environment: str
    raw_log: str
    occurrence_count: int
    status: str
    diagnosis: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}