/* Окно броска кубика — общий модуль для приключения и боя.
   Показывает, какой кубик с какими гранями и на что бросить; принимает ручной
   ввод (игрок бросил реальный кубик) или автобросок с анимацией и звуком.
   Разметку создаёт сам (см. _ensureDom), стили — css/dice.css.

   API (все методы на window.DiceModal):
     open(spec)      → Promise<{auto:bool, value:int|null}> — выбор игрока;
                       spec: {dice:"1d20", count, sides, min, max, modifier,
                              threshold, label, actor, stage, crit}
     spin()          → запустить анимацию катящегося кубика (числа мелькают)
     settle(result)  → Promise — остановить кубик на значении и показать исход;
                       result: {value, total, modifier, threshold, label,
                                outcome: "crit"|"hit"|"success"|"miss"|"fail"|
                                         "fumble"|"damage"|"heal"}
     close()         → скрыть окно */
"use strict";

const DiceModal = (() => {
  // ── звуки (Web Audio, без файлов — как SFX в app.js) ──
  let _actx = null;
  const ac = () => {
    if (!_actx) _actx = new (window.AudioContext || window.webkitAudioContext)();
    if (_actx.state === "suspended") _actx.resume();
    return _actx;
  };
  const tone = (freq, dur, type = "sine", vol = 0.2, delay = 0) => {
    const c = ac(), o = c.createOscillator(), g = c.createGain();
    o.connect(g); g.connect(c.destination);
    o.type = type; o.frequency.value = freq;
    const t0 = c.currentTime + delay;
    g.gain.setValueAtTime(vol, t0);
    g.gain.exponentialRampToValueAtTime(0.001, t0 + dur);
    o.start(t0); o.stop(t0 + dur);
  };
  const click = (vol = 0.3) => {
    const c = ac(), sr = c.sampleRate;
    const buf = c.createBuffer(1, Math.ceil(sr * 0.04), sr);
    const d = buf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * Math.exp(-i / (d.length * 0.12));
    const src = c.createBufferSource(), g = c.createGain();
    g.gain.value = vol; src.buffer = buf; src.connect(g); g.connect(c.destination); src.start();
  };
  const SND = {
    tumble: () => click(0.16 + Math.random() * 0.12),                    // стук кубика о стол
    land:   () => { click(0.4); tone(180, 0.1, "square", 0.12); },
    crit:    () => [523, 659, 784, 1047, 1319].forEach((f, i) => tone(f, 0.22, "sine", 0.2, i * 0.07)),
    success: () => { tone(523, 0.12, "sine", 0.18); tone(784, 0.24, "sine", 0.2, 0.1); },
    fail: () => { tone(240, 0.16, "sawtooth", 0.13); tone(160, 0.28, "sawtooth", 0.11, 0.12); },
    fumble: () => { tone(200, 0.14, "sawtooth", 0.18); tone(130, 0.2, "sawtooth", 0.16, 0.12); tone(85, 0.4, "sawtooth", 0.14, 0.26); },
    number: () => { tone(440, 0.09, "triangle", 0.14); tone(660, 0.16, "triangle", 0.12, 0.07); },
  };

  // ── форма кубика: многоугольник по числу граней (SVG points, вокруг 60,60) ──
  const SHAPES = {
    4:  "60,14 106,98 14,98",
    6:  "22,22 98,22 98,98 22,98",
    8:  "60,10 110,60 60,110 10,60",
    10: "60,10 106,44 92,106 28,106 14,44",
    12: "60,10 106,44 92,106 28,106 14,44",
    20: "60,8 105,33 105,87 60,112 15,87 15,33",
  };

  const OUTCOME_VIEW = {
    crit:    { text: "КРИТ!",       cls: "crit",    snd: "crit" },
    hit:     { text: "Попадание!",  cls: "success", snd: "success" },
    success: { text: "Успех!",      cls: "success", snd: "success" },
    miss:    { text: "Промах",      cls: "fail",    snd: "fail" },
    fail:    { text: "Провал",      cls: "fail",    snd: "fail" },
    fumble:  { text: "Крит. провал!", cls: "fumble", snd: "fumble" },
    damage:  { text: "урона",       cls: "number",  snd: "number" },
    heal:    { text: "лечения",     cls: "number",  snd: "number" },
  };

  let dom = null;          // корневые элементы окна
  let spinTimer = null;    // интервал мелькания чисел
  let spec = null;         // текущий запрос броска

  function _ensureDom() {
    if (dom) return dom;
    const bd = document.createElement("div");
    bd.className = "dice-backdrop hidden";
    bd.innerHTML = `
      <div class="dice-box">
        <div class="dice-actor"></div>
        <div class="dice-title"></div>
        <div class="dice-formula"></div>
        <div class="dice-crit-note hidden">⚡ Критическое попадание — кубики урона удвоены!</div>
        <div class="dice-stage">
          <div class="dice-die">
            <svg viewBox="0 0 120 120">
              <polygon class="dice-shape" points=""/>
              <text class="dice-num" x="60" y="60" text-anchor="middle" dominant-baseline="central"></text>
            </svg>
            <div class="dice-notation"></div>
          </div>
        </div>
        <div class="dice-outcome hidden"></div>
        <div class="dice-controls">
          <button type="button" class="dice-auto btn-primary">🎲 Автобросок</button>
          <div class="dice-or">или введите свой бросок</div>
          <div class="dice-manual">
            <input class="dice-input" type="number" inputmode="numeric">
            <button type="button" class="dice-submit btn-secondary">Ввести</button>
          </div>
          <div class="dice-hint"></div>
        </div>
      </div>`;
    document.body.appendChild(bd);
    dom = {
      backdrop: bd,
      box: bd.querySelector(".dice-box"),
      actor: bd.querySelector(".dice-actor"),
      title: bd.querySelector(".dice-title"),
      formula: bd.querySelector(".dice-formula"),
      critNote: bd.querySelector(".dice-crit-note"),
      die: bd.querySelector(".dice-die"),
      shape: bd.querySelector(".dice-shape"),
      num: bd.querySelector(".dice-num"),
      notation: bd.querySelector(".dice-notation"),
      outcome: bd.querySelector(".dice-outcome"),
      controls: bd.querySelector(".dice-controls"),
      autoBtn: bd.querySelector(".dice-auto"),
      input: bd.querySelector(".dice-input"),
      submitBtn: bd.querySelector(".dice-submit"),
      hint: bd.querySelector(".dice-hint"),
    };
    return dom;
  }

  function _formula(s) {
    const mod = s.modifier ? (s.modifier > 0 ? ` + ${s.modifier}` : ` − ${-s.modifier}`) : "";
    const vs = s.threshold != null ? `  против  ${s.threshold}` : "";
    return `${s.dice}${mod}${vs}`;
  }

  function open(rollSpec) {
    const d = _ensureDom();
    spec = rollSpec;
    _stopSpin();

    d.actor.textContent = rollSpec.actor || "";
    d.title.textContent = rollSpec.label || "Бросок кубика";
    d.formula.textContent = _formula(rollSpec);
    d.critNote.classList.toggle("hidden", !(rollSpec.crit && rollSpec.stage === "damage"));
    d.shape.setAttribute("points", SHAPES[rollSpec.sides] || SHAPES[20]);
    d.num.textContent = "?";
    d.notation.textContent = rollSpec.dice;
    d.die.className = "dice-die";
    d.box.className = "dice-box";
    d.outcome.classList.add("hidden");
    d.outcome.textContent = "";
    d.controls.classList.remove("hidden");

    d.input.value = "";
    d.input.min = rollSpec.min != null ? rollSpec.min : 1;
    d.input.max = rollSpec.max != null ? rollSpec.max : (rollSpec.count || 1) * rollSpec.sides;
    d.input.placeholder = `${d.input.min}–${d.input.max}`;
    d.hint.textContent = `Бросьте настоящий кубик (${rollSpec.dice}) и введите сумму — или доверьте бросок игре`;

    d.backdrop.classList.remove("hidden");
    d.input.focus();

    return new Promise(resolve => {
      const done = (res) => {
        d.autoBtn.onclick = d.submitBtn.onclick = d.input.onkeydown = null;
        d.controls.classList.add("hidden");
        resolve(res);
      };
      d.autoBtn.onclick = () => done({ auto: true, value: null });
      const submitManual = () => {
        const v = parseInt(d.input.value, 10);
        const lo = Number(d.input.min), hi = Number(d.input.max);
        if (isNaN(v) || v < lo || v > hi) {
          d.input.classList.add("shake");
          setTimeout(() => d.input.classList.remove("shake"), 400);
          return;
        }
        done({ auto: false, value: v });
      };
      d.submitBtn.onclick = submitManual;
      d.input.onkeydown = (e) => { if (e.key === "Enter") submitManual(); };
    });
  }

  function spin() {
    const d = _ensureDom();
    _stopSpin();
    d.die.classList.add("rolling");
    const lo = spec ? (spec.min || 1) : 1;
    const hi = spec ? (spec.max || 20) : 20;
    let tick = 0;
    spinTimer = setInterval(() => {
      d.num.textContent = lo + Math.floor(Math.random() * (hi - lo + 1));
      if (tick++ % 2 === 0) SND.tumble();
    }, 80);
  }

  function _stopSpin() {
    if (spinTimer) { clearInterval(spinTimer); spinTimer = null; }
    if (dom) dom.die.classList.remove("rolling");
  }

  function settle(result) {
    const d = _ensureDom();
    return new Promise(resolve => {
      const finish = () => {
        _stopSpin();
        SND.land();
        d.num.textContent = result.value;
        d.die.classList.add("landed");

        const view = OUTCOME_VIEW[result.outcome] || { text: "", cls: "number", snd: "number" };
        setTimeout(() => {
          d.die.classList.add("out-" + view.cls);
          d.box.classList.add("out-" + view.cls);
          let text;
          if (result.outcome === "damage" || result.outcome === "heal") {
            const total = result.total != null ? result.total : result.value;
            text = `${total} ${view.text}`;
          } else {
            const totalPart = result.total != null && result.total !== result.value
              ? ` (итог ${result.total})` : "";
            text = `${view.text}${totalPart}`;
          }
          d.outcome.textContent = text;
          d.outcome.className = "dice-outcome out-" + view.cls;
          SND[view.snd]();
          setTimeout(resolve, 1500);
        }, 280);
      };
      // если крутились — дать анимации мгновение «дожить», иначе сразу
      setTimeout(finish, spinTimer ? 450 : 0);
    });
  }

  function close() {
    _stopSpin();
    if (dom) dom.backdrop.classList.add("hidden");
    spec = null;
  }

  return { open, spin, settle, close };
})();
