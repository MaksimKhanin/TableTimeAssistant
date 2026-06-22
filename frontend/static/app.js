'use strict';

// ── State ────────────────────────────────────────────────────────────────────
let currentAdventureId = null;
let ws = null;
let isThinking = false;
let thinkingMsgEl = null;
let pendingRollSpec = null;   // set while the GM is blocking on a required roll
let _adventureCharacters = []; // cached character list for the current adventure

// ── Roll type metadata ────────────────────────────────────────────────────────
const ROLL_TYPE_LABELS = {
  attack: 'Бросок атаки', initiative: 'Инициатива', damage: 'Урон',
  save_str: 'Спасбросок СИЛ', save_dex: 'Спасбросок ЛОВ', save_con: 'Спасбросок ТЕЛ',
  save_int: 'Спасбросок ИНТ', save_wis: 'Спасбросок МДР', save_cha: 'Спасбросок ХАР',
  check_str: 'Проверка СИЛ', check_dex: 'Проверка ЛОВ', check_con: 'Проверка ТЕЛ',
  check_int: 'Проверка ИНТ', check_wis: 'Проверка МДР', check_cha: 'Проверка ХАР',
};
function rollTypeLabel(t) { return ROLL_TYPE_LABELS[t] || t; }
function isD20Type(t) {
  return t === 'attack' || t === 'initiative' || t.startsWith('save_') || t.startsWith('check_');
}

const ROLL_CATEGORIES = [
  { value: 'save', label: 'Спасброски' },
  { value: 'attack', label: 'Атаки' },
  { value: 'check', label: 'Проверки навыков' },
  { value: 'initiative', label: 'Инициатива' },
];

// ── View Navigation ──────────────────────────────────────────────────────────
function showView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const el = document.getElementById(`view-${name}`);
  if (el) el.classList.add('active');
}
function showOverlay(name) { document.getElementById(`view-${name}`).classList.remove('hidden'); }
function hideOverlay(name) { document.getElementById(`view-${name}`).classList.add('hidden'); }

// ── API helpers ──────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(`/api${path}`, opts);
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

