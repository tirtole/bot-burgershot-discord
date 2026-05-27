import asyncpg
import os

db = None

async def connect_db():
    global db

    db = await asyncpg.connect(
        os.getenv("DATABASE_URL")
    )

    print("[DATABASE] Connecté à PostgreSQL")

await db.execute("""
CREATE TABLE IF NOT EXISTS services (
    user_id BIGINT PRIMARY KEY,
    start_timestamp BIGINT
)
""")

await db.execute(
    "INSERT INTO services VALUES($1, $2)",
    user_id,
    timestamp
)
