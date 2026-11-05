/* Korsordsmakaren – gränssnitt utan ramverk. */
"use strict";

const ACROSS = "across";
const DOWN = "down";
const LETTER_RE = /^[a-zåäöéèàüáí]$/i;
const STORAGE_KEY = "korsord.v1";

// ------------------------------------------------------------------ tillstånd
let S = null;
let wordlistSource = "";
let cur = { r: 0, c: 0, dir: ACROSS };
let drawing = false;
let slots = [];          // beräknade luckor
let numbers = new Map(); // cellindex -> nummer
let badKeys = new Set(); // luckor vars ord saknas i ordlistan
let clueEls = new Map(); // nyckel -> <li>
let lastSlotSignature = "";

const $ = (id) => document.getElementById(id);
const board = $("board");

function newPuzzle(rows, cols) {
  return {
    title: $("title") ? $("title").value : "Mitt korsord",
    rows, cols,
    cells: Array.from({ length: rows * cols }, () => ({ b: false, ch: "", auto: false })),
    clues: {},
    symmetry: false,
  };
}

const idx = (r, c) => r * S.cols + c;
const cell = (r, c) => S.cells[idx(r, c)];
const inside = (r, c) => r >= 0 && c >= 0 && r < S.rows && c < S.cols;
const white = (r, c) => inside(r, c) && !cell(r, c).b;

function normLetter(ch) {
  const up = ch.toUpperCase();
  if ("ÅÄÖ".includes(up)) return up;
  return up.normalize("NFD")[0];
}

// ------------------------------------------------------------------ luckor
function computeSlots() {
  slots = [];
  numbers = new Map();
  let n = 0;
  for (let r = 0; r < S.rows; r++) {
    for (let c = 0; c < S.cols; c++) {
      if (!white(r, c)) continue;
      const a = !white(r, c - 1) && white(r, c + 1);
      const d = !white(r - 1, c) && white(r + 1, c);
      if (!a && !d) continue;
      n++;
      numbers.set(idx(r, c), n);
      if (a) {
        const cells = [];
        for (let cc = c; white(r, cc); cc++) cells.push([r, cc]);
        slots.push({ num: n, dir: ACROSS, row: r, col: c, cells, key: `${r},${c},${ACROSS}` });
      }
      if (d) {
        const cells = [];
        for (let rr = r; white(rr, c); rr++) cells.push([rr, c]);
        slots.push({ num: n, dir: DOWN, row: r, col: c, cells, key: `${r},${c},${DOWN}` });
      }
    }
  }
}

function slotAt(r, c, dir) {
  return slots.find((s) => s.dir === dir && s.cells.some(([rr, cc]) => rr === r && cc === c)) || null;
}

function currentSlot() {
  return slotAt(cur.r, cur.c, cur.dir) || slotAt(cur.r, cur.c, cur.dir === ACROSS ? DOWN : ACROSS);
}

function slotPattern(slot) {
  return slot.cells.map(([r, c]) => cell(r, c).ch || "?").join("");
}

// ------------------------------------------------------------------ rendering
function render() {
  computeSlots();
  const slot = white(cur.r, cur.c) ? currentSlot() : null;
  if (slot) cur.dir = slot.dir;
  const inSlot = new Set(slot ? slot.cells.map(([r, c]) => idx(r, c)) : []);

  const size = Math.max(22, Math.min(44, Math.floor((Math.min(window.innerWidth, 1400) * 0.55) / S.cols)));
  board.style.setProperty("--cell", (window.innerWidth < 900 ? Math.min(size, Math.floor((window.innerWidth - 40) / S.cols)) : size) + "px");
  board.style.gridTemplateColumns = `repeat(${S.cols}, var(--cell))`;
  board.classList.toggle("drawing", drawing);

  const html = [];
  for (let r = 0; r < S.rows; r++) {
    for (let c = 0; c < S.cols; c++) {
      const i = idx(r, c);
      const x = S.cells[i];
      const cls = ["cell"];
      if (x.b) cls.push("block");
      if (inSlot.has(i)) cls.push("in-slot");
      if (r === cur.r && c === cur.c) cls.push("cursor");
      const num = numbers.get(i);
      html.push(
        `<div class="${cls.join(" ")}" data-r="${r}" data-c="${c}">` +
          (num ? `<span class="num">${num}</span>` : "") +
          (x.ch && !x.b ? `<span class="letter${x.auto ? " auto" : ""}">${x.ch}</span>` : "") +
          `</div>`
      );
    }
  }
  board.innerHTML = html.join("");
  renderClues(slot);
  renderSlotPanel(slot);
  scheduleSave();
  scheduleCheck();
}

