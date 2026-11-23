# Autonomous Log Triage & Incident Debugger

An asynchronous, event-driven **Agentic SRE pipeline** that ingests production crash logs, deduplicates alert storms in Redis, retrieves relevant source code and runbooks via `pgvector`, inspects local Git history, and synthesizes structured root-cause diagnoses using **LangGraph**.

* **Live SRE Command Center UI:** https://incident-debugger-agent.onrender.com
* **Interactive Swagger API Docs:** https://incident-debugger-agent.onrender.com/docs

---

## Why This Project Exists

During production outages, engineering teams face two bottlenecks:
1. **Alert Storms:** A single failing service emits thousands of identical stack traces with varying timestamps, UUIDs, and memory addresses—overwhelming on-call engineers and wasting LLM inference credits if processed naively.
2. **High Mean Time to Resolution (MTTR):** Engineers spend critical minutes context-switching between log aggregators, source files, incident runbooks, and `git log` to isolate root causes.

This system automates first-responder triage while keeping log ingestion completely non-blocking.

---

## System Architecture

```text
[Crashing Service / SRE Command Center UI]
       │
       ▼  POST /ingest
[FastAPI Ingestion API]
       ├──► Regex Normalization + SHA-256 Fingerprinting (16-char hash)
       ├──► Upstash Redis Atomic INCR + TTL (3600s) ──► Suppresses alert storms
       ├──► Neon PostgreSQL (incidents table) ────────► Persists state & counts
       └──► ARQ Background Queue (on count == 1)
                   │
                   ▼
         [ARQ Async Worker]
                   │
                   ▼
      [LangGraph Triage Agent]
1. Triage Node     ──► Classifies severity (P1–P4) & exception metadata
2. Retrieve Node   ──► 384-dim cosine search over Neon pgvector (code_chunks)
3. Inspect Node    ──► Reads bounded file lines & recent git commits
4. Synthesize Node ──► Outputs Pydantic-validated DiagnosisReport JSON
                   │
                   ▼
   [Neon PostgreSQL Update] ──► Live UI & GET /incidents/{fingerprint}
```

---

## Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **API & Validation** | Python 3.12 / 3.14, FastAPI, Pydantic v2, Uvicorn |
| **Queue & Deduplication** | Upstash Serverless Redis (`rediss://` TLS), ARQ (async worker queue) |
| **Database & Vector Store** | Neon PostgreSQL 16, `pgvector` (`Vector(384)`), SQLAlchemy (async), `asyncpg` |
| **Agent & Embeddings** | LangGraph, Gemini 3.x fallback chain (`gemini-3.5-flash-lite` → `gemini-3.8-flash`), `gemini-embedding-001` (384-dim) with deterministic offline fallback |
| **Frontend & Deployment** | Tailwind CSS (embedded SRE Command Center UI), Docker, Render Cloud |
| **Testing & Evals** | `pytest`, `pytest-asyncio`, custom 5-case evaluation harness |

---

## Repository Structure

```text
incident-debugger-agent/
├── app/
│   ├── agent/
│   │   ├── graph.py            # Compiled 4-node LangGraph state machine
│   │   ├── nodes.py            # triage, retrieve, inspect, and synthesize nodes
│   │   ├── schemas.py          # Strict Pydantic models (TriageResult, DiagnosisReport)
│   │   └── tools.py            # Read-only pgvector search, path-safe file reader, git log tool
│   ├── api/
│   │   ├── routes.py           # GET /health, GET /incidents, POST /ingest, GET /incidents/{fingerprint}
│   │   └── schemas.py          # Request/response contracts
│   ├── core/
│   │   ├── database.py         # Async SQLAlchemy engine, Neon URL normalizer & pgvector init
│   │   ├── embeddings.py       # Gemini API 384-dim embedder with offline hash fallback
│   │   ├── fingerprint.py      # Regex log normalizer & deterministic SHA-256 hasher
│   │   └── models.py           # Incident & CodeChunk ORM models
│   ├── static/
│   │   └── index.html          # Real-time SRE Incident Command Center dashboard
│   ├── worker/
│   │   └── tasks.py            # ARQ background worker executing the LangGraph agent
│   └── main.py                 # FastAPI entrypoint serving UI & auto-seeding pgvector
├── sample_service/
│   ├── auth.py                 # Sample service with reproducible runtime faults
│   └── runbooks/
│       └── auth_outage.md      # Operational runbook indexed into pgvector
├── scripts/
│   └── index_repo.py           # Overlapping line chunker & vector indexer
├── evals/
│   ├── dataset.json            # Synthetic production incident evaluation cases
│   └── run_eval.py             # Automated accuracy & latency benchmark runner
├── tests/
│   ├── test_agent.py           # End-to-end LangGraph diagnosis integration test
│   └── test_fingerprint.py     # Unit tests for log normalization & hash determinism
├── Dockerfile                  # Production single-container API + ARQ worker image
├── docker-compose.yml          # Local PostgreSQL (pgvector:pg16) & Redis 7 services
├── pytest.ini
└── requirements.txt
```

