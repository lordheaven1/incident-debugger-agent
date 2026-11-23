# Auth Service Incident Runbook

## ZeroDivisionError in calculate_token_quota
- **Cause:** Occurs when `active_windows` is `0` right after a Redis cache flush or cold service boot.
- **Fix:** Guard `active_windows <= 0` and return a safe default quota instead of dividing by zero.

## KeyError on user_id or permissions
- **Cause:** Legacy mobile clients send flat JWT claims without a nested `permissions` dictionary.
- **Fix:** Use `.get()` with fallback defaults (`session_payload.get("permissions", {}).get("role", "guest")`).