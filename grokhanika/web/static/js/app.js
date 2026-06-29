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
  async patch(url, body) {
    const r = await fetch(url, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return { ok: r.ok, status: r.status, data: await r.json() };
  },
  async delete(url) {
    const r = await fetch(url, { method: "DELETE" });
    return { ok: r.ok, status: r.status };
  },
};

// ───────────────────────── Звуки (Web Audio API, без файлов) ─────────────────────────

const SFX = (() => {
  let _ctx = null;
  const ac = () => {
    if (!_ctx) _ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (_ctx.state === "suspended") _ctx.resume();
    return _ctx;
  };

  const tone = (freq, dur, type = "sine", vol = 0.22) => {
    const c = ac(), o = c.createOscillator(), g = c.createGain();
    o.connect(g); g.connect(c.destination);
    o.type = type; o.frequency.value = freq;
    g.gain.setValueAtTime(vol, c.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + dur);
    o.start(c.currentTime); o.stop(c.currentTime + dur);
  };

  const burst = (dur, vol = 0.35, decay = 0.25) => {
    const c = ac(), sr = c.sampleRate;
    const buf = c.createBuffer(1, Math.ceil(sr * dur), sr);
    const d = buf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * Math.exp(-i / (d.length * decay));
    const src = c.createBufferSource(), g = c.createGain();
    g.gain.value = vol; src.connect(g); g.connect(c.destination); src.start();
  };

  // [[freq, delayMs, dur, type?, vol?], ...]
  const seq = (notes) => notes.forEach(([f, d, t, tp, v]) => setTimeout(() => tone(f, t, tp || "sine", v || 0.18), d));

  return {
    // ── Инвентарь ──
    pickup()  { tone(560, 0.08, "sine", 0.16); },
    equip()   { seq([[440, 0, 0.07, "square", 0.1], [700, 70, 0.2, "sine", 0.22]]); },
    unequip() { tone(320, 0.13, "sine", 0.14); },
    deny()    { seq([[210, 0, 0.09, "sawtooth", 0.14], [150, 90, 0.13, "sawtooth", 0.11]]); },

    // ── Бой ──
    hit() { burst(0.1, 0.38, 0.22); setTimeout(() => tone(160, 0.12, "square", 0.14), 18); },
    miss() {
      const c = ac(), o = c.createOscillator(), g = c.createGain();
      o.connect(g); g.connect(c.destination); o.type = "sine";
      o.frequency.setValueAtTime(310, c.currentTime);
      o.frequency.exponentialRampToValueAtTime(90, c.currentTime + 0.2);
      g.gain.setValueAtTime(0.13, c.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + 0.2);
      o.start(); o.stop(c.currentTime + 0.2);
    },
    kill()  { seq([[220, 0, 0.11, "sawtooth", 0.28], [155, 115, 0.16, "sawtooth", 0.22], [100, 285, 0.32, "sawtooth", 0.18]]); },
    spell() { seq([[523, 0, 0.17, "sine", 0.14], [659, 55, 0.17, "sine", 0.14], [784, 110, 0.17, "sine", 0.14], [1047, 165, 0.22, "sine", 0.15]]); },
    heal()  { seq([[523, 0, 0.21, "sine", 0.11], [659, 70, 0.21, "sine", 0.12], [784, 140, 0.27, "sine", 0.13]]); },
    aoe()   { burst(0.22, 0.5, 0.14); seq([[240, 30, 0.22, "sawtooth", 0.2], [180, 140, 0.22, "sawtooth", 0.17]]); },

    // ── Исход боя ──
    victory() { seq([[523, 0, 0.13, "sine", 0.2], [659, 120, 0.13, "sine", 0.2], [784, 240, 0.13, "sine", 0.2], [1047, 360, 0.42, "sine", 0.25]]); },
    defeat()  { seq([[280, 0, 0.22, "sine", 0.2], [230, 200, 0.22, "sine", 0.18], [180, 420, 0.4, "sine", 0.16]]); },
  };
})();

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
  if (mode === "adv" && !advState.ready) initAdventure();
}

// Переключение под-вкладок в Отладке/Админке
let _adminTab = "world";
function showAdminTab(tab) {
  _adminTab = tab;
  $$(".admin-sub-tab").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
  $$(".admin-sub-section").forEach(s => s.classList.toggle("hidden", s.dataset.section !== tab));
  if (tab === "sim" && !state.roster) initSim();
  if (tab === "llm") loadLLMSettings();
}

document.addEventListener("click", (e) => {
  const modeBtn = e.target.closest(".mode-btn");
  if (modeBtn) showMode(modeBtn.dataset.mode);
  const goto = e.target.closest("[data-goto]");
  if (goto) {
    showMode(goto.dataset.goto);
    if (goto.dataset.gotoTab) showAdminTab(goto.dataset.gotoTab);
  }
  const subTab = e.target.closest(".admin-sub-tab");
  if (subTab) showAdminTab(subTab.dataset.tab);
});

