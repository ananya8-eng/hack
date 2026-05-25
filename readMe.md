# Aegis — AI-Powered Financial Intelligence Platform

An adaptive financial filing intelligence platform for **10-K / 10-Q PDFs**. Upload a filing, run a LangGraph pipeline for risk and sentiment analysis, optionally enrich with SEC EDGAR peer filings, and explore results in a Next.js dashboard with a citation-backed RAG chatbot.

## What it does

- **Upload & ingest** — PDF text extraction (PyMuPDF), narrative section discovery, chunking, and Qdrant Cloud indexing via the embedding service.
- **Map-reduce analysis** — Financial intelligence agent analyzes sections in parallel, then synthesizes risks, severity, sentiment, and summaries.
- **Agentic scraping** — When context is thin or the user asks for comparisons, the graph plans targets, fetches filings via `sec-edgar-downloader`, and validates sources before re-analysis.
- **Comparative insights** — Cross-filing benchmarks, tone shifts, and peer comparisons grounded in retrieved text (no fabricated financial tables).
- **RAG chat** — Ask questions about a completed report with chunk citations; comparison-style questions can trigger on-demand peer scraping.
- **Guardrails** — Input/output checks for scope, length, and safe LLM responses on upload and chat.

## Tech stack

| Layer | Technology |
|--------|------------|
| Frontend | Next.js 16, React 19, Tailwind CSS 4, Recharts |
| Backend | FastAPI, Uvicorn |
| Orchestration | LangGraph |
| LLM | Cloud APIs with fallback: **NVIDIA NIM → Grok → Hugging Face → Gemini** |
| Embeddings | Remote service (`embedding-server/`) or mock vectors locally |
| Vector DB | Qdrant Cloud (via `embedding-server/`) |
| PDF | PyMuPDF |
| SEC data | `sec-edgar-downloader` |

> **Note:** Local Ollama is not used by the current `LLMClient`. Configure at least one cloud API key in `.env` (see below).

## Prerequisites

- **Python** 3.10+ (3.11 recommended)
- **Node.js** 20+ and npm
- **API keys** — at least one of: `NVIDIA_API_KEY`, `GROK_API_KEY` / `XAI_API_KEY`, `HUGGINGFACE_API_KEY` / `HF_TOKEN`, `GEMINI_API_KEY` / `GOOGLE_API_KEY`
- **SEC EDGAR** — `SEC_EDGAR_EMAIL` (required by SEC fair-access policy when downloading filings)
- **Qdrant Cloud** credentials on the embedding host (see `embedding-server/.env.example`); use `USE_MOCK_EMBEDDINGS=true` only for local dev without Qdrant

## Quick start

### 1. Clone and open the project

```bash
cd hack
```

All commands below assume your shell is in the repository root (`hack/`).

### 2. Backend setup

