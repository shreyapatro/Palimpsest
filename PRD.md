# Palimpsest — Product Requirements Document

**Track:** Track 1 — MemoryAgent
**Hackathon:** Global AI Hackathon Series with Qwen Cloud
**Deadline:** July 10, 2026, 2:30 AM GMT+5:30
**Builder:** Solo (Shreya)
**Status:** Draft v1 — scoped for a 3-day solo build

---

## 1. Problem Statement

Most "memory agent" demos treat memory as a write-once log: the agent stores everything it's told and retrieves the top-k nearest neighbors at query time. This looks impressive for a few turns but breaks down in exactly the ways real memory systems have to handle:

- **Contradiction.** Users change their minds, correct themselves, or state something that conflicts with an earlier memory. A naive system either keeps both (confusing the agent) or blindly overwrites (losing legitimate nuance, e.g. "hates spicy food in general" vs. "loves this one spicy dish").
- **Context pressure.** Memory stores grow unbounded, but the context window doesn't. Most systems handle this with a crude recency cutoff or top-k similarity search, silently dropping anything that falls outside — with no visibility into what was dropped or why.
- **Trust.** Not everything a user (or an attacker across sessions) says should be treated as equally reliable. Few systems distinguish between a stated fact/preference and an attempted instruction injection.

Palimpsest is a memory agent built to make these three problems — and the agent's handling of them — **visible**, not hidden behind a chat window.

---

## 2. Goals

### Must Have (core demo, non-negotiable)
1. **Ingestion & classification** — every incoming message is classified (`fact`, `preference`, `instruction`) via Qwen, with structured JSON output.
2. **Conflict-aware revision** — new memories are checked against existing ones via embedding similarity; genuine conflicts are adjudicated by Qwen (`supersede` / `exception` / `evolve`), with a stored, human-readable reasoning trace.
3. **Decay scoring** — every memory has a live-computed score (`recency × frequency × relevance-to-current-query`), recalculated at retrieval time.
4. **Memory-pressure compression** — low-score, stale memory clusters are periodically summarized by Qwen into a single compressed node ("forgetting via compression," not deletion — originals are archived, not destroyed).
5. **Context-budget-aware retrieval** — a hard, small top-k limit simulates a real constrained context window; retrieval is always shown against this budget.
6. **Visible memory dashboard** — a UI panel showing every memory's status (active/superseded/archived/compressed), decay score, and reasoning trace. This is the actual centerpiece of the demo, not an afterthought.
7. **Deployed on Alibaba Cloud** — FastAPI backend on ECS, PostgreSQL + pgvector on ApsaraDB RDS, same VPC/region.

### Should Have (cheap, adds real depth if time allows)
8. **Trust tagging** — messages classified as `instruction` are tagged `untrusted` and never silently promoted to influence agent behavior; this is a lightweight rule on top of #1, not a full quarantine system.

### Won't Have (this cycle)
- Full adversarial memory-poisoning defense system (deferred — too much scope for 3 days).
- `qwen3-rerank` reranking step (stretch goal only, Day 3).
- MCP tool-server exposure of the memory store (stretch goal only; plain function-calling substitutes if time allows).
- Multi-user auth / multi-tenant support (single demo user is fine).

---

## 3. Demo Domain

A deliberately mundane **personal life-admin assistant** (food preferences, schedule habits, recurring small requests). The domain is intentionally low-stakes so 100% of judge attention goes to the memory engine, not the use case.

---

## 4. Users

- **Primary:** hackathon judges evaluating technical depth, architecture, and problem value.
- **Secondary (framing only):** a hypothetical end user chatting with a personal assistant across many short sessions.

---

## 5. Architecture

```
User message
   │
   ▼
[qwen3.6-flash, structured output] → classify: fact / preference / instruction
   │                                → tag trust_level: trusted / untrusted
   ▼
[text-embedding-v3] → embed content
   │
   ▼
[pgvector similarity search] → candidate conflicting/related memories
   │
   ▼
[qwen3.7-max, thinking mode] → conflict adjudication → structured JSON:
   │   {action: supersede | exception | evolve | none, reason: "..."}
   ▼
[Postgres write] → memory row: content, embedding, type, trust_level,
   │                status, decay_score, reasoning_trace, timestamps
   ▼
[Decay scoring — plain Python, no LLM call]
   │   score = w1·recency + w2·frequency + w3·query_relevance
   ▼
[Compression job — qwen3.7-plus] → summarizes low-score clusters
   │                               into single compressed memory nodes
   ▼
[Retriever] → top-k under fixed context budget
   │
   ▼
[qwen3.7-plus] → final response, using retrieved memories as context
   │
   ▼
[Dashboard UI] → live view of all memories, statuses, scores, reasoning traces
```