function renderClues(active) {
  const signature = slots.map((s) => s.key + ":" + s.num).join("|");
  if (signature !== lastSlotSignature) {
    lastSlotSignature = signature;
    clueEls = new Map();
    for (const dir of [ACROSS, DOWN]) {
      const ol = $(dir === ACROSS ? "clues-across" : "clues-down");
      ol.innerHTML = "";
      for (const s of slots.filter((x) => x.dir === dir)) {
        const li = document.createElement("li");
        li.className = "clue";
        li.dataset.key = s.key;
        li.innerHTML =
          `<span class="n">${s.num}</span>` +
          `<span class="answer"><span class="pat"></span><button class="small ai" title="Föreslå ledtrådar med AI">✨ Förslag</button></span>` +
          `<textarea rows="1" placeholder="Skriv ledtråd …"></textarea>` +
          `<div class="ai-row"></div>`;
        const ta = li.querySelector("textarea");
        ta.value = S.clues[s.key] || "";
        ta.addEventListener("input", () => { S.clues[s.key] = ta.value; scheduleSave(); });
        ta.addEventListener("focus", () => { cur = { r: s.row, c: s.col, dir: s.dir }; highlightOnly(); });
        li.querySelector("button.ai").addEventListener("click", () => suggestClues(s.key, li));
        ol.appendChild(li);
        clueEls.set(s.key, li);
      }
    }
  }
  for (const s of slots) {
    const li = clueEls.get(s.key);
    if (!li) continue;
    li.querySelector(".pat").textContent = slotPattern(s).replaceAll("?", "·");
    li.querySelector(".answer").classList.toggle("bad", badKeys.has(s.key));
    li.classList.toggle("active", !!active && active.key === s.key);
  }
}

// Uppdatera markeringar utan att bygga om ledtrådslistan (behåller fokus i textrutor).
function highlightOnly() {
  const slot = currentSlot();
  const inSlot = new Set(slot ? slot.cells.map(([r, c]) => idx(r, c)) : []);
  for (const el of board.children) {
    const i = idx(+el.dataset.r, +el.dataset.c);
    el.classList.toggle("in-slot", inSlot.has(i));
    el.classList.toggle("cursor", +el.dataset.r === cur.r && +el.dataset.c === cur.c);
  }
  for (const [key, li] of clueEls) li.classList.toggle("active", !!slot && slot.key === key);
  renderSlotPanel(slot);
}

// ------------------------------------------------------------------ ordförslag
let suggestTimer = null;
let suggestSeq = 0;

function renderSlotPanel(slot) {
  const title = $("slot-title");
  const meta = $("slot-meta");
  const list = $("suggestions");
  if (!slot) {
    title.textContent = "Välj en ruta";
    meta.textContent = "Klicka i rutnätet för att se ord som passar.";
    list.innerHTML = "";
    return;
  }
  const pattern = slotPattern(slot);
  title.textContent = `${slot.num} ${slot.dir === ACROSS ? "vågrätt" : "lodrätt"}`;
  meta.innerHTML = `<code>${pattern.replaceAll("?", "·")}</code> · ${slot.cells.length} bokstäver`;
  clearTimeout(suggestTimer);
  suggestTimer = setTimeout(() => loadSuggestions(slot, pattern), 120);
}

