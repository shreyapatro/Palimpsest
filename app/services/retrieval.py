from app.config import settings
from app.qwen_client import embed
from app.services.scoring import full_score


def retrieve(conn, query: str, top_k: int | None = None):
    """
    Embed the query, pull candidate memories (active + compressed, never superseded/
    archived, and NEVER untrusted — this is the security boundary: content classified
    as an 'instruction' is stored for transparency/audit in the dashboard but must
    never be surfaced back into a prompt, or a memory-poisoning attempt could
    influence the agent's behavior simply by sitting in the database) scored by
    recency + frequency + query relevance, and return only the top_k under the fixed
    context budget. Also bumps access_count/last_accessed_at for whatever gets
    retrieved, so future scoring reflects that it was useful.
    """
    top_k = top_k or settings.context_budget_top_k
    query_embedding = embed(query)

    rows = conn.execute(
        """
        SELECT id, content, memory_type, last_accessed_at, access_count,
               1 - (embedding <=> %s) AS relevance
        FROM memories
        WHERE status IN ('active', 'compressed') AND trust_level = 'trusted'
        ORDER BY embedding <=> %s
        LIMIT 50
        """,
        (query_embedding, query_embedding),
    ).fetchall()

    scored = []
    for mem_id, content, memory_type, last_accessed_at, access_count, relevance in rows:
        score = full_score(last_accessed_at, access_count, relevance)
        scored.append((score, mem_id, content, memory_type))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    if top:
        ids = [t[1] for t in top]
        conn.execute(
            """
            UPDATE memories
            SET access_count = access_count + 1, last_accessed_at = now()
            WHERE id = ANY(%s)
            """,
            (ids,),
        )

    return [
        {"id": mem_id, "content": content, "memory_type": memory_type, "decay_score": score}
        for score, mem_id, content, memory_type in top
    ]
