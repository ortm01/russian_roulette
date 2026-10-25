#!/bin/bash
# Использование: scripts/set_tunnel.sh https://xxx.trycloudflare.com
set -e
URL="${1%/}"
case "$URL" in
  https://*.trycloudflare.com) ;;
  *) echo "Нужен адрес вида https://....trycloudflare.com"; exit 1 ;;
esac
CODE=$(curl -s -m 10 -o /dev/null -w "%{http_code}" "$URL/api/me" || true)
echo "Ответ туннеля: $CODE (нужен 401)"
[ "$CODE" = "401" ] || { echo "Туннель не отвечает, проверь API и cloudflared"; exit 1; }
cd "$(dirname "$0")/.."
echo "window.APP_CONFIG = { API_URL: \"$URL\" };" > docs/config.js
git add docs/config.js
git commit -m "Update tunnel URL"
git push