const state = {
  categories: null, currentCat: null, forms: null,
  roster: null, teams: { enemies: [], allies: [] },
  sim: null, step: 0, timer: null,
  editingCardId: null,
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
  const price = card.fields?.price;
  el.innerHTML = `
    <div class="card-art" style="${artStyle(card)}">
      ${icon}
      ${price != null ? `<span class="badge-price">🪙 ${price}</span>` : ""}
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
  const canEdit = state.forms && state.forms.some(f => f.card_type === card.card_type);
  $("#detail-body").innerHTML = `
    <button class="modal-close detail-close-btn" id="detail-close">✕</button>
    <div class="detail-art" style="${artStyle(card)}">${icon}
      ${card.is_unique ? '<span class="badge-unique">уник.</span>' : ""}</div>
    <div class="detail-content">
      <div class="sub">${card.type_label}</div>
      <h2>${esc(card.name)}</h2>
      ${card.description ? `<p class="desc">${esc(card.description)}</p>` : ""}
      <div class="kv">${rows.join("")}</div>
    </div>
    <div class="detail-foot">
      ${canEdit ? `<button class="btn-edit" id="detail-edit-btn">✏️ Редактировать</button>` : ""}
      <button class="btn-danger" id="detail-delete">🗑 Удалить</button>
    </div>`;
  $("#detail-close").onclick = () => closeModal("#detail-modal");
  if (canEdit) {
    $("#detail-edit-btn").onclick = () => { closeModal("#detail-modal"); openEditForm(card); };
  }
  $("#detail-delete").onclick = async () => {
    if (!confirm(`Удалить «${esc(card.name)}»? Это действие необратимо.`)) return;
    const { ok, status } = await API.delete(`/api/cards/${card.id}`);
    if (status === 204 || ok) {
      closeModal("#detail-modal");
      loadCards();
    } else {
      alert("Не удалось удалить: возможно, на неё ссылаются другие (например, она экипирована).");
    }
  };
  openModal("#detail-modal");
}

// ───────────────────────── форма добавления ─────────────────────────

function openAddForm() {
  state.editingCardId = null;
  const cat = categoryByKey(state.currentCat);
  const typeSel = $("#form-type");
  typeSel.innerHTML = "";
  typeSel.disabled = false;
  const allowed = state.forms.filter(fm => cat.creatable.includes(fm.card_type));
  allowed.forEach(fm => {
    const o = document.createElement("option");
    o.value = fm.card_type; o.textContent = `${fm.icon} ${fm.label}`;
    typeSel.appendChild(o);
  });
  typeSel.onchange = () => renderForm(typeSel.value);
  renderForm(allowed[0].card_type);
  $("#form-error").classList.add("hidden");
  $("#form-submit").textContent = "Создать";
  openModal("#modal");
}

function openEditForm(card) {
  state.editingCardId = card.id;
  const typeSel = $("#form-type");
  typeSel.innerHTML = "";
  typeSel.disabled = true;
  const form = formByType(card.card_type);
  const o = document.createElement("option");
  o.value = card.card_type; o.textContent = `${form.icon} ${form.label}`;
  typeSel.appendChild(o);
  typeSel.onchange = null;
  renderForm(card.card_type, card.form_values || {});
  $("#modal-title").textContent = `Редактировать: ${esc(card.name)}`;
  $("#form-error").classList.add("hidden");
  $("#form-submit").textContent = "Сохранить";

  // Для персонажей добавляем управление инвентарём и навыками
  if (card.card_type === "character") {
    renderCharManagementPanels(card);
  }

  openModal("#modal");
}

async function renderCharManagementPanels(card) {
  const modalBody = $(".modal-body");
  // Убираем старые панели если они были
  let existingPanels = $("#char-mgmt-panels");
  if (existingPanels) existingPanels.remove();

  const panels = document.createElement("div");
  panels.id = "char-mgmt-panels";

  // ── Экипировка ──
  const eqSection = document.createElement("div");
  eqSection.className = "char-mgmt-section";
  eqSection.innerHTML = `<div class="char-mgmt-title">⚔️ Экипировка</div>
    <div class="char-equip-row">
      <div class="char-equip-slot">
        <span class="char-equip-label">Оружие:</span>
        <span id="edit-weapon-name">${card.fields?.weapon ? esc(card.fields.weapon) : "—"}</span>
        <select id="edit-weapon-sel" style="flex:1;margin-left:8px"></select>
        <button class="btn-secondary char-equip-btn" id="edit-equip-weapon-btn">✓ Экипировать</button>
        <button class="btn-secondary char-equip-btn" id="edit-unequip-weapon-btn">✕ Снять</button>
      </div>
      <div class="char-equip-slot">
        <span class="char-equip-label">Броня:</span>
        <span id="edit-armor-name">${card.fields?.armor ? esc(card.fields.armor) : "—"}</span>
        <select id="edit-armor-sel" style="flex:1;margin-left:8px"></select>
        <button class="btn-secondary char-equip-btn" id="edit-equip-armor-btn">✓ Экипировать</button>
        <button class="btn-secondary char-equip-btn" id="edit-unequip-armor-btn">✕ Снять</button>
      </div>
    </div>`;
  panels.appendChild(eqSection);

  // ── Инвентарь ──
  const invSection = document.createElement("div");
  invSection.className = "char-mgmt-section";
  invSection.innerHTML = `<div class="char-mgmt-title">🎒 Инвентарь</div>
    <div id="edit-inv-list" class="char-mgmt-list"></div>
    <div class="char-mgmt-add-row">
      <select id="edit-add-item-sel" style="flex:1"></select>
      <button class="btn-secondary" id="edit-add-item-btn">➕ Добавить предмет</button>
    </div>`;
  panels.appendChild(invSection);

  // ── Навыки ──
  const skillSection = document.createElement("div");
  skillSection.className = "char-mgmt-section";
  skillSection.innerHTML = `<div class="char-mgmt-title">🎓 Навыки</div>
    <div id="edit-skill-list" class="char-mgmt-list"></div>
    <div class="char-mgmt-add-row">
      <select id="edit-add-skill-sel" style="flex:1"></select>
      <button class="btn-secondary" id="edit-add-skill-btn">➕ Добавить навык</button>
    </div>`;
  panels.appendChild(skillSection);

  modalBody.appendChild(panels);

  // Загружаем каталоги
  const [charData, itemsCatalog, skillsCatalog, equipment] = await Promise.all([
    API.get(`/api/cards/${card.id}`),
    API.get("/api/items-catalog"),
    API.get("/api/skills-catalog"),
    API.get("/api/equipment"),
  ]);

  // Заполняем текущий инвентарь
  const currentChar = charData;
  const invList = $("#edit-inv-list");
  function renderEditInv(charSnapshot) {
    invList.innerHTML = "";
    const inv = charSnapshot.fields?.inventory || currentChar.fields?.inventory || [];
    if (!inv.length) { invList.innerHTML = '<span class="muted hint">Инвентарь пуст</span>'; return; }
    // Получаем полные данные из свежего снимка (используем fields.inventory — имена)
    // Нам нужны id: берём из serialize данных
    inv.forEach(name => {
      // Найдём в каталоге по имени
      const found = itemsCatalog.find(it => it.name === name);
      if (!found) {
        const row = document.createElement("div"); row.className = "char-mgmt-row";
        row.innerHTML = `<span>${esc(name)}</span>`;
        invList.appendChild(row);
        return;
      }
      const row = document.createElement("div"); row.className = "char-mgmt-row";
      row.innerHTML = `<span>${esc(found.name)}</span><span class="muted" style="font-size:0.8em;margin-left:6px">${esc(found.card_type)}</span>
        <button class="btn-danger char-mgmt-rm" title="Убрать">✕</button>`;
      row.querySelector(".char-mgmt-rm").onclick = async () => {
        const r = await API.delete(`/api/characters/${card.id}/inventory/${found.id}`);
        if (r.ok) { const fresh = await API.get(`/api/cards/${card.id}`); renderEditInv(fresh); loadCards(); }
        else toast("Ошибка", true);
      };
      invList.appendChild(row);
    });
  }
  renderEditInv(currentChar);

  // Заполняем текущие навыки
  const skillList = $("#edit-skill-list");
  function renderEditSkills(charSnapshot) {
    skillList.innerHTML = "";
    const skills = charSnapshot.fields?.skills || currentChar.fields?.skills || [];
    if (!skills.length) { skillList.innerHTML = '<span class="muted hint">Нет навыков</span>'; return; }
    skills.forEach(name => {
      const found = skillsCatalog.find(s => s.name === name);
      const row = document.createElement("div"); row.className = "char-mgmt-row";
      row.innerHTML = `<span>${esc(name)}</span><button class="btn-danger char-mgmt-rm" title="Убрать">✕</button>`;
      if (found) {
        row.querySelector(".char-mgmt-rm").onclick = async () => {
          const r = await API.delete(`/api/characters/${card.id}/skills/${found.id}`);
          if (r.ok) { const fresh = await API.get(`/api/cards/${card.id}`); renderEditSkills(fresh); loadCards(); }
          else toast("Ошибка", true);
        };
      } else {
        row.querySelector(".char-mgmt-rm").disabled = true;
      }
      skillList.appendChild(row);
    });
  }
  renderEditSkills(currentChar);

  // Заполняем селект "добавить предмет"
  const addItemSel = $("#edit-add-item-sel");
  addItemSel.innerHTML = '<option value="">— выбрать предмет —</option>';
  itemsCatalog.forEach(it => {
    const opt = document.createElement("option");
    opt.value = it.id; opt.textContent = `${it.name} (${it.card_type})`;
    addItemSel.appendChild(opt);
  });

  $("#edit-add-item-btn").onclick = async () => {
    const itemId = addItemSel.value;
    if (!itemId) return;
    const { ok, data } = await API.post(`/api/characters/${card.id}/inventory`, { item_id: +itemId });
    if (ok) { renderEditInv(data); loadCards(); toast("Предмет добавлен"); }
    else toast(data?.errors?.__form__ || data?.error || "Ошибка", true);
  };

  // Заполняем селект "добавить навык"
  const addSkillSel = $("#edit-add-skill-sel");
  addSkillSel.innerHTML = '<option value="">— выбрать навык —</option>';
  skillsCatalog.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s.id; opt.textContent = s.name;
    addSkillSel.appendChild(opt);
  });

  $("#edit-add-skill-btn").onclick = async () => {
    const skillId = addSkillSel.value;
    if (!skillId) return;
    const { ok, data } = await API.post(`/api/characters/${card.id}/skills`, { skill_id: +skillId });
    if (ok) { renderEditSkills(data); loadCards(); toast("Навык добавлен"); }
    else toast(data?.errors?.__form__ || data?.error || "Ошибка", true);
  };

  // Экипировка: заполняем селект оружия из инвентаря
  const invWeapons = (currentChar.fields?.inventory || []).filter(name => {
    const it = itemsCatalog.find(i => i.name === name && i.card_type === "weapon");
    return !!it;
  });
  const weaponSel = $("#edit-weapon-sel");
  weaponSel.innerHTML = '<option value="">— из инвентаря —</option>';
  invWeapons.forEach(name => {
    const it = itemsCatalog.find(i => i.name === name && i.card_type === "weapon");
    if (it) { const opt = document.createElement("option"); opt.value = it.id; opt.textContent = it.name; weaponSel.appendChild(opt); }
  });
  // Также добавляем все доступные из полного каталога оружия
  equipment.weapons.forEach(w => {
    if (!invWeapons.includes(w.name)) {
      const opt = document.createElement("option"); opt.value = w.id; opt.textContent = `${w.name} (добавить из БД)`; weaponSel.appendChild(opt);
    }
  });

  const armorSel = $("#edit-armor-sel");
  const invArmors = (currentChar.fields?.inventory || []).filter(name => {
    const it = itemsCatalog.find(i => i.name === name && i.card_type === "armor");
    return !!it;
  });
  armorSel.innerHTML = '<option value="">— из инвентаря —</option>';
  invArmors.forEach(name => {
    const it = itemsCatalog.find(i => i.name === name && i.card_type === "armor");
    if (it) { const opt = document.createElement("option"); opt.value = it.id; opt.textContent = it.name; armorSel.appendChild(opt); }
  });
  equipment.armor.forEach(a => {
    if (!invArmors.includes(a.name)) {
      const opt = document.createElement("option"); opt.value = a.id; opt.textContent = `${a.name} (добавить из БД)`; armorSel.appendChild(opt);
    }
  });

  async function doEditEquip(slot, cardIdVal) {
    // Если предмет не в инвентаре — сначала добавим
    if (cardIdVal) {
      const inInv = (currentChar.fields?.inventory || []).some(name => {
        const it = itemsCatalog.find(i => i.id === +cardIdVal);
        return it && it.name === name;
      });
      if (!inInv) await API.post(`/api/characters/${card.id}/inventory`, { item_id: +cardIdVal });
    }
    const { ok, data } = await API.post(`/api/characters/${card.id}/equip`, { slot, card_id: cardIdVal ? +cardIdVal : null });
    if (ok) { toast(cardIdVal ? "Экипировано" : "Снято"); loadCards(); }
    else toast(data?.errors?.slot || "Ошибка", true);
  }

  $("#edit-equip-weapon-btn").onclick = () => doEditEquip("weapon", weaponSel.value || null);
  $("#edit-unequip-weapon-btn").onclick = () => doEditEquip("weapon", null);
  $("#edit-equip-armor-btn").onclick = () => doEditEquip("armor", armorSel.value || null);
  $("#edit-unequip-armor-btn").onclick = () => doEditEquip("armor", null);
}

function formByType(t) { return state.forms.find(f => f.card_type === t); }

function renderForm(cardType, values = {}) {
  const form = formByType(cardType);
  if (!state.editingCardId) {
    $("#modal-title").textContent = `Новая сущность: ${form.label}`;
  }
  $("#form-type-hint").textContent = form.note || "";
  const root = $("#entity-form");
  root.innerHTML = "";
  form.fields.forEach(fld => root.appendChild(renderField(fld, values[fld.name])));
}

function renderField(fld, initialValue = undefined) {
  const wrap = document.createElement("label");
  const isCheck = fld.type === "bool";
  const isWide = fld.type === "text";
  wrap.className = "field" + (isCheck ? " check" : "") + (isWide ? " full" : "");
  wrap.dataset.name = fld.name;

  let control;
  if (fld.type === "bool") {
    control = document.createElement("input");
    control.type = "checkbox";
    control.checked = initialValue !== undefined ? Boolean(initialValue) : Boolean(fld.default);
  } else if (fld.type === "choice") {
    control = document.createElement("select");
    const blank = document.createElement("option");
    blank.value = ""; blank.textContent = fld.required ? "— выберите —" : "— нет —";
    control.appendChild(blank);
    const activeValue = initialValue !== undefined ? initialValue : fld.default;
    (fld.choices || []).forEach(c => {
      const o = document.createElement("option");
      o.value = c.value; o.textContent = c.label;
      if (activeValue != null && String(c.value) === String(activeValue)) o.selected = true;
      control.appendChild(o);
    });
  } else {
    control = document.createElement("input");
    control.type = fld.type === "int" ? "number" : "text";
    const val = initialValue !== undefined ? initialValue : fld.default;
    if (val !== null && val !== undefined) control.value = val;
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

function _clearFormErrors() {
  $$("#entity-form .field").forEach(w => { w.classList.remove("invalid"); const e = $(".err", w); if (e) e.textContent = ""; });
  $("#form-error").classList.add("hidden");
}

function _showFormErrors(errors) {
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

async function submitForm() {
  if (state.editingCardId != null) { await submitEditForm(state.editingCardId); return; }
  const body = collectForm();
  const { ok, data } = await API.post("/api/cards", body);
  _clearFormErrors();
  if (ok) {
    closeModal("#modal");
    toast(`Создано: ${data.name}`);
    if (state.currentCat) loadCards();
    return;
  }
  _showFormErrors(data.errors || {});
}

async function submitEditForm(cardId) {
  const body = collectForm();
  const { ok, data } = await API.patch(`/api/cards/${cardId}`, body);
  _clearFormErrors();
  if (ok) {
    closeModal("#modal");
    toast(`Сохранено: ${data.name}`);
    if (state.currentCat) loadCards();
    return;
  }
  _showFormErrors(data.errors || {});
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

// runSim определена ниже (интерактивный бой или автосимуляция)

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
  if (o.winner === "party") SFX.victory();
  else if (o.winner === "enemy") SFX.defeat();
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

// ───────────────────────── ИНТЕРАКТИВНЫЙ БОЙ ─────────────────────────

const ib = {
  battleId: null,
  combatants: [],    // текущий снимок всех участников
  actor: null,       // опции хода текущего игрового персонажа
  status: null,      // "waiting" | "processing" | "over" | null
  dragging: null,    // uid карточки, которую тянут
  dragGhost: null,
};

// ── Переключение чекбокса "Ручное управление" ──

function updateManualHint() {
  const manual = $("#sim-manual").checked;
  $("#allies-hint").textContent = manual ? "(вы управляете)" : "(ИИ играет за всех)";
  $("#sim-go").textContent = manual ? "▶ Начать бой (ручной режим)" : "▶ Симулировать бой";
}
$("#sim-manual").addEventListener("change", updateManualHint);

// ── Запуск ──

async function runSim() {
  if ($("#sim-manual").checked) {
    await startInteractiveBattle();
  } else {
    await runAutoSim();
  }
}

// ── Автосимуляция (без изменений логики) ──

async function runAutoSim() {
  const allies = state.teams.allies.map(e => e.card.id);
  const enemies = state.teams.enemies.map(e => e.card.id);
  if (!allies.length || !enemies.length) { toast("Нужны участники с обеих сторон", true); return; }
  const seedVal = $("#sim-seed").value;
  const { ok, data } = await API.post("/api/simulate", {
    allies, enemies, seed: seedVal === "" ? null : Number(seedVal),
  });
  if (!ok) { toast(data.error || "Ошибка симуляции", true); return; }
  state.sim = data; state.step = 0;
  $("#battle-arena").classList.add("hidden");
  $("#sim-stage").classList.remove("hidden");
  $("#outcome").classList.add("hidden");
  $("#battle-log").innerHTML = "";
  renderStep(0, true);
  $("#sim-stage").scrollIntoView({ behavior: "smooth" });
}

// ── Интерактивный бой ──

async function startInteractiveBattle() {
  const allies = state.teams.allies.map(e => e.card.id);
  const enemies = state.teams.enemies.map(e => e.card.id);
  if (!allies.length || !enemies.length) { toast("Нужны участники с обеих сторон", true); return; }
  const seedVal = $("#sim-seed").value;

  const { ok, data } = await API.post("/api/battle/start", {
    allies, enemies, seed: seedVal === "" ? null : Number(seedVal),
  });
  if (!ok) { toast(data.error || "Ошибка запуска боя", true); return; }

  ib.battleId = data.battle_id;
  ib.combatants = data.combatants;

  $("#sim-stage").classList.add("hidden");
  $("#ba-log").innerHTML = "";
  $("#ba-verbose-log").textContent = "";
  $("#ba-outcome").classList.add("hidden");
  $("#battle-arena").classList.remove("hidden");
  $("#battle-arena").scrollIntoView({ behavior: "smooth" });
  initVerboseToggle();

  renderBattleArena(true);
  applyBattleEvents(data.events);

  if (data.status === "waiting") {
    ib.actor = data.actor;
    ib.status = "waiting";
    renderBattleArena();
    const actorC = ib.combatants.find(c => c.uid === data.actor.uid);
    if (actorC) showTurnBanner(actorC.name, actorC.side).then(() => highlightActorTurn(data.actor));
    else highlightActorTurn(data.actor);
  } else if (data.status === "over") {
    ib.status = "over";
    showBattleOutcome(data.outcome);
  }
}

// ── Отрисовка арены ──

function renderBattleArena(rebuild = false) {
  renderBattleRow("ba-enemies", "enemy", rebuild);
  renderBattleRow("ba-allies", "party", rebuild);
}

function renderBattleRow(rowId, side, rebuild = false) {
  const row = $(`#${rowId}`);
  const coms = ib.combatants.filter(c => c.side === side);
  if (rebuild || row.querySelectorAll(".bc").length !== coms.length) {
    row.innerHTML = "";
    coms.forEach(c => row.appendChild(createBattleCard(c)));
  } else {
    coms.forEach(c => updateBattleCard(c));
  }
}