async function loadSuggestions(slot, pattern) {
  const seq = ++suggestSeq;
  const list = $("suggestions");
  try {
    const res = await fetch(`api/words?limit=120&pattern=${encodeURIComponent(pattern)}`);
    const data = await res.json();
    if (seq !== suggestSeq) return;
    list.innerHTML = "";
    if (!pattern.includes("?")) {
      const known = data.total > 0;
      list.innerHTML = `<li class="empty">${known ? "Ordet finns i ordlistan." : "Ordet finns inte i ordlistan."}</li>`;
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.className = "small";
      btn.textContent = "Töm ordet";
      btn.onclick = () => { clearSlot(slot); };
      li.appendChild(btn);
      list.appendChild(li);
      return;
    }
    if (!data.words || data.words.length === 0) {
      list.innerHTML = `<li class="empty">Inga ord passar.</li>`;
      return;
    }
    $("slot-meta").innerHTML += ` · ${data.total} träffar`;
    for (const w of data.words) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.textContent = w.word;
      btn.title = `Poäng ${w.score}`;
      btn.onclick = () => placeWord(slot, w.word);
      li.appendChild(btn);
      list.appendChild(li);
    }
  } catch (e) {
    list.innerHTML = `<li class="empty">Kunde inte hämta ordförslag.</li>`;
  }
}

function placeWord(slot, word) {
  slot.cells.forEach(([r, c], i) => {
    const x = cell(r, c);
    if (x.ch !== word[i]) { x.ch = word[i]; x.auto = false; }
  });
  render();
  board.focus();
}

function clearSlot(slot) {
  // Behåll bokstäver som ingår i korsande, färdiga ord.
  for (const [r, c] of slot.cells) {
    const other = slotAt(r, c, slot.dir === ACROSS ? DOWN : ACROSS);
    if (other && !slotPattern(other).includes("?")) continue;
    cell(r, c).ch = "";
    cell(r, c).auto = false;
  }
  render();
}

// ------------------------------------------------------------------ redigering
function toggleBlock(r, c) {
  const v = !cell(r, c).b;
  const targets = [[r, c]];
  if ($("symmetry").checked) targets.push([S.rows - 1 - r, S.cols - 1 - c]);
  for (const [rr, cc] of targets) {
    const x = cell(rr, cc);
    x.b = v;
    if (v) { x.ch = ""; x.auto = false; }
  }
  render();
}

function step(dr, dc) {
  let r = cur.r + dr, c = cur.c + dc;
  if (inside(r, c)) { cur.r = r; cur.c = c; }
}

function advance(back = false) {
  const [dr, dc] = cur.dir === ACROSS ? [0, 1] : [1, 0];
  const s = back ? -1 : 1;
  const r = cur.r + dr * s, c = cur.c + dc * s;
  if (white(r, c)) { cur.r = r; cur.c = c; }
}

function jumpSlot(delta) {
  if (!slots.length) return;
  const ordered = [...slots.filter((s) => s.dir === ACROSS), ...slots.filter((s) => s.dir === DOWN)];
  const now = currentSlot();
  let i = now ? ordered.findIndex((s) => s.key === now.key) : -1;
  i = (i + delta + ordered.length) % ordered.length;
  const next = ordered[i];
  const empty = next.cells.find(([r, c]) => !cell(r, c).ch) || next.cells[0];
  cur = { r: empty[0], c: empty[1], dir: next.dir };
}

board.addEventListener("mousedown", (e) => {
  const el = e.target.closest(".cell");
  if (!el) return;
  e.preventDefault();
  board.focus();
  const r = +el.dataset.r, c = +el.dataset.c;
  if (drawing) { cur.r = r; cur.c = c; toggleBlock(r, c); return; }
  if (r === cur.r && c === cur.c) cur.dir = cur.dir === ACROSS ? DOWN : ACROSS;
  else { cur.r = r; cur.c = c; }
  render();
});