// ── Markdown renderer ────────────────────────────────────────────────────────
function renderMd(text) {
  const div = document.createElement('div');
  const html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^## (.+)$/gm, '<div class="md-h2">$1</div>')
    .replace(/^### (.+)$/gm, '<div class="md-h3">$1</div>');
  div.innerHTML = html;
  return div;
}

function esc(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function hpBarHTML(cur, max) {
  const pct = max > 0 ? Math.round((cur / max) * 100) : 0;
  const color = pct > 50 ? 'var(--success)' : pct > 25 ? 'var(--accent2)' : 'var(--danger)';
  return `<div class="hp-bar-bg"><div class="hp-bar" style="width:${pct}%;background:${color}"></div></div>`;
}

// ── Category icons ────────────────────────────────────────────────────────────
const CATEGORY_ICONS = {
  dungeon: '⛏️', dark: '🩸', horror: '👁️',
  sea: '⚓', intrigue: '🎭', default: '📖',
};
function categoryIcon(cat) { return CATEGORY_ICONS[cat] || CATEGORY_ICONS.default; }

// ── Home view ────────────────────────────────────────────────────────────────
async function loadAdventures() {
  const list = document.getElementById('adventures-list');
  list.innerHTML = '';
  try {
    const adventures = await api('GET', '/adventures');
    if (!adventures.length) {
      list.innerHTML = '<div class="empty-state">Нет сохранённых приключений.<br>Создайте первое!</div>';
      return;
    }
    adventures.forEach(a => {
      const item = document.createElement('div');
      item.className = 'adv-item';
      const date = new Date(a.created_at).toLocaleDateString('ru');
      const npcCount = a.npcs ? a.npcs.length : 0;
      item.innerHTML = `
        <div class="adv-item-info">
          <div class="adv-item-title">${esc(a.title)}</div>
          <div class="adv-item-meta">${a.player_count} игрок(а) · ${npcCount} NPC · ${date}</div>
        </div>
        <button class="adv-delete" data-id="${a.id}" title="Удалить">🗑</button>
      `;
      item.addEventListener('click', (e) => {
        if (e.target.classList.contains('adv-delete')) return;
        openAdventure(a.id, a.title);
      });
      item.querySelector('.adv-delete').addEventListener('click', async () => {
        if (!confirm(`Удалить "${a.title}"?`)) return;
        await api('DELETE', `/adventures/${a.id}`);
        loadAdventures();
      });
      list.appendChild(item);
    });
  } catch (e) {
    list.innerHTML = `<div class="empty-state">Ошибка загрузки: ${e.message}</div>`;
  }
}

// ── Template carousel ────────────────────────────────────────────────────────
let _templates = [];
let _selectedTemplateId = null;

async function loadTemplateCarousel() {
  const container = document.getElementById('template-carousel');
  container.innerHTML = '';
  _selectedTemplateId = null;

  try {
    _templates = await api('GET', '/templates');
  } catch {
    container.innerHTML = '<div style="color:var(--text-dim);font-size:13px">Не удалось загрузить шаблоны</div>';
    return;
  }

  // "Пустое приключение" pseudo-card
  const emptyCard = document.createElement('div');
  emptyCard.className = 'tmpl-card';
  emptyCard.innerHTML = `
    <div class="tmpl-card-icon">✏️</div>
    <div class="tmpl-card-title">С нуля</div>
    <div class="tmpl-card-meta">Чистая форма</div>
  `;
  emptyCard.addEventListener('click', () => {
    selectTemplate(null);
    document.querySelectorAll('.tmpl-card').forEach(c => c.classList.remove('selected'));
    emptyCard.classList.add('selected');
  });
  container.appendChild(emptyCard);

  _templates.forEach(tmpl => {
    const card = document.createElement('div');
    card.className = 'tmpl-card';
    card.dataset.id = tmpl.id;
    card.innerHTML = `
      <div class="tmpl-card-icon">${categoryIcon(tmpl.category)}</div>
      <div class="tmpl-card-title">${esc(tmpl.title)}</div>
      <div class="tmpl-card-meta">${tmpl.player_count} игрок(а)</div>
      ${!tmpl.is_builtin ? `<button class="tmpl-card-del" title="Удалить шаблон">✕</button>` : ''}
    `;
    card.addEventListener('click', (e) => {
      if (e.target.classList.contains('tmpl-card-del')) return;
      document.querySelectorAll('.tmpl-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      selectTemplate(tmpl);
    });
    if (!tmpl.is_builtin) {
      card.querySelector('.tmpl-card-del')?.addEventListener('click', async () => {
        if (!confirm(`Удалить шаблон "${tmpl.title}"?`)) return;
        await api('DELETE', `/templates/${tmpl.id}`);
        loadTemplateCarousel();
      });
    }
    container.appendChild(card);
  });
}

function selectTemplate(tmpl) {
  _selectedTemplateId = tmpl ? tmpl.id : null;

  if (!tmpl) {
    document.getElementById('adv-title').value = '';
    document.getElementById('adv-desc').value = '';
    document.getElementById('adv-role').value = 'Dungeon Master';
    _selectedHeroes = [];
    renderHeroSlots();
    document.getElementById('npc-forms').innerHTML = '';
    return;
  }

  document.getElementById('adv-title').value = tmpl.title;
  document.getElementById('adv-desc').value = tmpl.description;
  document.getElementById('adv-role').value = tmpl.gm_role;

  // Do not pre-populate heroes from template — players pick heroes from their own preset library.
  _selectedHeroes = [];
  renderHeroSlots();

  // Rebuild NPC forms
  const npcContainer = document.getElementById('npc-forms');
  npcContainer.innerHTML = '';
  (tmpl.npcs_json || []).forEach(n => addNpcForm(n));
}

// ── New Adventure form ────────────────────────────────────────────────────────
// Point-buy rules (no levels). Fetched from the backend; defaults as fallback.
let _charRules = {
  stat_min: 1, stat_max: 20, point_budget: 30,
  stat_keys: ['strength', 'dexterity', 'wisdom', 'charisma'],
};
async function ensureCharRules() {
  try { _charRules = await api('GET', '/char-rules'); } catch {}
}


// ── Hero Presets ───────────────────────────────────────────────────────────────
let _heroPresets = [];

async function loadHeroPresets() {
  try { _heroPresets = await api('GET', '/character-presets'); } catch { _heroPresets = []; }
}

function renderHeroesList() {
  const list = document.getElementById('heroes-list');
  if (!list) return;
  if (!_heroPresets.length) {
    list.innerHTML = '<p style="color:var(--text-dim);text-align:center;padding:32px">Нет сохранённых героев. Нажми ＋ чтобы добавить.</p>';
    return;
  }
  list.innerHTML = '';
  _heroPresets.forEach(h => {
    const card = document.createElement('div');
    card.className = 'hero-preset-card';
    card.innerHTML = `
      <div class="hero-preset-header">
        <span class="hero-preset-name">${esc(h.name)}</span>
        <span class="hero-preset-sub">${esc(h.race)} · ${esc(h.char_class)}</span>
        <button class="remove-btn hero-preset-del" data-id="${h.id}" title="Удалить">✕</button>
      </div>
      <div class="hero-preset-stats">
        <span>ХП ${h.max_hp}</span>
        <span title="Физ.защита">ФЗ ${h.phys_defense ?? Math.floor((h.dexterity||5)/2)}</span>
        <span title="Маг.защита">МЗ ${h.mag_defense ?? Math.floor((h.wisdom||5)/2)}</span>
        <span title="Мент.защита">МТЗ ${h.mental_defense ?? (5+Math.floor((h.charisma||5)/2))}</span>
        <span title="Сила">СИЛ ${h.strength}</span><span title="Ловкость">ЛОВ ${h.dexterity}</span>
        <span title="Мудрость">МДР ${h.wisdom}</span><span title="Харизма">ХАР ${h.charisma}</span>
      </div>
      ${h.abilities ? `<div class="hero-preset-abilities">${esc(h.abilities)}</div>` : ''}
    `;
    card.querySelector('.hero-preset-del').addEventListener('click', async () => {
      await api('DELETE', `/character-presets/${h.id}`);
      await loadHeroPresets();
      renderHeroesList();
    });
    list.appendChild(card);
  });
}

let _presetPickerCallback = null;

function openPresetPicker(onPick) {
  _presetPickerCallback = onPick;
  const list = document.getElementById('preset-picker-list');
  list.innerHTML = '';
  _heroPresets.forEach(h => {
    const item = document.createElement('div');
    item.className = 'preset-picker-item';
    item.innerHTML = `
      <div class="preset-picker-name">${esc(h.name)}</div>
      <div class="preset-picker-sub">${esc(h.race)} · ${esc(h.char_class)}</div>
      <div class="preset-picker-stats">
        <span>ХП ${h.max_hp}</span>
        <span title="Физ.защита">ФЗ ${h.phys_defense ?? Math.floor((h.dexterity||5)/2)}</span>
        <span title="Маг.защита">МЗ ${h.mag_defense ?? Math.floor((h.wisdom||5)/2)}</span>
        <span title="Мент.защита">МТЗ ${h.mental_defense ?? (5+Math.floor((h.charisma||5)/2))}</span>
        <span title="Сила">СИЛ ${h.strength}</span>
        <span title="Ловкость">ЛОВ ${h.dexterity}</span>
        <span title="Мудрость">МДР ${h.wisdom}</span>
        <span title="Харизма">ХАР ${h.charisma}</span>
      </div>
      ${h.abilities ? `<div class="preset-picker-abilities">${esc(h.abilities)}</div>` : ''}
    `;
    item.addEventListener('click', () => {
      hideOverlay('preset-picker');
      if (_presetPickerCallback) _presetPickerCallback(h);
      _presetPickerCallback = null;
    });
    list.appendChild(item);
  });
  showOverlay('preset-picker');
}

function _derivedStats(str, dex, wis, cha) {
  return {
    max_hp: 10 + Math.floor(str / 2),
    phys_defense: Math.floor(dex / 2),
    mag_defense: Math.floor(wis / 2),
    mental_defense: 5 + Math.floor(cha / 2),
    phys_attack_bonus: Math.floor(dex / 2),
    mag_attack_bonus: Math.floor(wis / 2),
    mental_attack_bonus: Math.floor(cha / 2),
  };
}

function buildPresetForm(container, prefill) {
  const p = prefill || {};
  const mn = _charRules.stat_min, mx = _charRules.stat_max;
  const budget = _charRules.point_budget || 30;
  const str = p.strength || 5, dex = p.dexterity || 5, wis = p.wisdom || 5, cha = p.charisma || 5;
  const d = _derivedStats(str, dex, wis, cha);
  container.innerHTML = `
    <div class="form-group"><label>Имя</label>
      <input class="c-name" type="text" placeholder="Арагорн" value="${esc(p.name || '')}" /></div>
    <div class="stats-grid">
      <div class="stat-field"><label>Раса</label><input class="c-race" type="text" value="${esc(p.race || 'Человек')}" /></div>
      <div class="stat-field"><label>Класс</label><input class="c-class" type="text" value="${esc(p.char_class || 'Воин')}" /></div>
      <div class="stat-field" title="Сила: +HP и +физ. урон (каждые 2 очка)">
        <label>СИЛ</label><input class="c-str c-stat" type="number" value="${str}" min="${mn}" max="${mx}" /></div>
      <div class="stat-field" title="Ловкость: +физ. защита и +физ. атака (каждые 2 очка); определяет инициативу">
        <label>ЛОВ</label><input class="c-dex c-stat" type="number" value="${dex}" min="${mn}" max="${mx}" /></div>
      <div class="stat-field" title="Мудрость: +маг. защита и +маг. атака/заклинания (каждые 2 очка)">
        <label>МДР</label><input class="c-wis c-stat" type="number" value="${wis}" min="${mn}" max="${mx}" /></div>
      <div class="stat-field" title="Харизма: +мент. защита и +убеждение/обман/угрозы (каждые 2 очка)">
        <label>ХАР</label><input class="c-cha c-stat" type="number" value="${cha}" min="${mn}" max="${mx}" /></div>
    </div>
    <div class="stat-budget-info">
      Использовано очков: <span class="stat-budget-used">${str+dex+wis+cha}</span> / ${budget}
      &nbsp;<span class="stat-budget-warn" style="color:var(--danger,#e55);display:none">⚠ превышен лимит!</span>
    </div>
    <div class="derived-stats-info">
      ХП <b>${d.max_hp}</b> · ФизЗащ <b>${d.phys_defense}</b> · МагЗащ <b>${d.mag_defense}</b> · МентЗащ <b>${d.mental_defense}</b>
      · ФизАтк +<b>${d.phys_attack_bonus}</b> · МагАтк +<b>${d.mag_attack_bonus}</b> · МентАтк +<b>${d.mental_attack_bonus}</b>
      · Урон <b>1d4+${Math.floor(str/2)}</b>
    </div>
    <div class="form-group"><label>Предыстория</label>
      <textarea class="c-background" rows="2" placeholder="Откуда персонаж, что им движет...">${esc(p.background||'')}</textarea></div>
  `;
  // Live update budget counter and derived stats
  container.querySelectorAll('.c-stat').forEach(inp => {
    inp.addEventListener('input', () => {
      const s = parseInt(container.querySelector('.c-str').value)||1;
      const d2 = parseInt(container.querySelector('.c-dex').value)||1;
      const w = parseInt(container.querySelector('.c-wis').value)||1;
      const c = parseInt(container.querySelector('.c-cha').value)||1;
      const total = s+d2+w+c;
      container.querySelector('.stat-budget-used').textContent = total;
      const warn = container.querySelector('.stat-budget-warn');
      if (warn) warn.style.display = total > (_charRules.point_budget || 30) ? '' : 'none';
      const der = _derivedStats(s, d2, w, c);
      container.querySelector('.derived-stats-info').innerHTML =
        `ХП <b>${der.max_hp}</b> · ФизЗащ <b>${der.phys_defense}</b> · МагЗащ <b>${der.mag_defense}</b> · МентЗащ <b>${der.mental_defense}</b>` +
        ` · ФизАтк +<b>${der.phys_attack_bonus}</b> · МагАтк +<b>${der.mag_attack_bonus}</b> · МентАтк +<b>${der.mental_attack_bonus}</b>` +
        ` · Урон <b>1d4+${Math.floor(s/2)}</b>`;
    });
  });
}

function readPresetForm(container) {
  const g = sel => container.querySelector(sel);
  const str = parseInt(g('.c-str').value) || 5;
  const dex = parseInt(g('.c-dex').value) || 5;
  const wis = parseInt(g('.c-wis').value) || 5;
  const cha = parseInt(g('.c-cha').value) || 5;
  const budget = _charRules.point_budget || 30;
  if (str + dex + wis + cha > budget) {
    throw new Error(`Сумма характеристик (${str+dex+wis+cha}) превышает лимит ${budget}`);
  }
  return {
    name: g('.c-name').value.trim(),
    race: g('.c-race').value.trim() || 'Человек',
    char_class: g('.c-class').value.trim() || 'Воин',
    strength: str, dexterity: dex, wisdom: wis, charisma: cha,
    damage_dice: '1d4',
    abilities: '',
    background: (g('.c-background') ? g('.c-background').value.trim() : ''),
  };
}


// ── Hero slots (replaces manual character forms) ───────────────────────────
let _selectedHeroes = [];  // array of preset/character objects chosen for this adventure

function renderHeroSlots() {
  const container = document.getElementById('hero-slots');
  if (!container) return;
  container.innerHTML = '';

  if (!_selectedHeroes.length) {
    const empty = document.createElement('div');
    empty.className = 'hero-slot-empty';
    empty.textContent = 'Нет выбранных героев. Нажми «🧙 Добавить из базы».';
    container.appendChild(empty);
    return;
  }

  _selectedHeroes.forEach((h, idx) => {
    const card = document.createElement('div');
    card.className = 'hero-slot-card';
    card.innerHTML = `
      <div class="hero-slot-header">
        <span class="hero-slot-name">${esc(h.name)}</span>
        <span class="hero-slot-sub">${esc(h.race)} · ${esc(h.char_class)}</span>
        <button class="remove-btn hero-slot-remove" title="Убрать">✕</button>
      </div>
      <div class="hero-slot-stats">
        <span>ХП ${h.max_hp}</span>
        <span title="Физ.защита">ФЗ ${h.phys_defense ?? Math.floor((h.dexterity||5)/2)}</span>
        <span title="Маг.защита">МЗ ${h.mag_defense ?? Math.floor((h.wisdom||5)/2)}</span>
        <span title="Мент.защита">МТЗ ${h.mental_defense ?? (5+Math.floor((h.charisma||5)/2))}</span>
        <span title="Сила">СИЛ ${h.strength}</span><span title="Ловкость">ЛОВ ${h.dexterity}</span>
        <span title="Мудрость">МДР ${h.wisdom}</span><span title="Харизма">ХАР ${h.charisma}</span>
      </div>
      ${h.abilities ? `<div class="hero-slot-abilities">${esc(h.abilities)}</div>` : ''}
    `;
    card.querySelector('.hero-slot-remove').addEventListener('click', () => {
      _selectedHeroes.splice(idx, 1);
      renderHeroSlots();
    });
    container.appendChild(card);
  });
}

function addNpcForm(prefill) {
  const p = prefill || {};
  const mn = _charRules.stat_min || 1, mx = _charRules.stat_max || 20;
  const budget = _charRules.point_budget || 30;
  const str = p.strength || 5, dex = p.dexterity || 5, wis = p.wisdom || 5, cha = p.charisma || 5;
  const d = _derivedStats(str, dex, wis, cha);
  const container = document.getElementById('npc-forms');
  const idx = container.children.length + 1;
  const card = document.createElement('div');
  card.className = 'npc-card';
  card.innerHTML = `
    <h3>Персонаж ${idx}</h3>
    <button class="remove-btn" title="Удалить">✕</button>
    <div class="form-group">
      <label>Имя</label>
      <input class="n-name" type="text" placeholder="Барон Мортис" value="${esc(p.name || '')}" />
    </div>
    <div class="stats-grid">
      <div class="stat-field"><label>Роль</label><input class="n-role" type="text" placeholder="Злодей" value="${esc(p.role || '')}" /></div>
      <div class="stat-field"><label>Тип</label>
        <select class="n-enemy">
          <option value="1" ${p.is_enemy ? 'selected' : ''}>Враг</option>
          <option value="0" ${!p.is_enemy ? 'selected' : ''}>Союзник</option>
        </select>
      </div>
      <div class="stat-field" title="Сила: +HP, +физ. урон"><label>СИЛ</label><input class="n-str n-stat" type="number" value="${str}" min="${mn}" max="${mx}" /></div>
      <div class="stat-field" title="Ловкость: +физ. защита, +физ. атака, инициатива"><label>ЛОВ</label><input class="n-dex n-stat" type="number" value="${dex}" min="${mn}" max="${mx}" /></div>
      <div class="stat-field" title="Мудрость: +маг. защита, +маг. атака"><label>МДР</label><input class="n-wis n-stat" type="number" value="${wis}" min="${mn}" max="${mx}" /></div>
      <div class="stat-field" title="Харизма: +мент. защита, +убеждение/угрозы"><label>ХАР</label><input class="n-cha n-stat" type="number" value="${cha}" min="${mn}" max="${mx}" /></div>
    </div>
    <div class="stat-budget-info">
      Очков: <span class="n-budget-used">${str+dex+wis+cha}</span> / ${budget}
      <span class="n-budget-warn" style="color:var(--danger,#e55);display:none"> ⚠ превышен!</span>
    </div>
    <div class="derived-stats-info n-derived">
      ХП <b>${d.max_hp}</b> · ФизЗащ <b>${d.phys_defense}</b> · МагЗащ <b>${d.mag_defense}</b> · МентЗащ <b>${d.mental_defense}</b>
      · ФизАтк +<b>${d.phys_attack_bonus}</b> · Урон <b>1d4+${Math.floor(str/2)}</b>
    </div>
    <div class="form-group">
      <label>Характер и мотивация</label>
      <textarea class="n-personality" rows="2" placeholder="Холодный, расчётливый...">${esc(p.personality || '')}</textarea>
    </div>
    <div class="form-group">
      <label>Манера речи</label>
      <textarea class="n-voice" rows="1" placeholder="Говорит высокопарно...">${esc(p.voice_style || '')}</textarea>
    </div>
  `;
  card.querySelector('.remove-btn').addEventListener('click', () => card.remove());
  // Live update NPC derived stats
  card.querySelectorAll('.n-stat').forEach(inp => {
    inp.addEventListener('input', () => {
      const s = parseInt(card.querySelector('.n-str').value)||1;
      const d2 = parseInt(card.querySelector('.n-dex').value)||1;
      const w = parseInt(card.querySelector('.n-wis').value)||1;
      const c = parseInt(card.querySelector('.n-cha').value)||1;
      const total = s+d2+w+c;
      card.querySelector('.n-budget-used').textContent = total;
      const warn = card.querySelector('.n-budget-warn');
      if (warn) warn.style.display = total > budget ? '' : 'none';
      const der = _derivedStats(s, d2, w, c);
      card.querySelector('.n-derived').innerHTML =
        `ХП <b>${der.max_hp}</b> · ФизЗащ <b>${der.phys_defense}</b> · МагЗащ <b>${der.mag_defense}</b> · МентЗащ <b>${der.mental_defense}</b>` +
        ` · ФизАтк +<b>${der.phys_attack_bonus}</b> · Урон <b>1d4+${Math.floor(s/2)}</b>`;
    });
  });
  container.appendChild(card);
}

function collectCharacters() {
  return _selectedHeroes.map(h => ({
    name: h.name,
    race: h.race || 'Человек',
    char_class: h.char_class || 'Воин',
    strength: h.strength || 5,
    dexterity: h.dexterity || 5,
    wisdom: h.wisdom || 5,
    charisma: h.charisma || 5,
    damage_dice: h.damage_dice || '1d4',
    abilities: h.abilities || '',
    background: h.background || '',
  }));
}

function collectNpcs() {
  return Array.from(document.querySelectorAll('.npc-card')).map(card => {
    const str = parseInt(card.querySelector('.n-str').value) || 5;
    const dex = parseInt(card.querySelector('.n-dex').value) || 5;
    const wis = parseInt(card.querySelector('.n-wis').value) || 5;
    const cha = parseInt(card.querySelector('.n-cha').value) || 5;
    return {
      name: card.querySelector('.n-name').value.trim() || 'NPC',
      role: card.querySelector('.n-role').value.trim(),
      is_enemy: parseInt(card.querySelector('.n-enemy').value),
      strength: str, dexterity: dex, wisdom: wis, charisma: cha,
      personality: card.querySelector('.n-personality').value.trim(),
      voice_style: card.querySelector('.n-voice').value.trim(),
    };
  });
}

// ── Game view ─────────────────────────────────────────────────────────────────
async function openAdventure(id, title) {
  currentAdventureId = id;
  pendingRollSpec = null;
  setInputEnabled(true);
  document.getElementById('game-title').textContent = title;
  document.getElementById('chat-messages').innerHTML = '';
  document.getElementById('scene-panel').classList.add('hidden');
  showView('game');

  const adv = await api('GET', `/adventures/${id}`);
  _adventureCharacters = adv.characters || [];
  const sel = document.getElementById('player-select');
  sel.innerHTML = '';
  adv.characters.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.name;
    opt.textContent = `${c.name} (${c.char_class})`;
    sel.appendChild(opt);
  });

  const messages = await api('GET', `/adventures/${id}/messages`);
  messages.forEach(m => appendMessage(m.role, m.content, m.player_name, false));

  // Restore the last scene panel + suggestions (unless a roll is mid-flight).
  if (adv.scene_state) renderScene(adv.scene_state);

  connectWS(id);
}

function connectWS(adventureId) {
  if (ws) ws.close();
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/${adventureId}`);
  ws.onmessage = (e) => handleWSMessage(JSON.parse(e.data));
  ws.onclose = () => {
    setTimeout(() => {
      if (currentAdventureId === adventureId) connectWS(adventureId);
    }, 3000);
  };
  ws.onerror = () => ws.close();
}

function handleWSMessage(data) {
  if (data.type !== 'chunk') console.log('[WS]', data.type, data);
  if (data.type === 'thinking') {
    if (!thinkingMsgEl) thinkingMsgEl = appendMessage('thinking', '...', null, true);
  } else if (data.type === 'chunk') {
    if (thinkingMsgEl) {
      const bubble = thinkingMsgEl.querySelector('.msg-bubble');
      if (bubble) {
        thinkingMsgEl.className = 'msg assistant';
        bubble.className = 'msg-bubble';
        if (!thinkingMsgEl.dataset.streaming) {
          bubble.innerHTML = '';
          thinkingMsgEl.dataset.streaming = '1';
          thinkingMsgEl._raw = '';
        }
        thinkingMsgEl._raw = (thinkingMsgEl._raw || '') + data.content;
        bubble.innerHTML = '';
        bubble.appendChild(renderMd(thinkingMsgEl._raw));
        scrollChat();
      }
    }
  } else if (data.type === 'think_done') {
    appendThinkBlock(data.content);
  } else if (data.type === 'done') {
    if (thinkingMsgEl && !thinkingMsgEl.dataset.streaming) {
      // Spinner was never converted to a response bubble — remove it
      thinkingMsgEl.remove();
    }
    thinkingMsgEl = null;
    isThinking = false;
    setInputEnabled(!pendingRollSpec);
    scrollChat();
  } else if (data.type === 'roll_required') {
    // A pre-pass gate may leave a bare spinner (no streamed narration) — clear it.
    if (thinkingMsgEl && !thinkingMsgEl.dataset.streaming) thinkingMsgEl.remove();
    thinkingMsgEl = null;
    const isNew = !pendingRollSpec;
    pendingRollSpec = data.spec;
    isThinking = false;
    setInputEnabled(false);
    // Append a card for new rolls (not for re-sent "blocked" gate reminders).
    if (!data.blocked && isNew) {
      appendRollPromptCard(data.spec);
    }
  } else if (data.type === 'scene_update') {
    renderScene(data);
  } else if (data.type === 'dice_result') {
    appendMessage('dice', data.content, null, true);
  } else if (data.type === 'hp_update') {
    appendMessage('dice', data.content, null, true);
    // Live-refresh the party panel if it's currently open.
    const partyView = document.getElementById('view-party');
    if (partyView && !partyView.classList.contains('hidden')) loadPartyPanel();
  } else if (data.type === 'roll_cancelled') {
    pendingRollSpec = null;
    setInputEnabled(true);
  } else if (data.type === 'error') {
    if (thinkingMsgEl) { thinkingMsgEl.remove(); thinkingMsgEl = null; }
    isThinking = false;
    setInputEnabled(!pendingRollSpec);
    appendMessage('dice', `⚠️ Ошибка: ${data.message}`, null, true);
  }
}

function appendMessage(role, content, playerName, scroll) {
  const container = document.getElementById('chat-messages');
  const msg = document.createElement('div');
  msg.className = `msg ${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  if (role === 'thinking') bubble.textContent = content;
  else bubble.appendChild(renderMd(content));
  msg.appendChild(bubble);
  if (role === 'user' && playerName) {
    const meta = document.createElement('div');
    meta.className = 'msg-meta';
    meta.textContent = playerName;
    msg.appendChild(meta);
  }
  container.appendChild(msg);
  if (scroll) scrollChat();
  return msg;
}

function scrollChat() {
  const c = document.getElementById('chat-messages');
  c.scrollTop = c.scrollHeight;
}

// ── Scene panel (location + objective, driven by the referee) ─────────────────
function renderScene(scene) {
  if (!scene) return;
  const panel = document.getElementById('scene-panel');
  const loc = (scene.location || '').trim();
  const obj = (scene.objective || '').trim();
  if (loc || obj) {
    document.getElementById('scene-location').textContent = loc || '—';
    document.getElementById('scene-objective').textContent = obj || '—';
    panel.title = scene.summary || '';
    panel.classList.remove('hidden');
  } else {
    panel.classList.add('hidden');
  }
}

function appendThinkBlock(content) {
  const container = document.getElementById('chat-messages');
  const block = document.createElement('div');
  block.className = 'think-block';
  block.innerHTML = `
    <div class="think-block-header">
      <span class="think-toggle">▶</span>
      <span>🧠 Размышление ГМа</span>
    </div>
    <div class="think-block-body">${esc(content)}</div>
  `;
  block.querySelector('.think-block-header').addEventListener('click', () => {
    block.classList.toggle('open');
    scrollChat();
  });
  // Insert before the current spinner so thinking appears above the response
  if (thinkingMsgEl) {
    container.insertBefore(block, thinkingMsgEl);
  } else {
    container.appendChild(block);
  }
  scrollChat();
}

function setInputEnabled(enabled) {
  document.getElementById('btn-send').disabled = !enabled;
  document.getElementById('chat-input').disabled = !enabled;
}

function sendMessage() {
  if (isThinking) return;
  if (pendingRollSpec) return; // roll pending — ignore chat input
  const content = document.getElementById('chat-input').value.trim();
  if (!content) return;
  const playerName = document.getElementById('player-select').value;
  appendMessage('user', content, playerName, true);
  document.getElementById('chat-input').value = '';
  isThinking = true;
  setInputEnabled(false);
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'message', player_name: playerName, content }));
  } else {
    appendMessage('dice', '⚠️ Нет соединения с сервером', null, true);
    isThinking = false;
    setInputEnabled(true);
  }
}

