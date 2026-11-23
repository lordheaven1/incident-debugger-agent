from app.core.fingerprint import generate_fingerprint, normalize_log


def test_normalize_log_strips_dynamic_tokens():
    log_a = "2026-11-23T10:00:00Z ERROR user 550e8400-e29b-41d4-a716-446655440000 failed at 0x7f1a2b line 42"
    log_b = "2026-11-24T22:15:30Z ERROR user 123e4567-e89b-12d3-a456-426614174000 failed at 0x9c4d1e line 99"
    assert normalize_log(log_a) == normalize_log(log_b)


def test_generate_fingerprint_deterministic():
    log_1 = "2026-11-23T10:00:00Z ERROR ZeroDivisionError: division by zero at line 5"
    log_2 = "2026-11-23T11:30:45Z ERROR ZeroDivisionError: division by zero at line 12"
    fp_1 = generate_fingerprint("auth-service", log_1)
    fp_2 = generate_fingerprint("auth-service", log_2)
    assert len(fp_1) == 16
    assert fp_1 == fp_2


def test_generate_fingerprint_distinguishes_different_errors():
    fp_zero = generate_fingerprint("auth-service", "ERROR ZeroDivisionError: division by zero")
    fp_key = generate_fingerprint("auth-service", "ERROR KeyError: permissions")
    assert fp_zero != fp_key