board.addEventListener("keydown", (e) => {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key;
  if (LETTER_RE.test(k)) {
    if (!white(cur.r, cur.c)) return;
    const x = cell(cur.r, cur.c);
    x.ch = normLetter(k);
    x.auto = false;
    advance();
  } else if (k === "Backspace") {
    const x = cell(cur.r, cur.c);
    if (x.ch && !x.b) { x.ch = ""; x.auto = false; }
    else { advance(true); const y = cell(cur.r, cur.c); if (!y.b) { y.ch = ""; y.auto = false; } }
  } else if (k === "Delete") {
    const x = cell(cur.r, cur.c); x.ch = ""; x.auto = false;
  } else if (k === "." || k === "#") {
    toggleBlock(cur.r, cur.c); e.preventDefault(); return;
  } else if (k === " ") {
    cur.dir = cur.dir === ACROSS ? DOWN : ACROSS;
  } else if (k === "ArrowRight") { step(0, 1); if (cur.dir !== ACROSS && slotAt(cur.r, cur.c, ACROSS)) cur.dir = ACROSS; }
  else if (k === "ArrowLeft") { step(0, -1); if (cur.dir !== ACROSS && slotAt(cur.r, cur.c, ACROSS)) cur.dir = ACROSS; }
  else if (k === "ArrowDown") { step(1, 0); if (cur.dir !== DOWN && slotAt(cur.r, cur.c, DOWN)) cur.dir = DOWN; }
  else if (k === "ArrowUp") { step(-1, 0); if (cur.dir !== DOWN && slotAt(cur.r, cur.c, DOWN)) cur.dir = DOWN; }
  else if (k === "Tab") { jumpSlot(e.shiftKey ? -1 : 1); }
  else return;
  e.preventDefault();
  render();
});

// ------------------------------------------------------------------ verktyg
$("btn-new").onclick = () => {
  const rows = Math.max(3, Math.min(25, +$("rows").value || 9));
  const cols = Math.max(3, Math.min(25, +$("cols").value || 9));
  const hasContent = S.cells.some((x) => x.b || x.ch) || Object.values(S.clues).some(Boolean);
  if (hasContent && !confirm("Skapa ett nytt rutnät? Nuvarande korsord ersätts.")) return;
  const title = $("title").value;
  S = newPuzzle(rows, cols);
  S.title = title;
  cur = { r: 0, c: 0, dir: ACROSS };
  lastSlotSignature = "";
  render();
};

$("btn-draw").onclick = () => {
  drawing = !drawing;
  $("btn-draw").setAttribute("aria-pressed", String(drawing));
  render();
  board.focus();
};

$("symmetry").onchange = () => { S.symmetry = $("symmetry").checked; scheduleSave(); };
$("title").oninput = () => { S.title = $("title").value; scheduleSave(); };

$("btn-clear-auto").onclick = () => {
  S.cells.forEach((x) => { if (x.auto) { x.ch = ""; x.auto = false; } });
  render();
};
$("btn-clear-all").onclick = () => {
  if (!confirm("Ta bort alla bokstäver? Svarta rutor och ledtrådar behålls.")) return;
  S.cells.forEach((x) => { x.ch = ""; x.auto = false; });
  render();
};

function gridForApi() {
  const g = [];
  for (let r = 0; r < S.rows; r++) {
    const row = [];
    for (let c = 0; c < S.cols; c++) {
      const x = cell(r, c);
      row.push(x.b ? "#" : x.ch);
    }
    g.push(row);
  }
  return g;
}

$("btn-fill").onclick = async () => {
  const btn = $("btn-fill");
  btn.disabled = true;
  btn.textContent = "Fyller …";
  try {
    const res = await fetch("api/fill", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ grid: gridForApi(), timeout: 15, seed: Math.floor(Math.random() * 1e9) }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Fel vid fyllning");
    if (!data.ok) { toast(data.message, true); return; }
    for (let r = 0; r < S.rows; r++) {
      for (let c = 0; c < S.cols; c++) {
        const x = cell(r, c);
        const v = data.grid[r][c];
        if (!x.b && !x.ch && v) { x.ch = v; x.auto = true; }
      }
    }
    render();
    toast(`Fyllt på ${(data.elapsed_ms / 1000).toFixed(1)} s`);
  } catch (e) {
    toast(e.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "Fyll automatiskt";
  }
};

// ------------------------------------------------------------------ ordkontroll
let checkTimer = null;
function scheduleCheck() {
  clearTimeout(checkTimer);
  checkTimer = setTimeout(checkWords, 400);
}
async function checkWords() {
  try {
    const res = await fetch("api/check", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ grid: gridForApi() }),
    });
    if (!res.ok) return;
    const data = await res.json();
    badKeys = new Set(data.slots.filter((s) => s.known === false).map((s) => s.key));
    for (const [key, li] of clueEls) li.querySelector(".answer").classList.toggle("bad", badKeys.has(key));
  } catch (_) { /* servern nere – ignorera */ }
}

