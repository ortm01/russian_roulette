import os
from contextlib import asynccontextmanager
from decimal import Decimal

from pathlib import Path

from dotenv import load_dotenv

_here = Path(__file__).resolve().parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import game_service as gs
from auth import AuthError, validate_init_data
from database import close_db, get_or_create_user, init_db
from game_logic import GameError

BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "https://ortm01.github.io").split(",")
    if o.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(title="Russian Roulette API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(GameError)
async def game_error_handler(request: Request, exc: GameError):
    return JSONResponse(status_code=400, content={"error": str(exc)})


def money(value):
    """Деньги отдаём строками с двумя знаками, чтобы JS не портил числа."""
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, dict):
        return {k: money(v) for k, v in value.items()}
    if isinstance(value, list):
        return [money(v) for v in value]
    return value


async def current_user(authorization: str = Header(default="")):
    if not BOT_TOKEN:
        raise HTTPException(500, "BOT_TOKEN не настроен на сервере")
    if not authorization.startswith("tma "):
        raise HTTPException(401, "Нет данных Telegram")
    try:
        tg = validate_init_data(authorization[4:], BOT_TOKEN)
    except AuthError as e:
        raise HTTPException(401, str(e))
    name = tg.get("username") or tg.get("first_name")
    return await get_or_create_user(tg["id"], name)


class StartBody(BaseModel):
    mode: int
    bullets: int
    bet: Decimal


@app.get("/api/me")
async def me(user=Depends(current_user)):
    active = await gs.get_active_game(user["telegram_id"])
    return money({
        "name": user["username"],
        "balance": user["balance"],
        "active_game": active,
    })


@app.post("/api/game/start")
async def game_start(body: StartBody, user=Depends(current_user)):
    return money(await gs.start_game(user["telegram_id"], body.mode, body.bullets, body.bet))


@app.post("/api/game/step")
async def game_step(user=Depends(current_user)):
    return money(await gs.take_step(user["telegram_id"]))


@app.post("/api/game/cashout")
async def game_cashout(user=Depends(current_user)):
    return money(await gs.cash_out(user["telegram_id"]))


@app.get("/api/leaderboard")
async def leaderboard(user=Depends(current_user)):
    return money({"top": await gs.leaderboard(20)})


@app.post("/api/bonus")
async def bonus(user=Depends(current_user)):
    return money(await gs.claim_daily_bonus(user["telegram_id"]))
