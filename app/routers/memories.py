from fastapi import APIRouter

from app.db import get_conn
from app.models import MemoryOut
from app.services.compression import compress_stale_memories
from app.services.scoring import recompute_all_decay_scores

router = APIRouter()


@router.get("/memories", response_model=list[MemoryOut])
def list_memories():
    """Full memory listing for the dashboard, most recently created first."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, content, memory_type, trust_level, status, supersedes_id,
                   compressed_from, reasoning_trace, access_count, decay_score,
                   created_at, last_accessed_at
            FROM memories
            ORDER BY created_at DESC
            """
        ).fetchall()

    cols = [
        "id", "content", "memory_type", "trust_level", "status", "supersedes_id",
        "compressed_from", "reasoning_trace", "access_count", "decay_score",
        "created_at", "last_accessed_at",
    ]
    return [MemoryOut(**dict(zip(cols, row))) for row in rows]


@router.post("/memories/rescore")
def rescore():
    """Recompute recency/frequency-based decay scores for all active memories."""
    with get_conn() as conn:
        updated = recompute_all_decay_scores(conn)
    return {"updated": updated}


@router.post("/memories/compress")
def compress():
    """Trigger a compression pass over stale, low-score memory clusters."""
    with get_conn() as conn:
        created = compress_stale_memories(conn)
    return {"compressed_groups": created}
