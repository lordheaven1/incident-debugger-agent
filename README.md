# Autonomous Log Triage & Incident Debugger

An asynchronous, event-driven **Agentic SRE pipeline** that ingests production crash logs, deduplicates alert storms in Redis, retrieves relevant source code and runbooks via `pgvector`, inspects local Git history, and synthesizes structured root-cause diagnoses using **LangGraph**.

---

## Why This Project Exists

During production outages, engineering teams face two bottlenecks:
1. **Alert Storms:** A single failing service emits thousands of identical stack traces with varying timestamps, UUIDs, and memory addresses—overwhelming on-call engineers and wasting LLM inference credits if processed naively.
2. **High Mean Time to Resolution (MTTR):** Engineers spend critical minutes context-switching between log aggregators, source files, incident runbooks, and `git log` to isolate root causes.

This system automates first-responder triage while keeping log ingestion completely non-blocking.

---

## System Architecture

```text
[Crashing Service]
       │
       ▼  POST /ingest
[FastAPI Ingestion API]
       ├──► Regex Normalization + SHA-256 Fingerprinting (16-char hash)
       ├──► Redis Atomic INCR + TTL (3600s) ──► Suppresses duplicate alert storms
       ├──► PostgreSQL (incidents table) ─────► Persists incident state & counts
       └──► ARQ Background Queue (on count == 1)
                   │
                   ▼
         [ARQ Async Worker]
                   │
                   ▼
      [LangGraph Triage Agent]
         1. Triage Node     ──► Classifies severity (P1–P4) & exception metadata
         2. Retrieve Node   ──► Cosine similarity search over pgvector (code_chunks)
         3. Inspect Node    ──► Reads bounded file lines & recent git commits
         4. Synthesize Node ──► Outputs Pydantic-validated DiagnosisReport JSON
                   │
                   ▼
      [PostgreSQL Update] ──► Accessible via GET /incidents/{fingerprint}
```

---

## Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **API & Validation** | Python 3.14, FastAPI, Pydantic v2, Uvicorn |
| **Queue & Deduplication** | Redis 7, ARQ (async worker queue) |
| **Database & Vector Store** | PostgreSQL 16, `pgvector` (`Vector(384)`), SQLAlchemy (async), `asyncpg` |
| **Agent & Embeddings** | LangGraph, `sentence-transformers` (`all-MiniLM-L6-v2`), Gemini API (`gemini-3.8-flash`) with deterministic offline fallback |
| **Infrastructure & Testing** | Docker Compose, `pytest`, `pytest-asyncio` |

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
│   │   ├── routes.py           # GET /health, POST /ingest, GET /incidents/{fingerprint}
│   │   └── schemas.py          # Request/response contracts
│   ├── core/
│   │   ├── database.py         # Async SQLAlchemy engine & pgvector initialization
│   │   ├── fingerprint.py      # Regex log normalizer & deterministic SHA-256 hasher
│   │   └── models.py           # Incident & CodeChunk ORM models
│   ├── worker/
│   │   └── tasks.py            # ARQ background worker executing the LangGraph agent
│   └── main.py                 # FastAPI entrypoint with lifespan DB initialization
├── sample_service/
│   ├── auth.py                 # Sample service with reproducible runtime faults
│   └── runbooks/
│       └── auth_outage.md      # Operational runbook indexed into pgvector
├── scripts/
│   └── index_repo.py           # Overlapping line chunker & MiniLM vector indexer
├── evals/
│   ├── dataset.json            # Synthetic production incident evaluation cases
│   └── run_eval.py             # Automated accuracy & latency benchmark runner
├── tests/
│   ├── test_agent.py           # End-to-end LangGraph diagnosis integration test
│   └── test_fingerprint.py     # Unit tests for log normalization & hash determinism
├── docker-compose.yml          # PostgreSQL (pgvector:pg16) & Redis 7 services
├── pytest.ini
└── requirements.txt
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
Create a `.env` file in the root directory to enable live LLM synthesis via Gemini. If omitted, the agent automatically uses its built-in deterministic fallback synthesizer:
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
# Terminal 1: FastAPI Server
uvicorn app.main:app --reload

# Terminal 2: ARQ Background Worker
arq app.worker.tasks.WorkerSettings
```

### 5. Ingest a Crash Log & Fetch Diagnosis
```powershell
$body = '{"service_name":"auth-service","raw_log":"2026-11-23T19:15:00Z ERROR ZeroDivisionError: division by zero in calculate_token_quota at sample_service/auth.py line 5"}'
$res = Invoke-RestMethod -Uri "http://localhost:8000/ingest" -Method Post -ContentType "application/json" -Body $body

Start-Sleep -Seconds 4
Invoke-RestMethod -Uri "http://localhost:8000/incidents/$($res.fingerprint)" -Method Get
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
* **Sandboxed Read-Only Tooling:** File inspection tools enforce root-path resolution checks (`Path.resolve()`) to prevent directory traversal, while Git inspection runs strictly read-only `git log` commands.
* **Resilient Dual-Mode Inference:** Enforces structured Pydantic outputs (`TriageResult` and `DiagnosisReport`) on Gemini `gemini-2.5-flash` calls while supporting zero-dependency offline execution for CI testing.