// ── Party panel ───────────────────────────────────────────────────────────────
function buildHpCard(entity, isNpc, adventureId, refreshFn) {
  const el = document.createElement('div');
  const cssClass = isNpc ? (entity.is_enemy ? 'enemy' : 'ally') : '';
  el.className = `party-char ${cssClass}`;
  const sub = isNpc
    ? `${esc(entity.role || (entity.is_enemy ? 'Враг' : 'Союзник'))} · ФЗ ${entity.phys_defense ?? entity.armor_class ?? 2}`
    : `${esc(entity.race)} ${esc(entity.char_class)} · ФЗ ${entity.phys_defense ?? 2} МЗ ${entity.mag_defense ?? 2} МТЗ ${entity.mental_defense ?? 7}`;
  el.innerHTML = `
    <div class="party-char-name">${esc(entity.name)}</div>
    <div class="party-char-sub">${sub}</div>
    <div class="hp-bar-wrap">
      ${hpBarHTML(entity.current_hp, entity.max_hp)}
      <div class="hp-text">${entity.current_hp}/${entity.max_hp} ХП</div>
    </div>
    <div class="hp-controls">
      <button class="hp-heal">+</button>
      <input class="hp-delta" type="number" value="5" min="1" max="999" />
      <button class="hp-damage">−</button>
      <span style="font-size:12px;color:var(--text-dim);margin-left:4px">${entity.status}</span>
    </div>
  `;
  el.querySelector('.hp-heal').addEventListener('click', async () => {
    const delta = parseInt(el.querySelector('.hp-delta').value) || 5;
    const endpoint = isNpc ? `/adventures/${adventureId}/npc-hp` : `/adventures/${adventureId}/hp`;
    const body = isNpc ? { npc_id: entity.id, delta } : { character_id: entity.id, delta };
    await api('POST', endpoint, body);
    refreshFn();
  });
  el.querySelector('.hp-damage').addEventListener('click', async () => {
    const delta = -(parseInt(el.querySelector('.hp-delta').value) || 5);
    const endpoint = isNpc ? `/adventures/${adventureId}/npc-hp` : `/adventures/${adventureId}/hp`;
    const body = isNpc ? { npc_id: entity.id, delta } : { character_id: entity.id, delta };
    await api('POST', endpoint, body);
    refreshFn();
  });
  return el;
}

