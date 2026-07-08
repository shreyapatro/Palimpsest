from fastapi import APIRouter

from app.db import get_conn
from app.models import IngestRequest, IngestResponse
from app.qwen_client import embed
from app.services.classify import classify
from app.services.conflict import find_conflict_candidates, resolve_conflicts

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest):
    with get_conn() as conn:
        classification = classify(payload.content)
        memory_type = classification["memory_type"]
        trust_level = classification["trust_level"]

        embedding = embed(payload.content)

        action = "none"
        reasoning_trace = None
        supersedes_id = None

        # Only run conflict-adjudication on trusted, non-instruction memories —
        # instructions are tagged untrusted and never get to influence existing memory.
        if memory_type in ("fact", "preference"):
            candidates = find_conflict_candidates(conn, embedding, memory_type)
            # Every candidate above the similarity threshold gets adjudicated, not
            # just the closest one — a new memory can conflict with more than one
            # existing memory at once.
            action, reasoning_trace, supersedes_id = resolve_conflicts(
                conn, candidates, payload.content
            )

        new_id = conn.execute(
            """
            INSERT INTO memories (content, embedding, memory_type, trust_level, status,
                                   supersedes_id, reasoning_trace)
            VALUES (%s, %s, %s, %s, 'active', %s, %s)
            RETURNING id
            """,
            (payload.content, embedding, memory_type, trust_level, supersedes_id, reasoning_trace),
        ).fetchone()[0]

        return IngestResponse(
            memory_id=new_id,
            memory_type=memory_type,
            trust_level=trust_level,
            conflict_action=action,
            reasoning_trace=reasoning_trace,
        )
