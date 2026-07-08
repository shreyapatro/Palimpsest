from collections import defaultdict

import numpy as np

from app.config import settings
from app.qwen_client import chat_completion, embed

COMPRESSION_SYSTEM_PROMPT = """You compress a group of low-value, stale memories held by \
a personal assistant into a single concise summary memory. Preserve any concrete facts \
or preferences that are still potentially useful; drop redundant or one-off details. \
Respond with a single short paragraph, no preamble, no markdown."""


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _cluster_by_similarity(items: list[tuple]) -> list[list[tuple]]:
    """
    Greedy single-link clustering: repeatedly take an unclustered memory as a seed
    and pull in every other unclustered memory whose embedding is similar enough,
    rather than grouping purely by memory_type. items: list of (id, content, embedding_np).
    """
    unclustered = list(items)
    clusters = []

    while unclustered:
        seed = unclustered.pop(0)
        cluster = [seed]
        remaining = []
        for item in unclustered:
            similarity = _cosine_similarity(seed[2], item[2])
            if similarity >= settings.cluster_similarity_threshold:
                cluster.append(item)
            else:
                remaining.append(item)
        unclustered = remaining
        clusters.append(cluster)

    return clusters


def compress_stale_memories(conn) -> list[dict]:
    """
    Finds stale (low decay-score) active memories, clusters them by actual embedding
    similarity within each memory_type (not just by type alone — two unrelated stale
    preferences don't get mashed into one incoherent summary), and summarizes each
    qualifying cluster into a single new 'compressed' memory node. Originals are marked
    'archived' and linked via compressed_from, not deleted, so they remain queryable
    directly if needed.
    """
    created = []

    rows = conn.execute(
        """
        SELECT id, memory_type, content, embedding
        FROM memories
        WHERE status = 'active' AND decay_score < %s
        """,
        (settings.compression_score_threshold,),
    ).fetchall()

    by_type = defaultdict(list)
    for mem_id, memory_type, content, embedding in rows:
        by_type[memory_type].append((mem_id, content, embedding.to_numpy()))

    for memory_type, items in by_type.items():
        for cluster in _cluster_by_similarity(items):
            if len(cluster) < settings.compression_min_cluster_size:
                continue

            ids = [c[0] for c in cluster]
            contents = [c[1] for c in cluster]
            joined = "\n".join(f"- {c}" for c in contents)

            summary = chat_completion(
                model=settings.model_compression,
                system_prompt=COMPRESSION_SYSTEM_PROMPT,
                user_prompt=f"Memory type: {memory_type}\nMemories to compress:\n{joined}",
            )
            summary_embedding = embed(summary)

            new_id = conn.execute(
                """
                INSERT INTO memories (content, embedding, memory_type, trust_level, status,
                                       compressed_from, reasoning_trace, decay_score)
                VALUES (%s, %s, %s, 'trusted', 'compressed', %s, %s, 1.0)
                RETURNING id
                """,
                (
                    summary,
                    summary_embedding,
                    memory_type,
                    ids,
                    f"Compressed from {len(ids)} similar stale memories "
                    f"(score below {settings.compression_score_threshold}, "
                    f"cluster similarity >= {settings.cluster_similarity_threshold}).",
                ),
            ).fetchone()[0]

            conn.execute(
                "UPDATE memories SET status = 'archived' WHERE id = ANY(%s)", (ids,)
            )

            created.append({"new_memory_id": new_id, "compressed_from": ids, "summary": summary})

    return created
