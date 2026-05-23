# PG AI Platform

AI-powered PG/Coliving lead management — WhatsApp bot + voice calling + smart property matching.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python 3.12) |
| Database | Supabase (Postgres + pgvector + RLS) |
| Cache / Broker | Upstash Redis (prod) / Docker Redis (dev) |
| LLM | Gemini Flash (primary) + Groq (fallback) |
| Agent Framework | LangGraph |
| WhatsApp | Meta Cloud API |
| Voice (Phase 2) | Vapi + Exotel + Sarvam AI |
| Dashboard (Week 4) | Next.js 15 |
| Background Jobs | Celery |
| Local Dev | Docker Compose |

## Prerequisites

- Python 3.10+ (3.12 recommended)
- Node.js 18+ (for dashboard in Week 4)
- Docker Desktop
- Git
- A [Supabase](https://supabase.com) project

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/AyushSinghGhuraiya/pg-ai-platform.git
cd pg-ai-platform
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your Supabase URL + keys
```

### 3. Set up Supabase schema

1. Go to [Supabase Dashboard](https://app.supabase.com) → your project → SQL Editor
2. Run `scripts/schema.sql` (paste contents, click Run)
3. Run `scripts/seed_gurugram.sql`
4. Run `scripts/seed_first_tenant.sql`
5. Copy the tenant `id` from the output — you'll use it later

### 4. Start local services

```bash
# Start Redis only (fastest for dev)
docker compose up redis -d

# Or start everything
docker compose up -d
```

### 5. Set up Python virtualenv

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 6. Run the backend

```bash
cd backend
uvicorn main:app --reload
```

Visit:
- API: http://localhost:8000
- Health: http://localhost:8000/health
- Docs: http://localhost:8000/docs

## Project Structure

```
pg-ai-platform/
├── backend/
│   ├── api/            # FastAPI routers + webhook handlers
│   ├── agent/          # LangGraph conversation agent
│   ├── prompts/        # Prompt templates (versioned)
│   ├── services/       # External service clients (WhatsApp, Vapi, LLM…)
│   ├── db/             # Supabase query helpers
│   ├── workers/        # Celery tasks (retries, reminders, re-engagement)
│   ├── utils/          # Phone formatting, time helpers, logging
│   ├── main.py         # FastAPI app entry point
│   └── config.py       # Pydantic settings (loads .env)
├── scripts/
│   ├── schema.sql          # Full DB schema — run on Supabase
│   ├── seed_gurugram.sql   # 40+ Gurugram location aliases
│   └── seed_first_tenant.sql
├── docker/
│   ├── Dockerfile.backend
│   └── Dockerfile.worker
├── docker-compose.yml  # Redis + backend + worker
└── .env.example        # All required env vars (no secrets)
```

## Development Commands

```bash
# Run backend with hot reload
cd backend && uvicorn main:app --reload

# Run Celery worker
cd backend && celery -A workers.celery_app worker --loglevel=debug

# Lint
cd backend && ruff check .

# Type check
cd backend && mypy .

# Tests
cd backend && pytest
```

## Day-by-Day Roadmap

| Phase | Days | Focus |
|---|---|---|
| Foundation | 1-2 | Repo, schema, config (this setup) |
| Core Agent | 3-7 | LangGraph slot extraction + WhatsApp webhook |
| Property Search | 8-12 | Location resolver, property ranker, results sharing |
| Voice (Vapi) | 13-18 | Outbound calling, transcript processing |
| Dashboard | 19-25 | Next.js frontend |
| Production | 26-30 | Docker → Railway/Render, monitoring |

## Security Notes

- Never commit `.env` — it is in `.gitignore`
- Rotate Supabase keys if they are ever exposed
- RLS is enabled on all tables — add policies before going to production