// ------------------------------------------------------------------ AI-ledtrådar
async function suggestClues(key, li) {
  const slot = slots.find((s) => s.key === key);
  if (!slot) return;
  const answer = slotPattern(slot);
  const row = li.querySelector(".ai-row");
  if (answer.includes("?")) { toast("Fyll i hela ordet först"); return; }
  row.innerHTML = `<span class="slot-meta">Frågar AI …</span>`;
  try {
    const res = await fetch("api/clues", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ answer, difficulty: $("difficulty").value, count: 4, context: $("title").value }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "AI-fel");
    row.innerHTML = "";
    if (!data.clues.length) row.innerHTML = `<span class="slot-meta">Inga användbara förslag.</span>`;
    for (const clue of data.clues) {
      const b = document.createElement("button");
      b.className = "small ai-pick";
      b.textContent = clue;
      b.onclick = () => {
        const ta = li.querySelector("textarea");
        ta.value = clue;
        S.clues[key] = clue;
        row.innerHTML = "";
        scheduleSave();
      };
      row.appendChild(b);
    }
  } catch (e) {
    row.innerHTML = "";
    toast(e.message, true);
  }
}

// ------------------------------------------------------------------ spara/öppna
let saveTimer = null;
function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(serialize())); } catch (_) { /* privat läge */ }
  }, 300);
}

function serialize() {
  computeSlots();
  return {
    format: "korsord/1",
    title: $("title").value,
    rows: S.rows,
    cols: S.cols,
    grid: gridForApi(),
    auto: S.cells.map((x) => (x.auto ? 1 : 0)),
    entries: slots.map((s) => ({
      num: s.num, direction: s.dir, row: s.row, col: s.col,
      answer: slotPattern(s), clue: S.clues[s.key] || "",
    })),
  };
}

function load(data) {
  if (!data || !Array.isArray(data.grid)) throw new Error("Okänt filformat");
  const rows = data.grid.length, cols = data.grid[0].length;
  S = newPuzzle(rows, cols);
  S.title = data.title || "Mitt korsord";
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const v = data.grid[r][c] || "";
      const x = cell(r, c);
      x.b = v === "#";
      x.ch = x.b ? "" : v;
      x.auto = !!(data.auto && data.auto[idx(r, c)]);
    }
  }
  for (const e of data.entries || []) if (e.clue) S.clues[`${e.row},${e.col},${e.direction}`] = e.clue;
  $("title").value = S.title;
  $("rows").value = rows;
  $("cols").value = cols;
  cur = { r: 0, c: 0, dir: ACROSS };
  lastSlotSignature = "";
  render();
}

