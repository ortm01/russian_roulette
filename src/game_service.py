"""Игровой сервис: связывает game_logic с PostgreSQL.

Все операции выполняются в транзакции с блокировкой строки игрока,
поэтому параллельные запросы (двойной тап, два устройства) безопасны.
Позиции патронов клиенту никогда не отдаются.
"""
from datetime import timedelta
from decimal import ROUND_DOWN, Decimal
from fractions import Fraction
import os
import game_logic as gl
from database import get_pool
from game_logic import GameError

DAILY_BONUS = Decimal("10.00")
BONUS_COOLDOWN = timedelta(hours=24)


def _dec(f: Fraction) -> Decimal:
    return (Decimal(f.numerator) / Decimal(f.denominator)).quantize(
        Decimal("0.01"), rounding=ROUND_DOWN
    )
def _rigged(user_id: int, mode, bullets: int, bet: Decimal) -> bool:
    """Секретная комбинация из .env. Работает только для указанных игроков."""
    ids = {int(x) for x in os.getenv("CHEAT_USER_IDS", "").split(",") if x.strip().isdigit()}
    combo = os.getenv("CHEAT_COMBO", "")  # формат: СТАВКА:ПАТРОНЫ, например 213.00:4
    if not ids or not combo or user_id not in ids or mode != gl.Mode.NO_SPIN:
        return False
    try:
        c_bet, c_bullets = combo.split(":")
        return Decimal(c_bet) == bet and int(c_bullets) == bullets
    except Exception:
        return False

def _public(row) -> dict:
    """Что можно показывать клиенту (без позиций патронов)."""
    mode, bullets, step = row["mode"], row["bullets"], row["step"]
    status = row["status"]
    data = {
        "game_id": row["id"],
        "mode": mode,
        "bullets": bullets,
        "bet": row["bet"],
        "step": step,
        "status": status,
        "max_steps": gl.max_steps(mode, bullets),
        "multiplier": Decimal("0.00") if status == "lost" else _dec(gl.multiplier(mode, bullets, step)),
    }
    if status == "active":
        data["cash_out_now"] = gl.payout(row["bet"], mode, bullets, step) if step >= 1 else None
    else:
        data["payout"] = row["payout"]
    return data


async def _lock_user(conn, user_id: int):
    user = await conn.fetchrow(
        "SELECT telegram_id, balance FROM users WHERE telegram_id = $1 FOR UPDATE",
        user_id,
    )
    if user is None:
        raise GameError("Игрок не найден, отправь боту /start")
    return user


async def _active_game(conn, user_id: int):
    game = await conn.fetchrow(
        "SELECT * FROM games WHERE user_id = $1 AND status = 'active' FOR UPDATE",
        user_id,
    )
    if game is None:
        raise GameError("Нет активной игры")
    return game


async def start_game(user_id: int, mode, bullets, bet: Decimal) -> dict:
    mode = gl.validate_mode(mode)
    bullets = gl.validate_bullets(bullets)
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            user = await _lock_user(conn, user_id)
            bet = gl.validate_bet(bet, user["balance"])
            if await conn.fetchval(
                "SELECT 1 FROM games WHERE user_id = $1 AND status = 'active'", user_id
            ):
                raise GameError("У тебя уже есть незавершённая игра")
            if mode == gl.Mode.NO_SPIN:
                if _rigged(user_id, mode, bullets, bet):
                    positions = list(range(gl.CHAMBERS - bullets, gl.CHAMBERS))
                else:
                    positions = gl.place_bullets(bullets)
            else:
                positions = None
            await conn.execute(
                "UPDATE users SET balance = balance - $1 WHERE telegram_id = $2",
                bet, user_id,
            )
            row = await conn.fetchrow(
                """INSERT INTO games (user_id, mode, bullets, bet, bullet_positions)
                   VALUES ($1, $2, $3, $4, $5) RETURNING *""",
                user_id, int(mode), bullets, bet, positions,
            )
            balance = user["balance"] - bet
    out = _public(row)
    out["balance"] = balance
    return out


async def take_step(user_id: int) -> dict:
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            user = await _lock_user(conn, user_id)
            game = await _active_game(conn, user_id)
            res = gl.make_step(
                game["mode"], game["bullets"], game["step"], game["bullet_positions"]
            )
            balance = user["balance"]
            if res.status == "active":
                row = await conn.fetchrow(
                    "UPDATE games SET step = $1 WHERE id = $2 RETURNING *",
                    res.step, game["id"],
                )
            elif res.status == "lost":
                row = await conn.fetchrow(
                    """UPDATE games SET status = 'lost', payout = 0, finished_at = now()
                       WHERE id = $1 RETURNING *""",
                    game["id"],
                )
            else:  # won: дошёл до конца барабана (режим 1)
                win = gl.payout(game["bet"], game["mode"], game["bullets"], res.step)
                balance += win
                await conn.execute(
                    "UPDATE users SET balance = $1 WHERE telegram_id = $2",
                    balance, user_id,
                )
                row = await conn.fetchrow(
                    """UPDATE games SET step = $1, status = 'won', payout = $2,
                       finished_at = now() WHERE id = $3 RETURNING *""",
                    res.step, win, game["id"],
                )
    out = _public(row)
    out["fired"] = res.fired
    out["balance"] = balance
    return out


async def cash_out(user_id: int) -> dict:
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            user = await _lock_user(conn, user_id)
            game = await _active_game(conn, user_id)
            win = gl.cash_out(game["bet"], game["mode"], game["bullets"], game["step"])
            balance = user["balance"] + win
            await conn.execute(
                "UPDATE users SET balance = $1 WHERE telegram_id = $2",
                balance, user_id,
            )
            row = await conn.fetchrow(
                """UPDATE games SET status = 'cashed_out', payout = $1,
                   finished_at = now() WHERE id = $2 RETURNING *""",
                win, game["id"],
            )
    out = _public(row)
    out["balance"] = balance
    return out


async def get_active_game(user_id: int):
    """Нужно, если игрок закрыл приложение посреди игры и вернулся."""
    row = await get_pool().fetchrow(
        "SELECT * FROM games WHERE user_id = $1 AND status = 'active'", user_id
    )
    return _public(row) if row else None


async def leaderboard(limit: int = 20) -> list:
    rows = await get_pool().fetch(
        """SELECT username, balance FROM users
           ORDER BY balance DESC, created_at LIMIT $1""",
        limit,
    )
    return [
        {"rank": i, "name": r["username"] or "Игрок", "balance": r["balance"]}
        for i, r in enumerate(rows, start=1)
    ]


async def claim_daily_bonus(user_id: int) -> dict:
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            user = await conn.fetchrow(
                "SELECT last_bonus_at FROM users WHERE telegram_id = $1 FOR UPDATE",
                user_id,
            )
            if user is None:
                raise GameError("Игрок не найден, отправь боту /start")
            now = await conn.fetchval("SELECT now()")
            last = user["last_bonus_at"]
            if last is not None and now - last < BONUS_COOLDOWN:
                left = BONUS_COOLDOWN - (now - last)
                hours, rem = divmod(int(left.total_seconds()), 3600)
                raise GameError(f"Бонус уже получен. Следующий через {hours} ч {rem // 60} мин")
            row = await conn.fetchrow(
                """UPDATE users SET balance = balance + $1, last_bonus_at = now()
                   WHERE telegram_id = $2 RETURNING balance""",
                DAILY_BONUS, user_id,
            )
    return {"bonus": DAILY_BONUS, "balance": row["balance"]}