async function loadPartyPanel() {
  const partyList = document.getElementById('party-list');
  const npcList = document.getElementById('npc-list');
  partyList.innerHTML = '';
  npcList.innerHTML = '';
  try {
    const adv = await api('GET', `/adventures/${currentAdventureId}`);
    if (adv.characters.length) {
      const t = document.createElement('div');
      t.className = 'panel-section-title';
      t.textContent = 'Игроки';
      partyList.appendChild(t);
      adv.characters.forEach(c => partyList.appendChild(buildHpCard(c, false, currentAdventureId, loadPartyPanel)));
    }
    if (adv.npcs && adv.npcs.length) {
      const render = (list, label) => {
        if (!list.length) return;
        const t = document.createElement('div');
        t.className = 'panel-section-title';
        t.textContent = label;
        npcList.appendChild(t);
        list.forEach(n => npcList.appendChild(buildHpCard(n, true, currentAdventureId, loadPartyPanel)));
      };
      render(adv.npcs.filter(n => n.is_enemy), 'Враги');
      render(adv.npcs.filter(n => !n.is_enemy), 'Союзники');
    }
  } catch (e) {
    partyList.innerHTML = `<div class="empty-state">Ошибка: ${e.message}</div>`;
  }
}

// ── Dice panel ────────────────────────────────────────────────────────────────
async function loadDicePanel() {
  const container = document.getElementById('dice-options');
  container.innerHTML = '';
  const adv = await api('GET', `/adventures/${currentAdventureId}`);

  const charOptions = adv.characters.map(c => `<option value="char:${c.id}">${esc(c.name)} (${esc(c.char_class)})</option>`).join('');
  const npcOptions = (adv.npcs || []).map(n => `<option value="npc:${n.id}">${esc(n.name)} (${n.is_enemy ? '⚔ враг' : '🤝 союзник'})</option>`).join('');

  const modeRow = document.createElement('div');
  modeRow.className = 'form-group';
  modeRow.innerHTML = `<label>Кто бросает</label><select id="dice-actor-sel">${charOptions}${npcOptions}</select>`;
  container.appendChild(modeRow);

  const acRow = document.createElement('div');
  acRow.className = 'form-group';
  acRow.innerHTML = `<label>КД / DC цели</label><input id="dice-ac" type="number" value="12" min="1" max="30" />`;
  container.appendChild(acRow);

  const makeGrid = (rolls) => {
    const grid = document.createElement('div');
    grid.className = 'dice-grid';
    rolls.forEach(rt => {
      const btn = document.createElement('div');
      btn.className = 'dice-option';
      btn.innerHTML = `<span class="dice-icon">${rt.icon}</span>${esc(rt.label)}`;
      btn.addEventListener('click', async () => {
        const actorVal = document.getElementById('dice-actor-sel').value;
        const targetAc = parseInt(document.getElementById('dice-ac').value) || 12;
        const [actorType, actorId] = actorVal.split(':');
        try {
          let result;
          if (actorType === 'npc') {
            result = await api('POST', `/adventures/${currentAdventureId}/npc-roll`, {
              npc_id: parseInt(actorId), roll_type: rt.type,
              target_ac: rt.type === 'attack' ? targetAc : null,
            });
          } else {
            result = await api('POST', `/adventures/${currentAdventureId}/roll`, {
              character_id: parseInt(actorId), roll_type: rt.type,
              target_ac: rt.type === 'attack' || rt.type.startsWith('save_') ? targetAc : null,
            });
          }
          appendMessage('dice', result.result, null, true);
          hideOverlay('dice');
        } catch (e) { alert(`Ошибка: ${e.message}`); }
      });
      grid.appendChild(btn);
    });
    return grid;
  };

  const label1 = document.createElement('div');
  label1.className = 'panel-section-title';
  label1.style.margin = '8px 0 4px';
  label1.textContent = 'Боевые броски';
  container.appendChild(label1);
  container.appendChild(makeGrid([
    { type: 'initiative', label: 'Инициатива', icon: '⚡' },
    { type: 'attack', label: 'Атака', icon: '⚔️' },
    { type: 'damage', label: 'Урон', icon: '💥' },
    { type: 'save_str', label: 'Спасбросок СИЛ', icon: '💪' },
    { type: 'save_dex', label: 'Спасбросок ЛОВ', icon: '🏃' },
    { type: 'save_con', label: 'Спасбросок ТЕЛ', icon: '🛡' },
    { type: 'save_int', label: 'Спасбросок ИНТ', icon: '🧠' },
    { type: 'save_wis', label: 'Спасбросок МДР', icon: '🌿' },
    { type: 'save_cha', label: 'Спасбросок ХАР', icon: '✨' },
  ]));

  const label2 = document.createElement('div');
  label2.className = 'panel-section-title';
  label2.style.margin = '8px 0 4px';
  label2.textContent = 'Произвольный кубик';
  container.appendChild(label2);
  container.appendChild(makeGrid([
    { type: 'd4', label: 'd4', icon: '🎲' },
    { type: 'd6', label: 'd6', icon: '🎲' },
    { type: 'd8', label: 'd8', icon: '🎲' },
    { type: 'd10', label: 'd10', icon: '🎲' },
    { type: 'd12', label: 'd12', icon: '🎲' },
    { type: 'd20', label: 'd20', icon: '🎲' },
    { type: 'd100', label: 'd100', icon: '🎲' },
  ]));
}

