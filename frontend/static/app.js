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

function showOverlay(name) {
  document.getElementById(`view-${name}`).classList.remove('hidden');
}
function hideOverlay(name) {
  document.getElementById(`view-${name}`).classList.add('hidden');
}

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

// ── Markdown renderer (minimal) ───────────────────────────────────────────────
function renderMd(text) {
  const div = document.createElement('div');
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^## (.+)$/gm, '<div class="md-h2">$1</div>')
    .replace(/^### (.+)$/gm, '<div class="md-h3">$1</div>');
  div.innerHTML = html;
  return div;
}

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
      item.innerHTML = `
        <div class="adv-item-info">
          <div class="adv-item-title">${esc(a.title)}</div>
          <div class="adv-item-meta">${a.player_count} игрок(а) · ${a.status} · ${date}</div>
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

function esc(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── New Adventure form ────────────────────────────────────────────────────────
function buildCharacterForms(count) {
  const container = document.getElementById('characters-forms');
  container.innerHTML = '';
  for (let i = 1; i <= count; i++) {
    const card = document.createElement('div');
    card.className = 'char-card';
    card.dataset.index = i;
    card.innerHTML = `
      <h3>Персонаж ${i}</h3>
      <div class="form-group">
        <label>Имя</label>
        <input class="c-name" type="text" placeholder="Арагорн" />
      </div>
      <div class="stats-grid">
        <div class="stat-field"><label>Раса</label><input class="c-race" type="text" value="Human" /></div>
        <div class="stat-field"><label>Класс</label><input class="c-class" type="text" value="Fighter" /></div>
        <div class="stat-field"><label>Уровень</label><input class="c-level" type="number" value="1" min="1" max="20" /></div>
        <div class="stat-field"><label>СИЛ</label><input class="c-str" type="number" value="10" min="1" max="20" /></div>
        <div class="stat-field"><label>ЛОВ</label><input class="c-dex" type="number" value="10" min="1" max="20" /></div>
        <div class="stat-field"><label>ТЕЛ</label><input class="c-con" type="number" value="10" min="1" max="20" /></div>
        <div class="stat-field"><label>ИНТ</label><input class="c-int" type="number" value="10" min="1" max="20" /></div>
        <div class="stat-field"><label>МДР</label><input class="c-wis" type="number" value="10" min="1" max="20" /></div>
        <div class="stat-field"><label>ХАР</label><input class="c-cha" type="number" value="10" min="1" max="20" /></div>
        <div class="stat-field"><label>Макс ХП</label><input class="c-hp" type="number" value="10" min="1" /></div>
        <div class="stat-field"><label>КД</label><input class="c-ac" type="number" value="10" min="1" /></div>
        <div class="stat-field"><label>Бонус атаки</label><input class="c-atk" type="number" value="0" /></div>
      </div>
      <div class="stat-field"><label>Кости урона</label><input class="c-dmg" type="text" value="1d6" /></div>
      <div class="form-group">
        <label>Способности / черты</label>
        <textarea class="c-abilities" rows="2" placeholder="Второе дыхание, Боевой стиль: Дуэль..."></textarea>
      </div>
      <div class="form-group">
        <label>Предыстория</label>
        <textarea class="c-background" rows="2" placeholder="Бывший солдат, ищущий искупления..."></textarea>
      </div>
    `;
    container.appendChild(card);
  }
}

function collectCharacters() {
  const cards = document.querySelectorAll('.char-card');
  return Array.from(cards).map(card => ({
    name: card.querySelector('.c-name').value.trim() || `Персонаж ${card.dataset.index}`,
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

// ── Game view ─────────────────────────────────────────────────────────────────
async function openAdventure(id, title) {
  currentAdventureId = id;
  document.getElementById('game-title').textContent = title;
  document.getElementById('chat-messages').innerHTML = '';
  showView('game');

  // Load adventure data (characters)
  const adv = await api('GET', `/adventures/${id}`);
  const sel = document.getElementById('player-select');
  sel.innerHTML = '';
  adv.characters.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.name;
    opt.textContent = `${c.name} (${c.char_class})`;
    sel.appendChild(opt);
  });

  // Load history
  const messages = await api('GET', `/adventures/${id}/messages`);
  messages.forEach(m => appendMessage(m.role, m.content, m.player_name, false));

  // Connect WebSocket
  connectWS(id);
}

function connectWS(adventureId) {
  if (ws) ws.close();
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/${adventureId}`);

  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    handleWSMessage(data);
  };

  ws.onclose = () => {
    setTimeout(() => {
      if (currentAdventureId === adventureId) connectWS(adventureId);
    }, 3000);
  };

  ws.onerror = () => ws.close();
}