function createBattleCard(c) {
  const unit = document.createElement("div");
  unit.className = "bc-unit";

  // Зона эффектов слева
  const effZone = document.createElement("div");
  effZone.className = "bc-eff-zone";
  effZone.innerHTML = renderEffectCols(c.effects || []);

  // Ячейка: карточка + имя
  const cell = document.createElement("div");
  cell.className = "bc-cell";

  const el = document.createElement("div");
  el.className = "bc";
  el.dataset.uid = c.uid;
  el.dataset.side = c.side;
  if (!c.alive || c.dying) el.classList.add("down");
  if (c.has_bastion) el.classList.add("has-bastion");

  const pct = c.max_hp ? Math.max(0, (c.hp / c.max_hp) * 100) : 0;
  const hpColor = c.side === "enemy"
    ? `background:linear-gradient(90deg,var(--enemy),#ff8a7d)`
    : `background:linear-gradient(90deg,var(--good),#8fd36a)`;
  const descAttr = c.description ? ` title="${esc(c.description)}"` : "";
  el.innerHTML = `
    ${c.has_bastion ? '<div class="bc-bastion-badge">🛡</div>' : ""}
    <div class="bc-icon"${descAttr}>${TYPE_ICON[c.kind] || "❓"}</div>
    <div class="hpbar"><i style="width:${pct}%;${hpColor}"></i></div>
    <div class="bc-hp">${c.hp}/${c.max_hp}</div>
    <div class="bc-defenses">${renderDefenses(c)}</div>`;

  const nameEl = document.createElement("div");
  nameEl.className = "bc-name";
  nameEl.textContent = c.name;

  cell.appendChild(el);
  cell.appendChild(nameEl);
  unit.appendChild(effZone);
  unit.appendChild(cell);

  if (c.side === "party") setupAllyDrag(el, c.uid);
  return unit;
}

function renderDefenses(c) {
  if (c.phys_def == null) return "";
  return `
    <div class="bc-def-chip" title="Физическая защита">
      <span class="bc-def-icon">🛡️</span><span class="bc-def-val">${c.phys_def}</span>
    </div>
    <div class="bc-def-chip" title="Магическая защита">
      <span class="bc-def-icon">🔮</span><span class="bc-def-val">${c.mag_def}</span>
    </div>
    <div class="bc-def-chip" title="Ментальная защита">
      <span class="bc-def-icon">🧠</span><span class="bc-def-val">${c.mental_def}</span>
    </div>`;
}

function renderEffectCols(effects) {
  if (!effects.length) return "";
  const cols = [];
  for (let i = 0; i < effects.length; i += 5) cols.push(effects.slice(i, i + 5));
  return cols.map(col =>
    `<div class="bc-eff-col">${col.map(renderEffectDot).join("")}</div>`
  ).join("");
}

function renderEffectDot(e) {
  const isSpecial = e.modifier === 0;
  const cls = isSpecial ? "special" : (e.modifier > 0 ? "buff" : "debuff");
  const icon = isSpecial ? "✦" : (e.modifier > 0 ? "▲" : "▼");
  const sign = e.modifier > 0 ? "+" : "";
  const modStr = isSpecial ? "" : ` ${sign}${e.modifier}`;
  const dur = e.duration > 0 ? ` (${e.duration} р.)` : "";
  const tip = `${e.description || e.target}${modStr}${dur}`.trim();
  return `<span class="bc-eff-dot ${cls}" title="${esc(tip)}">${icon}</span>`;
}

function updateBattleCard(c) {
  const el = document.querySelector(`.bc[data-uid="${c.uid}"]`);
  if (!el) return;
  const pct = c.max_hp ? Math.max(0, (c.hp / c.max_hp) * 100) : 0;
  el.querySelector(".hpbar > i").style.width = pct + "%";
  el.querySelector(".bc-hp").textContent = `${c.hp}/${c.max_hp}`;
  el.classList.toggle("down", !c.alive || c.dying);
  el.classList.toggle("has-bastion", c.has_bastion);
  const badge = el.querySelector(".bc-bastion-badge");
  if (c.has_bastion && !badge) {
    const div = document.createElement("div");
    div.className = "bc-bastion-badge"; div.textContent = "🛡";
    el.prepend(div);
  } else if (!c.has_bastion && badge) {
    badge.remove();
  }
  const defEl = el.querySelector(".bc-defenses");
  if (defEl) defEl.innerHTML = renderDefenses(c);
  // обновляем эффекты в зоне слева от карточки
  const unit = el.closest(".bc-unit");
  if (unit) {
    const effZone = unit.querySelector(".bc-eff-zone");
    if (effZone) effZone.innerHTML = renderEffectCols(c.effects || []);
  }
}

// ── Подсветка хода ──

function highlightActorTurn(actor) {
  $$(".bc[data-side=party]").forEach(el => {
    const isActor = parseInt(el.dataset.uid) === actor.uid;
    el.classList.toggle("active-turn", isActor);
    const unit = el.closest(".bc-unit");
    if (unit) unit.classList.toggle("dimmed", !isActor && !el.classList.contains("down"));
  });
  $("#ba-turn-label").textContent = `Ходит: ${actor.name}`;
  setArenaButtons(true);
}

function clearTurnHighlight() {
  $$(".bc").forEach(el => el.classList.remove("active-turn", "valid-target", "invalid-target"));
  $$(".bc-unit").forEach(el => el.classList.remove("dimmed"));
  $("#ba-turn-label").textContent = "";
  setArenaButtons(false);
}

function setArenaButtons(enabled) {
  $("#ba-flee").disabled = !enabled;
  $("#ba-pass").disabled = !enabled;
}

// ── Drag-to-attack ──

function setupAllyDrag(el, uid) {
  let longTimer = null;
  let dragStarted = false;
  let sx, sy;

  el.addEventListener("contextmenu", e => {
    e.preventDefault();
    if (canActorAct(uid)) showRadialMenu(e.clientX, e.clientY, uid);
  });

  el.addEventListener("pointerdown", e => {
    if (!canActorAct(uid)) return;
    e.preventDefault();
    sx = e.clientX; sy = e.clientY;
    dragStarted = false;
    el.setPointerCapture(e.pointerId);

    longTimer = setTimeout(() => {
      if (!dragStarted) showRadialMenu(sx, sy, uid);
    }, 500);

    function onMove(e) {
      if (!dragStarted && (Math.abs(e.clientX - sx) > 8 || Math.abs(e.clientY - sy) > 8)) {
        dragStarted = true;
        clearTimeout(longTimer);
        startDrag(uid, e.clientX, e.clientY);
      }
      if (dragStarted) moveDrag(e.clientX, e.clientY);
    }
    function onUp(e) {
      clearTimeout(longTimer);
      cleanup();
      if (dragStarted) endDrag(e.clientX, e.clientY, uid);
    }
    function onCancel() { clearTimeout(longTimer); cleanup(); cancelDrag(); }
    function cleanup() {
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onCancel);
    }
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onCancel);
  });
}

function startDrag(uid, x, y) {
  ib.dragging = uid;
  const actor = ib.actor;
  if (!actor) return;

  // Подсветить допустимые цели
  $$(".bc[data-side=enemy]").forEach(el => {
    const t = actor.targets.find(t => t.uid === parseInt(el.dataset.uid));
    el.classList.toggle("valid-target", !!(t && t.available));
    el.classList.toggle("invalid-target", !(t && t.available));
  });

  // Создать призрак
  const src = document.querySelector(`.bc[data-uid="${uid}"]`);
  const ghost = src.cloneNode(true);
  ghost.className = "bc drag-ghost";
  ghost.style.width = src.offsetWidth + "px";
  document.body.appendChild(ghost);
  ib.dragGhost = ghost;
  moveDrag(x, y);
}