// ── Inline roll prompt card ───────────────────────────────────────────────────
function appendRollPromptCard(spec) {
  const container = document.getElementById('chat-messages');
  const card = document.createElement('div');
  card.className = 'msg roll-prompt';

  const needsDc = spec.type === 'attack' || (spec.type || '').startsWith('save_') || (spec.type || '').startsWith('check_');
  const dcVal = spec.dc != null ? spec.dc : (spec.type === 'attack' ? 12 : 13);
  const typeLabel = rollTypeLabel(spec.type);
  const reasonText = spec.reason ? `«${spec.reason}»` : '';

  // Use cached characters — no async API call needed
  const characters = _adventureCharacters;

  // Build actor select
  let actorSelectHTML = '';
  if (spec.locked && spec.actor_id) {
    const name = spec.actor_name || spec.actor || 'Персонаж';
    actorSelectHTML = `<select class="roll-actor-sel" disabled>
      <option value="${spec.actor_id}">${esc(name)}</option>
    </select>`;
  } else if (characters.length > 0) {
    const want = (spec.actor || '').trim().toLowerCase();
    const opts = characters.map(c => {
      const selected = want && c.name.toLowerCase().startsWith(want) ? 'selected' : '';
      return `<option value="${c.id}" ${selected}>${esc(c.name)} (${esc(c.char_class)})</option>`;
    }).join('');
    actorSelectHTML = `<select class="roll-actor-sel">${opts}</select>`;
  } else {
    actorSelectHTML = `<span style="color:var(--text-dim)">(персонаж)</span>`;
  }

  card.innerHTML = `
    <div class="roll-prompt-header">🎲 Требуется бросок</div>
    <div class="roll-prompt-type">${esc(typeLabel)}</div>
    ${reasonText ? `<div class="roll-prompt-reason">${esc(reasonText)}</div>` : ''}
    <div class="roll-prompt-actor-row">Персонаж: ${actorSelectHTML}</div>
    ${needsDc ? `<div class="roll-prompt-dc">DC / КД: <strong>${dcVal}</strong></div>` : ''}
    <div class="roll-prompt-controls">
      <div class="roll-prompt-manual">
        <input class="roll-manual-input" type="number" min="1" max="100"
               placeholder="${isD20Type(spec.type) ? 'd20 (1–20)' : 'сумма'}" />
        <button class="btn-secondary roll-manual-btn">Ввести вручную</button>
      </div>
      <button class="btn-primary roll-auto-btn">🎲 Бросить ${esc(typeLabel)}</button>
    </div>
    <button class="roll-cancel-btn">↩ Другое действие (отменить)</button>
  `;

  function getActorId() {
    const sel = card.querySelector('.roll-actor-sel');
    if (sel) return parseInt(sel.value) || null;
    if (spec.actor_id) return spec.actor_id;
    return characters.length > 0 ? characters[0].id : null;
  }

  function doRoll(auto) {
    if (!pendingRollSpec) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) { alert('Нет соединения с сервером'); return; }

    const actorId = getActorId();
    if (!actorId) { alert('Не удалось определить персонажа.'); return; }

    const payload = {
      type: 'roll_result',
      actor_type: 'char',
      actor_id: actorId,
      roll_type: spec.type,
      dc: needsDc ? dcVal : null,
    };

    if (!auto) {
      const v = parseInt(card.querySelector('.roll-manual-input').value);
      if (Number.isNaN(v)) { alert('Введите значение кубика.'); return; }
      if (isD20Type(spec.type)) payload.manual_die = v;
      else payload.manual_total = v;
    }

    card.querySelectorAll('button').forEach(b => { b.disabled = true; });
    card.querySelector('.roll-manual-input').disabled = true;

    ws.send(JSON.stringify(payload));
    pendingRollSpec = null;
    isThinking = true;
    setInputEnabled(false);
  }

  card.querySelector('.roll-auto-btn').addEventListener('click', () => doRoll(true));
  card.querySelector('.roll-manual-btn').addEventListener('click', () => doRoll(false));
  card.querySelector('.roll-cancel-btn').addEventListener('click', () => {
    if (!pendingRollSpec) return;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'cancel_roll' }));
    }
    pendingRollSpec = null;
    card.querySelectorAll('button').forEach(b => { b.disabled = true; });
    setInputEnabled(true);
  });

  container.appendChild(card);
  scrollChat();
}