function handleWSMessage(data) {
  if (data.type === 'thinking') {
    if (!thinkingMsgEl) {
      thinkingMsgEl = appendMessage('thinking', '...', null, true);
    }
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
  } else if (data.type === 'error') {
    if (thinkingMsgEl) {
      thinkingMsgEl.remove();
      thinkingMsgEl = null;
    }
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

  if (role === 'thinking') {
    bubble.textContent = content;
  } else if (role === 'dice') {
    bubble.appendChild(renderMd(content));
  } else {
    bubble.appendChild(renderMd(content));
  }

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
async function loadPartyPanel() {
  const list = document.getElementById('party-list');
  list.innerHTML = '';
  try {
    const adv = await api('GET', `/adventures/${currentAdventureId}`);
    adv.characters.forEach(c => {
      const pct = Math.round((c.current_hp / c.max_hp) * 100);
      const hpColor = pct > 50 ? 'var(--success)' : pct > 25 ? 'var(--accent2)' : 'var(--danger)';
      const el = document.createElement('div');
      el.className = 'party-char';
      el.innerHTML = `
        <div class="party-char-name">${esc(c.name)}</div>
        <div class="party-char-sub">${esc(c.race)} ${esc(c.char_class)} · Ур.${c.level} · КД ${c.armor_class}</div>
        <div class="hp-bar-wrap">
          <div class="hp-bar-bg"><div class="hp-bar" style="width:${pct}%;background:${hpColor}"></div></div>
          <div class="hp-text">${c.current_hp}/${c.max_hp} ХП</div>
        </div>
        <div class="hp-controls">
          <button class="hp-heal" data-id="${c.id}">+</button>
          <input class="hp-delta" type="number" value="5" min="1" max="999" />
          <button class="hp-damage" data-id="${c.id}">−</button>
          <span style="font-size:12px;color:var(--text-dim);margin-left:4px">${c.status}</span>
        </div>
      `;
      el.querySelector('.hp-heal').addEventListener('click', async () => {
        const delta = parseInt(el.querySelector('.hp-delta').value) || 5;
        await api('POST', `/adventures/${currentAdventureId}/hp`, { character_id: c.id, delta });
        loadPartyPanel();
      });
      el.querySelector('.hp-damage').addEventListener('click', async () => {
        const delta = -(parseInt(el.querySelector('.hp-delta').value) || 5);
        await api('POST', `/adventures/${currentAdventureId}/hp`, { character_id: c.id, delta });
        loadPartyPanel();
      });
      list.appendChild(el);
    });
  } catch (e) {
    list.innerHTML = `<div class="empty-state">Ошибка: ${e.message}</div>`;
  }
}

// ── Dice panel ────────────────────────────────────────────────────────────────
async function loadDicePanel() {
  const container = document.getElementById('dice-options');
  container.innerHTML = '';

  const rollTypes = [
    { type: 'initiative', label: 'Инициатива', icon: '⚡' },
    { type: 'attack', label: 'Атака', icon: '⚔️' },
    { type: 'damage', label: 'Урон', icon: '💥' },
    { type: 'save_str', label: 'Спасбросок СИЛ', icon: '💪' },
    { type: 'save_dex', label: 'Спасбросок ЛОВ', icon: '🏃' },
    { type: 'save_con', label: 'Спасбросок ТЕЛ', icon: '🛡' },
    { type: 'save_int', label: 'Спасбросок ИНТ', icon: '🧠' },
    { type: 'save_wis', label: 'Спасбросок МДР', icon: '🌿' },
    { type: 'save_cha', label: 'Спасбросок ХАР', icon: '✨' },
    { type: 'd4', label: 'Просто d4', icon: '🎲' },
    { type: 'd6', label: 'Просто d6', icon: '🎲' },
    { type: 'd8', label: 'Просто d8', icon: '🎲' },
    { type: 'd10', label: 'Просто d10', icon: '🎲' },
    { type: 'd12', label: 'Просто d12', icon: '🎲' },
    { type: 'd20', label: 'Просто d20', icon: '🎲' },
    { type: 'd100', label: 'Просто d100', icon: '🎲' },
  ];

  const adv = await api('GET', `/adventures/${currentAdventureId}`);
  const chars = adv.characters;

  // Character selector
  const selRow = document.createElement('div');
  selRow.className = 'form-group';
  selRow.innerHTML = `<label>Персонаж</label><select id="dice-char-sel">${chars.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('')}</select>`;
  container.appendChild(selRow);

  // AC input for attack
  const acRow = document.createElement('div');
  acRow.className = 'form-group';
  acRow.innerHTML = `<label>КД цели (для атаки)</label><input id="dice-ac" type="number" value="12" min="1" max="30" />`;
  container.appendChild(acRow);

  const grid = document.createElement('div');
  grid.className = 'dice-grid';
  rollTypes.forEach(rt => {
    const btn = document.createElement('div');
    btn.className = 'dice-option';
    btn.innerHTML = `<span class="dice-icon">${rt.icon}</span>${esc(rt.label)}`;
    btn.addEventListener('click', async () => {
      const charId = parseInt(document.getElementById('dice-char-sel').value);
      const targetAc = parseInt(document.getElementById('dice-ac').value) || 12;
      try {
        const result = await api('POST', `/adventures/${currentAdventureId}/roll`, {
          character_id: charId,
          roll_type: rt.type,
          target_ac: rt.type === 'attack' || rt.type.startsWith('save_') ? targetAc : null,
        });
        appendMessage('dice', result.result, null, true);
        hideOverlay('dice');
      } catch (e) {
        alert(`Ошибка: ${e.message}`);
      }
    });
    grid.appendChild(btn);
  });
  container.appendChild(grid);
}

// ── LLM Settings ──────────────────────────────────────────────────────────────
async function loadLLMSettings() {
  try {
    const cfg = await api('GET', '/llm/config');
    document.getElementById('llm-url').value = cfg.base_url;
    document.getElementById('llm-model').value = cfg.model;
    document.getElementById('llm-temp').value = cfg.temperature;
    document.getElementById('llm-tokens').value = cfg.max_tokens;
  } catch {}
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
  // Navigation
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

  // Home
  document.getElementById('btn-new-adventure').addEventListener('click', () => {
    buildCharacterForms(parseInt(document.getElementById('adv-players')?.value || 3));
    showView('new');
  });

  document.getElementById('btn-settings').addEventListener('click', async () => {
    await loadLLMSettings();
    showOverlay('settings');
  });

  // New adventure — player count change
  document.getElementById('adv-players').addEventListener('change', (e) => {
    buildCharacterForms(parseInt(e.target.value));
  });

  // Start adventure
  document.getElementById('btn-start-adventure').addEventListener('click', async () => {
    const title = document.getElementById('adv-title').value.trim();
    const desc = document.getElementById('adv-desc').value.trim();
    const role = document.getElementById('adv-role').value.trim() || 'Dungeon Master';
    const playerCount = parseInt(document.getElementById('adv-players').value);

    if (!title || !desc) { alert('Заполните название и описание приключения'); return; }

    const characters = collectCharacters();
    try {
      document.getElementById('btn-start-adventure').disabled = true;
      const adv = await api('POST', '/adventures', {
        title, description: desc, gm_role: role, player_count: playerCount, characters,
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

  // Game input
  document.getElementById('btn-send').addEventListener('click', sendMessage);
  document.getElementById('chat-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });

  // Party panel
  document.getElementById('btn-party').addEventListener('click', async () => {
    await loadPartyPanel();
    showOverlay('party');
  });
  document.getElementById('btn-close-party').addEventListener('click', () => hideOverlay('party'));

  // Dice panel
  document.getElementById('btn-dice-menu').addEventListener('click', async () => {
    await loadDicePanel();
    showOverlay('dice');
  });
  document.getElementById('btn-close-dice').addEventListener('click', () => hideOverlay('dice'));

  // Settings
  document.getElementById('btn-close-settings').addEventListener('click', () => hideOverlay('settings'));
  document.getElementById('btn-save-llm').addEventListener('click', async () => {
    await api('PUT', '/llm/config', {
      base_url: document.getElementById('llm-url').value.trim(),
      model: document.getElementById('llm-model').value.trim(),
      temperature: parseFloat(document.getElementById('llm-temp').value),
      max_tokens: parseInt(document.getElementById('llm-tokens').value),
    });
    hideOverlay('settings');
  });
  document.getElementById('btn-check-llm').addEventListener('click', checkLLMStatus);

  // Init
  buildCharacterForms(3);
  loadAdventures();
});
