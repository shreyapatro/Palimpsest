import json

from openai import OpenAI
from pgvector.psycopg import Vector

from app.config import settings

client = OpenAI(
    api_key=settings.dashscope_api_key,
    base_url=settings.dashscope_base_url,
)


def embed(text: str) -> Vector:
    """
    Return the embedding for a piece of text, wrapped as a pgvector Vector.
    IMPORTANT: pgvector's psycopg adapter only auto-converts its own Vector type
    (or numpy arrays) into Postgres's 'vector' type — a plain Python list gets sent
    as a generic double precision[] array instead, which breaks any <=> comparison
    against a vector column. Wrapping here means every call site downstream (insert,
    conflict-check, retrieval, compression) gets a value that dumps correctly.
    """
    resp = client.embeddings.create(
        model=settings.embedding_model,
        input=text,
    )
    return Vector(resp.data[0].embedding)


def structured_completion(
    model: str,
    system_prompt: str,
    user_prompt: str,
    thinking: bool = False,
) -> dict:
    """
    Call a Qwen model and force JSON-only output.
    The system prompt MUST instruct the model to return raw JSON with no
    markdown fences or preamble; we still defensively strip fences below.
    """
    extra_body = {}
    if thinking:
        extra_body["enable_thinking"] = True

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        extra_body=extra_body or None,
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


def chat_completion(model: str, system_prompt: str, user_prompt: str) -> str:
    """Plain (non-JSON) completion, used for the final user-facing response."""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content