function moveDrag(x, y) {
  if (!ib.dragGhost) return;
  const g = ib.dragGhost;
  g.style.left = (x - g.offsetWidth / 2) + "px";
  g.style.top = (y - g.offsetHeight / 2) + "px";
}

function endDrag(x, y, uid) {
  if (ib.dragGhost) { ib.dragGhost.remove(); ib.dragGhost = null; }
  restoreDragVisuals();

  // Найти карточку под пальцем/курсором
  const el = document.elementFromPoint(x, y);
  const card = el && el.closest(".bc[data-side=enemy]");
  if (card) {
    const targetUid = parseInt(card.dataset.uid);
    const actor = ib.actor;
    const t = actor && actor.targets.find(t => t.uid === targetUid);
    if (t && t.available) {
      showAttackPopup(uid, targetUid);
    } else {
      card.classList.add("shake");
      setTimeout(() => card.classList.remove("shake"), 450);
    }
  }
  ib.dragging = null;
}

function cancelDrag() {
  if (ib.dragGhost) { ib.dragGhost.remove(); ib.dragGhost = null; }
  restoreDragVisuals();
  ib.dragging = null;
}

function restoreDragVisuals() {
  $$(".bc").forEach(el => el.classList.remove("valid-target", "invalid-target"));
  if (ib.actor) highlightActorTurn(ib.actor);
}

// ── Попап выбора действия ──

function showAttackPopup(actorUid, targetUid) {
  const actor = ib.actor;
  if (!actor || actor.uid !== actorUid) return;
  const t = actor.targets.find(t => t.uid === targetUid);
  const list = $("#ap-list");
  list.innerHTML = "";
  $("#ap-title").textContent = `→ ${t ? t.name : "цель"}`;

  addApItem("⚔️ Физическая атака", () => {
    sendAction({ kind: "attack_physical", target_uid: targetUid });
    closeApPopup();
  });
  actor.spells.forEach(sp => {
    addApItem(`✨ ${sp.name}  (${sp.damage}, сл.${sp.difficulty})`, () => {
      sendAction({ kind: "cast_spell", target_uid: targetUid, carrier_card_id: sp.carrier_id });
      closeApPopup();
    });
  });

  openApPopup();
}

function addApItem(label, onClick, disabled = false) {
  const btn = document.createElement("button");
  btn.className = "ap-item" + (disabled ? " disabled" : "");
  btn.textContent = label;
  if (onClick && !disabled) btn.onclick = onClick;
  $("#ap-list").appendChild(btn);
}

function openApPopup() { $("#action-popup").classList.remove("hidden"); $("#action-popup-bg").classList.remove("hidden"); }
function closeApPopup() { $("#action-popup").classList.add("hidden"); $("#action-popup-bg").classList.add("hidden"); }

// ── Радиальное меню ──

function showRadialMenu(cx, cy, uid) {
  const actor = ib.actor;
  if (!actor || actor.uid !== uid) return;

  const items = buildRadialItems(actor);
  if (!items.length) return;

  const r = 82;

  // Clamp so the ring (radius + half-item 28px) stays within viewport
  const margin = r + 28;
  cx = Math.max(margin, Math.min(window.innerWidth  - margin, cx));
  cy = Math.max(margin, Math.min(window.innerHeight - margin, cy));

  const menu = $("#radial-menu");
  menu.innerHTML = "";

  // Центральная точка
  const center = document.createElement("div");
  center.className = "radial-center";
  center.style.left = cx + "px";
  center.style.top = cy + "px";
  menu.appendChild(center);
  items.forEach((item, i) => {
    const angle = ((-90 + (360 / items.length) * i) * Math.PI) / 180;
    const ix = cx + r * Math.cos(angle);
    const iy = cy + r * Math.sin(angle);
    const el = document.createElement("button");
    el.className = "radial-item" + (item.disabled ? " disabled" : "");
    el.style.left = ix + "px";
    el.style.top = iy + "px";
    el.style.animationDelay = `${i * 30}ms`;
    el.title = item.tooltip || item.label;
    el.innerHTML = `<span class="ri-icon">${item.icon}</span><span class="ri-label">${esc(item.label)}</span>`;
    if (!item.disabled) el.onclick = () => { closeRadialMenu(); item.action(); };
    menu.appendChild(el);
  });

  menu.classList.remove("hidden");
  setTimeout(() => document.addEventListener("pointerdown", closeRadialMenuOnce), 80);
}

function closeRadialMenuOnce(e) {
  if (!e.target.closest(".radial-item")) closeRadialMenu();
}
function closeRadialMenu() {
  $("#radial-menu").classList.add("hidden");
  document.removeEventListener("pointerdown", closeRadialMenuOnce);
}

function buildRadialItems(actor) {
  const items = [];

  // Физическая атака → выбор цели
  items.push({
    icon: "⚔️", label: "Атака",
    action: () => showTargetPopup("attack", actor),
  });

  // Заклинания → выбор цели
  actor.spells.forEach(sp => {
    items.push({
      icon: "✨", label: sp.name,
      action: () => showTargetPopup("spell", actor, sp),
    });
  });

  // Активные способности
  actor.active_abilities.forEach(ab => {
    items.push({
      icon: "⭐", label: ab.name,
      action: () => sendAction({ kind: "activate_ability", ability_name: ab.name }),
    });
  });

  // Зелье
  if (actor.has_potion) {
    items.push({
      icon: "🧪", label: "Зелье",
      action: () => sendAction({ kind: "use_potion" }),
    });
  }

  // Договориться
  items.push({
    icon: "🤝", label: "Договор",
    disabled: !actor.can_negotiate.available,
    tooltip: actor.can_negotiate.reason || "Начать переговоры",
    action: () => sendAction({ kind: "negotiate", enemy_side: "enemy" }),
  });

  // Устрашение
  items.push({
    icon: "😱", label: "Устрашить",
    disabled: !actor.can_intimidate.available,
    tooltip: actor.can_intimidate.reason || "Устрашить врагов",
    action: () => sendAction({ kind: "intimidate", enemy_side: "enemy" }),
  });

  return items.slice(0, 8);
}

function showTargetPopup(type, actor, spell = null) {
  const list = $("#ap-list");
  list.innerHTML = "";
  $("#ap-title").textContent = type === "spell"
    ? `Цель: ${spell.name}`
    : "Выбрать цель";

  const targets = actor.targets.filter(t => t.available);
  if (!targets.length) {
    addApItem("Нет допустимых целей", null, true);
  } else {
    targets.forEach(t => {
      const hpPct = t.max_hp ? Math.round((t.hp / t.max_hp) * 100) : 0;
      const label = `${t.name}  ${t.hp}/${t.max_hp} HP${t.has_bastion ? " 🛡" : ""}  (${hpPct}%)`;
      addApItem(label, () => {
        if (type === "spell") {
          sendAction({ kind: "cast_spell", target_uid: t.uid, carrier_card_id: spell.carrier_id });
        } else {
          sendAction({ kind: "attack_physical", target_uid: t.uid });
        }
        closeApPopup();
      });
    });
  }
  openApPopup();
}

// ── Отправка действия ──

async function sendAction(actionData) {
  if (!ib.battleId || ib.status !== "waiting") return;
  ib.status = "processing";
  clearTurnHighlight();

  const { ok, data } = await API.post(`/api/battle/${ib.battleId}/action`, actionData);
  if (!ok) {
    toast(data.error || "Ошибка", true);
    ib.status = "waiting";
    if (ib.actor) highlightActorTurn(ib.actor);
    return;
  }

  await animateBattleEvents(data.events);

  ib.combatants = data.combatants;
  renderBattleArena();

  if (data.status === "waiting") {
    ib.actor = data.actor;
    ib.status = "waiting";
    // Баннер — в начале хода игрока, после того как враги отыграли
    const actorCombatant = ib.combatants.find(c => c.uid === data.actor.uid);
    if (actorCombatant) await showTurnBanner(actorCombatant.name, actorCombatant.side);
    highlightActorTurn(data.actor);
  } else if (data.status === "over") {
    ib.status = "over";
    ib.actor = null;
    clearTurnHighlight();
    showBattleOutcome(data.outcome);
  }
}

// ── Анимация событий ──

function applyBattleEvents(events) {
  const log = $("#ba-log");
  events.forEach(ev => appendEventToLog(log, ev));
  log.scrollTop = log.scrollHeight;
  if (events.length) updateRoundLabel(events[events.length - 1]);
  appendVerboseLog(events);
}

async function animateBattleEvents(events) {
  const log = $("#ba-log");
  let lastActorUid = null;
  for (const ev of events) {
    // Баннер только для хода врага (ход игрока — после окончания анимации)
    if (ev.phase === "action" && ev.actor_uid != null && ev.actor_uid !== lastActorUid) {
      lastActorUid = ev.actor_uid;
      const c = ib.combatants.find(x => x.uid === ev.actor_uid);
      if (c && c.side === "enemy") await showTurnBanner(c.name, c.side, 800);
    }

    appendEventToLog(log, ev);
    log.scrollTop = log.scrollHeight;
    updateRoundLabel(ev);

    const logText = (ev.log || []).join(" ");
    let soundPlayed = false;

    if (ev.combatants) {
      const prevHp = {};
      ib.combatants.forEach(c => { prevHp[c.uid] = c.hp; });
      let targetUid = null, anyDied = false, anyHealed = false;
      ev.combatants.forEach(c => {
        if (prevHp[c.uid] !== undefined) {
          const d = c.hp - prevHp[c.uid];
          if (d < 0) { if (!targetUid) targetUid = c.uid; if (c.hp <= 0) anyDied = true; }
          if (d > 0) anyHealed = true;
        }
      });
      if (ev.actor_uid && targetUid) animateAttack(ev.actor_uid, targetUid);
      ev.combatants.forEach(c => {
        updateBattleCard(c);
        if (prevHp[c.uid] !== undefined && prevHp[c.uid] !== c.hp) {
          spawnDmgFloat(c.uid, c.hp - prevHp[c.uid]);
        }
      });
      // Звук по приоритету: смерть > AoE > лечение > заклинание/удар
      if (anyDied)                          { SFX.kill();  soundPlayed = true; }
      else if (logText.includes("[взрыв]")) { SFX.aoe();   soundPlayed = true; }
      else if (anyHealed)                   { SFX.heal();  soundPlayed = true; }
      else if (targetUid) {
        logText.includes("кастует") ? SFX.spell() : SFX.hit();
        soundPlayed = true;
      }
    }
    // Промах или провал заклинания — HP не меняется, определяем по тексту
    if (!soundPlayed) {
      if (logText.includes("промахивается") || logText.includes("проваливает")) SFX.miss();
      else if (logText.includes("кастует")) SFX.spell();
    }

    appendVerboseLog([ev]);
    await pause(220);
  }
}

