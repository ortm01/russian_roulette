const tg = window.Telegram && window.Telegram.WebApp;
if (tg) { tg.ready(); tg.expand(); }

const API = ((window.APP_CONFIG && window.APP_CONFIG.API_URL) || "").replace(/\/$/, "");
// В Telegram данные приходят сами. Для проверки в обычном браузере: страница#dev=<initData>
const initData = (tg && tg.initData) || (location.hash.startsWith("#dev=") ? location.hash.slice(5) : "");

const $ = (id) => document.getElementById(id);
let balance = "0.00";
let busy = false;

async function api(path, method = "GET", body) {
  const res = await fetch(API + path, {
    method,
    headers: { "Authorization": "tma " + initData, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = {};
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Некорректные данные";
    throw new Error(data.error || detail);
  }
  return data;
}

function msg(text, kind) {
  const el = $("message");
  el.textContent = text || "";
  el.className = "message " + (kind || "");
}

function setBalance(b) {
  balance = b;
  $("balance").textContent = "$" + b;
}

function renderGame(g) {
  const active = g && g.status === "active";
  $("setup").classList.toggle("hidden", !!active);
  $("play").classList.toggle("hidden", !active);
  if (!active) return;
  const modeName = g.mode === 1 ? "без прокрутки" : "с прокруткой";
  const limit = g.max_steps ? " из " + g.max_steps : "";
  $("gameInfo").textContent =
    "Режим: " + modeName + " · патронов: " + g.bullets + " · ставка $" + g.bet + " · шаг " + g.step + limit;
  $("gameMult").textContent = g.step >= 1
    ? "×" + g.multiplier + " · забрать сейчас: $" + g.cash_out_now
    : "Сделай первый выстрел";
  $("cashBtn").disabled = g.step < 1;
}

async function loadBoard() {
  try {
    const data = await api("/api/leaderboard");
    const list = $("board");
    list.textContent = "";
    data.top.forEach((row) => {
      const li = document.createElement("li");
      li.textContent = row.name + " — $" + row.balance;
      list.appendChild(li);
    });
  } catch (e) { /* рейтинг не критичен */ }
}

// Любое действие: блокируем кнопки на время запроса, показываем ошибки
async function action(fn) {
  if (busy) return;
  busy = true;
  document.querySelectorAll("button").forEach((b) => (b.disabled = true));
  try { await fn(); }
  catch (e) { msg(e.message, "bad"); }
  finally {
    busy = false;
    document.querySelectorAll("button").forEach((b) => (b.disabled = false));
    const cash = $("cashBtn");
    if (!$("play").classList.contains("hidden") && cash.dataset.noStep === "1") cash.disabled = true;
  }
}

$("maxBtn").onclick = () => { $("bet").value = balance; };

$("startBtn").onclick = () => action(async () => {
  const bet = $("bet").value.trim().replace(",", ".");
  const g = await api("/api/game/start", "POST", {
    mode: Number($("mode").value),
    bullets: Number($("bullets").value),
    bet: bet,
  });
  setBalance(g.balance);
  msg("");
  renderGame(g);
  $("cashBtn").dataset.noStep = "1";
});

$("stepBtn").onclick = () => action(async () => {
  const r = await api("/api/game/step", "POST");
  setBalance(r.balance);
  if (r.status === "lost") {
    msg("💥 Выстрел! Ставка $" + r.bet + " потеряна.", "bad");
    renderGame(null);
    loadBoard();
  } else if (r.status === "won") {
    msg("🏆 Дошёл до конца барабана! Выигрыш $" + r.payout, "good");
    renderGame(null);
    loadBoard();
  } else {
    msg("Щелчок… патрона нет.", "");
    renderGame(r);
    $("cashBtn").dataset.noStep = r.step >= 1 ? "0" : "1";
  }
});

$("cashBtn").onclick = () => action(async () => {
  const r = await api("/api/game/cashout", "POST");
  setBalance(r.balance);
  msg("✅ Забрал $" + r.payout, "good");
  renderGame(null);
  loadBoard();
});

$("bonusBtn").onclick = () => action(async () => {
  const r = await api("/api/bonus", "POST");
  setBalance(r.balance);
  msg("Получено $" + r.bonus + " 🎁", "good");
  loadBoard();
});

(async function init() {
  if (!initData) {
    msg("Открой игру из Telegram (кнопка «Играть» в боте).", "bad");
    return;
  }
  try {
    const me = await api("/api/me");
    setBalance(me.balance);
    renderGame(me.active_game);
    if (me.active_game) $("cashBtn").dataset.noStep = me.active_game.step >= 1 ? "0" : "1";
    if (!me.active_game) $("setup").classList.remove("hidden");
    loadBoard();
  } catch (e) {
    msg("Не удалось подключиться к серверу: " + e.message, "bad");
  }
})();
