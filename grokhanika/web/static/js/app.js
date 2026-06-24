/* Мастерская «Гроханики» — фронтенд админки и симулятора боя.
   Ванильный JS поверх JSON-API. Логика отрисовки изолирована от данных, поэтому
   её несложно заменить на React/Canvas с настоящими анимациями. */
"use strict";

const API = {
  async get(url) { const r = await fetch(url); return r.json(); },
  async post(url, body) {
    const r = await fetch(url, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return { ok: r.ok, status: r.status, data: await r.json() };
  },
};

// эмодзи-заглушка арта по типу карточки (если нет картинки)
const TYPE_ICON = {
  character: "🧝", creature: "👹", weapon: "⚔️", armor: "🛡️",
  item: "🎒", spellbook: "📖", scroll: "📜", instrument: "🪕", skill: "🎓",
};
const ART_BG = {
  character: "#2c3a52", creature: "#4a2c34", weapon: "#3a3450", armor: "#2c4a3e",
  item: "#4a4230", spellbook: "#36304e", scroll: "#45402c", instrument: "#3e2c4a",
  skill: "#2c4450",
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function toast(msg, isErr = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (isErr ? " err" : "");
  setTimeout(() => t.classList.add("hidden"), 2600);
}

// ───────────────────────── переключение режимов ─────────────────────────

function showMode(mode) {
  $$(".mode-btn").forEach(b => b.classList.toggle("active", b.dataset.mode === mode));
  $$(".view").forEach(v => v.classList.toggle("hidden", v.dataset.view !== mode));
  if (mode === "admin" && !state.categories) initAdmin();
  if (mode === "sim" && !state.roster) initSim();
}

document.addEventListener("click", (e) => {
  const modeBtn = e.target.closest(".mode-btn");
  if (modeBtn) showMode(modeBtn.dataset.mode);
  const goto = e.target.closest("[data-goto]");
  if (goto) showMode(goto.dataset.goto);
});

const state = {
  categories: null, currentCat: null, forms: null,
  roster: null, teams: { enemies: [], allies: [] },
  sim: null, step: 0, timer: null,
};

// ───────────────────────── АДМИНКА ─────────────────────────

async function initAdmin() {
  state.categories = await API.get("/api/categories");
  state.forms = await API.get("/api/forms");
  const tabs = $("#cat-tabs");
  tabs.innerHTML = "";
  state.categories.forEach((cat, i) => {
    const b = document.createElement("button");
    b.className = "cat-tab" + (i === 0 ? " active" : "");
    b.textContent = `${cat.icon} ${cat.label}`;
    b.onclick = () => selectCategory(cat.key);
    b.dataset.key = cat.key;
    tabs.appendChild(b);
  });
  selectCategory(state.categories[0].key);
}

function categoryByKey(key) { return state.categories.find(c => c.key === key); }

function selectCategory(key) {
  state.currentCat = key;
  $$(".cat-tab").forEach(t => t.classList.toggle("active", t.dataset.key === key));
  const cat = categoryByKey(key);
  renderToolbar(cat);
  // кнопка добавления активна, только если в категории есть что создавать
  $("#add-btn").classList.toggle("hidden", !cat.creatable.length);
  loadCards();
}

function renderToolbar(cat) {
  const tb = $("#toolbar");
  tb.innerHTML = "";
  if (cat.filters.length) {
    tb.appendChild(makeSelect("filter", "Фильтр",
      cat.filters.map(f => ({ value: f.value, label: f.label })), "all"));
  }
  if (cat.sorts.length) {
    tb.appendChild(makeSelect("sort", "Сортировка", cat.sorts, cat.sorts[0].value));
    const orderCtrl = document.createElement("div");
    orderCtrl.className = "ctrl";
    orderCtrl.innerHTML = `<label>Порядок</label>`;
    const ob = document.createElement("button");
    ob.className = "order"; ob.dataset.order = "asc"; ob.textContent = "▲ возр.";
    ob.onclick = () => {
      const desc = ob.dataset.order === "asc";
      ob.dataset.order = desc ? "desc" : "asc";
      ob.textContent = desc ? "▼ убыв." : "▲ возр.";
      loadCards();
    };
    orderCtrl.appendChild(ob);
    tb.appendChild(orderCtrl);
  }
}

function makeSelect(id, label, options, def) {
  const wrap = document.createElement("div");
  wrap.className = "ctrl";
  wrap.innerHTML = `<label>${label}</label>`;
  const sel = document.createElement("select");
  sel.id = `tb-${id}`;
  options.forEach(o => {
    const opt = document.createElement("option");
    opt.value = o.value; opt.textContent = o.label;
    if (o.value === def) opt.selected = true;
    sel.appendChild(opt);
  });
  sel.onchange = loadCards;
  wrap.appendChild(sel);
  return wrap;
}

async function loadCards() {
  const cat = state.currentCat;
  const filter = $("#tb-filter")?.value || "all";
  const sort = $("#tb-sort")?.value || "name";
  const order = $(".order")?.dataset.order || "asc";
  const q = `/api/cards?category=${cat}&filter=${filter}&sort=${sort}&order=${order}`;
  const { items } = await API.get(q);
  renderCards(items, cat);
}

function renderCards(items, cat) {
  const grid = $("#card-grid");
  grid.innerHTML = "";
  $("#empty-state").classList.toggle("hidden", items.length > 0);
  items.forEach((it, idx) => {
    grid.appendChild(cat === "abilities" ? abilityCard(it, idx) : gameCard(it, idx));
  });
}

function artStyle(card) {
  if (card.image_url) return `background-image:url('${card.image_url}')`;
  return `background:${ART_BG[card.card_type] || "#2a2740"}`;
}

function gameCard(card, idx) {
  const el = document.createElement("div");
  el.className = "game-card";
  el.style.animationDelay = `${Math.min(idx * 30, 300)}ms`;
  const icon = card.image_url ? "" : (TYPE_ICON[card.card_type] || "❓");
  el.innerHTML = `
    <div class="card-art" style="${artStyle(card)}">
      ${icon}
      ${card.is_unique ? '<span class="badge-unique">уник.</span>' : ""}
    </div>
    <div class="card-body">
      <div class="card-type">${card.type_label}</div>
      <div class="card-name">${esc(card.name)}</div>
      <div class="card-stats">${cardChips(card)}</div>
    </div>`;
  el.onclick = () => showDetail(card);
  return el;
}

function cardChips(card) {
  const chips = [];
  const f = card.fields || {};
  const s = card.stats;
  if (s) {
    chips.push(chip("HP", s.hp));
    chips.push(chip("Физз", s.phys_defense));
  }
  if (card.card_type === "skill") {
    chips.push(`<span class="stat-chip">${f.is_passive ? "пассивный" : "активный"}</span>`);
    if (f.spell_name) chips.push(chip("Заклинание", esc(f.spell_name)));
  }
  if (f.damage_dice) chips.push(chip("Урон", f.damage_dice));
  if (f.phys_def_bonus != null) chips.push(chip("Защ", `+${f.phys_def_bonus}`));
  if (f.heal_dice) chips.push(chip("Хил", f.heal_dice));
  if (f.grants_skill) chips.push(chip("Даёт навык", esc(f.grants_skill)));
  if (f.ignores_bastion) chips.push(`<span class="stat-chip">игнор. Бастион</span>`);
  if (f.price != null) chips.push(chip("Цена", f.price));
  return chips.join("");
}
function chip(k, v) { return `<span class="stat-chip">${k} <b>${v}</b></span>`; }

function abilityCard(ab, idx) {
  const el = document.createElement("div");
  el.className = "game-card";
  el.style.animationDelay = `${Math.min(idx * 30, 300)}ms`;
  el.innerHTML = `
    <div class="card-art" style="background:${ART_BG.spellbook}">✨</div>
    <div class="card-body">
      <div class="card-type">Способность · ${esc(ab.trigger)}</div>
      <div class="card-name">${esc(ab.name)}</div>
      <div class="card-stats">
        ${ab.owner ? chip("Носитель", esc(ab.owner)) : ""}
        ${ab.chance != null ? chip("Шанс", Math.round(ab.chance * 100) + "%") : ""}
        ${ab.actions_summary ? `<span class="stat-chip">${esc(ab.actions_summary)}</span>` : ""}
      </div>
    </div>`;
  el.onclick = () => toast(ab.description || ab.name);
  return el;
}

// деталь карточки
function showDetail(card) {
  const icon = card.image_url ? "" : (TYPE_ICON[card.card_type] || "❓");
  const rows = [];
  const f = card.fields || {};
  const labelMap = {
    is_player: "Игровой", is_sentient: "Разумный", strength: "Сила", dexterity: "Ловкость",
    wisdom: "Мудрость", charisma: "Харизма", money: "Деньги", weapon: "Оружие", armor: "Броня",
    hp: "HP", phys_defense: "Физ. защита", mag_defense: "Маг. защита", mental_defense: "Мент. защита",
    phys_damage_dice: "Урон", damage_dice: "Урон", str_requirement: "Треб. Силы",
    dex_requirement: "Треб. Ловкости", is_ranged: "Дальнобойное", price: "Цена",
    phys_def_bonus: "Бонус физзащиты", is_consumable: "Расходуемый", heal_dice: "Лечение",
    spell_name: "Заклинание", difficulty: "Сложность", attack_stat: "Хар-ка атаки",
    is_passive: "Пассивный", non_sellable: "Нельзя продать", in_inventory: "Занимает слот инвентаря",
    skills: "Навыки", grants_skill: "Даёт навык", ignores_bastion: "Игнорирует Бастион",
  };
  const fmt = (v) => v === true ? "да" : v === false ? "нет" : Array.isArray(v) ? (v.join(", ") || "—") : (v ?? "—");
  Object.entries(f).forEach(([k, v]) => {
    if (v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length)) return;
    rows.push(`<div class="k">${labelMap[k] || k}</div><div>${esc(String(fmt(v)))}</div>`);
  });
  if (card.stats) {
    const s = card.stats;
    rows.push(`<div class="k">Вычислено</div><div>HP ${s.hp} · физз ${s.phys_defense} · магз ${s.mag_defense} · ментз ${s.mental_defense}</div>`);
    rows.push(`<div class="k">Атаки</div><div>физ d20+${s.phys_attack_bonus} · маг d20+${s.mag_attack_bonus} · урон ${s.phys_damage}</div>`);
  }
  if (card.abilities && card.abilities.length) {
    rows.push(`<div class="k">Способности</div><div>${card.abilities.map(esc).join(", ")}</div>`);
  }
  $("#detail-body").innerHTML = `
    <div class="detail-art" style="${artStyle(card)}">${icon}
      ${card.is_unique ? '<span class="badge-unique">уник.</span>' : ""}</div>
    <div class="detail-content">
      <div class="sub">${card.type_label}</div>
      <h2>${esc(card.name)}</h2>
      ${card.description ? `<p class="desc">${esc(card.description)}</p>` : ""}
      <div class="kv">${rows.join("")}</div>
    </div>`;
  openModal("#detail-modal");
}

// ───────────────────────── форма добавления ─────────────────────────

function openAddForm() {
  const cat = categoryByKey(state.currentCat);
  const typeSel = $("#form-type");
  typeSel.innerHTML = "";
  const allowed = state.forms.filter(fm => cat.creatable.includes(fm.card_type));
  allowed.forEach(fm => {
    const o = document.createElement("option");
    o.value = fm.card_type; o.textContent = `${fm.icon} ${fm.label}`;
    typeSel.appendChild(o);
  });
  typeSel.onchange = () => renderForm(typeSel.value);
  renderForm(allowed[0].card_type);
  $("#form-error").classList.add("hidden");
  openModal("#modal");
}

function formByType(t) { return state.forms.find(f => f.card_type === t); }

function renderForm(cardType) {
  const form = formByType(cardType);
  $("#modal-title").textContent = `Новая сущность: ${form.label}`;
  $("#form-type-hint").textContent = form.note || "";
  const root = $("#entity-form");
  root.innerHTML = "";
  form.fields.forEach(fld => root.appendChild(renderField(fld)));
}

function renderField(fld) {
  const wrap = document.createElement("label");
  const isCheck = fld.type === "bool";
  const isWide = fld.type === "text";
  wrap.className = "field" + (isCheck ? " check" : "") + (isWide ? " full" : "");
  wrap.dataset.name = fld.name;

  let control;
  if (fld.type === "bool") {
    control = document.createElement("input");
    control.type = "checkbox";
    if (fld.default) control.checked = true;
  } else if (fld.type === "choice") {
    control = document.createElement("select");
    const blank = document.createElement("option");
    blank.value = ""; blank.textContent = fld.required ? "— выберите —" : "— нет —";
    control.appendChild(blank);
    (fld.choices || []).forEach(c => {
      const o = document.createElement("option");
      o.value = c.value; o.textContent = c.label;
      if (String(c.value) === String(fld.default)) o.selected = true;
      control.appendChild(o);
    });
  } else {
    control = document.createElement("input");
    control.type = fld.type === "int" ? "number" : "text";
    if (fld.default !== null && fld.default !== undefined) control.value = fld.default;
    if (fld.type === "dice") control.placeholder = "напр. 1d8";
    if (fld.min != null) control.min = fld.min;
    if (fld.max != null) control.max = fld.max;
  }
  control.dataset.field = fld.name;
  control.dataset.ftype = fld.type;

  const labelText = `<span class="field-label">${esc(fld.label)}${fld.required ? ' <span class="req">*</span>' : ""}</span>`;
  if (isCheck) {
    wrap.appendChild(control);
    const sp = document.createElement("span");
    sp.innerHTML = labelText + (fld.hint ? `<span class="field-hint">${esc(fld.hint)}</span>` : "");
    wrap.appendChild(sp);
  } else {
    wrap.insertAdjacentHTML("beforeend", labelText);
    wrap.appendChild(control);
    if (fld.hint) wrap.insertAdjacentHTML("beforeend", `<span class="field-hint">${esc(fld.hint)}</span>`);
    wrap.insertAdjacentHTML("beforeend", `<span class="err"></span>`);
    control.addEventListener("input", () => validateField(wrap, control, fld));
  }
  return wrap;
}

// живая клиентская подсказка по формату (сервер всё равно валидирует повторно)
function validateField(wrap, control, fld) {
  const v = control.value.trim();
  let msg = "";
  if (!v) { if (fld.required) msg = "Обязательное поле"; }
  else if (fld.type === "int" && !/^-?\d+$/.test(v)) msg = "Нужно целое число";
  else if (fld.type === "dice" && !/^\s*\d+\s*[dD]\s*(4|6|8|10|12|20)\s*$/.test(v)) msg = "Формат NdM (d4..d20)";
  wrap.classList.toggle("invalid", !!msg);
  $(".err", wrap).textContent = msg;
  return !msg;
}

function collectForm() {
  const body = { card_type: $("#form-type").value };
  $$("#entity-form [data-field]").forEach(ctrl => {
    const name = ctrl.dataset.field;
    if (ctrl.dataset.ftype === "bool") body[name] = ctrl.checked;
    else if (ctrl.value !== "") body[name] = ctrl.value;
  });
  return body;
}

async function submitForm() {
  const body = collectForm();
  const { ok, data } = await API.post("/api/cards", body);
  // сбрасываем прежние ошибки
  $$("#entity-form .field").forEach(w => { w.classList.remove("invalid"); const e = $(".err", w); if (e) e.textContent = ""; });
  $("#form-error").classList.add("hidden");
  if (ok) {
    closeModal("#modal");
    toast(`Создано: ${data.name}`);
    if (state.currentCat) loadCards();
    return;
  }
  const errors = data.errors || {};
  Object.entries(errors).forEach(([field, msg]) => {
    if (field === "__form__") {
      const fe = $("#form-error");
      fe.textContent = msg; fe.classList.remove("hidden");
      return;
    }
    const wrap = $(`#entity-form .field[data-name="${field}"]`);
    if (wrap) { wrap.classList.add("invalid"); const e = $(".err", wrap); if (e) e.textContent = msg; }
  });
}

// ───────────────────────── СИМУЛЯЦИЯ ─────────────────────────

async function initSim() {
  state.roster = await API.get("/api/roster");
  renderPool();
}

function allCombatants() {
  return [...state.roster.heroes, ...state.roster.npc];
}

function renderPool() {
  const pool = $("#pool-list");
  pool.innerHTML = "";
  allCombatants().forEach(c => {
    const el = document.createElement("div");
    el.className = "roster-chip";
    el.innerHTML = `
      <span class="ico">${TYPE_ICON[c.card_type] || "❓"}</span>
      <div class="meta">
        <div class="rn">${esc(c.name)}</div>
        <div class="rs">${c.type_label}${c.stats ? " · HP " + c.stats.hp : ""}</div>
        <div class="add-targets">
          <button data-t="enemies">→ враги</button>
          <button data-t="allies">→ союзники</button>
        </div>
      </div>`;
    el.querySelectorAll(".add-targets button").forEach(b =>
      b.onclick = (e) => { e.stopPropagation(); addToTeam(b.dataset.t, c); });
    pool.appendChild(el);
  });
}

function addToTeam(team, card) {
  state.teams[team].push({ uid: Date.now() + Math.random(), card });
  renderTeams();
}
function removeFromTeam(team, uid) {
  state.teams[team] = state.teams[team].filter(x => x.uid !== uid);
  renderTeams();
}
function renderTeams() {
  ["enemies", "allies"].forEach(team => {
    const list = $(`#team-${team}`);
    list.innerHTML = "";
    state.teams[team].forEach(entry => {
      const el = document.createElement("div");
      el.className = "roster-chip";
      el.innerHTML = `
        <span class="ico">${TYPE_ICON[entry.card.card_type] || "❓"}</span>
        <div class="meta"><div class="rn">${esc(entry.card.name)}</div>
          <div class="rs">${entry.card.type_label}</div></div>
        <span class="rm">✕</span>`;
      el.querySelector(".rm").onclick = () => removeFromTeam(team, entry.uid);
      list.appendChild(el);
    });
  });
}

async function runSim() {
  const allies = state.teams.allies.map(e => e.card.id);
  const enemies = state.teams.enemies.map(e => e.card.id);
  if (!allies.length || !enemies.length) { toast("Нужны участники с обеих сторон", true); return; }
  const seedVal = $("#sim-seed").value;
  const { ok, data } = await API.post("/api/simulate", {
    allies, enemies, seed: seedVal === "" ? null : Number(seedVal),
  });
  if (!ok) { toast(data.error || "Ошибка симуляции", true); return; }
  state.sim = data; state.step = 0;
  $("#sim-stage").classList.remove("hidden");
  $("#outcome").classList.add("hidden");
  $("#battle-log").innerHTML = "";
  renderStep(0, true);
  $("#sim-stage").scrollIntoView({ behavior: "smooth" });
}

function fighterEl(c) {
  const pct = c.max_hp ? Math.max(0, (c.hp / c.max_hp) * 100) : 0;
  const el = document.createElement("div");
  el.className = "fighter" + (c.alive ? "" : " down") + (c.dying ? " dying" : "");
  el.dataset.uid = c.uid; el.dataset.side = c.side;
  el.innerHTML = `
    <div class="fh"><span class="fn">${TYPE_ICON[c.kind] || ""} ${esc(c.name)}</span>
      <span class="fhp">${c.hp}/${c.max_hp}</span></div>
    <div class="hpbar"><i style="width:${pct}%"></i></div>`;
  return el;
}

function renderStep(idx, rebuild = false) {
  const ev = state.sim.events[idx];
  if (!ev) return;
  // стороны
  ["enemies", "allies"].forEach(team => {
    const side = team === "enemies" ? "enemy" : "party";
    const host = $(`#stage-${team}`);
    const fighters = ev.combatants.filter(c => c.side === side);
    if (rebuild || host.children.length !== fighters.length) {
      host.innerHTML = "";
      fighters.forEach(c => host.appendChild(fighterEl(c)));
    } else {
      fighters.forEach(c => updateFighter(host, c));
    }
    fighters.forEach(c => {
      const fe = host.querySelector(`[data-uid="${c.uid}"]`);
      if (fe) fe.classList.toggle("acting", c.uid === ev.actor_uid);
    });
  });
  $("#stage-round").textContent = ev.phase === "start" ? "Начало боя" : `Раунд ${ev.round}`;
  // лог: показываем строки до текущего шага включительно
  renderLogUpTo(idx);
  state.step = idx;
  if (idx >= state.sim.events.length - 1) showOutcome();
}

function updateFighter(host, c) {
  const fe = host.querySelector(`[data-uid="${c.uid}"]`);
  if (!fe) return;
  const pct = c.max_hp ? Math.max(0, (c.hp / c.max_hp) * 100) : 0;
  fe.querySelector(".hpbar > i").style.width = pct + "%";
  fe.querySelector(".fhp").textContent = `${c.hp}/${c.max_hp}`;
  fe.classList.toggle("down", !c.alive);
  fe.classList.toggle("dying", c.dying);
}

function renderLogUpTo(idx) {
  const log = $("#battle-log");
  log.innerHTML = "";
  let lastRound = 0;
  for (let i = 0; i <= idx; i++) {
    const ev = state.sim.events[i];
    if (ev.round !== lastRound && ev.phase !== "start") {
      lastRound = ev.round;
      const rm = document.createElement("div");
      rm.className = "line round-mark";
      rm.textContent = `— Раунд ${ev.round} —`;
      log.appendChild(rm);
    }
    ev.log.forEach(line => {
      const d = document.createElement("div");
      d.className = "line"; d.textContent = line;
      log.appendChild(d);
    });
  }
  log.scrollTop = log.scrollHeight;
}

function showOutcome() {
  const o = state.sim.outcome;
  const box = $("#outcome");
  let cls = "draw", txt;
  if (o.winner === "party") { cls = "win-allies"; txt = "🛡️ Победа союзников!"; }
  else if (o.winner === "enemy") { cls = "win-enemies"; txt = "👹 Победа врагов!"; }
  else txt = o.ended_by === "negotiation" ? "🤝 Бой завершён переговорами" :
             o.ended_by === "timeout" ? "⏳ Ничья по таймауту" : "Ничья";
  const surv = Object.entries(o.survivors)
    .map(([s, names]) => `${state.sim.sides[s] || s}: ${names.join(", ") || "—"}`).join(" · ");
  box.className = "outcome " + cls;
  box.innerHTML = `<div>${txt}</div>
    <div class="survivors">за ${o.rounds} раунд(ов) · ${o.ended_by}</div>
    <div class="survivors">Выжившие — ${surv}</div>`;
  box.classList.remove("hidden");
}

function stepBy(delta) {
  const n = Math.min(Math.max(0, state.step + delta), state.sim.events.length - 1);
  renderStep(n);
}

function togglePlay() {
  if (state.timer) { clearInterval(state.timer); state.timer = null; $("#pb-play").textContent = "⏯ Авто"; return; }
  $("#pb-play").textContent = "⏸ Пауза";
  state.timer = setInterval(() => {
    if (state.step >= state.sim.events.length - 1) { togglePlay(); return; }
    stepBy(1);
  }, 900);
}

// ───────────────────────── модалки/утилиты ─────────────────────────

function openModal(sel) { $(sel).classList.remove("hidden"); }
function closeModal(sel) { $(sel).classList.add("hidden"); }
function esc(s) { return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

// ───────────────────────── привязка событий ─────────────────────────

$("#add-btn").onclick = openAddForm;
$("#modal-close").onclick = () => closeModal("#modal");
$("#form-cancel").onclick = () => closeModal("#modal");
$("#form-submit").onclick = submitForm;
$("#sim-go").onclick = runSim;
$("#pb-prev").onclick = () => stepBy(-1);
$("#pb-next").onclick = () => stepBy(1);
$("#pb-play").onclick = togglePlay;
$$(".modal-backdrop").forEach(m => m.onclick = (e) => { if (e.target === m) m.classList.add("hidden"); });

showMode("home");