function animateAttack(attackerUid, targetUid) {
  const src = document.querySelector(`.bc[data-uid="${attackerUid}"]`);
  const tgt = document.querySelector(`.bc[data-uid="${targetUid}"]`);
  if (!src || !tgt) return;
  const sr = src.getBoundingClientRect();
  const tr = tgt.getBoundingClientRect();
  const dx = (tr.left + tr.width / 2) - (sr.left + sr.width / 2);
  const dy = (tr.top + tr.height / 2) - (sr.top + sr.height / 2);
  const dist = Math.sqrt(dx * dx + dy * dy) || 1;
  const nx = (dx / dist) * Math.min(28, dist * 0.35);
  const ny = (dy / dist) * Math.min(28, dist * 0.35);

  // Атакующий — рывок вперёд и назад
  src.style.transition = "transform 90ms ease-out";
  src.style.transform = `translate(${nx}px,${ny}px) scale(1.06)`;
  setTimeout(() => {
    src.style.transition = "transform 200ms ease-in-out";
    src.style.transform = "";
    setTimeout(() => { src.style.transition = ""; }, 220);
  }, 90);

  // Цель — вспышка при попадании (с небольшой задержкой)
  setTimeout(() => {
    tgt.classList.remove("hit-flash");
    void tgt.offsetWidth; // reflow
    tgt.classList.add("hit-flash");
    setTimeout(() => tgt.classList.remove("hit-flash"), 400);
  }, 80);
}

function appendVerboseLog(events) {
  const pre = $("#ba-verbose-log");
  if (!pre) return;
  events.forEach(ev => {
    if (!ev.log || !ev.log.length) return;
    if (ev.phase === "round_start") pre.textContent += `\n=== Раунд ${ev.round} ===\n`;
    ev.log.forEach(line => { pre.textContent += line + "\n"; });
  });
  pre.scrollTop = pre.scrollHeight;
}

function initVerboseToggle() {
  const cb = document.getElementById("ba-verbose");
  const wrap = document.getElementById("ba-verbose-wrap");
  if (!cb || !wrap) return;
  cb.addEventListener("change", () => {
    wrap.classList.toggle("hidden", !cb.checked);
  });
}

function showTurnBanner(name, side, duration = 1100) {
  return new Promise(resolve => {
    const el = document.createElement("div");
    el.className = "turn-banner" + (side === "enemy" ? " side-enemy" : " side-ally");
    el.style.animationDuration = duration + "ms";
    el.innerHTML = `
      <div class="turn-banner-inner">
        <div class="turn-banner-label">Ходит</div>
        <div class="turn-banner-name">${esc(name)}</div>
      </div>`;
    document.body.appendChild(el);
    setTimeout(() => { el.remove(); resolve(); }, duration);
  });
}

function appendEventToLog(log, ev) {
  if (ev.phase === "round_start" || (ev.phase === "start" && ev.log.length === 0)) {
    if (ev.phase === "round_start") {
      const rm = document.createElement("div");
      rm.className = "line round-mark";
      rm.textContent = `— Раунд ${ev.round} —`;
      log.appendChild(rm);
    }
  }
  ev.log.forEach(line => {
    const d = document.createElement("div");
    d.className = "line"; d.textContent = line;
    log.appendChild(d);
  });
}

function updateRoundLabel(ev) {
  if (ev.phase === "start") { $("#ba-round-label").textContent = "Начало боя"; return; }
  if (ev.phase === "round_start" || ev.phase === "action" || ev.phase === "round_end") {
    $("#ba-round-label").textContent = `Раунд ${ev.round}`;
  }
}

function spawnDmgFloat(uid, delta) {
  const card = document.querySelector(`.bc[data-uid="${uid}"]`);
  if (!card) return;
  const rect = card.getBoundingClientRect();
  const el = document.createElement("div");
  el.className = "dmg-float" + (delta > 0 ? " heal" : "");
  el.textContent = (delta > 0 ? "+" : "") + delta;
  el.style.left = (rect.left + rect.width / 2 - 16) + "px";
  el.style.top = (rect.top + 8) + "px";
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 950);
}

function showBattleOutcome(outcome) {
  if (outcome.winner === "party") SFX.victory();
  else if (outcome.winner === "enemy") SFX.defeat();
  const box = $("#ba-outcome");
  let cls = "draw", txt;
  if (outcome.winner === "party") { cls = "win-allies"; txt = "🛡️ Победа союзников!"; }
  else if (outcome.winner === "enemy") { cls = "win-enemies"; txt = "👹 Победа врагов!"; }
  else txt = outcome.ended_by === "negotiation" ? "🤝 Бой завершён переговорами"
           : outcome.ended_by === "timeout" ? "⏳ Ничья по таймауту" : "Ничья";
  const surv = Object.entries(outcome.survivors)
    .map(([s, names]) => `${s === "party" ? "Союзники" : "Враги"}: ${names.join(", ") || "—"}`).join(" · ");
  box.className = "outcome " + cls;
  box.innerHTML = `<div>${txt}</div>
    <div class="survivors">за ${outcome.rounds} раунд(ов) · ${outcome.ended_by}</div>
    <div class="survivors">Выжившие — ${surv}</div>
    <button onclick="leaveBattle()" style="margin-top:14px" class="btn-secondary">← Назад к настройке</button>`;
  box.classList.remove("hidden");
}

function leaveBattle() {
  $("#battle-arena").classList.add("hidden");
  Object.assign(ib, { battleId: null, combatants: [], actor: null, status: null, dragging: null, dragGhost: null });
}

function canActorAct(uid) {
  return ib.status === "waiting" && ib.actor && ib.actor.uid === uid;
}