```bash
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

Create `.env` in the project root (copy from the template below). **Do not commit `.env`.**

```bash
# Minimal example — set at least one LLM key and your SEC email
NVIDIA_API_KEY=your_key_here
SEC_EDGAR_EMAIL=you@example.com
SEC_EDGAR_COMPANY_NAME=YourOrgName
API_HOST=127.0.0.1
API_PORT=8000
CORS_ORIGINS=http://localhost:3000
```

Start the API:

```bash
python -m backend.main
```

Or with Uvicorn directly:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health) → `{"status":"ok",...}`

Interactive API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 3. Frontend setup

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The UI polls the backend while the LangGraph pipeline runs (default timeout 15 minutes — see `NEXT_PUBLIC_PIPELINE_POLL_TIMEOUT_MS`).

### 4. Run a filing analysis

1. Open the dashboard and upload a **PDF** (10-K or 10-Q).
2. Optionally set **company name** and a **focus query** (e.g. “Compare supply chain risk with AMD”).
3. Wait for status logs to reach `completed` (pipeline runs in the background after upload).
4. Review risks, sentiment, comparisons, and use the chat panel on the report.

Scraped SEC filings are stored under `./scraped_filings` (gitignored).

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `127.0.0.1` | FastAPI bind host |
| `API_PORT` | `8000` | FastAPI port |
| `CORS_ORIGINS` | `*` | Comma-separated origins for the Next.js app |
| `NVIDIA_API_KEY` | — | Primary LLM (NVIDIA integrate API) |
| `NVIDIA_MODEL` | `meta/llama-3.1-8b-instruct` | NVIDIA model id |
| `GROK_API_KEY` / `XAI_API_KEY` | — | xAI Grok fallback |
| `HUGGINGFACE_API_KEY` / `HF_TOKEN` | — | Hugging Face inference fallback |
| `HUGGINGFACE_MODEL` | `Qwen/Qwen2.5-3B-Instruct` | HF model id |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | — | Google Gemini fallback |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model |
| `LLM_DEFAULT_TIMEOUT` | `90` | Per-request LLM timeout (seconds) |
| `EMBEDDING_SERVICE_URL` | — | Embedding server base (e.g. `http://127.0.0.1:8088`) — **required for production** |
| `EMBEDDING_SERVICE_MODE` | `qdrant` | `qdrant`: `/embed` indexes into Qdrant; backend searches Qdrant directly |
| `EMBEDDING_SERVICE_PATH` | `/embed` | POST path to embed + store a chunk in Qdrant |
| `EMBEDDING_QUERY_PATH` | `/query` | POST path to embed a user search query (vectors only; backend searches Qdrant) |
| `QDRANT_URL` | — | Qdrant Cloud URL — **required on backend for search** |
| `QDRANT_API_KEY` | — | Qdrant Cloud API key |
| `QDRANT_COLLECTION` | `documents` | Collection name (must match embedding-server) |
| `EMBEDDING_BODY_FORMAT` | `text` | `text` = `{"text":"..."}` per request; `texts` = batch `{"texts":[...]}` |
| `EMBEDDING_SERVICE_API_KEY` | — | `X-API-Key` for the embedding service |
| `EMBEDDING_SERVICE_TIMEOUT` | `120` | HTTP timeout (seconds) for embedding batches |
| `USE_MOCK_EMBEDDINGS` | `true` | In-memory vectors only when `EMBEDDING_SERVICE_URL` is unset |
| `PRELOAD_EMBEDDINGS_ON_STARTUP` | `false` | Warm up embedding client at startup |
| `SEC_EDGAR_EMAIL` | — | **Required** for SEC downloads |
| `SEC_EDGAR_COMPANY_NAME` | `AegisFinancialAgent` | SEC downloader user-agent identity |
| `SCRAPED_FILINGS_DIR` | `./scraped_filings` | Local SEC filing cache |
| `GUARDRAILS_ENABLED` | `true` | Enable guardrail checks |

Frontend (`frontend/.env.local`):

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` | Backend base URL |
| `NEXT_PUBLIC_PIPELINE_POLL_TIMEOUT_MS` | `900000` | Max wait for pipeline (15 min) |

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Service health |
| `POST` | `/api/upload` | Upload PDF (`file`), optional `company_name`, `user_query` |
| `GET` | `/api/reports` | List reports |
| `GET` | `/api/reports/{id}` | Full report + analysis result |
| `GET` | `/api/reports/{id}/status` | Pipeline step + logs (for polling) |
| `POST` | `/api/reports/trigger` | Re-run or extend analysis on an existing report |
| `POST` | `/api/chat` | RAG / comparison chat (`report_id`, `message`) |

## Pipeline flow (LangGraph)

```text
Upload PDF
    → discover sections → chunk & index (Qdrant)
    → map-reduce financial analysis
    → [optional] scrape SEC / web → validate → comparative re-analysis
    → finalize → dashboard + chat
