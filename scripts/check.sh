#!/bin/bash
echo "--- прокси-переменные (должно быть пусто)"
env | grep -i proxy
echo "--- Telegram (нужно 302)"
curl -s -m 10 -o /dev/null -w "%{http_code}\n" https://api.telegram.org
echo "--- GitHub (нужно 200)"
curl -s -m 10 -o /dev/null -w "%{http_code}\n" https://github.com
echo "--- PostgreSQL (нужно accepting connections)"
pg_isready -h localhost
echo "--- API локально (нужно 401)"
curl -s -m 5 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/me
