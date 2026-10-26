# Русская рулетка: Telegram-бот и мини-приложение

Игра «Русская рулетка» внутри Telegram: игрок ставит **виртуальные доллары**, делает «выстрелы» и либо увеличивает выигрыш, либо проигрывает ставку. Реальные деньги не используются. Есть общий рейтинг игроков по балансу.

**Стек:** Python, aiogram 3, FastAPI, PostgreSQL, HTML/CSS/JavaScript, git, Obsidian (заметки).

## Правила игры

- Барабан на 6 ячеек, патронов от 1 до 5.
- Старт: баланс **$100**. Ставка от **$1** до всего баланса. Ежедневный бонус **$10** (раз в 24 часа).
- **Режим 1 (без прокрутки).** Патроны лежат на своих местах, шаги идут по очереди. Множитель растёт всё быстрее. Если дошёл до последнего безопасного шага (`6 − патроны`), выигрыш засчитывается автоматически.
- **Режим 2 (с прокруткой).** Барабан крутится на каждом шаге, шансы одинаковые, шагов без предела. Множитель растёт линейно, остановиться и забрать выигрыш можно после первого шага.
- Все множители умножаются на **0.97** (небольшой перевес игры), выплата округляется вниз до цента.
- Исход выстрела определяет только сервер (`secrets`), позиции патронов клиенту не передаются.

## Структура проекта

```
src/
  main_bot.py      # Telegram-бот (/start, кнопка «Играть»)
  api.py           # FastAPI: API для мини-приложения
  auth.py          # проверка подписи initData из Telegram
  database.py      # подключение к PostgreSQL (asyncpg)
  game_logic.py    # правила, множители, случайность (без БД и Telegram)
  game_service.py  # игровые операции в транзакциях
docs/              # мини-приложение (публикуется на GitHub Pages)
  index.html  style.css  app.js  config.js
db/schema.sql      # таблицы users и games
tests/             # юнит-тесты логики и проверки подписи
scripts/           # вспомогательные скрипты (проверка сети, туннель, тестовые данные)
.env.example       # шаблон переменных окружения
```

## Запуск для разработки

```bash
git clone https://github.com/ortm01/russian_roulette.git
cd russian_roulette
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

1. **PostgreSQL:** создай пользователя и базу, затем примени схему:
```bash
   psql -h localhost -U roulette -d roulette_db -f db/schema.sql
```
2. **`.env`:** скопируй `.env.example` в `src/.env` (или в корень) и заполни:
   - `BOT_TOKEN`: токен от @BotFather,
   - `WEBAPP_URL`: адрес мини-приложения (GitHub Pages),
   - `DATABASE_URL`: `postgresql://пользователь:пароль@localhost:5432/roulette_db`,
   - `ALLOWED_ORIGINS`: разрешённые адреса страницы (через запятую),
   - `PROXY_URL`: прокси для бота, если Telegram недоступен напрямую (иначе пусто).
3. **Бот:** `python src/main_bot.py`
4. **API:** `python -m uvicorn --app-dir src api:app --reload --port 8000`
5. **Тесты:** `PYTHONPATH=src python -m unittest discover -s tests`

> `.env` и токены никогда не коммитим (они в `.gitignore`).

## API

Все запросы с заголовком `Authorization: tma <initData>` (данные из `Telegram.WebApp.initData`). Сервер проверяет подпись токеном бота. Деньги в ответах приходят строками (`"100.00"`).

| Метод | Путь | Что делает |
|---|---|---|
| GET | `/api/me` | профиль, баланс, активная игра |
| POST | `/api/game/start` | начать игру: `{mode, bullets, bet}` |
| POST | `/api/game/step` | сделать выстрел |
| POST | `/api/game/cashout` | забрать выигрыш |
| GET | `/api/leaderboard` | рейтинг (топ-20) |
| POST | `/api/bonus` | ежедневный бонус |

Ошибки правил игры приходят как `401` с полем `error`.

## Мини-приложение (для дизайнеров)

Вся вёрстка в `docs/`. Менять можно `index.html` и `style.css`, логика в `app.js`. **Не меняйте `id` элементов** (`balance`, `mode`, `bullets`, `bet`, `startBtn`, `stepBtn`, `cashBtn`, `bonusBtn`, `board`, `message`, `setup`, `play`), иначе игра перестанет работать. Адрес API лежит в `docs/config.js`.

Изменения на GitHub Pages появляются через 1-2 минуты после пуша в `main`.

## Публикация API на время разработки

Пока нет постоянного сервера, API открывается наружу временным туннелем Cloudflare:

bash:
cloudflared tunnel --url http://127.0.0.1:8000
scripts/set_tunnel.sh https://НОВЫЙ-АДРЕС.trycloudflare.com   # обновит docs/config.js и запушит

Адрес туннеля меняется при каждом запуске. Проверка: `scripts/check.sh`.
