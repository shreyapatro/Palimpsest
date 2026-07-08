from app.config import settings
from app.qwen_client import structured_completion

CONFLICT_SYSTEM_PROMPT = """You are adjudicating a potential conflict between two memories \
held by a personal assistant agent. Respond with ONLY a raw JSON object (no markdown \
fences, no preamble) matching this exact schema:

{
  "action": "supersede" | "exception" | "evolve" | "none",
  "reason": "<one or two plain-English sentences explaining the decision>"
}

Definitions:
- "supersede": the new memory directly contradicts the old one and should replace it \
  (the old one was simply wrong or outdated).
- "exception": both memories can be true simultaneously; the new one is a narrower \
  exception to the old, more general one (e.g. "dislikes spicy food" + "loves this \
  specific spicy dish" -> exception, keep both).
- "evolve": the user's preference has genuinely changed over time; the old memory \
  should be marked stale but the change itself is worth noting as a trend, not an error.
- "none": there is no real conflict; these memories are unrelated or fully compatible \
  and require no action.
"""


def find_conflict_candidates(conn, embedding, memory_type: str, exclude_id=None):
    """
    Vector-search existing active memories of the same type above the similarity
    threshold, capped at conflict_max_candidates. Each candidate triggers a full
    qwen3.7-max adjudication call (the most expensive model in the pipeline, run
    with thinking mode on) — capping this controls cost without losing the
    multi-candidate conflict resolution behavior itself.
    """
    rows = conn.execute(
        """
        SELECT id, content, 1 - (embedding <=> %s) AS similarity
        FROM memories
        WHERE status = 'active' AND memory_type = %s
          AND (%s::bigint IS NULL OR id != %s)
        ORDER BY embedding <=> %s
        LIMIT %s
        """,
        (embedding, memory_type, exclude_id, exclude_id, embedding, settings.conflict_max_candidates),
    ).fetchall()
    return [r for r in rows if r[2] >= settings.conflict_similarity_threshold]


def adjudicate(old_content: str, new_content: str) -> dict:
    """Ask Qwen (thinking mode) to decide how the new memory relates to the old one."""
    user_prompt = f'Existing memory: "{old_content}"\nNew memory: "{new_content}"'
    return structured_completion(
        model=settings.model_conflict,
        system_prompt=CONFLICT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        thinking=True,
    )


# Priority order for which single action gets reported at the top level when a new
# memory conflicts with more than one existing memory at once.
_ACTION_PRIORITY = {"supersede": 3, "evolve": 2, "exception": 1, "none": 0}


def resolve_conflicts(conn, candidates, new_content: str):
    """
    Adjudicate EVERY candidate above the similarity threshold, not just the closest
    one — a new memory can genuinely conflict with more than one existing memory
    (e.g. two separately-phrased old preferences that are both now outdated).
    Applies the correct status transition to each candidate independently, then
    returns a single summarized outcome for the API response:
      (top_level_action, combined_reasoning_trace, primary_supersedes_id)
    """
    if not candidates:
        return "none", None, None

    decisions = []
    primary_supersedes_id = None

    for candidate_id, candidate_content, _similarity in candidates:
        decision = adjudicate(candidate_content, new_content)
        action = decision.get("action", "none")
        reason = decision.get("reason", "")
        decisions.append((candidate_id, action, reason))

        if action in ("supersede", "evolve"):
            conn.execute(
                "UPDATE memories SET status = 'superseded' WHERE id = %s",
                (candidate_id,),
            )
            if primary_supersedes_id is None:
                primary_supersedes_id = candidate_id
        # "exception" and "none" leave that candidate untouched.

    top_action = max((d[1] for d in decisions), key=lambda a: _ACTION_PRIORITY.get(a, 0))

    # Combine reasoning traces from every candidate that actually had a real decision
    # (skip "none" entries so the trace stays focused on what actually happened).
    trace_lines = [f"#{cid}: {reason}" for cid, action, reason in decisions if action != "none"]
    combined_trace = " | ".join(trace_lines) if trace_lines else None

    return top_action, combined_trace, primary_supersedes_id