$("btn-save").onclick = () => {
  const blob = new Blob([JSON.stringify(serialize(), null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  const name = ($("title").value || "korsord").trim().replace(/[^\wåäöÅÄÖ-]+/g, "-").toLowerCase();
  a.href = URL.createObjectURL(blob);
  a.download = `${name || "korsord"}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};

$("file-open").onchange = async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  try { load(JSON.parse(await f.text())); toast("Korsordet öppnat"); }
  catch (err) { toast("Kunde inte öppna filen: " + err.message, true); }
  e.target.value = "";
};

// ------------------------------------------------------------------ utskrift
function buildPrint() {
  computeSlots();
  const esc = (s) => s.replace(/[&<>"]/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));
  let html = `<h1 class="print-title">${esc($("title").value)}</h1>`;

  // Rutnätet ritas som SVG: fyllda ytor i SVG skrivs alltid ut, till skillnad
  // från CSS-bakgrunder som webbläsare hoppar över om inte "skriv ut bakgrunder" är på.
  const U = 10; // en ruta = 10 enheter
  const cellMm = Math.min(13, 174 / S.cols, 150 / S.rows);
  const w = S.cols * U, h = S.rows * U;
  let svg = `<svg class="print-grid" xmlns="http://www.w3.org/2000/svg" viewBox="-0.5 -0.5 ${w + 1} ${h + 1}" ` +
    `style="width:${(S.cols * cellMm).toFixed(1)}mm;height:${(S.rows * cellMm).toFixed(1)}mm">`;
  for (let r = 0; r < S.rows; r++) {
    for (let c = 0; c < S.cols; c++) {
      const x = cell(r, c);
      svg += `<rect x="${c * U}" y="${r * U}" width="${U}" height="${U}" fill="${x.b ? "#000" : "#fff"}" stroke="#000" stroke-width="0.35"/>`;
      const n = numbers.get(idx(r, c));
      if (n && !x.b) svg += `<text x="${c * U + 0.7}" y="${r * U + 2.9}" font-size="2.7" font-family="Helvetica, Arial, sans-serif">${n}</text>`;
    }
  }
  svg += `<rect x="0" y="0" width="${w}" height="${h}" fill="none" stroke="#000" stroke-width="1"/></svg>`;
  html += svg;

  html += `<div class="print-clues">`;
  for (const [dir, label] of [[ACROSS, "Vågrätt"], [DOWN, "Lodrätt"]]) {
    html += `<section><h3>${label}</h3><ol>`;
    for (const s of slots.filter((x) => x.dir === dir)) {
      const clue = S.clues[s.key] ? esc(S.clues[s.key]) : `<span class="missing">…</span>`;
      html += `<li><b>${s.num}</b><span>${clue} (${s.cells.length})</span></li>`;
    }
    html += `</ol></section>`;
  }
  html += `</div>`;
  if (/saldo|words\.tsv/i.test(wordlistSource)) html += `<p class="print-credit">Ordlista: SALDO, Språkbanken Text (CC BY 4.0)</p>`;
  $("print").innerHTML = html;
}
window.addEventListener("beforeprint", buildPrint);
$("btn-print").onclick = () => { buildPrint(); window.print(); };

// ------------------------------------------------------------------ status
let statusTimer = null;
async function loadStatus() {
  const el = $("status");
  try {
    const res = await fetch("api/status");
    const st = await res.json();
    const wl = st.wordlist;
    wordlistSource = wl.source;
    let txt = `${wl.count.toLocaleString("sv-SE")} ord (${wl.source})`;
    if (wl.fetch_status === "pågår") txt += " · hämtar SALDO …";
    if (wl.fetch_status === "misslyckades") txt += " · SALDO-hämtning misslyckades";
    txt += st.ai.enabled ? ` · AI: ${st.ai.provider}` : " · AI av";
    el.textContent = txt;
    if (wl.source === "exempellista" && wl.fetch_status !== "pågår") {
      const b = document.createElement("button");
      b.className = "small";
      b.textContent = "Hämta SALDO";
      b.title = "Ladda ner Språkbankens fria ordlista (ca 70 MB) och bygg om ordindexet";
      b.onclick = async () => { await fetch("api/wordlist/fetch", { method: "POST" }); loadStatus(); };
      el.appendChild(b);
    }
    if (wl.fetch_error) el.title = wl.fetch_error;
    clearTimeout(statusTimer);
    if (wl.fetch_status === "pågår") statusTimer = setTimeout(loadStatus, 5000);
  } catch (_) {
    el.textContent = "Servern svarar inte";
  }
}

let toastTimer = null;
function toast(msg, error = false) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.toggle("error", error);
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 3500);
}

// ------------------------------------------------------------------ start
(function init() {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"); } catch (_) { saved = null; }
  if (saved) {
    try { load(saved); } catch (_) { S = newPuzzle(9, 9); render(); }
  } else {
    // Ett litet startmönster så att man ser hur det fungerar.
    S = newPuzzle(9, 9);
    for (const [r, c] of [[0, 4], [1, 4], [2, 0], [2, 1], [4, 3], [4, 5], [3, 8], [4, 4]]) {
      cell(r, c).b = true;
      cell(8 - r, 8 - c).b = true;
    }
    render();
  }
  loadStatus();
  window.addEventListener("resize", () => render());
  board.focus();
})();
