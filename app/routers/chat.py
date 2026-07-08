from fastapi import APIRouter

from app.config import settings
from app.db import get_conn
from app.models import ChatRequest, ChatResponse, RetrievedMemory
from app.qwen_client import chat_completion
from app.services.retrieval import retrieve

router = APIRouter()

RESPONSE_SYSTEM_PROMPT = """You are a personal assistant. Use the memories provided \
below as context about the user, but only where relevant — don't force them in. \
If no memories are relevant, just answer normally."""


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    with get_conn() as conn:
        memories = retrieve(conn, payload.query)

        if memories:
            memory_block = "\n".join(f"- ({m['memory_type']}) {m['content']}" for m in memories)
            user_prompt = f"Known memories about the user:\n{memory_block}\n\nUser query: {payload.query}"
        else:
            user_prompt = payload.query

        answer = chat_completion(
            model=settings.model_response,
            system_prompt=RESPONSE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        return ChatResponse(
            answer=answer,
            memories_used=[
                RetrievedMemory(
                    id=m["id"],
                    content=m["content"],
                    memory_type=m["memory_type"],
                    decay_score=m["decay_score"],
                )
                for m in memories
            ],
        )