// ── Forced roll (mandatory dice gate) ─────────────────────────────────────────
async function showForcedRoll(spec, blocked) {
  document.getElementById('forced-roll-reason').textContent = spec.reason
    ? `Мастер требует бросок: ${spec.reason}`
    : 'Мастер требует бросок, чтобы продолжить повествование.';
  document.getElementById('forced-roll-type').textContent = rollTypeLabel(spec.type);

  // Who rolls. If the GM named a specific character, lock to it — the player
  // can't reassign the roll. NPCs never reach here (they auto-roll server-side).
  const actorSel = document.getElementById('forced-roll-actor');
  actorSel.innerHTML = '';
  if (spec.locked && spec.actor_id) {
    const o = document.createElement('option');
    o.value = `char:${spec.actor_id}`;
    o.textContent = spec.actor_name || 'Персонаж';
    actorSel.appendChild(o);
    actorSel.value = o.value;
    actorSel.disabled = true;
  } else {
    actorSel.disabled = false;
    try {
      const adv = await api('GET', `/adventures/${currentAdventureId}`);
      adv.characters.forEach(c => {   // players only — never roll for NPCs
        const o = document.createElement('option');
        o.value = `char:${c.id}`;
        o.textContent = `${c.name} (${c.char_class})`;
        actorSel.appendChild(o);
      });
      if (spec.actor) {
        const want = spec.actor.trim().toLowerCase();
        const match = Array.from(actorSel.options).find(o => o.textContent.toLowerCase().startsWith(want));
        if (match) actorSel.value = match.value;
      }
    } catch {}
  }

  // DC row — only meaningful for saves, checks and attacks.
  const dcRow = document.getElementById('forced-roll-dc-row');
  const needsDc = spec.type === 'attack' || spec.type.startsWith('save_') || spec.type.startsWith('check_');
  if (needsDc) {
    dcRow.classList.remove('hidden');
    document.getElementById('forced-roll-dc').value =
      spec.dc != null ? spec.dc : (spec.type === 'attack' ? 12 : 13);
  } else {
    dcRow.classList.add('hidden');
  }

  // Hybrid: d20 face for d20-based rolls, raw sum for damage / generic dice.
  const valEl = document.getElementById('forced-roll-value');
  valEl.placeholder = isD20Type(spec.type) ? 'd20' : 'сумма';
  valEl.value = '';

  // Docked, non-blocking: hide the normal input row, keep chat + header usable.
  document.getElementById('roll-bar').classList.remove('hidden');
  document.querySelector('#view-game .message-row').classList.add('hidden');
}