**Backend:** FastAPI (Python)
**Database:** ApsaraDB RDS for PostgreSQL + pgvector extension (HNSW index, cosine similarity)
**LLM/embeddings:** Qwen Cloud API (OpenAI-compatible SDK), models: `qwen3.6-flash`, `qwen3.7-plus`, `qwen3.7-max`, `text-embedding-v3`
**Deployment:** Alibaba Cloud ECS (Docker container) + RDS, same VPC/region
**Frontend:** single-page HTML/JS (chat pane + memory dashboard pane) served by FastAPI — kept deliberately simple given the timeline

---

## 6. Data Model (core table)

```sql
CREATE TABLE memories (
    id              BIGSERIAL PRIMARY KEY,
    content         TEXT NOT NULL,
    embedding       VECTOR(1024),
    memory_type     TEXT NOT NULL,       -- fact | preference | instruction
    trust_level     TEXT NOT NULL DEFAULT 'trusted',  -- trusted | untrusted
    status          TEXT NOT NULL DEFAULT 'active',   -- active | superseded | archived | compressed
    supersedes_id   BIGINT REFERENCES memories(id),
    compressed_from BIGINT[],            -- source memory ids, if this is a compressed node
    reasoning_trace TEXT,                 -- human-readable explanation of the last decision made about this memory
    access_count    INT NOT NULL DEFAULT 0,
    decay_score     FLOAT NOT NULL DEFAULT 1.0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON memories USING hnsw (embedding vector_cosine_ops);
```

---

## 7. API Endpoints (draft)

| Endpoint | Method | Purpose |
|---|---|---|
| `/ingest` | POST | Submit a new message; runs classify → embed → conflict-check → write |
| `/chat` | POST | Submit a query; runs retrieval → response generation |
| `/memories` | GET | List all memories with status/score/trace, for the dashboard |
| `/memories/compress` | POST | Manually trigger a compression pass (also runnable on a schedule) |
| `/health` | GET | Deployment health check |

---

## 8. Judging Criteria Mapping

| Criterion | Weight | How Palimpsest addresses it |
|---|---|---|
| Technical Depth & Engineering | 30% | Custom conflict-adjudication pipeline, decay-scoring engine, compression job — not just an API call wrapped in a chat UI |
| Innovation & AI Creativity | 30% | Modular pipeline (classify → embed → conflict-check → score → compress → retrieve), each stage independently testable |
| Problem Value & Impact | 25% | Memory conflict resolution and context-budget triage are real, unresolved production problems for any long-running agent |
| Presentation & Documentation | 15% | Live dashboard visualizes internal logic directly; architecture diagram, README, and this PRD document the system clearly |

---

## 9. Timeline (3-day solo sprint)

- **Day 1 (Jul 7):** Alibaba Cloud account + ECS + RDS provisioning, Qwen API key + coupon claimed, DB schema live, FastAPI skeleton, ingestion/classification/embedding pipeline working locally.
- **Day 2 (Jul 8):** Conflict detection, decay scoring, compression job, retrieval, chat endpoint wired end-to-end; basic dashboard UI.
- **Day 3 (Jul 9):** Deploy to ECS, verify end-to-end on cloud, write README + architecture diagram, record proof-of-deployment clip + 3-minute demo video, final polish. Submit with buffer before the Jul 10, 2:30 AM IST cutoff.

## 10. Risks

- **Time is the binding constraint**, not technical difficulty — every "should have" gets cut first if Day 2 runs long.
- **Cloud provisioning delays** (account verification, RDS instance spin-up) eat into Day 1 if not started immediately.
- **Qwen coupon activation lag** — start building against free-tier quota immediately rather than waiting on the $40 coupon to land.