function pause(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Кнопки боя ──

$("#ba-flee").onclick = () => {
  if (ib.status !== "waiting") return;
  if (!confirm("Попытаться сбежать всей группой?\n\nКаждый бросает d20 + DEX ≥ 10. Провал — гибель.")) return;
  closeRadialMenu();
  sendAction({ kind: "flee" });
};

$("#ba-pass").onclick = () => {
  if (ib.status !== "waiting") return;
  sendAction({ kind: "pass" });
};

$("#ap-cancel").onclick = closeApPopup;
$("#action-popup-bg").onclick = closeApPopup;

// ───────────────────────── Состояние группы ─────────────────────────

const partyState = { chars: [], sessions: [], sessionId: "" };
let _dragCtx = null; // { charId, cardId, cardType, fromSlot: null|"weapon"|"armor" }

async function initParty() {
  // Оставлено для совместимости — теперь вызывается через openAdvPartyPanel
}

async function loadPartyChars() {
  partyState.chars = await API.get("/api/party");
  renderParty();
}

function renderParty() {
  const grid = $("#adv-party-grid");
  if (!grid) return;
  grid.innerHTML = "";
  if (!partyState.chars.length) {
    grid.innerHTML = '<p style="color:var(--muted);text-align:center;padding:40px">Нет игровых персонажей.</p>';
    return;
  }
  partyState.chars.forEach(ch => grid.appendChild(buildCharCard(ch)));
}

function buildCharCard(ch) {
  const el = document.createElement("div");
  el.className = "party-char";
  const hpPct = ch.max_hp ? Math.max(0, Math.min(100, (ch.current_hp / ch.max_hp) * 100)) : 0;
  const fillCls = hpPct > 50 ? "" : hpPct > 25 ? " low" : " crit";

  el.innerHTML = `
    <div class="pch-head">
      <div class="pch-name">${esc(ch.name)}</div>
      ${ch.description ? `<div class="pch-desc">${esc(ch.description)}</div>` : ""}
      <div class="pch-hp-row">
        <div class="pch-hp-bar"><div class="pch-hp-fill${fillCls}" style="width:${hpPct}%"></div></div>
        <span class="pch-hp-label">${ch.current_hp} / ${ch.max_hp} HP</span>
      </div>
      <div class="pch-money">💰 ${ch.money} зол.</div>
    </div>

    <div class="pch-body">
      <div class="pch-equip-zone">
        <div class="pch-slot-header">⚔️ Оружие</div>
        <div class="pch-drop-slot" data-char-id="${ch.id}" data-drop-zone="weapon">
          ${ch.equipped_weapon ? `
            <div class="pch-equipped-item" draggable="true"
                 data-char-id="${ch.id}" data-card-id="${ch.equipped_weapon.id}"
                 data-card-type="weapon" data-from-slot="weapon">
              <div class="pch-eqi-name">${esc(ch.equipped_weapon.name)}</div>
              <div class="pch-eqi-sub">⚔️ ${ch.equipped_weapon.damage_dice}</div>
              ${ch.equipped_weapon.description ? `<div class="pch-eqi-desc">${esc(ch.equipped_weapon.description)}</div>` : ""}
            </div>` : `
            <div class="pch-slot-empty">Нет оружия<span class="pch-slot-hint">перетащи из инвентаря</span></div>`}
        </div>
      </div>
      <div class="pch-equip-zone">
        <div class="pch-slot-header">🛡️ Доспех</div>
        <div class="pch-drop-slot" data-char-id="${ch.id}" data-drop-zone="armor">
          ${ch.equipped_armor ? `
            <div class="pch-equipped-item" draggable="true"
                 data-char-id="${ch.id}" data-card-id="${ch.equipped_armor.id}"
                 data-card-type="armor" data-from-slot="armor">
              <div class="pch-eqi-name">${esc(ch.equipped_armor.name)}</div>
              <div class="pch-eqi-sub">🛡️ +${ch.equipped_armor.phys_def_bonus} к ФЗ</div>
              ${ch.equipped_armor.description ? `<div class="pch-eqi-desc">${esc(ch.equipped_armor.description)}</div>` : ""}
            </div>` : `
            <div class="pch-slot-empty">Нет доспеха<span class="pch-slot-hint">перетащи из инвентаря</span></div>`}
        </div>
      </div>
      <div class="pch-stats-col">
        <div class="pch-slot-header">Характеристики</div>
        <div class="pch-stats">
          <div class="pch-stat-row"><span class="pch-sico">💪</span><b>${ch.strength}</b><span class="pch-sname">Сила</span></div>
          <div class="pch-stat-row"><span class="pch-sico">🏃</span><b>${ch.dexterity}</b><span class="pch-sname">Ловкость</span></div>
          <div class="pch-stat-row"><span class="pch-sico">🧠</span><b>${ch.wisdom}</b><span class="pch-sname">Мудрость</span></div>
          <div class="pch-stat-row"><span class="pch-sico">💬</span><b>${ch.charisma}</b><span class="pch-sname">Харизма</span></div>
          <div class="pch-stat-row"><span class="pch-sico">🛡</span><b>${ch.phys_defense}</b><span class="pch-sname">Физзащита</span></div>
          <div class="pch-stat-row"><span class="pch-sico">✨</span><b>${ch.mag_defense}</b><span class="pch-sname">Магзащита</span></div>
        </div>
        ${ch.skills.length ? `
          <div class="pch-skills-title">Навыки</div>
          ${ch.skills.map(s => `
            <div class="pch-skill">
              <span>${esc(s.name)}</span>
              <span class="pch-skill-tag">${s.is_passive ? "пас." : "акт."}</span>
            </div>`).join("")}
        ` : ""}
      </div>
    </div>

    <div class="pch-inv-zone" data-char-id="${ch.id}" data-drop-zone="inventory">
      <div class="pch-inv-header">Инвентарь</div>
      <div class="pch-inv-items">
        ${ch.inventory.length
          ? ch.inventory.map(it => buildInvItem(it, ch.id)).join("")
          : '<span class="pch-inv-empty">пусто</span>'}
      </div>
    </div>
  `;

  // Drag from equipped slot → inventory = unequip
  el.querySelectorAll("[data-from-slot]").forEach(item => {
    item.addEventListener("dragstart", e => {
      SFX.pickup();
      _dragCtx = {
        charId: +item.dataset.charId,
        cardId: +item.dataset.cardId,
        cardType: item.dataset.cardType,
        fromSlot: item.dataset.fromSlot,
      };
      item.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
    });
    item.addEventListener("dragend", () => item.classList.remove("dragging"));
  });

  // Drag from inventory → equip slot (мышь + тач)
  el.querySelectorAll("[data-inv-item]").forEach(item => {
    item.addEventListener("dragstart", e => {
      SFX.pickup();
      _dragCtx = {
        charId: +item.dataset.charId,
        cardId: +item.dataset.cardId,
        cardType: item.dataset.cardType,
        fromSlot: null,
      };
      item.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
    });
    item.addEventListener("dragend", () => item.classList.remove("dragging"));
    setupInvItemInteraction(item);
  });

  // Также вешаем меню на неэкипируемые предметы
  el.querySelectorAll(".pch-inv-item:not([data-inv-item])").forEach(item => {
    setupInvItemInteraction(item);
  });

  // Контекстное меню на экипированные предметы
  el.querySelectorAll("[data-from-slot]").forEach(item => {
    item.addEventListener("contextmenu", e => { e.preventDefault(); showPartyRadialMenu(e.clientX, e.clientY, item, "equipped"); });
    setupLongPress(item, () => showPartyRadialMenu(0, 0, item, "equipped", true));
  });

  // Drop zones
  el.querySelectorAll("[data-drop-zone]").forEach(zone => {
    zone.addEventListener("dragover", e => {
      if (!_dragCtx) return;
      if (+zone.dataset.charId !== _dragCtx.charId) return;
      const dz = zone.dataset.dropZone;
      // Equip slots only accept inventory items of matching type
      if (dz === "weapon" && (_dragCtx.cardType !== "weapon" || _dragCtx.fromSlot !== null)) return;
      if (dz === "armor"  && (_dragCtx.cardType !== "armor"  || _dragCtx.fromSlot !== null)) return;
      // Inventory zone only accepts items dragged from an equip slot
      if (dz === "inventory" && _dragCtx.fromSlot === null) return;
      e.preventDefault();
      zone.classList.add("drag-over");
    });
    zone.addEventListener("dragleave", e => {
      if (!zone.contains(e.relatedTarget)) zone.classList.remove("drag-over");
    });
    zone.addEventListener("drop", async e => {
      e.preventDefault();
      zone.classList.remove("drag-over");
      if (!_dragCtx) return;
      if (+zone.dataset.charId !== _dragCtx.charId) return;
      const ctx = { ..._dragCtx };
      _dragCtx = null;
      if (zone.dataset.dropZone === "inventory") {
        await doEquip(ctx.charId, ctx.fromSlot, null);
      } else {
        if (ctx.fromSlot !== null) return;
        await doEquip(ctx.charId, zone.dataset.dropZone, ctx.cardId);
      }
    });
  });

  return el;
}

function buildInvItem(it, charId) {
  const isEquippable = it.card_type === "weapon" || it.card_type === "armor";
  const tags = [];
  if (it.passive_in_inventory) tags.push(`<span class="pch-tag passive">в инвентаре</span>`);
  if (it.grants_skill) {
    // убираем дублирующий префикс "Навык" из названия навыка
    const skillName = it.grants_skill.replace(/^[Нн]авык\s+/u, "");
    tags.push(`<span class="pch-tag passive">🎓 ${esc(skillName)}</span>`);
  }
  if (it.heal_dice) tags.push(`<span class="pch-tag heal">💊 ${it.heal_dice}</span>`);
  if (it.spell_name) tags.push(`<span class="pch-tag spell">⚡ ${esc(it.spell_name)}${it.damage_dice ? " " + it.damage_dice : ""}</span>`);
  if (it.is_consumable) tags.push(`<span class="pch-tag">одноразовый</span>`);
  const dataAttrs = isEquippable
    ? `draggable="true" data-inv-item data-char-id="${charId}" data-card-id="${it.id}" data-card-type="${it.card_type}"`
    : `data-char-id="${charId}" data-card-id="${it.id}" data-card-type="${it.card_type}"`;
  return `<div class="pch-inv-item${isEquippable ? " equippable" : ""}" ${dataAttrs}
    data-is-consumable="${it.is_consumable || false}"
    data-item-name="${esc(it.name)}">
    <span class="pch-inv-ico">${it.type_icon || "📦"}</span>
    <div class="pch-inv-info">
      <div class="pch-inv-name">${esc(it.name)}</div>
      ${tags.length ? `<div class="pch-inv-tags">${tags.join("")}</div>` : ""}
    </div>
  </div>`;
}

async function doEquip(charId, slot, cardId) {
  const { ok, data } = await API.post(`/api/characters/${charId}/equip`, { slot, card_id: cardId });
  if (!ok) { SFX.deny(); toast(data?.errors?.slot || data?.errors?.__form__ || "Ошибка при экипировке", true); return; }
  cardId ? SFX.equip() : SFX.unequip();
  const idx = partyState.chars.findIndex(c => c.id === charId);
  if (idx !== -1) partyState.chars[idx] = data;
  renderParty();
  toast(cardId ? "Экипировано" : "Снято");
}

// ── Touch drag-and-drop для инвентаря ──

let _touchDragEl = null;
let _touchGhost = null;
let _touchCtx = null;

function setupInvItemInteraction(item) {
  item.addEventListener("contextmenu", e => {
    e.preventDefault();
    showPartyRadialMenu(e.clientX, e.clientY, item, "inventory");
  });
  setupLongPress(item, () => showPartyRadialMenu(0, 0, item, "inventory", true));

  if (!item.dataset.invItem) return; // только equippable тянем

  item.addEventListener("touchstart", e => {
    const touch = e.touches[0];
    _touchCtx = {
      charId: +item.dataset.charId,
      cardId: +item.dataset.cardId,
      cardType: item.dataset.cardType,
      fromSlot: null,
    };
    _touchDragEl = item;
    SFX.pickup();
    item.classList.add("dragging");

    const ghost = item.cloneNode(true);
    ghost.className = item.className + " touch-drag-ghost";
    ghost.style.width = item.offsetWidth + "px";
    document.body.appendChild(ghost);
    _touchGhost = ghost;
    _moveTouchGhost(touch.clientX, touch.clientY);
  }, { passive: true });

  item.addEventListener("touchmove", e => {
    if (!_touchGhost) return;
    e.preventDefault();
    const touch = e.touches[0];
    _moveTouchGhost(touch.clientX, touch.clientY);
    // подсвечиваем зону под пальцем
    _touchGhost.style.display = "none";
    const below = document.elementFromPoint(touch.clientX, touch.clientY);
    _touchGhost.style.display = "";
    $$("[data-drop-zone]").forEach(z => z.classList.remove("drag-over"));
    const zone = below && below.closest("[data-drop-zone]");
    if (zone && _isValidDrop(zone, _touchCtx)) zone.classList.add("drag-over");
  }, { passive: false });

  item.addEventListener("touchend", e => {
    if (!_touchGhost) return;
    const touch = e.changedTouches[0];
    _touchGhost.style.display = "none";
    const below = document.elementFromPoint(touch.clientX, touch.clientY);
    _touchGhost.remove(); _touchGhost = null;
    _touchDragEl && _touchDragEl.classList.remove("dragging");
    _touchDragEl = null;
    $$("[data-drop-zone]").forEach(z => z.classList.remove("drag-over"));
    const zone = below && below.closest("[data-drop-zone]");
    if (zone && _touchCtx && _isValidDrop(zone, _touchCtx)) {
      const ctx = { ..._touchCtx }; _touchCtx = null;
      doEquip(ctx.charId, zone.dataset.dropZone, ctx.cardId);
    } else {
      _touchCtx = null;
    }
  }, { passive: true });
}

function _moveTouchGhost(x, y) {
  if (!_touchGhost) return;
  _touchGhost.style.left = (x - _touchGhost.offsetWidth / 2) + "px";
  _touchGhost.style.top = (y - _touchGhost.offsetHeight / 2) + "px";
}

function _isValidDrop(zone, ctx) {
  if (+zone.dataset.charId !== ctx.charId) return false;
  const dz = zone.dataset.dropZone;
  if (dz === "weapon" && (ctx.cardType !== "weapon" || ctx.fromSlot !== null)) return false;
  if (dz === "armor"  && (ctx.cardType !== "armor"  || ctx.fromSlot !== null)) return false;
  if (dz === "inventory" && ctx.fromSlot === null) return false;
  return true;
}

// ── Long-press helper ──

function setupLongPress(el, callback) {
  let timer = null;
  let moved = false;
  el.addEventListener("pointerdown", e => {
    moved = false;
    timer = setTimeout(() => { if (!moved) callback(); }, 600);
  });
  el.addEventListener("pointermove", () => { moved = true; clearTimeout(timer); });
  el.addEventListener("pointerup", () => clearTimeout(timer));
  el.addEventListener("pointercancel", () => clearTimeout(timer));
}

// ── Радиальное меню для инвентаря ──

function showPartyRadialMenu(cx, cy, itemEl, mode, center = false) {
  const charId = +itemEl.dataset.charId;
  const cardId = +itemEl.dataset.cardId;
  const cardType = itemEl.dataset.cardType;
  const fromSlot = itemEl.dataset.fromSlot || null;
  const isConsumable = itemEl.dataset.isConsumable === "true";
  const itemName = itemEl.dataset.itemName || "";

  const items = [];

  if (mode === "equipped") {
    items.push({
      icon: "⬇️", label: "Снять",
      action: () => doEquip(charId, fromSlot, null),
    });
  } else {
    if (cardType === "weapon") {
      items.push({ icon: "⚔️", label: "Экипировать", action: () => doEquip(charId, "weapon", cardId) });
    } else if (cardType === "armor") {
      items.push({ icon: "🛡️", label: "Надеть", action: () => doEquip(charId, "armor", cardId) });
    }
    if (isConsumable) {
      items.push({
        icon: "🧪", label: "Использовать",
        action: () => toast(`«${itemName}» использован (эффект применяется через движок)`, false),
      });
    }
  }

  items.push({
    icon: "ℹ️", label: "Инфо",
    action: () => toast(itemName || "Предмет"),
  });

  if (!items.length) return;

  // Если позиция не задана (long-press на мобиле) — центрируем относительно элемента
  if (center) {
    const rect = itemEl.getBoundingClientRect();
    cx = rect.left + rect.width / 2;
    cy = rect.top + rect.height / 2;
  }

  const r = 70;
  const margin = r + 32;
  cx = Math.max(margin, Math.min(window.innerWidth  - margin, cx));
  cy = Math.max(margin, Math.min(window.innerHeight - margin, cy));

  const menu = $("#radial-menu");
  menu.innerHTML = "";

  const centerDot = document.createElement("div");
  centerDot.className = "radial-center";
  centerDot.style.left = cx + "px";
  centerDot.style.top = cy + "px";
  menu.appendChild(centerDot);

  items.forEach((item, i) => {
    const angle = ((-90 + (360 / items.length) * i) * Math.PI) / 180;
    const ix = cx + r * Math.cos(angle);
    const iy = cy + r * Math.sin(angle);
    const el = document.createElement("button");
    el.className = "radial-item";
    el.style.left = ix + "px";
    el.style.top = iy + "px";
    el.style.animationDelay = `${i * 30}ms`;
    el.title = item.label;
    el.innerHTML = `<span class="ri-icon">${item.icon}</span><span class="ri-label">${esc(item.label)}</span>`;
    el.onclick = () => { closePartyRadialMenu(); item.action(); };
    menu.appendChild(el);
  });

  menu.classList.remove("hidden");
  setTimeout(() => document.addEventListener("pointerdown", _closePartyRadialOnce), 80);
}

function _closePartyRadialOnce(e) {
  if (!e.target.closest(".radial-item")) closePartyRadialMenu();
}
function closePartyRadialMenu() {
  $("#radial-menu").classList.add("hidden");
  document.removeEventListener("pointerdown", _closePartyRadialOnce);
}

// ── Панель группы внутри приключения ──

async function openAdvPartyPanel(sessionId) {
  const panel = $("#adv-party-panel");
  panel.classList.remove("hidden");
  const grid = $("#adv-party-grid");
  grid.innerHTML = '<p style="color:var(--muted);padding:20px">Загрузка…</p>';
  try {
    let chars;
    if (sessionId) {
      const data = await API.get(`/api/adventure/${sessionId}`);
      if (data.error) { chars = []; }
      else {
        const sessionPartyIds = new Set((data.party || []).map(c => c.id));
        const allChars = await API.get("/api/party");
        chars = allChars.filter(c => sessionPartyIds.has(c.id));
      }
    } else {
      chars = await API.get("/api/party");
    }
    partyState.chars = chars;
    grid.innerHTML = "";
    if (!chars.length) {
      grid.innerHTML = '<p style="color:var(--muted);text-align:center;padding:40px">Нет персонажей в группе.</p>';
    } else {
      chars.forEach(ch => grid.appendChild(buildCharCard(ch)));
    }
  } catch (e) {
    grid.innerHTML = '<p style="color:var(--muted);padding:20px">Ошибка загрузки.</p>';
  }
}

// ───────────────────────── привязка событий ─────────────────────────

function resetFormModal() {
  state.editingCardId = null;
  $("#form-type").disabled = false;
  $("#form-submit").textContent = "Создать";
  closeModal("#modal");
}

$("#add-btn").onclick = openAddForm;
$("#modal-close").onclick = resetFormModal;
$("#form-cancel").onclick = resetFormModal;
$("#form-submit").onclick = submitForm;
$("#sim-go").onclick = runSim;
$("#pb-prev").onclick = () => stepBy(-1);
$("#pb-next").onclick = () => stepBy(1);
$("#pb-play").onclick = togglePlay;
$$(".modal-backdrop").forEach(m => m.onclick = (e) => {
  if (e.target === m) {
    if (m.id === "modal") resetFormModal();
    else m.classList.add("hidden");
  }
});

showMode("home");

// ═════════════════════════ LLM / RAG вкладка (Отладка/Админка) ═════════════════════════

const LLM_FIELDS = {
  narrator: ["base_url", "model", "api_key", "temperature"],
  system: ["base_url", "model", "api_key", "temperature"],
  embedder: ["model"],
  memory: ["window_messages", "compact_threshold", "episodic_top_k", "retrieval_top_k"],
};

let _llmLoaded = false;

async function loadLLMSettings() {
  if (_llmLoaded) return;
  _llmLoaded = true;
  const cfg = await API.get("/api/adventure/settings");
  for (const [sec, fields] of Object.entries(LLM_FIELDS)) {
    fields.forEach(f => {
      const el = $(`#llm-${sec}-${f}`);
      if (el && cfg[sec] && cfg[sec][f] != null) el.value = cfg[sec][f];
    });
  }
}

function collectLLMSettings() {
  const out = {};
  for (const [sec, fields] of Object.entries(LLM_FIELDS)) {
    out[sec] = {};
    fields.forEach(f => {
      const el = $(`#llm-${sec}-${f}`);
      if (!el) return;
      let v = el.value;
      if (el.type === "number" && v !== "") v = Number(v);
      out[sec][f] = v;
    });
  }
  return out;
}

async function saveLLMSettings() {
  const r = await fetch("/api/adventure/settings", {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectLLMSettings()),
  });
  if (!r.ok) { toast("Не удалось сохранить настройки", true); return; }
  _llmLoaded = false; // принудительно перечитать при следующем открытии
  toast("Настройки LLM сохранены");
}