```

**Agents**

- **Financial intelligence agent** — Risk/sentiment analysis, scrape planning, comparative re-analysis.
- **Validator agent** — Filters scraped content (company, filing type, freshness, relevance).

**Deterministic modules** — PDF extraction, section extraction, chunking, embeddings, Qdrant storage, scraper execution.

## Project structure

## Docker

Embedding runs on a **separate machine** — set `EMBEDDING_SERVICE_URL` in `.env` to that host (e.g. ngrok URL). The compose file only runs **backend + frontend**.

```bash
cp .env.docker.example .env
# Edit .env — remote EMBEDDING_SERVICE_URL, Qdrant, LLM keys

docker compose build
docker compose up
```

Optional **local** embedding (only if not using a remote host):

```bash
docker compose -f docker-compose.yml -f docker-compose.embedding.yml --profile embedding up
```

| Service | Host port | Image |
|---------|-----------|--------|
| Frontend | 3000 | `aegis-frontend:latest` |
| Backend API | 8000 | `aegis-backend:latest` |

## Deploy to Render

1. Push the repo to GitHub (`render.yaml` defines two Docker web services).
2. In [Render Blueprints](https://dashboard.render.com/select-repo?type=blueprint), connect the repo and apply the blueprint.
3. In the Render dashboard, set secret env vars from `render.env.example` (especially `EMBEDDING_SERVICE_URL` pointing at your remote embedding host).
4. After deploy: open **aegis-web** URL; the API is **aegis-api** (`RENDER_EXTERNAL_URL` is wired into the frontend build).

Authorize the **Render MCP** plugin in Cursor to create or update services from the agent (`list_workspaces` → select workspace → `create_web_service` with `runtime: docker`).

## Split deployment (AWS + embedding host)

1. On a **dedicated machine** (office server, GPU box, etc.): run `embedding-server/` with Docker Compose (nginx on port **8088**). See `embedding-server/README.md`.
2. On **EC2**: deploy FastAPI + frontend only; set `EMBEDDING_SERVICE_URL=http://<embedding-host>:8088` and matching `EMBEDDING_SERVICE_API_KEY`. Set `USE_MOCK_EMBEDDINGS=false`.
3. Restrict security groups so only the EC2 instance can reach port 8088 on the embedding host.

```text
hack/
├── embedding-server/    # BGE model + nginx (separate machine)
├── backend/
│   ├── agents/          # financial_agent, validator, llm_client, map-reduce
│   ├── graph/           # langgraph_flow.py
│   ├── extraction/      # section discovery & models
│   ├── ingestion/       # pdf_extractor
│   ├── rag/             # chunking, retrieval, citations, chat comparison
│   ├── tools/           # chroma, embeddings, scraper, scrape_plan
│   ├── guardrails/
│   ├── tests/
│   ├── config.py
│   └── main.py          # FastAPI app
├── frontend/
│   └── app/             # Next.js dashboard UI
├── requirements.txt
├── .env                 # local secrets (not in git)
└── readMe.md
```

## Tests

From the repo root with the venv active:

```bash
pip install pytest
python -m pytest backend/tests -q
```

Tests cover guardrails, section extraction, LLM JSON/fallback, map-reduce, scraper planning, and embeddings/Chroma integration (mock embeddings where applicable).

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| LLM errors / empty analysis | At least one API key in `.env`; watch backend logs for provider fallback order |
| Slow indexing / empty vectors | `EMBEDDING_SERVICE_URL` reachable from EC2; embedding host `curl :8088/health`; API keys match |
| SEC scrape failures | `SEC_EDGAR_EMAIL` set; network access; ticker/company name in upload metadata |
| Frontend cannot reach API | `NEXT_PUBLIC_API_BASE_URL` matches `API_HOST`/`API_PORT`; `CORS_ORIGINS` includes `http://localhost:3000` |
| Upload blocked | Guardrails — keep queries financial and within length limits |

## License & attribution

Built for the Financial Analysis Platform hackathon. SEC EDGAR data is subject to [SEC fair access](https://www.sec.gov/os/webmaster-faq#developers) requirements — use a valid contact email and reasonable request rates.
