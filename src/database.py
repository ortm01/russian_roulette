import os

import asyncpg

_pool = None


async def init_db():
    global _pool
    _pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))


async def close_db():
    if _pool:
        await _pool.close()


async def get_or_create_user(telegram_id: int, username):
    """Создаёт игрока с балансом $100 при первом входе, иначе возвращает существующего."""
    async with _pool.acquire() as conn:
        return await conn.fetchrow(
            """
            INSERT INTO users (telegram_id, username)
            VALUES ($1, $2)
            ON CONFLICT (telegram_id)
            DO UPDATE SET username = EXCLUDED.username
            RETURNING telegram_id, username, balance
            """,
            telegram_id,
            username,
        )
