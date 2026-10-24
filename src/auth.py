"""Проверка initData мини-приложения Telegram."""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class AuthError(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str, max_age: int = 86400, now=None) -> dict:
    """Возвращает данные пользователя Telegram или бросает AuthError."""
    if not init_data:
        raise AuthError("Пустые данные Telegram")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise AuthError("Нет подписи")

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise AuthError("Неверная подпись")

    try:
        auth_date = int(pairs["auth_date"])
    except (KeyError, ValueError):
        raise AuthError("Нет даты авторизации")
    if (now if now is not None else time.time()) - auth_date > max_age:
        raise AuthError("Данные устарели, перезапусти приложение")

    try:
        user = json.loads(pairs["user"])
        user["id"] = int(user["id"])
    except (KeyError, ValueError, TypeError):
        raise AuthError("Нет данных пользователя")
    return user