---

## Live Cloud Demo (Render + Neon + Upstash)

Open **https://incident-debugger-agent.onrender.com** to dispatch crash logs from the web UI, or test the live API from PowerShell:

```powershell
$baseUrl = "[https://incident-debugger-agent.onrender.com](https://incident-debugger-agent.onrender.com)"

# 1. Verify FastAPI & Upstash TLS Redis health
Invoke-RestMethod -Uri "$baseUrl/health" -Method Get

# 2. Ingest a production crash log
$body = '{"service_name":"auth-service","raw_log":"2026-11-23T23:55:00Z ERROR ZeroDivisionError: division by zero in calculate_token_quota for user 550e8400-e29b-41d4-a716-446655440000 at sample_service/auth.py line 5"}'
$res = Invoke-RestMethod -Uri "$baseUrl/ingest" -Method Post -ContentType "application/json" -Body $body

# 3. Poll until the ARQ worker finishes LangGraph triage
do {
    Start-Sleep -Seconds 3
    $incident = Invoke-RestMethod -Uri "$baseUrl/incidents/$($res.fingerprint)" -Method Get
} while ($incident.status -in @("queued", "investigating"))

$incident.status
$incident.diagnosis
```

---

## Quickstart & Local Setup

### 1. Clone & Create Virtual Environment
```powershell
git clone [https://github.com/lordheaven1/incident-debugger-agent.git](https://github.com/lordheaven1/incident-debugger-agent.git)
cd incident-debugger-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
Create a `.env` file in the root directory to enable live LLM synthesis and embeddings via Gemini. If omitted, the agent automatically uses its built-in deterministic fallback synthesizer and local hash embeddings:
```env
GEMINI_API_KEY=your_gemini_api_key
```

### 3. Start Infrastructure & Index Codebase
```powershell
docker compose up -d
python -m scripts.index_repo
```

### 4. Start API Server & Background Worker
Open two terminals with `.venv` activated:
```powershell
# Terminal 1: FastAPI Server & Command Center UI (http://localhost:8000)
uvicorn app.main:app --reload

# Terminal 2: ARQ Background Worker
arq app.worker.tasks.WorkerSettings
```

---

## Testing & Evaluation

Run the unit and integration test suite (`4/4` passing) and the 5-case evaluation harness:
```powershell
pytest -v
python -m evals.run_eval
```

---

## Key Engineering Highlights

* **Alert Storm Deduplication:** Normalizes dynamic log tokens (`UUID`, hex pointers, ISO-8601 timestamps, numeric literals) before hashing so duplicate crashes increment a Redis TTL counter (`incident:count:{fingerprint}`) without triggering redundant agent runs.
* **Lightweight Cloud Architecture (<150 MB RAM):** Replaces heavy local PyTorch weights with 384-dimensional `gemini-embedding-001` API embeddings and normalizes Neon `asyncpg` and Upstash `rediss://` TLS parameters to run both FastAPI and ARQ inside a single 512 MB Render container.
* **Sandboxed Read-Only Tooling:** File inspection tools enforce root-path resolution checks (`Path.resolve()`) to prevent directory traversal, while Git inspection runs strictly read-only `git log` commands.
* **Resilient Multi-Model Inference:** Enforces structured Pydantic outputs (`TriageResult` and `DiagnosisReport`) across an automated Gemini 3.x fallback chain while preserving zero-dependency offline execution for CI testing.