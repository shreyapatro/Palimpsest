import asyncio

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import get_conn, init_schema
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
    """
    Actually verifies the database connection rather than just confirming the
    process is alive — useful once deployed, to distinguish 'the container is
    running' from 'the container can actually do its job'.
    """
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
        return {"status": "ok", "database": "reachable"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "unreachable", "detail": str(e)},
        )


# Mounted last so it doesn't shadow the API routes above; serves static/index.html at "/"
app.mount("/", StaticFiles(directory="static", html=True), name="static")