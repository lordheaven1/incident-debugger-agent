from datetime import datetime, timezone


def calculate_token_quota(total_requests: int, active_windows: int) -> float:
    return total_requests / active_windows


def extract_user_profile(session_payload: dict) -> dict:
    user_id = session_payload["user_id"]
    role = session_payload["permissions"]["role"]
    return {
        "user_id": user_id,
        "role": role,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }