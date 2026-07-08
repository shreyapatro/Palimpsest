from datetime import datetime

from pydantic import BaseModel


class IngestRequest(BaseModel):
    content: str


class IngestResponse(BaseModel):
    memory_id: int
    memory_type: str
    trust_level: str
    conflict_action: str  # none | supersede | exception | evolve
    reasoning_trace: str | None


class ChatRequest(BaseModel):
    query: str


class RetrievedMemory(BaseModel):
    id: int
    content: str
    memory_type: str
    decay_score: float


class ChatResponse(BaseModel):
    answer: str
    memories_used: list[RetrievedMemory]


class MemoryOut(BaseModel):
    id: int
    content: str
    memory_type: str
    trust_level: str
    status: str
    supersedes_id: int | None
    compressed_from: list[int] | None
    reasoning_trace: str | None
    access_count: int
    decay_score: float
    created_at: datetime
    last_accessed_at: datetime
