import pytest
from app.agent.graph import run_triage_agent
from app.agent.schemas import DiagnosisReport
from app.core.database import engine


@pytest.mark.asyncio
async def test_triage_agent_diagnoses_zero_division():
    try:
        raw_report = await run_triage_agent(
            fingerprint="test_fp_001",
            service_name="auth-service",
            environment="production",
            raw_log="2026-11-23T19:15:00Z ERROR ZeroDivisionError: division by zero in calculate_token_quota",
        )
        validated = DiagnosisReport(**raw_report)
        assert validated.severity == "P1"
        assert validated.exception_type == "ZeroDivisionError"
        assert validated.affected_file == "sample_service/auth.py"
        assert 0.0 <= validated.confidence <= 1.0
    finally:
        await engine.dispose()