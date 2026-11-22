# Autonomous Log Triage & Incident Debugger

An asynchronous, Agentic SRE pipeline built with **FastAPI, Redis, PostgreSQL (`pgvector`), and LangGraph** to ingest production error logs, deduplicate recurring stack traces, and automatically diagnose root causes.

---

## Current Progress (Phase 1 Completed)

* **Containerized Infrastructure (`docker-compose.yml`):** Configured local Docker services for PostgreSQL 16 (`pgvector/pgvector:pg16`) with persistent volume storage and Redis (`redis:7-alpine`) with healthchecks.
* **Stack-Trace Fingerprinting (`app/core/fingerprint.py`):** Built a normalization engine that strips volatile fields (UUIDs, hex memory addresses, ISO timestamps, and numeric IDs) before generating a deterministic 16-character SHA-256 fingerprint.
* **Async Ingestion & Deduplication API (`app/api/`):** Implemented `GET /health` and `POST /ingest` in FastAPI backed by async Redis counters. Identical stack traces within a 1-hour window increment `occurrence_count` and set `queued_for_triage: false`, preventing redundant downstream LLM calls during log storms.

---

## Project Structure

```text
incident-debugger-agent/
├── app/
│   ├── api/
│   │   ├── routes.py          # /health and /ingest endpoints
│   │   └── schemas.py         # Pydantic request/response models
│   ├── core/
│   │   └── fingerprint.py     # Log normalization & SHA-256 hashing
│   ├── agent/                 # (Phase 3) LangGraph workflow & tools
│   ├── worker/                # (Phase 2) Async background queue consumer
│   └── main.py                # FastAPI application entrypoint
├── scripts/                   # (Phase 2) Repo & runbook vector indexer
├── evals/                     # (Phase 3) Synthetic bug benchmark
├── tests/                     # Pytest suite
├── docker-compose.yml
├── requirements.txt
└── .gitignore
