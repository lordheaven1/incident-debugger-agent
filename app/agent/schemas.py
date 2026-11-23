from typing import Literal
from pydantic import BaseModel, Field


class TriageResult(BaseModel):
    severity: Literal["P1", "P2", "P3", "P4"]
    exception_type: str
    suspected_file: str | None = None
    suspected_function: str | None = None
    search_query: str


class DiagnosisReport(BaseModel):
    severity: Literal["P1", "P2", "P3", "P4"]
    exception_type: str
    root_cause: str
    affected_file: str
    affected_lines: str
    recent_commit: str
    suggested_fix: str
    confidence: float = Field(..., ge=0.0, le=1.0)