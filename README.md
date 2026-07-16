# Palimpsest

**A memory agent that revises itself — not just remembers.**

A personal project exploring what a genuinely self-maintaining memory system looks like for an LLM agent, built on the Qwen Cloud API. Originally scoped around a hackathon prompt (Qwen Cloud's MemoryAgent track), but built and finished independently as a portfolio project.

> A palimpsest is a manuscript that's been written on, scraped clean, and written on again — the old text still faintly visible beneath the new. That's the idea here: memory that gets actively revised, compressed, and reasoned about, not just piled up.

**Live demo:** [palimpsest-9euo.onrender.com](https://palimpsest-9euo.onrender.com) — dashboard at `/`, interactive API docs at `/docs`. Hosted on Render's free tier, so the first request after a period of inactivity may take 30-60 seconds to wake up.

---

## Why this exists

Most memory-agent demos accumulate. They store everything and retrieve the nearest neighbors. What they don't show is what happens when:

- A user's stated preference **contradicts** an earlier one — does the agent notice, and how does it decide what to believe now?
- The memory store grows past what fits in the context window — what gets dropped, what gets compressed, and can you actually *see* that decision happening?
- Someone tries to slip in something that looks like an instruction rather than a fact or preference — does it get treated with appropriate caution?

Palimpsest makes all three of these visible, live, in a dashboard — instead of hiding them behind a chat window.

![Palimpsest architecture](./docs/architecture.png)

---

## Features

- **Conflict-aware memory revision** — new input is checked against every sufficiently-similar existing memory (not just the closest one); genuine contradictions are adjudicated (superseded, treated as an exception, or logged as an evolving preference), with a plain-English reasoning trace stored alongside each decision.
- **Decay-scored retrieval under a fixed context budget** — every memory has a live score (recency × frequency × relevance); only the top-k highest-scoring memories make it into any given response.
- **Compression, not deletion** — stale memories are clustered by actual embedding similarity (not just by type) and summarized into a single compressed node instead of being thrown away. The originals are archived and still queryable directly.
- **Trust boundary, enforced at retrieval** — messages that look like instructions rather than facts/preferences are flagged `untrusted` and stored for transparency, but are excluded from the context sent to the LLM — so a memory-poisoning attempt can't influence behavior just by sitting in the database.
- **Background maintenance loop** — decay rescoring and compression run automatically on an interval, not just when manually triggered.
- **Resilient Qwen Cloud calls** — retry with exponential backoff on transient failures (rate limits, timeouts, momentary API hiccups), without retrying on non-retryable errors like auth/permission failures.
- **Live memory dashboard** — every memory's status, score, and reasoning trace, visible in real time, including a literal "ghost" view of what a memory superseded.

---

## Architecture

```
User message
   │
   ▼
Qwen (qwen3.6-flash) → classify: fact / preference / instruction + trust tag
   │
   ▼
Qwen (text-embedding-v3) → embed content
   │
   ▼
pgvector similarity search → up to N candidate related/conflicting memories
   │
   ▼
Qwen (qwen3.7-max, thinking mode) → conflict adjudication per candidate (structured JSON)
   │
   ▼
PostgreSQL write → status, decay_score, reasoning_trace, timestamps
   │
   ▼
Decay scoring (plain Python) → recency × frequency × relevance
   │
   ▼
Qwen (qwen3.7-plus) → similarity-clustered compression for low-score memories
   │
   ▼
Top-k retrieval under fixed budget, trusted-only → Qwen (qwen3.7-plus) → response
   │
   ▼
Dashboard UI → live memory states + reasoning traces
```

See [`PRD.md`](./PRD.md) for the full product spec, data model, and API contract.
See [`docs/architecture.svg`](./docs/architecture.svg) for the source diagram.

---

## Tech Stack

| Layer | Choice |
|---|---|
| LLM / embeddings | Qwen Cloud API (`qwen3.6-flash`, `qwen3.7-plus`, `qwen3.7-max`, `text-embedding-v3`) |
| Backend | FastAPI (Python) |
| Database | PostgreSQL + `pgvector` (HNSW index, cosine similarity) — [Supabase](https://supabase.com) free tier includes pgvector by default |
| Deployment | Docker container on [Render](https://render.com) (free tier) |
| Frontend | Single-page HTML/JS (chat pane + memory dashboard) |

---

## Getting Started (local dev)

```bash
git clone <this-repo-url>
cd palimpsest
cp .env.example .env   # fill in DASHSCOPE_API_KEY and DATABASE_URL
docker-compose up --build
```

Then open `http://localhost:8000/` for the dashboard, or `http://localhost:8000/docs` for the interactive API docs.

Environment variables (`.env`):
```
DASHSCOPE_API_KEY=your_qwen_cloud_api_key
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

---

## Deployment

This project is designed to run as a single Docker container against any PostgreSQL instance with `pgvector` enabled — it isn't tied to a specific cloud provider. The path that requires the least setup:

1. **Database — [Supabase](https://supabase.com):** create a free project, enable the `vector` extension under Database → Extensions, and copy the connection string into `DATABASE_URL`.
2. **Backend — [Render](https://render.com):** create a new Web Service from this GitHub repo, choose "Docker" as the environment, and set the environment variables from `.env` in Render's dashboard.
3. Confirm connectivity: `curl https://<your-render-url>/health` should return `{"status": "ok", "database": "reachable"}`.

Any other Docker-capable host + Postgres-with-pgvector combination (ECS + RDS, a VPS, Railway, Fly.io, etc.) works the same way — only `DATABASE_URL` changes.

---

## API Overview

| Endpoint | Method | Purpose |
|---|---|---|
| `/ingest` | POST | Submit a message; runs classify → embed → conflict-check → write |
| `/chat` | POST | Submit a query; runs retrieval → response generation |
| `/memories` | GET | List all memories with status/score/trace, for the dashboard |
| `/memories/rescore` | POST | Manually trigger decay rescoring |
| `/memories/compress` | POST | Manually trigger a compression pass |
| `/health` | GET | Health check — verifies the database connection is actually reachable |

---

## License

This project is licensed under the [MIT License](./LICENSE).

---

## Background

Originally scoped around Track 1 (MemoryAgent) of a Qwen Cloud hackathon, focused on three things most memory-agent demos skip: conflict-aware revision, memory-pressure triage via compression instead of deletion, and a trust boundary against memory poisoning. Built independently end-to-end as a portfolio project.
