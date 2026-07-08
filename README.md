# Palimpsest

**A memory agent that revises itself — not just remembers.**

Built for the **Global AI Hackathon Series with Qwen Cloud** — Track 1: MemoryAgent.

> A palimpsest is a manuscript that's been written on, scraped clean, and written on again — the old text still faintly visible beneath the new. That's the idea here: memory that gets actively revised, compressed, and reasoned about, not just piled up.

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

- **Conflict-aware memory revision** — new input is checked against existing memories; genuine contradictions are adjudicated (superseded, treated as an exception, or logged as an evolving preference), with a plain-English reasoning trace stored alongside the decision.
- **Decay-scored retrieval under a fixed context budget** — every memory has a live score (recency × frequency × relevance); only the top-k highest-scoring memories make it into any given response.
- **Compression, not deletion** — low-score, stale memory clusters get summarized into a single compressed node instead of being thrown away. The original memories are archived and still queryable directly.
- **Trust tagging** — messages that look like instructions rather than facts/preferences are flagged and never silently promoted to influence agent behavior.
- **Live memory dashboard** — every memory's status, score, and reasoning trace, visible in real time.

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
pgvector similarity search → candidate related/conflicting memories
   │
   ▼
Qwen (qwen3.7-max, thinking mode) → conflict adjudication (structured JSON)
   │
   ▼
PostgreSQL write → status, decay_score, reasoning_trace, timestamps
   │
   ▼
Decay scoring (plain Python) → recency × frequency × relevance
   │
   ▼
Qwen (qwen3.7-plus) → compression job for low-score clusters
   │
   ▼
Top-k retrieval under fixed budget → Qwen (qwen3.7-plus) → response
   │
   ▼
Dashboard UI → live memory states + reasoning traces
```

See [`PRD.md`](./PRD.md) for the full product spec, data model, and API contract.
See [`architecture.png`](./docs/architecture.png) for the visual diagram (referenced in the submission).

---

## Tech Stack

| Layer | Choice |
|---|---|
| LLM / embeddings | Qwen Cloud API (`qwen3.6-flash`, `qwen3.7-plus`, `qwen3.7-max`, `text-embedding-v3`) |
| Backend | FastAPI (Python) |
| Database | ApsaraDB RDS for PostgreSQL + `pgvector` (HNSW index, cosine similarity) |
| Deployment | Alibaba Cloud ECS (Docker) + RDS, same VPC/region |
| Frontend | Single-page HTML/JS (chat pane + memory dashboard) |

---

## Getting Started (local dev)

```bash
git clone <this-repo-url>
cd palimpsest
cp .env.example .env   # fill in DASHSCOPE_API_KEY and DATABASE_URL
pip install -r requirements.txt --break-system-packages
uvicorn app.main:app --reload
```

Environment variables (`.env`):
```
DASHSCOPE_API_KEY=your_qwen_cloud_api_key
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
DATABASE_URL=postgresql://user:password@localhost:5432/palimpsest
```

---

## Deployment (Alibaba Cloud)

1. Provision an **ApsaraDB RDS for PostgreSQL** instance (v14+), install the `pgvector` extension via the console's Plugin Marketplace.
2. Provision an **ECS instance** in the same region/VPC as the RDS instance.
3. Build and run the Docker container on ECS, pointing `DATABASE_URL` at the RDS instance's internal endpoint.
4. Confirm connectivity: `curl http://<ecs-ip>:8000/health`

Proof-of-deployment recording: [`docs/deployment-proof.mp4`](./docs/deployment-proof.mp4) *(link added at submission time)*

---

## API Overview

| Endpoint | Method | Purpose |
|---|---|---|
| `/ingest` | POST | Submit a message; runs classify → embed → conflict-check → write |
| `/chat` | POST | Submit a query; runs retrieval → response generation |
| `/memories` | GET | List all memories with status/score/trace, for the dashboard |
| `/memories/compress` | POST | Trigger a compression pass |
| `/health` | GET | Health check |

---

## Demo Video

*(Link added at submission time — ~3 minute walkthrough showing conflict revision and memory compression live.)*

---

## License

This project is licensed under the [MIT License](./LICENSE).

---

## Hackathon Details

- **Track:** Track 1 — MemoryAgent
- **Event:** Global AI Hackathon Series with Qwen Cloud
- **Deployment:** Alibaba Cloud (ECS + ApsaraDB RDS for PostgreSQL)