function hideRollBar() {
  document.getElementById('roll-bar').classList.add('hidden');
  document.querySelector('#view-game .message-row').classList.remove('hidden');
}

function cancelForcedRoll() {
  if (!pendingRollSpec) return;
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'cancel_roll' }));
  }
  pendingRollSpec = null;
  hideRollBar();
  setInputEnabled(true);
  document.getElementById('chat-input').focus();
}

function submitForcedRoll(auto) {
  if (!pendingRollSpec) return;
  if (!ws || ws.readyState !== WebSocket.OPEN) { alert('Нет соединения с сервером'); return; }

  const spec = pendingRollSpec;
  const [actorType, actorId] = document.getElementById('forced-roll-actor').value.split(':');
  const dcRow = document.getElementById('forced-roll-dc-row');
  const dc = dcRow.classList.contains('hidden')
    ? null
    : (parseInt(document.getElementById('forced-roll-dc').value) || null);

  const payload = {
    type: 'roll_result',
    actor_type: actorType === 'npc' ? 'npc' : 'char',
    actor_id: parseInt(actorId),
    roll_type: spec.type,
    dc,
  };

  if (!auto) {
    const v = parseInt(document.getElementById('forced-roll-value').value);
    if (Number.isNaN(v)) {
      alert('Введите значение кубика или нажмите «Бросить автоматически».');
      return;
    }
    if (isD20Type(spec.type)) payload.manual_die = v;
    else payload.manual_total = v;
  }

  ws.send(JSON.stringify(payload));
  pendingRollSpec = null;
  hideRollBar();
  isThinking = true;
  setInputEnabled(false);
}

// ── Prompt Config ─────────────────────────────────────────────────────────────
function _applyPromptConfig(cfg) {
  document.getElementById('prompt-system').value = cfg.system_addendum || '';
  document.getElementById('prompt-reminder').value = cfg.turn_reminder || '';
  document.getElementById('prompt-roll-enforcement').checked = cfg.roll_enforcement !== false;
  document.getElementById('prompt-hp-tracking').checked = cfg.hp_tracking !== false;
  document.getElementById('prompt-referee-decide').value = cfg.referee_decide_system || '';
  document.getElementById('prompt-referee-analyze').value = cfg.referee_analyze_system || '';
  renderRollRules(cfg.roll_rules || []);
}

async function loadPromptConfig() {
  try {
    const cfg = await api('GET', '/prompt-config');
    _applyPromptConfig(cfg);
  } catch {}
}

function renderRollRules(rules) {
  const list = document.getElementById('roll-rules-list');
  list.innerHTML = '';
  rules.forEach(r => addRollRuleRow(r));
}

function addRollRuleRow(rule) {
  const r = rule || { category: 'check', name: '', when: '', die: 'd20', default_dc: 13, enabled: true };
  const list = document.getElementById('roll-rules-list');
  const card = document.createElement('div');
  card.className = 'roll-rule-card';
  const catOptions = ROLL_CATEGORIES.map(c =>
    `<option value="${c.value}" ${c.value === r.category ? 'selected' : ''}>${esc(c.label)}</option>`).join('');
  card.innerHTML = `
    <div class="roll-rule-head">
      <label class="checkbox-label">
        <input type="checkbox" class="rr-enabled" ${r.enabled !== false ? 'checked' : ''} /> Активно
      </label>
      <button class="remove-btn rr-remove" title="Удалить">✕</button>
    </div>
    <div class="stats-grid">
      <div class="stat-field"><label>Название</label><input class="rr-name" type="text" value="${esc(r.name || '')}" /></div>
      <div class="stat-field"><label>Категория</label><select class="rr-category">${catOptions}</select></div>
      <div class="stat-field"><label>Кость</label><input class="rr-die" type="text" value="${esc(r.die || 'd20')}" /></div>
      <div class="stat-field"><label>DC по умолч.</label><input class="rr-dc" type="number" value="${r.default_dc != null ? r.default_dc : ''}" /></div>
    </div>
    <div class="form-group">
      <label>Когда срабатывает (подсказка для ГМа)</label>
      <textarea class="rr-when" rows="2">${esc(r.when || '')}</textarea>
    </div>
  `;
  card.querySelector('.rr-remove').addEventListener('click', () => card.remove());
  list.appendChild(card);
}

function collectRollRules() {
  return Array.from(document.querySelectorAll('.roll-rule-card')).map(card => {
    const dcVal = card.querySelector('.rr-dc').value;
    return {
      enabled: card.querySelector('.rr-enabled').checked,
      name: card.querySelector('.rr-name').value.trim(),
      category: card.querySelector('.rr-category').value,
      die: card.querySelector('.rr-die').value.trim() || 'd20',
      default_dc: dcVal === '' ? null : (parseInt(dcVal) || null),
      when: card.querySelector('.rr-when').value.trim(),
    };
  });
}

// ── LLM Settings ──────────────────────────────────────────────────────────────
async function loadLLMSettings() {
  try {
    const cfg = await api('GET', '/llm/config');
    document.getElementById('llm-url').value = cfg.base_url;
    document.getElementById('llm-model').value = cfg.model;
    document.getElementById('llm-temp').value = cfg.temperature;
    document.getElementById('llm-tokens').value = cfg.max_tokens;
    document.getElementById('llm-show-thinking').checked = cfg.show_thinking || false;
    document.getElementById('llm-utility-model').value = cfg.utility_model || '';
    document.getElementById('llm-utility-temp').value =
      cfg.utility_temperature !== undefined ? cfg.utility_temperature : 0.1;
  } catch {}
  await populateModelsList();
}

async function populateModelsList() {
  const hint = document.getElementById('llm-models-hint');
  const dl = document.getElementById('llm-models-list');
  hint.textContent = 'Загрузка моделей...';
  try {
    const models = await api('GET', '/llm/models');
    dl.innerHTML = models.map(m => `<option value="${esc(m)}">`).join('');
    hint.textContent = models.length
      ? `Доступно: ${models.length} моделей. Нажмите поле модели для выбора.`
      : 'Модели не найдены. Проверьте URL и соединение.';
  } catch {
    hint.textContent = 'Не удалось загрузить список моделей.';
  }
}

async function checkLLMStatus() {
  const badge = document.getElementById('llm-status');
  badge.className = 'status-badge';
  badge.textContent = 'Проверка...';
  badge.style.display = 'block';
  try {
    const status = await api('GET', '/llm/status');
    if (status.ok) {
      badge.className = 'status-badge ok';
      badge.textContent = `✅ Подключено. Модели: ${status.models.join(', ')}`;
    } else {
      badge.className = 'status-badge error';
      badge.textContent = `❌ Ошибка: ${status.error}`;
    }
  } catch (e) {
    badge.className = 'status-badge error';
    badge.textContent = `❌ ${e.message}`;
  }
}

