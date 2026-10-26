async function action(fn) {
  if (busy) return;
  busy = true;
  document.querySelectorAll("button").forEach((b) => {
    b.disabled = true;
    b.setAttribute("aria-busy", "true");
  });
  try { await fn(); }
  catch (e) { msg(e.message, "bad"); }
  finally {
    busy = false;
    document.querySelectorAll("button").forEach((b) => {
      b.disabled = false;
      b.removeAttribute("aria-busy");
    });
    const cash = $("cashBtn");
    if (!$("play").classList.contains("hidden") && cash.dataset.noStep === "1") {
      cash.disabled = true;
    }
  }
}

function renderGame(g) {
  const active = g && g.status === "active";
  $("setup").classList.toggle("hidden", !!active);
  $("play").classList.toggle("hidden", !active);
  if (!active) return;

  const modeName = g.mode === 1 ? "без прокрутки" : "с прокруткой";
  const limit = g.max_steps ? ` · шаг ${g.step}/${g.max_steps}` : ` · шаг ${g.step}`;

  $("gameInfo").textContent =
    `${modeName} · патронов: ${g.bullets} · ставка $${g.bet}${limit}`;

  if (g.step >= 1) {
    $("gameMult").innerHTML =
      `×${g.multiplier}<div class="mult-caption">забрать сейчас: $${g.cash_out_now}</div>`;
  } else {
    $("gameMult").innerHTML =
      `<div class="mult-caption" style="font-size:15px;text-transform:none;letter-spacing:0">Сделай первый выстрел</div>`;
  }

  $("cashBtn").disabled = g.step < 1;
  $("cashBtn").dataset.noStep = g.step >= 1 ? "0" : "1";
}

async function loadBoard() {
  try {
    const data = await api("/api/leaderboard");
    const list = $("board");
    list.textContent = "";
    data.top.forEach((row, i) => {
      const li = document.createElement("li");
      if (i < 3) li.classList.add(`top-${i + 1}`);

      const rank = document.createElement("span");
      rank.className = "rank";
      rank.textContent = String(i + 1);

      const name = document.createElement("span");
      name.className = "name";
      name.textContent = row.name;

      const amount = document.createElement("span");
      amount.className = "amount";
      amount.textContent = "$" + row.balance;

      li.append(rank, name, amount);
      list.appendChild(li);
    });
  } catch (e) { /* рейтинг не критичен */ }
}
$("stepBtn").onclick = () => action(async () => {
  const r = await api("/api/game/step", "POST");
  setBalance(r.balance);
  if (r.status === "lost") {
    msg("Выстрел. Ставка $" + r.bet + " потеряна.", "bad");
    renderGame(null);
    loadBoard();
  } else if (r.status === "won") {
    msg("Дошёл до конца барабана. Выигрыш $" + r.payout, "good");
    renderGame(null);
    loadBoard();
  } else {
    msg("Щелчок — патрона нет.", "");
    renderGame(r);
    $("cashBtn").dataset.noStep = r.step >= 1 ? "0" : "1";
  }
});

$("cashBtn").onclick = () => action(async () => {
  const r = await api("/api/game/cashout", "POST");
  setBalance(r.balance);
  msg("Забрал $" + r.payout, "good");
  renderGame(null);
  loadBoard();
});

$("bonusBtn").onclick = () => action(async () => {
  const r = await api("/api/bonus", "POST");
  setBalance(r.balance);
  msg("Получено $" + r.bonus, "good");
  loadBoard();
});