"""Игровая логика «Русской рулетки». Не зависит от Telegram и базы данных.

Деньги считаются целыми центами и дробями (Fraction), без float,
чтобы не было ошибок округления.
"""
import secrets
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import IntEnum
from fractions import Fraction

CHAMBERS = 6
MIN_BULLETS = 1
MAX_BULLETS = 5
MIN_BET = Decimal("1.00")
HOUSE_FACTOR = Fraction(97, 100)  # «комиссия» игры: все множители умножаются на 0.97

# Криптостойкий генератор. Обычный random для денег не годится.
_rng = secrets.SystemRandom()


class GameError(ValueError):
    """Некорректные параметры или действие."""


class Mode(IntEnum):
    NO_SPIN = 1  # без прокрутки, патроны лежат фиксированно, шаги по порядку
    SPIN = 2     # прокрутка на каждом шаге, шансы одинаковые


@dataclass(frozen=True)
class StepResult:
    fired: bool          # был выстрел
    step: int            # число успешных шагов после этого хода
    status: str          # 'active' | 'lost' | 'won'
    multiplier: Fraction # множитель после хода (для 'lost' равен 0)


# ---------- проверки ----------

def validate_mode(mode) -> Mode:
    try:
        return Mode(mode)
    except ValueError:
        raise GameError("Неизвестный режим игры")


def validate_bullets(bullets) -> int:
    if not isinstance(bullets, int) or isinstance(bullets, bool):
        raise GameError("Число патронов должно быть целым")
    if not MIN_BULLETS <= bullets <= MAX_BULLETS:
        raise GameError(f"Патронов может быть от {MIN_BULLETS} до {MAX_BULLETS}")
    return bullets


def validate_bet(bet, balance: Decimal) -> Decimal:
    """Ставка: Decimal, не меньше $1, не больше баланса, максимум 2 знака."""
    if not isinstance(bet, Decimal):
        raise GameError("Ставка должна быть Decimal (создавай через Decimal(str(...)))")
    try:
        if not bet.is_finite() or bet != bet.quantize(Decimal("0.01")):
            raise GameError("В ставке максимум 2 знака после запятой")
    except InvalidOperation:
        raise GameError("Некорректная ставка")
    if bet < MIN_BET:
        raise GameError(f"Минимальная ставка ${MIN_BET}")
    if bet > balance:
        raise GameError("Ставка больше баланса")
    return bet


# ---------- математика ----------

def max_steps(mode, bullets):
    """Режим 1: до конца барабана безопасно столько шагов. Режим 2: без предела."""
    mode, bullets = validate_mode(mode), validate_bullets(bullets)
    return CHAMBERS - bullets if mode == Mode.NO_SPIN else None


def survival_probability(mode, bullets, step: int) -> Fraction:
    """Вероятность пережить `step` шагов подряд."""
    mode, bullets = validate_mode(mode), validate_bullets(bullets)
    if step < 0:
        raise GameError("Шаг не может быть отрицательным")
    if mode == Mode.NO_SPIN:
        if step > CHAMBERS - bullets:
            raise GameError("Дальше конца барабана шагов нет")
        p = Fraction(1)
        for i in range(step):
            p *= Fraction(CHAMBERS - bullets - i, CHAMBERS - i)
        return p
    return Fraction(CHAMBERS - bullets, CHAMBERS) ** step


def multiplier(mode, bullets, step: int) -> Fraction:
    """Множитель выигрыша после `step` успешных шагов.

    Режим 1: 1 / вероятность дожить до шага (растёт всё быстрее).
    Режим 2: линейный рост 1 + step * d, где d = bullets / (6 - bullets).
    К шагам >= 1 применяется HOUSE_FACTOR. На шаге 0 множитель 1 (просто ставка).
    """
    mode, bullets = validate_mode(mode), validate_bullets(bullets)
    if step == 0:
        return Fraction(1)
    if mode == Mode.NO_SPIN:
        return HOUSE_FACTOR / survival_probability(mode, bullets, step)
    if step < 0:
        raise GameError("Шаг не может быть отрицательным")
    d = Fraction(bullets, CHAMBERS - bullets)
    return HOUSE_FACTOR * (1 + step * d)


def payout(bet: Decimal, mode, bullets, step: int) -> Decimal:
    """Выплата в долларах, округление ВНИЗ до цента (в пользу игры)."""
    cents = int(bet * 100)
    m = multiplier(mode, bullets, step)
    result_cents = cents * m.numerator // m.denominator
    return (Decimal(result_cents) / 100).quantize(Decimal("0.01"))


# ---------- игровые действия ----------

def place_bullets(bullets, rng=None) -> list:
    """Для режима 1: случайные слоты барабана с патронами (хранить на сервере!)."""
    bullets = validate_bullets(bullets)
    rng = rng or _rng
    return sorted(rng.sample(range(CHAMBERS), bullets))


def make_step(mode, bullets, step: int, bullet_positions=None, rng=None) -> StepResult:
    """Один выстрел. `step` это число уже сделанных успешных шагов."""
    mode, bullets = validate_mode(mode), validate_bullets(bullets)
    rng = rng or _rng

    if mode == Mode.NO_SPIN:
        if bullet_positions is None or len(bullet_positions) != bullets:
            raise GameError("Для режима 1 нужны позиции патронов")
        limit = CHAMBERS - bullets
        if not 0 <= step < limit:
            raise GameError("Игра уже закончена")
        fired = step in bullet_positions
    else:
        if step < 0:
            raise GameError("Шаг не может быть отрицательным")
        fired = rng.randrange(CHAMBERS) < bullets

    if fired:
        return StepResult(True, step, "lost", Fraction(0))

    new_step = step + 1
    won = mode == Mode.NO_SPIN and new_step == CHAMBERS - bullets
    return StepResult(False, new_step, "won" if won else "active",
                      multiplier(mode, bullets, new_step))


def cash_out(bet: Decimal, mode, bullets, step: int) -> Decimal:
    """Забрать выигрыш. Нужен хотя бы один успешный шаг."""
    if step < 1:
        raise GameError("Нельзя забрать выигрыш до первого шага")
    return payout(bet, mode, bullets, step)