// ── Event wiring ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Back buttons
  document.querySelectorAll('[data-target]').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.target;
      if (target === 'home') {
        if (ws) { ws.close(); ws = null; }
        currentAdventureId = null;
        loadAdventures();
      }
      showView(target);
    });
  });

  // Home buttons
  document.getElementById('btn-new-adventure').addEventListener('click', async () => {
    await loadHeroPresets();
    document.getElementById('npc-forms').innerHTML = '';
    _selectedHeroes = [];
    renderHeroSlots();
    showView('new');
    await loadTemplateCarousel();
  });

  document.getElementById('btn-settings').addEventListener('click', async () => {
    await loadLLMSettings();
    showOverlay('settings');
  });

  document.getElementById('btn-prompts').addEventListener('click', async () => {
    await loadPromptConfig();
    showOverlay('prompts');
  });

  // New adventure form
  document.getElementById('btn-add-hero-slot').addEventListener('click', async () => {
    if (!_heroPresets.length) {
      alert('База героев пуста. Добавь героев через кнопку 🧙 на главном экране.');
      return;
    }
    if (_selectedHeroes.length >= 4) {
      alert('Максимум 4 героя в приключении.');
      return;
    }
    openPresetPicker(picked => {
      _selectedHeroes.push({ ...picked });
      renderHeroSlots();
    });
  });

  document.getElementById('btn-add-npc').addEventListener('click', () => addNpcForm());

  document.getElementById('btn-start-adventure').addEventListener('click', async () => {
    const title = document.getElementById('adv-title').value.trim();
    const desc = document.getElementById('adv-desc').value.trim();
    const role = document.getElementById('adv-role').value.trim() || 'Dungeon Master';
    if (!title || !desc) { alert('Заполните название и описание приключения'); return; }
    const characters = collectCharacters();
    if (!characters.length) { alert('Добавь хотя бы одного героя из базы.'); return; }
    const npcs = collectNpcs();
    try {
      document.getElementById('btn-start-adventure').disabled = true;
      const adv = await api('POST', '/adventures', {
        title, description: desc, gm_role: role, player_count: characters.length, characters, npcs,
      });
      showView('home');
      loadAdventures();
      openAdventure(adv.id, adv.title);
    } catch (e) {
      alert(`Ошибка: ${e.message}`);
    } finally {
      document.getElementById('btn-start-adventure').disabled = false;
    }
  });

  // Game
  document.getElementById('btn-send').addEventListener('click', sendMessage);
  document.getElementById('chat-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });

  document.getElementById('btn-party').addEventListener('click', async () => {
    await loadPartyPanel();
    showOverlay('party');
  });
  document.getElementById('btn-close-party').addEventListener('click', () => hideOverlay('party'));

  document.getElementById('btn-dice-menu').addEventListener('click', async () => {
    await loadDicePanel();
    showOverlay('dice');
  });
  document.getElementById('btn-close-dice').addEventListener('click', () => hideOverlay('dice'));

  // Save as template
  document.getElementById('btn-save-template').addEventListener('click', () => {
    document.getElementById('tmpl-name').value = document.getElementById('game-title').textContent;
    document.getElementById('tmpl-category').value = '';
    showOverlay('save-tmpl');
  });
  document.getElementById('btn-close-save-tmpl').addEventListener('click', () => hideOverlay('save-tmpl'));
  document.getElementById('btn-confirm-save-tmpl').addEventListener('click', async () => {
    const title = document.getElementById('tmpl-name').value.trim();
    const category = document.getElementById('tmpl-category').value.trim();
    if (!title) { alert('Введите название шаблона'); return; }
    try {
      await api('POST', '/templates', { title, category, adventure_id: currentAdventureId });
      hideOverlay('save-tmpl');
      alert('Шаблон сохранён!');
    } catch (e) { alert(`Ошибка: ${e.message}`); }
  });

  // Prompt config
  document.getElementById('btn-close-prompts').addEventListener('click', () => hideOverlay('prompts'));
  document.getElementById('btn-add-roll-rule').addEventListener('click', () => addRollRuleRow());
  document.getElementById('btn-save-prompts').addEventListener('click', async () => {
    await api('PUT', '/prompt-config', {
      system_addendum: document.getElementById('prompt-system').value,
      turn_reminder: document.getElementById('prompt-reminder').value,
      roll_enforcement: document.getElementById('prompt-roll-enforcement').checked,
      hp_tracking: document.getElementById('prompt-hp-tracking').checked,
      roll_rules: collectRollRules(),
      referee_decide_system: document.getElementById('prompt-referee-decide').value,
      referee_analyze_system: document.getElementById('prompt-referee-analyze').value,
    });
    hideOverlay('prompts');
    alert('Настройки сохранены. Применятся к следующей сессии.');
  });
  document.getElementById('btn-reset-prompts').addEventListener('click', async () => {
    if (!confirm('Сбросить все промпты на встроенные дефолты?')) return;
    const defaults = await api('GET', '/prompt-config/defaults');
    _applyPromptConfig(defaults);
    await api('PUT', '/prompt-config', {
      system_addendum: defaults.system_addendum,
      turn_reminder: defaults.turn_reminder,
      roll_enforcement: defaults.roll_enforcement,
      hp_tracking: defaults.hp_tracking,
      roll_rules: defaults.roll_rules,
      referee_decide_system: defaults.referee_decide_system,
      referee_analyze_system: defaults.referee_analyze_system,
    });
    alert('Промпты сброшены до дефолтов.');
  });

  // Forced roll bar
  document.getElementById('btn-forced-roll-submit').addEventListener('click', () => submitForcedRoll(false));
  document.getElementById('btn-forced-roll-auto').addEventListener('click', () => submitForcedRoll(true));
  document.getElementById('btn-forced-roll-cancel').addEventListener('click', () => cancelForcedRoll());
  document.getElementById('forced-roll-value').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); submitForcedRoll(false); }
  });

  // LLM settings
  document.getElementById('btn-close-settings').addEventListener('click', () => hideOverlay('settings'));
  document.getElementById('btn-save-llm').addEventListener('click', async () => {
    await api('PUT', '/llm/config', {
      base_url: document.getElementById('llm-url').value.trim(),
      model: document.getElementById('llm-model').value.trim(),
      temperature: parseFloat(document.getElementById('llm-temp').value),
      max_tokens: parseInt(document.getElementById('llm-tokens').value),
      show_thinking: document.getElementById('llm-show-thinking').checked,
      utility_model: document.getElementById('llm-utility-model').value.trim(),
      utility_temperature: parseFloat(document.getElementById('llm-utility-temp').value) || 0.1,
    });
    hideOverlay('settings');
  });
  document.getElementById('btn-check-llm').addEventListener('click', checkLLMStatus);
  document.getElementById('btn-load-models').addEventListener('click', populateModelsList);

  // Heroes page
  document.getElementById('btn-heroes').addEventListener('click', async () => {
    await loadHeroPresets();
    renderHeroesList();
    showView('heroes');
  });

  document.getElementById('btn-add-hero').addEventListener('click', () => {
    ensureCharRules().then(() => {
      buildPresetForm(document.getElementById('hero-form-fields'));
      showOverlay('add-hero');
    });
  });

  document.getElementById('btn-close-preset-picker').addEventListener('click', () => {
    hideOverlay('preset-picker');
    _presetPickerCallback = null;
  });
  document.getElementById('btn-close-add-hero').addEventListener('click', () => hideOverlay('add-hero'));

  document.getElementById('btn-confirm-add-hero').addEventListener('click', async () => {
    const container = document.getElementById('hero-form-fields');
    const data = readPresetForm(container);
    if (!data.name) { alert('Введи имя героя'); return; }
    try {
      await api('POST', '/character-presets', data);
      hideOverlay('add-hero');
      await loadHeroPresets();
      renderHeroesList();
    } catch (e) {
      alert('Ошибка: ' + (e.message || e));
    }
  });

  // Init
  loadAdventures();
  loadHeroPresets();
});
