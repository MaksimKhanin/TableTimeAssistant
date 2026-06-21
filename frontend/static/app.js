'use strict';

// ── State ────────────────────────────────────────────────────────────────────
let currentAdventureId = null;
let ws = null;
let isThinking = false;
let thinkingMsgEl = null;

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
    // Clear to defaults
    document.getElementById('adv-title').value = '';
    document.getElementById('adv-desc').value = '';
    document.getElementById('adv-role').value = 'Dungeon Master';
    document.getElementById('adv-players').value = '3';
    buildCharacterForms(3);
    document.getElementById('npc-forms').innerHTML = '';
    return;
  }

  // Fill fields
  document.getElementById('adv-title').value = tmpl.title;
  document.getElementById('adv-desc').value = tmpl.description;
  document.getElementById('adv-role').value = tmpl.gm_role;
  document.getElementById('adv-players').value = String(tmpl.player_count);

  // Rebuild character forms with template data
  buildCharacterForms(tmpl.player_count, tmpl.characters_json);

  // Rebuild NPC forms
  const npcContainer = document.getElementById('npc-forms');
  npcContainer.innerHTML = '';
  (tmpl.npcs_json || []).forEach(n => addNpcForm(n));
}

// ── New Adventure form ────────────────────────────────────────────────────────
function buildCharacterForms(count, prefill) {
  const container = document.getElementById('characters-forms');
  container.innerHTML = '';
  for (let i = 0; i < count; i++) {
    const p = prefill && prefill[i] ? prefill[i] : {};
    const card = document.createElement('div');
    card.className = 'char-card';
    card.dataset.index = i + 1;
    card.innerHTML = `
      <h3>Персонаж ${i + 1}</h3>
      <div class="form-group">
        <label>Имя</label>
        <input class="c-name" type="text" placeholder="Арагорн" value="${esc(p.name || '')}" />
      </div>
      <div class="stats-grid">
        <div class="stat-field"><label>Раса</label><input class="c-race" type="text" value="${esc(p.race || 'Human')}" /></div>
        <div class="stat-field"><label>Класс</label><input class="c-class" type="text" value="${esc(p.char_class || 'Fighter')}" /></div>
        <div class="stat-field"><label>Уровень</label><input class="c-level" type="number" value="${p.level || 1}" min="1" max="20" /></div>
        <div class="stat-field"><label>СИЛ</label><input class="c-str" type="number" value="${p.strength || 10}" min="1" max="20" /></div>
        <div class="stat-field"><label>ЛОВ</label><input class="c-dex" type="number" value="${p.dexterity || 10}" min="1" max="20" /></div>
        <div class="stat-field"><label>ТЕЛ</label><input class="c-con" type="number" value="${p.constitution || 10}" min="1" max="20" /></div>
        <div class="stat-field"><label>ИНТ</label><input class="c-int" type="number" value="${p.intelligence || 10}" min="1" max="20" /></div>
        <div class="stat-field"><label>МДР</label><input class="c-wis" type="number" value="${p.wisdom || 10}" min="1" max="20" /></div>
        <div class="stat-field"><label>ХАР</label><input class="c-cha" type="number" value="${p.charisma || 10}" min="1" max="20" /></div>
        <div class="stat-field"><label>Макс ХП</label><input class="c-hp" type="number" value="${p.max_hp || 10}" min="1" /></div>
        <div class="stat-field"><label>КД</label><input class="c-ac" type="number" value="${p.armor_class || 10}" min="1" /></div>
        <div class="stat-field"><label>Бонус атаки</label><input class="c-atk" type="number" value="${p.attack_bonus || 0}" /></div>
      </div>
      <div class="stat-field"><label>Кости урона</label><input class="c-dmg" type="text" value="${esc(p.damage_dice || '1d6')}" /></div>
      <div class="form-group">
        <label>Способности / черты</label>
        <textarea class="c-abilities" rows="2" placeholder="Второе дыхание, Боевой стиль: Дуэль...">${esc(p.abilities || '')}</textarea>
      </div>
      <div class="form-group">
        <label>Предыстория</label>
        <textarea class="c-background" rows="2" placeholder="Бывший солдат, ищущий искупления...">${esc(p.background || '')}</textarea>
      </div>
    `;
    container.appendChild(card);
  }
}

