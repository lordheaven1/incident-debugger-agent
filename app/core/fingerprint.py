import hashlib
import re


_PATTERNS = [
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<UUID>"),
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "<HEX>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<TIMESTAMP>"),
    (re.compile(r"\b\d+\b"), "<NUM>"),
]


def normalize_log(raw_log: str) -> str:
    cleaned = raw_log.strip()
    for pattern, replacement in _PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return re.sub(r"\s+", " ", cleaned)


def generate_fingerprint(service_name: str, raw_log: str) -> str:
    normalized = normalize_log(raw_log)
    payload = f"{service_name.lower()}::{normalized}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]