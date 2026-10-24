import asyncio
import os
import sys
from decimal import Decimal

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, "src", ".env"))
load_dotenv(os.path.join(ROOT, ".env"))

import game_service as gs
from database import close_db, get_or_create_user, get_pool, init_db
from game_logic import GameError

TEST_ID = 999000111


async def cleanup():
    pool = get_pool()
    await pool.execute("DELETE FROM games WHERE user_id = $1", TEST_ID)
    await pool.execute("DELETE FROM users WHERE telegram_id = $1", TEST_ID)


async def main():
    await init_db()
    try:
        await cleanup()
        user = await get_or_create_user(TEST_ID, "smoke_test")
        print("баланс при создании:", user["balance"])

        # Два одновременных старта: должен пройти ровно один
        results = await asyncio.gather(
            gs.start_game(TEST_ID, 2, 1, Decimal("10.00")),
            gs.start_game(TEST_ID, 2, 1, Decimal("10.00")),
            return_exceptions=True,
        )
        ok = [r for r in results if isinstance(r, dict)]
        bad = [r for r in results if isinstance(r, GameError)]
        print("одновременные старты: успешных", len(ok), "отказов", len(bad))
        assert len(ok) == 1 and len(bad) == 1
        print("старт:", ok[0])

        for _ in range(3):
            r = await gs.take_step(TEST_ID)
            print("шаг:", r)
            if r["status"] != "active":
                break
        else:
            print("забрать:", await gs.cash_out(TEST_ID))

        print("рейтинг:", (await gs.leaderboard(3)))
        print("бонус:", await gs.claim_daily_bonus(TEST_ID))
        try:
            await gs.claim_daily_bonus(TEST_ID)
        except GameError as e:
            print("повторный бонус отклонён:", e)

        total = await get_pool().fetchval(
            "SELECT balance FROM users WHERE telegram_id = $1", TEST_ID
        )
        print("итоговый баланс:", total)
    finally:
        await cleanup()
        await close_db()


asyncio.run(main())