function addNpcForm(prefill) {
  const p = prefill || {};
  const container = document.getElementById('npc-forms');
  const idx = container.children.length + 1;
  const card = document.createElement('div');
  card.className = 'npc-card';
  card.innerHTML = `
    <h3>NPC ${idx}</h3>
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
      <div class="stat-field"><label>Макс ХП</label><input class="n-hp" type="number" value="${p.max_hp || 20}" min="1" /></div>
      <div class="stat-field"><label>КД</label><input class="n-ac" type="number" value="${p.armor_class || 12}" min="1" /></div>
      <div class="stat-field"><label>Бонус атаки</label><input class="n-atk" type="number" value="${p.attack_bonus || 3}" /></div>
      <div class="stat-field"><label>Кости урона</label><input class="n-dmg" type="text" value="${esc(p.damage_dice || '1d8')}" /></div>
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
  container.appendChild(card);
}

function collectCharacters() {
  return Array.from(document.querySelectorAll('.char-card')).map((card, i) => ({
    name: card.querySelector('.c-name').value.trim() || `Персонаж ${i + 1}`,
    race: card.querySelector('.c-race').value.trim(),
    char_class: card.querySelector('.c-class').value.trim(),
    level: parseInt(card.querySelector('.c-level').value) || 1,
    strength: parseInt(card.querySelector('.c-str').value) || 10,
    dexterity: parseInt(card.querySelector('.c-dex').value) || 10,
    constitution: parseInt(card.querySelector('.c-con').value) || 10,
    intelligence: parseInt(card.querySelector('.c-int').value) || 10,
    wisdom: parseInt(card.querySelector('.c-wis').value) || 10,
    charisma: parseInt(card.querySelector('.c-cha').value) || 10,
    max_hp: parseInt(card.querySelector('.c-hp').value) || 10,
    armor_class: parseInt(card.querySelector('.c-ac').value) || 10,
    attack_bonus: parseInt(card.querySelector('.c-atk').value) || 0,
    damage_dice: card.querySelector('.c-dmg').value.trim() || '1d6',
    abilities: card.querySelector('.c-abilities').value.trim(),
    background: card.querySelector('.c-background').value.trim(),
  }));
}

function collectNpcs() {
  return Array.from(document.querySelectorAll('.npc-card')).map(card => ({
    name: card.querySelector('.n-name').value.trim() || 'NPC',
    role: card.querySelector('.n-role').value.trim(),
    is_enemy: parseInt(card.querySelector('.n-enemy').value),
    max_hp: parseInt(card.querySelector('.n-hp').value) || 10,
    armor_class: parseInt(card.querySelector('.n-ac').value) || 10,
    attack_bonus: parseInt(card.querySelector('.n-atk').value) || 0,
    damage_dice: card.querySelector('.n-dmg').value.trim() || '1d6',
    personality: card.querySelector('.n-personality').value.trim(),
    voice_style: card.querySelector('.n-voice').value.trim(),
  }));
}

// ── Game view ─────────────────────────────────────────────────────────────────
async function openAdventure(id, title) {
  currentAdventureId = id;
  document.getElementById('game-title').textContent = title;
  document.getElementById('chat-messages').innerHTML = '';
  showView('game');

  const adv = await api('GET', `/adventures/${id}`);
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
  } else if (data.type === 'done') {
    thinkingMsgEl = null;
    isThinking = false;
    setInputEnabled(true);
    scrollChat();
  } else if (data.type === 'think_done') {
    appendThinkBlock(data.content);
  } else if (data.type === 'error') {
    if (thinkingMsgEl) { thinkingMsgEl.remove(); thinkingMsgEl = null; }
    isThinking = false;
    setInputEnabled(true);
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
  container.appendChild(block);
  scrollChat();
}

function setInputEnabled(enabled) {
  document.getElementById('btn-send').disabled = !enabled;
  document.getElementById('chat-input').disabled = !enabled;
}

function sendMessage() {
  if (isThinking) return;
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
    ? `${esc(entity.role || (entity.is_enemy ? 'Враг' : 'Союзник'))} · КД ${entity.armor_class}`
    : `${esc(entity.race)} ${esc(entity.char_class)} · Ур.${entity.level} · КД ${entity.armor_class}`;
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

// ── Prompt Config ─────────────────────────────────────────────────────────────
async function loadPromptConfig() {
  try {
    const cfg = await api('GET', '/prompt-config');
    document.getElementById('prompt-system').value = cfg.system_addendum || '';
    document.getElementById('prompt-reminder').value = cfg.turn_reminder || '';
  } catch {}
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
    document.getElementById('npc-forms').innerHTML = '';
    buildCharacterForms(3);
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
  document.getElementById('adv-players').addEventListener('change', (e) => {
    buildCharacterForms(parseInt(e.target.value));
  });
  document.getElementById('btn-add-npc').addEventListener('click', () => addNpcForm());

  document.getElementById('btn-start-adventure').addEventListener('click', async () => {
    const title = document.getElementById('adv-title').value.trim();
    const desc = document.getElementById('adv-desc').value.trim();
    const role = document.getElementById('adv-role').value.trim() || 'Dungeon Master';
    const playerCount = parseInt(document.getElementById('adv-players').value);
    if (!title || !desc) { alert('Заполните название и описание приключения'); return; }
    const characters = collectCharacters();
    const npcs = collectNpcs();
    try {
      document.getElementById('btn-start-adventure').disabled = true;
      const adv = await api('POST', '/adventures', {
        title, description: desc, gm_role: role, player_count: playerCount, characters, npcs,
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
  document.getElementById('btn-save-prompts').addEventListener('click', async () => {
    await api('PUT', '/prompt-config', {
      system_addendum: document.getElementById('prompt-system').value,
      turn_reminder: document.getElementById('prompt-reminder').value,
    });
    hideOverlay('prompts');
    alert('Промпты сохранены. Применятся к следующей сессии.');
  });
  document.getElementById('btn-reset-prompts').addEventListener('click', async () => {
    if (!confirm('Сбросить промпты на пустые?')) return;
    document.getElementById('prompt-system').value = '';
    document.getElementById('prompt-reminder').value = '';
    await api('PUT', '/prompt-config', { system_addendum: '', turn_reminder: '' });
    hideOverlay('prompts');
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
    });
    hideOverlay('settings');
  });
  document.getElementById('btn-check-llm').addEventListener('click', checkLLMStatus);
  document.getElementById('btn-load-models').addEventListener('click', populateModelsList);

  // Init
  buildCharacterForms(3);
  loadAdventures();
});
