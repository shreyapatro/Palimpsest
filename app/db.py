from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

from app.config import settings

pool = ConnectionPool(
    conninfo=settings.database_url,
    min_size=1,
    max_size=10,
    # prepare_threshold=None disables server-side prepared statements. Required
    # when connecting through a transaction-mode connection pooler (e.g. Supabase's
    # pooler on port 6543, or any pgbouncer in transaction mode) — those poolers can
    # route each query to a different underlying Postgres backend, so a prepared
    # statement cached against one backend connection may not exist on the next one,
    # causing "prepared statement already exists" / "does not exist" errors.
    kwargs={"autocommit": True, "prepare_threshold": None},
)


def get_conn():
    """
    Context manager yielding a connection with pgvector types registered.
    Usage: with get_conn() as conn: ...
    """
    return _RegisteredConnection()


class _RegisteredConnection:
    def __enter__(self):
        self._ctx = pool.connection()
        conn = self._ctx.__enter__()
        register_vector(conn)
        return conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._ctx.__exit__(exc_type, exc_val, exc_tb)


def init_schema():
    """Apply schema.sql on startup. Safe to call repeatedly (idempotent DDL)."""
    with open("schema.sql", "r") as f:
        ddl = f.read()
    with pool.connection() as conn:
        # The vector extension must exist BEFORE we ask psycopg to register the
        # 'vector' type, and before the rest of the schema (which references it) runs.
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        register_vector(conn)
        conn.execute(ddl)
