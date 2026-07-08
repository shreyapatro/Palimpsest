import asyncio

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_schema
from app.routers import chat, ingest, memories
from app.scheduler import maintenance_loop

app = FastAPI(title="Palimpsest", version="0.1.0")

app.include_router(ingest.router)
app.include_router(chat.router)
app.include_router(memories.router)


@app.on_event("startup")
def startup():
    init_schema()
    # Fire-and-forget background task: periodic decay rescoring + compression.
    # Manual /memories/rescore and /memories/compress endpoints still work too,
    # e.g. for triggering it on-camera during a demo.
    asyncio.create_task(maintenance_loop())


@app.get("/health")
def health():
    return {"status": "ok"}


# Mounted last so it doesn't shadow the API routes above; serves static/index.html at "/"
app.mount("/", StaticFiles(directory="static", html=True), name="static")
