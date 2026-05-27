import asyncpg
import os

db = None

async def connect_db():
    global db

    db = await asyncpg.connect(
        os.getenv("DATABASE_URL")
    )

    print("[DATABASE] Connecté à PostgreSQL")
