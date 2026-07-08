import math
from datetime import datetime, timezone

# Tunable weights — sum doesn't need to be 1, scores are relative to each other.
RECENCY_WEIGHT = 0.4
FREQUENCY_WEIGHT = 0.3
RELEVANCE_WEIGHT = 0.3

RECENCY_HALF_LIFE_DAYS = 14.0


def _recency_component(last_accessed_at: datetime) -> float:
    now = datetime.now(timezone.utc)
    days_elapsed = max((now - last_accessed_at).total_seconds() / 86400.0, 0.0)
    # Exponential decay: score halves every RECENCY_HALF_LIFE_DAYS
    return 0.5 ** (days_elapsed / RECENCY_HALF_LIFE_DAYS)


def _frequency_component(access_count: int) -> float:
    # Diminishing returns on repeated access
    return min(math.log1p(access_count) / math.log1p(20), 1.0)


def base_decay_score(last_accessed_at: datetime, access_count: int) -> float:
    """Recency + frequency only — used for background scoring, independent of any query."""
    return (
        RECENCY_WEIGHT * _recency_component(last_accessed_at)
        + FREQUENCY_WEIGHT * _frequency_component(access_count)
    ) / (RECENCY_WEIGHT + FREQUENCY_WEIGHT)


def full_score(last_accessed_at: datetime, access_count: int, relevance: float) -> float:
    """Recency + frequency + query relevance — used at retrieval time."""
    return (
        RECENCY_WEIGHT * _recency_component(last_accessed_at)
        + FREQUENCY_WEIGHT * _frequency_component(access_count)
        + RELEVANCE_WEIGHT * relevance
    )


def recompute_all_decay_scores(conn) -> int:
    """Recalculate and persist base_decay_score for every active memory. Returns rows updated."""
    rows = conn.execute(
        "SELECT id, last_accessed_at, access_count FROM memories WHERE status = 'active'"
    ).fetchall()
    for mem_id, last_accessed_at, access_count in rows:
        score = base_decay_score(last_accessed_at, access_count)
        conn.execute(
            "UPDATE memories SET decay_score = %s WHERE id = %s", (score, mem_id)
        )
    return len(rows)