async function testLLMSettings() {
  const body = collectLLMSettings();
  $("#llm-narrator-status").textContent = "проверка…";
  $("#llm-system-status").textContent = "проверка…";
  const r = await fetch("/api/adventure/settings/test", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  ["narrator", "system"].forEach(role => {
    const el = $(`#llm-${role}-status`);
    const res = data[role] || {};
    el.textContent = res.ok ? `✓ доступно (${res.model || ""})` : `✗ ${res.error || ("статус " + res.status)}`;
    el.className = "ai-status " + (res.ok ? "ok" : "err");
  });
}

// Быстрый выбор провайдера — заполняет оба поля (narrator + system)
$$(".llm-chip").forEach(chip => {
  chip.onclick = () => {
    const url = chip.dataset.url;
    const model = chip.dataset.model;
    ["narrator", "system"].forEach(role => {
      const urlEl = $(`#llm-${role}-base_url`);
      const modelEl = $(`#llm-${role}-model`);
      if (urlEl) urlEl.value = url;
      if (modelEl && model) modelEl.value = model;
    });
    $$(".llm-chip").forEach(c => c.classList.remove("active"));
    chip.classList.add("active");
    toast(`Провайдер: ${chip.textContent.trim()}`);
  };
});

$("#llm-save").onclick = saveLLMSettings;
$("#llm-test").onclick = testLLMSettings;

// ═════════════════════════ ПРИКЛЮЧЕНИЕ (ИИ-ГМ) ═════════════════════════

const advState = {
  ready: false, bound: false, presets: [], heroes: [],
  type: "custom", selectedIds: new Set(),
  session: null, streaming: false, loreEditId: null,
};

const advEsc = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

async function initAdventure() {
  advState.ready = true;
  if (!advState.bound) { bindAdventure(); advState.bound = true; }
  advState.presets = await API.get("/api/adventure/presets");
  const roster = await API.get("/api/roster");
  advState.heroes = roster.heroes || [];
  renderPresets();
  renderPartyPick();
  showAdvScreen("setup");
}

function showAdvScreen(which) {
  $("#adv-setup").classList.toggle("hidden", which !== "setup");
  $("#adv-play").classList.toggle("hidden", which !== "play");
}

function renderPresets() {
  const box = $("#adv-presets"); box.innerHTML = "";
  advState.presets.forEach((p, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "adv-preset" + ((advState.type === p.id || (i === 0 && advState.type === "custom" && p.id === "custom")) ? " active" : "");
    b.innerHTML = `<b>${advEsc(p.label)}</b><span>${advEsc(p.description)}</span>`;
    b.onclick = () => {
      advState.type = p.id;
      $$("#adv-presets .adv-preset").forEach(x => x.classList.remove("active"));
      b.classList.add("active");
      $("#adv-type-custom").classList.toggle("hidden", p.id !== "custom");
    };
    box.appendChild(b);
  });
}

function renderPartyPick() {
  const box = $("#adv-party-pick"); box.innerHTML = "";
  advState.heroes.forEach(h => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "adv-hero" + (advState.selectedIds.has(h.id) ? " active" : "");
    const ico = TYPE_ICON[h.card_type] || "🧝";
    b.innerHTML = `<span class="adv-hero-ico">${ico}</span><span>${advEsc(h.name)}</span>`;
    b.onclick = () => {
      if (advState.selectedIds.has(h.id)) advState.selectedIds.delete(h.id);
      else advState.selectedIds.add(h.id);
      b.classList.toggle("active");
    };
    box.appendChild(b);
  });
}

async function advStart() {
  const ids = [...advState.selectedIds];
  if (!ids.length) { toast("Выберите хотя бы одного персонажа", true); return; }
  let type = advState.type;
  if (type === "custom") type = $("#adv-type-custom").value.trim() || "custom";
  const body = {
    description: $("#adv-desc").value.trim(),
    goal: $("#adv-goal").value.trim(),
    adventure_type: type,
    character_ids: ids,
  };
  const res = await API.post("/api/adventure/start", body);
  if (!res.ok) { toast(res.data.error || "Не удалось начать", true); return; }
  advState.session = res.data.session;
  openPlay(advState.session, []);
  await streamGM(`/api/adventure/${advState.session.id}/intro`, { method: "GET" });
}

function openPlay(session, messages) {
  // Закрываем панель группы при открытии новой сессии
  $("#adv-party-panel").classList.add("hidden");
  advState.session = session;
  $("#adv-goalbar").innerHTML =
    `<span class="adv-goal-type">${advEsc(session.adventure_type)}</span>` +
    (session.goal ? ` <span class="adv-goal-text">🎯 ${advEsc(session.goal)}</span>` : "");
  // выбор «от чьего лица»
  const sel = $("#adv-speaker"); sel.innerHTML = "";
  (session.party || []).forEach(c => {
    const o = document.createElement("option");
    o.value = c.id; o.textContent = c.name; sel.appendChild(o);
  });
  $("#adv-chat").innerHTML = "";
  (messages || []).forEach(m => {
    if (m.role === "gm") addBubble("gm", null, m.content);
    else if (m.role === "player") addBubble("player", m.speaker, m.content);
  });
  showAdvScreen("play");
}

function addBubble(role, speaker, text) {
  const chat = $("#adv-chat");
  const div = document.createElement("div");
  div.className = "adv-msg adv-" + role;
  if (role === "player") {
    div.innerHTML = `<div class="adv-msg-who">${advEsc(speaker || "Игрок")}</div><div class="adv-msg-text"></div>`;
  } else {
    div.innerHTML = `<div class="adv-msg-who">🎙 Гейм-мастер</div><div class="adv-msg-text"></div>`;
  }
  const textEl = div.querySelector(".adv-msg-text");
  textEl.textContent = text || "";
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return { div, textEl };
}

function setIntentTag(bubble, intent) {
  const tags = [];
  if (intent.combat_initiation) tags.push("⚔️ бой");
  if (intent.requires_roll) tags.push("🎲 " + (intent.roll_type || "проверка"));
  if (intent.leaves_location) tags.push("🚶 уход");
  if (!tags.length) return;
  const tag = document.createElement("div");
  tag.className = "adv-intent-tag";
  tag.textContent = tags.join(" · ");
  bubble.div.querySelector(".adv-msg-who").appendChild(tag);
}

async function streamGM(url, opts) {
  if (advState.streaming) return;
  advState.streaming = true;
  $("#adv-send").disabled = true;
  const bubble = addBubble("gm", null, "");
  bubble.textEl.classList.add("adv-typing");
  try {
    const fetchOpts = { method: opts.method };
    if (opts.body) {
      fetchOpts.headers = { "Content-Type": "application/json" };
      fetchOpts.body = JSON.stringify(opts.body);
    }
    await streamSSE(url, fetchOpts, (ev) => {
      if (ev.type === "delta") {
        bubble.textEl.textContent += ev.text;
        $("#adv-chat").scrollTop = $("#adv-chat").scrollHeight;
      } else if (ev.type === "intent") {
        setIntentTag(bubble, ev.intent);
      } else if (ev.type === "scene") {
        renderScene(ev.scene);
      } else if (ev.type === "error") {
        toast("ГМ: " + ev.error, true);
        bubble.textEl.textContent += "\n[" + ev.error + "]";
      }
    });
  } catch (e) {
    toast("Поток прерван: " + e.message, true);
  } finally {
    bubble.textEl.classList.remove("adv-typing");
    advState.streaming = false;
    $("#adv-send").disabled = false;
  }
}

async function streamSSE(url, opts, onEvent) {
  const r = await fetch(url, opts);
  if (!r.ok || !r.body) {
    let msg = "HTTP " + r.status;
    try { const d = await r.json(); msg = d.error || msg; } catch (e) {}
    throw new Error(msg);
  }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, idx); buf = buf.slice(idx + 2);
      const line = frame.split("\n").find(l => l.startsWith("data:"));
      if (line) { try { onEvent(JSON.parse(line.slice(5).trim())); } catch (e) {} }
    }
  }
}

async function advSend() {
  const ta = $("#adv-text");
  const text = ta.value.trim();
  if (!text || advState.streaming || !advState.session) return;
  const sel = $("#adv-speaker");
  const speakerId = sel.value ? Number(sel.value) : null;
  const speakerName = sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].textContent : "Игрок";
  addBubble("player", speakerName, text);
  ta.value = "";
  await streamGM(`/api/adventure/${advState.session.id}/message`,
    { method: "POST", body: { character_id: speakerId, text } });
}

function sceneCard(card) {
  const div = document.createElement("div");
  div.className = "adv-scene-card";
  const ico = TYPE_ICON[card.card_type] || "❔";
  const style = card.image_url
    ? `background-image:url('${card.image_url}');background-size:cover;background-position:center`
    : `background:${ART_BG[card.card_type] || "#2c2a3a"}`;
  div.innerHTML = `<div class="adv-sc-art" style="${style}">${card.image_url ? "" : ico}</div>` +
    `<div class="adv-sc-name">${advEsc(card.name)}</div>`;
  div.title = card.description || card.name;
  return div;
}

function renderScene(scene) {
  if (!scene) return;
  const loc = $("#adv-scene-loc");
  loc.innerHTML = "";
  if (scene.location) loc.appendChild(sceneCard(scene.location));
  else loc.innerHTML = '<span class="muted">—</span>';
  const npcs = $("#adv-scene-npcs"); npcs.innerHTML = "";
  (scene.npcs || []).forEach(c => npcs.appendChild(sceneCard(c)));
  if (!scene.npcs || !scene.npcs.length) npcs.innerHTML = '<span class="muted">—</span>';
  const items = $("#adv-scene-items"); items.innerHTML = "";
  (scene.items || []).forEach(c => items.appendChild(sceneCard(c)));
  if (!scene.items || !scene.items.length) items.innerHTML = '<span class="muted">—</span>';
}

// ── продолжить (список сессий) ──

async function openResume() {
  const list = await API.get("/api/adventure/list");
  const box = $("#adv-resume-list"); box.innerHTML = "";
  $("#adv-resume").classList.remove("hidden");
  if (!list.length) { box.innerHTML = '<p class="hint">Сохранённых приключений пока нет.</p>'; return; }
  list.forEach(a => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "adv-resume-item";
    const party = (a.party || []).map(c => c.name).join(", ");
    b.innerHTML = `<b>${advEsc(a.title)}</b><span>${advEsc(a.adventure_type)} · ${advEsc(a.status)}</span>` +
      `<span class="muted">${advEsc(party)}</span>`;
    b.onclick = () => loadAdventure(a.id);
    box.appendChild(b);
  });
}

async function loadAdventure(id) {
  const data = await API.get(`/api/adventure/${id}`);
  if (data.error) { toast(data.error, true); return; }
  openPlay(data, data.messages);
  renderScene(data.scene);
}

// ── настройки ИИ ──

const AI_FIELDS = {
  narrator: ["base_url", "model", "api_key", "temperature"],
  system: ["base_url", "model", "api_key", "temperature"],
  embedder: ["model"],
  memory: ["window_messages", "compact_threshold", "episodic_top_k", "retrieval_top_k"],
};

async function openSettings() {
  const cfg = await API.get("/api/adventure/settings");
  for (const [sec, fields] of Object.entries(AI_FIELDS)) {
    fields.forEach(f => {
      const el = $(`#ai-${sec}-${f}`);
      if (el && cfg[sec] && cfg[sec][f] != null) el.value = cfg[sec][f];
    });
  }
  $("#ai-narrator-status").textContent = "";
  $("#ai-system-status").textContent = "";
  $("#ai-modal").classList.remove("hidden");
}

function collectSettings() {
  const out = {};
  for (const [sec, fields] of Object.entries(AI_FIELDS)) {
    out[sec] = {};
    fields.forEach(f => {
      const el = $(`#ai-${sec}-${f}`);
      if (!el) return;
      let v = el.value;
      if (el.type === "number" && v !== "") v = Number(v);
      out[sec][f] = v;
    });
  }
  return out;
}

async function saveSettings() {
  const r = await fetch("/api/adventure/settings", {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectSettings()),
  });
  if (!r.ok) { toast("Не удалось сохранить настройки", true); return; }
  toast("Настройки сохранены");
  $("#ai-modal").classList.add("hidden");
}

async function testSettings() {
  const body = collectSettings();
  $("#ai-narrator-status").textContent = "проверка…";
  $("#ai-system-status").textContent = "проверка…";
  const r = await fetch("/api/adventure/settings/test", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json();
  ["narrator", "system"].forEach(role => {
    const el = $(`#ai-${role}-status`);
    const res = data[role] || {};
    el.textContent = res.ok ? `✓ доступно (${res.model || ""})` : `✗ ${res.error || ("статус " + res.status)}`;
    el.className = "ai-status " + (res.ok ? "ok" : "err");
  });
}

// ── лор-база ──

async function openLore() {
  loreClear();
  await loreReload();
  $("#lore-modal").classList.remove("hidden");
}

async function loreReload() {
  const cat = $("#lore-filter").value;
  const items = await API.get(`/api/lore?category=${encodeURIComponent(cat)}`);
  const box = $("#lore-list"); box.innerHTML = "";
  if (!items.length) { box.innerHTML = '<p class="hint">Пусто.</p>'; return; }
  items.forEach(it => {
    const div = document.createElement("div");
    div.className = "lore-item";
    const cat = (it.fields && it.fields.category) || "custom";
    div.innerHTML = `<div class="lore-item-main"><b>${advEsc(it.name)}</b>` +
      `<span class="lore-cat">${advEsc(cat)}</span>` +
      `<p>${advEsc((it.description || "").slice(0, 140))}</p></div>` +
      `<div class="lore-item-actions">` +
      `<button class="lore-edit" title="Редактировать">✎</button>` +
      `<button class="lore-del" title="Удалить">🗑</button></div>`;
    div.querySelector(".lore-edit").onclick = () => loreEdit(it);
    div.querySelector(".lore-del").onclick = () => loreDelete(it.id);
    box.appendChild(div);
  });
}

function loreEdit(it) {
  advState.loreEditId = it.id;
  $("#lore-edit-id").value = it.id;
  $("#lore-edit-name").value = it.name || "";
  $("#lore-edit-category").value = (it.fields && it.fields.category) || "custom";
  $("#lore-edit-desc").value = it.description || "";
}

function loreClear() {
  advState.loreEditId = null;
  $("#lore-edit-id").value = "";
  $("#lore-edit-name").value = "";
  $("#lore-edit-category").value = "location";
  $("#lore-edit-desc").value = "";
}

async function loreSave() {
  const body = {
    name: $("#lore-edit-name").value.trim(),
    category: $("#lore-edit-category").value,
    description: $("#lore-edit-desc").value.trim(),
  };
  if (!body.name) { toast("Укажите название", true); return; }
  const id = advState.loreEditId;
  const url = id ? `/api/lore/${id}` : "/api/lore";
  const r = await fetch(url, {
    method: id ? "PUT" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    toast((d.errors && Object.values(d.errors)[0]) || d.error || "Ошибка", true);
    return;
  }
  toast(id ? "Факт обновлён" : "Факт добавлен");
  loreClear();
  loreReload();
}

async function loreDelete(id) {
  const r = await fetch(`/api/lore/${id}`, { method: "DELETE" });
  if (r.ok) { toast("Удалено"); if (advState.loreEditId === id) loreClear(); loreReload(); }
}

function bindAdventure() {
  $("#adv-start").onclick = advStart;
  $("#adv-send").onclick = advSend;
  $("#adv-text").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); advSend(); }
  });
  $("#adv-exit").onclick = () => {
    showAdvScreen("setup");
    $("#adv-resume").classList.add("hidden");
    $("#adv-party-panel").classList.add("hidden");
  };
  $("#adv-party-toggle").onclick = () => {
    const panel = $("#adv-party-panel");
    if (panel.classList.contains("hidden")) {
      openAdvPartyPanel(advState.session && advState.session.id);
    } else {
      panel.classList.add("hidden");
    }
  };
  $("#adv-party-close").onclick = () => $("#adv-party-panel").classList.add("hidden");
  $("#adv-resume-btn").onclick = openResume;
  $("#adv-settings-btn").onclick = openSettings;
  $("#adv-lore-btn").onclick = openLore;
  // настройки
  $("#ai-close").onclick = () => $("#ai-modal").classList.add("hidden");
  $("#ai-save").onclick = saveSettings;
  $("#ai-test").onclick = testSettings;
  // лор
  $("#lore-close").onclick = () => $("#lore-modal").classList.add("hidden");
  $("#lore-filter").onchange = loreReload;
  $("#lore-new").onclick = loreClear;
  $("#lore-edit-save").onclick = loreSave;
  $("#lore-edit-clear").onclick = loreClear;
}
