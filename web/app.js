/* MacroLens front end — vanilla JS, no framework, no build step.
   Renders the belief strip and measured gauges, and wires up the interactive
   layer: batch analyze, editable log, goals, insights, compare, dark mode. */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const state = {
  view: "analyze",
  mode: "single",          // single | batch
  file: null,
  result: null,            // { predictions, best, confident, threshold, macros }
  macros: null,            // recomputed on portion change
  dish: null,
  portion: 1.0,
  dishes: [],
  corrected: false,
  batch: [],               // [{ file, url, status, result }]
  log: [],                 // meal rows from /api/patterns
  goal: null,
  rangeDays: 14,
  settings: { theme: "light" },
};

const MACRO_META = {
  kcal:      { key: "Calories", unit: "kcal", ref: 800 },
  protein_g: { key: "Protein",  unit: "g",    ref: 60 },
  carbs_g:   { key: "Carbs",    unit: "g",    ref: 100 },
  fat_g:     { key: "Fat",      unit: "g",    ref: 50 },
};

/* ── helpers ─────────────────────────────────────────────────────────── */
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const title = (s) => String(s ?? "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

function toast(msg, kind) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = "toast" + (kind ? ` toast--${kind}` : "");
  el.classList.add("is-on");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("is-on"), 2600);
}

/* ── theme ───────────────────────────────────────────────────────────── */
function applyTheme(theme) {
  state.settings.theme = theme;
  document.body.dataset.theme = theme;
  try { localStorage.setItem("ml-theme", theme); } catch { /* ignore */ }
}

function toggleTheme() {
  const next = state.settings.theme === "dark" ? "light" : "dark";
  applyTheme(next);
  api("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ theme: next }),
  }).catch(() => { /* cache is enough */ });
  toast(`${next === "dark" ? "Dark" : "Light"} mode`);
}

/* ── routing ─────────────────────────────────────────────────────────── */
function setView(view) {
  state.view = view;
  $$(".nav__item").forEach((b) => {
    if (b.dataset.nav === view) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  $$(".view").forEach((s) => (s.hidden = s.dataset.view !== view));
  document.body.dataset.view = view;
  if (history.replaceState) history.replaceState(null, "", `#${view}`);
  else location.hash = view;
  if (view === "patterns") loadPatterns();
  if (view === "method") loadAccuracy();
  if (view === "compare") loadCompare();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ── status ──────────────────────────────────────────────────────────── */
async function pollStatus() {
  try {
    const h = await api("/api/health");
    const dot = $(".status__dot");
    const txt = $(".status__text");
    if (h.model_ready) {
      dot.className = "status__dot status__dot--ok";
      txt.textContent = "model ready";
    } else if (h.model_error) {
      dot.className = "status__dot";
      txt.textContent = "model offline";
    } else {
      dot.className = "status__dot status__dot--load";
      txt.textContent = "loading";
      setTimeout(pollStatus, 2500);
    }
  } catch { setTimeout(pollStatus, 4000); }
}

/* ═══════════════════════════════ ANALYZE ═══════════════════════════════ */
function showFile(file) {
  state.file = file;
  state.corrected = false;
  const img = $("#plateImg");
  img.src = URL.createObjectURL(file);
  img.hidden = false;
  $("#plateEmpty").hidden = true;
  $("#plateCaption").hidden = false;
  $("#plateFile").textContent = file.name || "camera";
  renderScanning();
  runAnalyze(file);
}

function renderScanning() {
  $("#readoutIdle").hidden = true;
  const live = $("#readoutLive");
  live.hidden = false;
  live.innerHTML = `
    <div class="scanning">
      <div class="scanning__line scanning__line--lg"></div>
      <div class="scanning__line scanning__line--sm"></div>
      <div class="scanning__line"></div>
      <div class="scanning__line"></div>
    </div>`;
}

async function runAnalyze(file) {
  const fd = new FormData();
  fd.append("file", file);
  try {
    const data = await api("/api/analyze", { method: "POST", body: fd });
    state.result = data;
    state.dish = data.best.label;
    state.portion = 1.0;
    state.macros = data.macros;
    renderResult();
  } catch (err) {
    $("#readoutLive").innerHTML =
      `<div class="label__unknown"><strong>That photo did not load.</strong><br>${esc(err.message)} Try another image.</div>`;
  }
}

/* ── belief strip + gauges ───────────────────────────────────────────── */
function beliefStrip(predictions) {
  const max = Math.max(...predictions.map((p) => p.score), 0.0001);
  const bars = predictions
    .map((p, i) => {
      const h = Math.max(6, (p.score / max) * 100);
      const cls = i === 0 ? "belief__bar--top" : "belief__bar--alt";
      return `<div class="belief__bar ${cls}" title="${esc(p.display)} — ${(p.score * 100).toFixed(1)}%">
                <div class="belief__fill" style="height:${h}%"></div>
              </div>`;
    })
    .join("");
  const legend = predictions
    .map((p, i) =>
      i === 0
        ? `<span class="belief__item"><span class="belief__swatch" style="background:var(--olive)"></span>${esc(title(p.label))} ${(p.score * 100).toFixed(0)}%</span>`
        : i < 3
        ? `<span class="belief__item belief__item--muted">${esc(title(p.label))} ${(p.score * 100).toFixed(0)}%</span>`
        : ""
    )
    .join("");
  return `<div class="belief">
      <div class="belief__head">
        <span class="belief__label">Model's belief — all 101 dishes</span>
        <span class="belief__label">top 5 shown</span>
      </div>
      <div class="belief__bare">${bars}</div>
      <div class="belief__legend">${legend}</div>
    </div>`;
}

function gauge(k, meta, m) {
  const v = m.values[k];
  const band = m.ranges[k];
  if (v == null) return "";
  const ref = meta.ref;
  let valHtml = `<b>${Math.round(v)}</b> <small>${meta.unit}</small>`;
  let gaugeHtml;
  if (band) {
    valHtml = `<b>${Math.round(band[0])}–${Math.round(band[1])}</b> <small>${meta.unit}</small>`;
    const lo = clamp((band[0] / ref) * 100, 0, 100);
    const hi = clamp((band[1] / ref) * 100, 0, 100);
    const mid = clamp((v / ref) * 100, 0, 100);
    gaugeHtml = `<div class="gauge__track">
        <div class="gauge__band" style="left:${lo}%;right:${100 - hi}%"></div>
        <div class="gauge__needle" style="left:${mid}%"></div>
      </div>`;
  } else {
    const pct = clamp((v / ref) * 100, 2, 100);
    gaugeHtml = `<div class="gauge__track"><div class="gauge__band" style="left:0;right:${100 - pct}%"></div></div>`;
  }
  return `<div class="label__row">
      <span class="label__key">${meta.key}</span>
      <span class="label__fig">
        <span class="gauge" role="img" aria-label="${meta.key}${band ? ` between ${Math.round(band[0])} and ${Math.round(band[1])}` : ` ${Math.round(v)}`} ${meta.unit}">${gaugeHtml}</span>
        <span class="label__val">${valHtml}</span>
      </span>
    </div>`;
}

function renderLabel() {
  const m = state.macros;
  const mount = $("#labelMount");
  if (!mount) return;
  if (!m || !m.known) {
    mount.innerHTML = `<div class="label__unknown">
        <strong>No nutrition data for this dish yet.</strong><br>
        It will still be logged, but left out of calorie totals until it is added to the table.
      </div>`;
    return;
  }
  const rows = Object.entries(MACRO_META).map(([k, meta]) => gauge(k, meta, m)).join("");
  mount.innerHTML = `<div class="label">${rows}</div>
    <p class="label__note">${esc(m.note)}</p>`;
}

function renderResult() {
  const { predictions, best, confident } = state.result;
  const live = $("#readoutLive");
  live.hidden = false;
  $("#readoutIdle").hidden = true;

  const verdict = confident
    ? `<div class="verdict verdict--ok"><span class="verdict__dot"></span>
         <span class="verdict__text">Confident match</span>
         <span class="verdict__conf">${(best.score * 100).toFixed(0)}% sure</span></div>`
    : `<div class="verdict verdict--doubt"><span class="verdict__dot"></span>
         <span class="verdict__text">Not sure — your call</span>
         <span class="verdict__conf">${(best.score * 100).toFixed(0)}% sure</span></div>`;

  live.innerHTML = `
    ${verdict}
    <div class="dish">
      <div class="dish__name" id="dishName">${esc(title(state.dish))}</div>
      <div class="dish__row">
        <span class="dish__sub">${state.result.macros.known ? "in nutrition table" : "no nutrition data"}</span>
        <button class="dish__change" id="changeDish">wrong? change dish</button>
      </div>
    </div>
    ${beliefStrip(predictions)}
    <div id="labelMount"></div>
    <div id="portionMount"></div>
    <div class="actions">
      <button class="btn btn--primary" id="logBtn">Log this meal</button>
      <button class="btn btn--ghost" id="resetBtn">New photo</button>
    </div>`;

  renderLabel();
  renderPortion();
  $("#changeDish").onclick = openDishPicker;
  $("#logBtn").onclick = logMeal;
  $("#resetBtn").onclick = resetPlate;
}

function renderPortion() {
  const mount = $("#portionMount");
  if (!mount) return;
  mount.innerHTML = `
    <div class="portion">
      <div class="portion__head">
        <span class="portion__label">Portion you actually ate</span>
        <span class="portion__value" id="portionVal">${state.portion.toFixed(2)}×</span>
      </div>
      <input type="range" id="portionRange" min="0.5" max="2" step="0.25" value="${state.portion}" aria-label="Portion multiplier" />
      <div class="portion__scale"><span>½ plate</span><span>standard</span><span>2×</span></div>
      <p class="portion__hint">A photo can't weigh food. Set it here, and every figure above re-computes as a range.</p>
    </div>`;
  const range = $("#portionRange");
  range.oninput = async () => {
    state.portion = parseFloat(range.value);
    $("#portionVal").textContent = `${state.portion.toFixed(2)}×`;
    try {
      const data = await api("/api/estimate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dish: state.dish, portion: state.portion }),
      });
      state.macros = data.macros;
      renderLabel();
    } catch { /* keep last known */ }
  };
}

function openDishPicker() {
  const current = state.dish;
  const options = state.dishes
    .map((d) => `<option value="${d}" ${d === current ? "selected" : ""}>${esc(title(d))}</option>`)
    .join("");
  const nameEl = $("#dishName");
  nameEl.outerHTML = `<select class="cmp-select" id="dishSelect" style="width:100%;font-family:var(--font-display);font-size:1.25rem">${options}</select>`;
  const sel = $("#dishSelect");
  sel.focus();
  const commit = async () => {
    state.dish = sel.value;
    state.corrected = true;
    const data = await api("/api/estimate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dish: state.dish, portion: state.portion }),
    });
    state.macros = data.macros;
    renderResult();
  };
  sel.onchange = commit;
  sel.onblur = () => { if ($("#dishSelect")) renderResult(); };
}

async function logMeal() {
  if (!state.result) return;
  try {
    await api("/api/log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dish: state.dish,
        display: title(state.dish),
        confidence: state.result.best.score,
        portion: state.portion,
        corrected: state.corrected,
      }),
    });
    toast(`Logged ${title(state.dish)}`);
  } catch {
    toast("Could not log that", "doubt");
  }
}

function resetPlate() {
  state.file = null;
  state.result = null;
  state.macros = null;
  state.corrected = false;
  const img = $("#plateImg");
  img.hidden = true;
  img.removeAttribute("src");
  $("#plateEmpty").hidden = false;
  $("#plateCaption").hidden = true;
  $("#readoutLive").hidden = true;
  $("#readoutLive").innerHTML = "";
  $("#readoutIdle").hidden = false;
}

/* ═══════════════════════════════ BATCH ═════════════════════════════════ */
function setMode(mode) {
  state.mode = mode;
  $$(".modeswitch__btn").forEach((b) => {
    const on = b.dataset.mode === mode;
    b.classList.toggle("is-on", on);
    b.setAttribute("aria-pressed", String(on));
  });
  // The plate stays visible in both modes: in batch it becomes a many-file
  // drop zone (drag a folder straight onto it), alongside the picker.
  $("#platePrompt").textContent = mode === "batch" ? "Drop meal photos" : "Drop a meal photo";
  $("#plateHint").innerHTML =
    mode === "batch" ? "or <u>browse files</u> · pick several at once" : "or <u>browse files</u> · JPG, PNG, WebP";
  $("#samples").hidden = mode === "batch" || !$("#samplesRow").children.length;
  if (mode === "single") {
    if (!state.result) { $("#readoutLive").hidden = true; $("#readoutIdle").hidden = false; }
    else renderResult();
  } else {
    renderBatch();
  }
}

function addBatchFiles(files) {
  for (const f of files) {
    state.batch.push({ file: f, url: URL.createObjectURL(f), status: "queued", result: null });
  }
  renderBatch();
  runBatch();
}

function renderBatch() {
  const live = $("#readoutLive");
  $("#readoutIdle").hidden = true;
  live.hidden = false;

  if (!state.batch.length) {
    live.innerHTML = `
      <div class="batch">
        <div class="batch__head">
          <span class="batch__title">Batch</span>
          <span class="batch__count">nothing queued</span>
        </div>
        <p class="portion__hint" style="margin:0">Switch to the plate and drop several photos at once — the whole folder is scored in one pass, and every low-confidence guess is flagged for you.</p>
        <button class="btn btn--primary" id="batchPick">Choose photos</button>
      </div>`;
    $("#batchPick").onclick = () => pickFiles(true);
    return;
  }

  const rows = state.batch.map((it, i) => {
    let meta;
    if (it.status === "queued") {
      meta = `<div class="batch__dish"><span class="mini-bar" style="display:inline-block;width:90px"></span></div><div class="batch__name">queued…</div>`;
    } else if (it.status === "error") {
      meta = `<div class="batch__dish">Unreadable</div><div class="batch__name">${esc(it.file.name)}</div>`;
    } else {
      const r = it.result;
      const confCls = r.confident ? "batch__conf--ok" : "batch__conf--doubt";
      meta = `<div class="batch__dish">${esc(title(r.best.label))}</div>
              <div class="batch__name">${esc(it.file.name)}</div>`;
    }
    const right =
      it.status === "done"
        ? `<div style="text-align:right">
             <div class="batch__conf ${it.result.confident ? "batch__conf--ok" : "batch__conf--doubt"}">${(it.result.best.score * 100).toFixed(0)}%</div>
             ${it.result.confident ? "" : '<div class="batch__flag">check</div>'}
           </div>`
        : it.status === "queued" ? `<div class="batch__conf">…</div>` : "";
    return `<div class="batch__row">
        <img class="batch__thumb" src="${it.url}" alt="" />
        <div class="batch__meta">${meta}</div>
        ${right}
      </div>`;
  }).join("");

  const done = state.batch.filter((b) => b.status === "done");
  const flagged = done.filter((b) => !b.result.confident).length;
  const totalKcal = done.reduce((acc, b) => acc + (b.result.macros.values.kcal || 0), 0);

  live.innerHTML = `
    <div class="batch">
      <div class="batch__head">
        <span class="batch__title">Batch</span>
        <span class="batch__count">${done.length} / ${state.batch.length} scored</span>
      </div>
      <div class="batch__list">${rows}</div>
      ${done.length ? `
      <div class="batch__killsum">
        <span class="batch__kill"><b>${done.length}</b> meal${done.length === 1 ? "" : "s"}</span>
        <span class="batch__kill"><b>${flagged}</b> need${flagged === 1 ? "s" : ""} a look</span>
        <span class="batch__kill"><b>${Math.round(totalKcal)}</b> kcal total</span>
      </div>
      <div class="actions" style="padding:0">
        <button class="btn btn--primary" id="batchLog">Log all ${done.length}</button>
        <button class="btn btn--ghost" id="batchClear">Clear</button>
      </div>` : ""}
    </div>`;

  if ($("#batchLog")) {
    $("#batchLog").onclick = async () => {
      let n = 0;
      for (const it of done) {
        try {
          await api("/api/log", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              dish: it.result.best.label,
              display: title(it.result.best.label),
              confidence: it.result.best.score,
              portion: 1.0,
              corrected: false,
            }),
          });
          n++;
        } catch { /* skip */ }
      }
      toast(`Logged ${n} meals`);
    };
    $("#batchClear").onclick = () => { state.batch = []; renderBatch(); };
  }
}

async function runBatch() {
  const queued = state.batch.filter((b) => b.status === "queued");
  if (!queued.length) return;
  const fd = new FormData();
  queued.forEach((b) => fd.append("files", b.file));
  try {
    const data = await api("/api/analyze-batch", { method: "POST", body: fd });
    data.results.forEach((r, i) => {
      const item = queued[i];
      if (!item) return;
      if (r.ok) { item.status = "done"; item.result = r; }
      else { item.status = "error"; }
    });
  } catch {
    queued.forEach((b) => (b.status = "error"));
  }
  renderBatch();
}

/* ═══════════════════════════════ PATTERNS ══════════════════════════════ */
async function loadPatterns() {
  const body = $("#patternsBody");
  let data;
  try { data = await api(`/api/patterns?days=${state.rangeDays}`); }
  catch { body.innerHTML = `<div class="patterns"><div class="empty"><div class="empty__title">Could not load your log.</div></div></div>`; return; }

  state.log = data.meals || [];
  state.goal = data.goal;

  const s = data.summary;
  if (!s.meals) {
    body.innerHTML = `<div class="patterns">
        <div class="empty">
          <div class="empty__title">Nothing logged yet</div>
          <div class="empty__body">Analyze a meal and hit “Log this meal” — your patterns appear here.</div>
          <button class="btn btn--primary" id="toAnalyze">Analyze a meal</button>
        </div>
      </div>`;
    $("#toAnalyze").onclick = () => setView("analyze");
    return;
  }

  const stats = `<div class="stat-grid">
      ${statCell("Meals logged", s.meals)}
      ${statCell("Avg calories", Math.round(s.avg_kcal), "per meal")}
      ${statCell("Avg confidence", Math.round(s.avg_confidence * 100) + "%")}
      ${statCell("You corrected the model", s.corrections, s.corrections === 1 ? "time" : "times")}
    </div>`;

  // goal card
  const gp = data.goalProgress;
  const goalCard = `<div class="panel" style="margin-top:18px">
      <div class="panel__title">Daily goal</div>
      <div class="panel__sub">${gp ? "Recent days against your target" : "Set a target to track it"}</div>
      ${gp ? goalRing(gp) : `<p class="portion__hint" style="margin:0 0 12px">No goal set yet. 2000 kcal is a common starting point.</p>`}
      <div class="goal__editor">
        <label class="eyebrow" for="goalInput">Daily kcal</label>
        <input class="goal__input" id="goalInput" type="number" min="800" max="6000" step="50" value="${data.goal || 2000}" />
        <button class="btn btn--ghost" id="goalSave" style="padding:8px 14px">${gp ? "Update" : "Set goal"}</button>
        ${gp ? '<button class="btn btn--ghost" id="goalClear" style="padding:8px 14px">Clear</button>' : ""}
      </div>
    </div>`;

  // insights
  const insights = data.insights && data.insights.length
    ? `<div class="panel" style="margin-top:18px">
         <div class="panel__title">What your log says</div>
         <div class="panel__sub">Computed from your rows, not guesses</div>
         <div class="insights">${data.insights.map(insightCard).join("")}</div>
       </div>`
    : "";

  // daily bar chart
  const daily = data.daily || [];
  const maxKcal = Math.max(...daily.map((d) => d.kcal || 0), 1);
  const bars = daily.map((d) => {
    const h = Math.max(4, ((d.kcal || 0) / maxKcal) * 100);
    const day = new Date(d.day).toLocaleDateString(undefined, { day: "numeric" });
    return `<div class="bars__col" title="${d.day}: ${Math.round(d.kcal)} kcal">
              <span class="bars__val">${Math.round(d.kcal)}</span>
              <div class="bars__bar" style="height:${h}%"></div>
              <span class="bars__lab">${day}</span>
            </div>`;
  }).join("");
  const dailyPanel = `<div class="panel">
      <div class="panel__title">Calories per day</div>
      <div class="panel__sub">Last ${state.rangeDays} days · summed from your log</div>
      <div class="bars">${bars || '<span class="bars__lab">no recent meals</span>'}</div>
    </div>`;

  // weekday split
  const wd = data.weekday || [];
  const wMax = Math.max(...wd.map((d) => d.avg_kcal), 1);
  const wdBars = wd.map((d) => {
    const h = Math.max(3, (d.avg_kcal / wMax) * 100);
    const weekend = ["Sat", "Sun"].includes(d.dow);
    return `<div class="bars__col" title="${d.dow}: ${d.avg_kcal} kcal avg over ${d.days} days">
              <span class="bars__val">${d.avg_kcal || ""}</span>
              <div class="bars__bar ${weekend ? "" : "bars__bar--soft"}" style="height:${h}%"></div>
              <span class="bars__lab">${d.dow}</span>
            </div>`;
  }).join("");
  const weekdayPanel = `<div class="panel">
      <div class="panel__title">Average by weekday</div>
      <div class="panel__sub">Weekends highlighted · avg kcal/day</div>
      <div class="bars">${wdBars}</div>
    </div>`;

  // macro split
  const split = data.macroSplit;
  const totalG = (split.protein_g + split.carbs_g + split.fat_g) || 1;
  const macroPanel = `<div class="panel">
      <div class="panel__title">Macro split</div>
      <div class="panel__sub">Total grams across your log</div>
      <div class="macro">
        ${macroRow("Protein", split.protein_g, totalG, "p")}
        ${macroRow("Carbs", split.carbs_g, totalG, "c")}
        ${macroRow("Fat", split.fat_g, totalG, "f")}
      </div>
    </div>`;

  // most-logged dishes
  const topRows = data.topDishes.map((d, i) => `<div class="dish-row">
      <span class="dish-row__rank">${String(i + 1).padStart(2, "0")}</span>
      <span class="dish-row__name">${esc(d.display)}</span>
      <span class="dish-row__count">${d.count}×</span>
      <span class="dish-row__kcal">≈ ${Math.round(d.avg_kcal)} kcal</span>
    </div>`).join("");

  body.innerHTML = `<div class="patterns">
      <div style="display:flex;justify-content:flex-end;margin-bottom:14px;gap:10px;align-items:center;flex-wrap:wrap">
        <a class="btn btn--ghost" style="padding:8px 14px;text-decoration:none" href="/api/export.csv" download>Export CSV</a>
        <div class="rangepick" role="group" aria-label="Chart range">
          ${[7, 14, 30].map((d) => `<button class="rangepick__btn ${d === state.rangeDays ? "is-on" : ""}" data-days="${d}">${d}d</button>`).join("")}
        </div>
      </div>
      ${stats}
      ${goalCard}
      ${insights}
      <div class="panels">${dailyPanel}${macroPanel}</div>
      <div class="panels">${weekdayPanel}<div class="panel">
        <div class="panel__title">Most-logged dishes</div>
        <div class="panel__sub">Ranked by frequency</div>${topRows}
      </div></div>
      <div class="panel" style="margin-top:18px">
        <div class="panel__title">Your log</div>
        <div class="panel__sub">Edit a portion or remove a row · changes save automatically</div>
        ${logTable(state.log)}
      </div>
    </div>`;

  wirePatterns();
}

function statCell(key, val, suffix) {
  return `<div class="stat"><div class="stat__key">${key}</div>
    <div class="stat__val">${val}${suffix ? ` <small>${suffix}</small>` : ""}</div></div>`;
}

function macroRow(name, g, total, kind) {
  const pct = Math.round((g / total) * 100);
  return `<div class="macro__item">
      <span class="macro__name">${name}</span>
      <div class="macro__track"><div class="macro__fill macro__fill--${kind}" style="width:${pct}%"></div></div>
      <span class="macro__g">${Math.round(g)} g</span>
    </div>`;
}

function insightCard(f) {
  return `<div class="insight insight--${f.kind}">
      <div class="insight__title">${esc(f.title)}</div>
      <div class="insight__detail">${esc(f.detail)}</div>
    </div>`;
}

function goalRing(gp) {
  const r = 56, c = 2 * Math.PI * r;
  const pct = gp.days_logged ? gp.days_on_target / gp.days_logged : 0;
  const off = c * (1 - clamp(pct, 0, 1));
  return `<div class="goal">
      <div class="goal__ring">
        <svg viewBox="0 0 132 132" role="img" aria-label="${Math.round(pct * 100)}% of days on target">
          <circle class="goal__track" cx="66" cy="66" r="${r}"/>
          <circle class="goal__arc" cx="66" cy="66" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="${off}"/>
        </svg>
        <div class="goal__center">
          <div class="goal__pct">${gp.days_on_target}<span style="font-size:1rem;color:var(--mute)">/${gp.days_logged}</span></div>
          <div class="goal__cap">on target</div>
        </div>
      </div>
      <div class="goal__info">
        <div class="goal__nums">Goal <b>${Math.round(gp.goal)} kcal</b> · band <b>${gp.band_low}–${gp.band_high}</b></div>
        <div class="goal__nums" style="margin-top:6px">Recent average <b>${Math.round(gp.avg_kcal)} kcal</b> across ${gp.days_logged} logged days.</div>
      </div>
    </div>`;
}

function logTable(meals) {
  if (!meals.length) return `<p class="portion__hint">No rows yet.</p>`;
  const rows = meals.slice().reverse().slice(0, 60).map((m) => {
    const when = m.logged_at ? new Date(m.logged_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "—";
    return `<tr data-id="${m.id}">
        <td class="lt-mono">${when}</td>
        <td class="lt-dish">${esc(m.display)}</td>
        <td class="lt-mono">${m.kcal != null ? Math.round(m.kcal) : "—"}</td>
        <td class="lt-mono lt-right">${m.portion != null ? m.portion.toFixed(2) + "×" : "—"}</td>
        <td class="lt-mono lt-right">${Math.round((m.confidence || 0) * 100)}%</td>
        <td class="lt-actions">
          <span class="row-actions">
            <button class="row-btn" data-edit="${m.id}">edit</button>
            <button class="row-btn row-btn--del" data-del="${m.id}">remove</button>
          </span>
        </td>
      </tr>`;
  }).join("");
  return `<table class="logtable">
      <thead><tr><th>When</th><th>Dish</th><th>kcal</th><th class="lt-right">Portion</th><th class="lt-right">Conf.</th><th class="lt-right">Actions</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function wirePatterns() {
  $$(".rangepick__btn").forEach((b) => (b.onclick = () => {
    state.rangeDays = parseInt(b.dataset.days, 10);
    loadPatterns();
  }));

  const goalSave = $("#goalSave");
  if (goalSave) goalSave.onclick = async () => {
    const v = parseFloat($("#goalInput").value);
    if (!v || v <= 0) return;
    await api("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ daily_goal: v }) });
    toast(`Goal set to ${Math.round(v)} kcal`);
    loadPatterns();
  };
  const goalClear = $("#goalClear");
  if (goalClear) goalClear.onclick = async () => {
    await api("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ daily_goal: 0 }) });
    toast("Goal cleared");
    loadPatterns();
  };

  $$("[data-del]").forEach((b) => (b.onclick = async () => {
    try {
      await api(`/api/log/${b.dataset.del}`, { method: "DELETE" });
      toast("Row removed");
      loadPatterns();
    } catch { toast("Could not remove", "doubt"); }
  }));

  $$("[data-edit]").forEach((b) => (b.onclick = () => {
    const id = b.dataset.edit;
    const tr = b.closest("tr");
    const meal = state.log.find((m) => String(m.id) === String(id));
    const cell = tr.children[3];
    cell.innerHTML = `<span class="portion-inline">
        <input type="range" min="0.5" max="2" step="0.25" value="${meal.portion || 1}" data-range="${id}" aria-label="Portion" />
        <b class="lt-mono" data-pv="${id}">${(meal.portion || 1).toFixed(2)}×</b>
      </span>`;
    b.textContent = "save";
    b.onclick = async () => {
      const val = parseFloat($(`[data-range="${id}"]`).value);
      try {
        const res = await api(`/api/log/${id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ portion: val }),
        });
        toast(`Updated to ${(res.macros.values.kcal != null) ? Math.round(res.macros.values.kcal) + " kcal" : "saved"}`);
        loadPatterns();
      } catch { toast("Could not update", "doubt"); }
    };
    const range = $(`[data-range="${id}"]`);
    range.oninput = () => { $(`[data-pv="${id}"]`).textContent = `${parseFloat(range.value).toFixed(2)}×`; };
  }));
}

/* ═══════════════════════════════ COMPARE ═══════════════════════════════ */
async function loadCompare() {
  const body = $("#compareBody");
  if (!state.dishes.length) {
    try { state.dishes = (await api("/api/dishes")).dishes; } catch { /* ignore */ }
  }
  const opts = state.dishes.map((d) => `<option value="${d}">${esc(title(d))}</option>`).join("");
  const a = state.dishes.includes("pizza") ? "pizza" : state.dishes[0];
  const b = state.dishes.includes("caesar_salad") ? "caesar_salad" : state.dishes[1];
  body.innerHTML = `
    <div class="compare">
      <div class="cmp-pickers">
        <div class="cmp-field"><label for="cmpA">Dish A</label>
          <select class="cmp-select" id="cmpA">${opts}</select></div>
        <div class="cmp-field"><label for="cmpAP">Portion</label>
          <input class="cmp-num" id="cmpAP" type="number" min="0.25" max="4" step="0.25" value="1" /></div>
        <div class="cmp-vs">vs</div>
        <div class="cmp-field"><label for="cmpB">Dish B</label>
          <select class="cmp-select" id="cmpB">${opts}</select></div>
        <div class="cmp-field"><label for="cmpBP">Portion</label>
          <input class="cmp-num" id="cmpBP" type="number" min="0.25" max="4" step="0.25" value="1" /></div>
      </div>
      <div id="cmpOut"></div>
    </div>`;
  $("#cmpA").value = a;
  $("#cmpB").value = b;
  ["cmpA", "cmpB", "cmpAP", "cmpBP"].forEach((id) => {
    const el = $("#" + id);
    el.onchange = runCompare;
    if (el.type === "number") el.oninput = debounce(runCompare, 350);
  });
  runCompare();
}

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

async function runCompare() {
  const out = $("#cmpOut");
  if (!out) return;
  const body = {
    dish_a: $("#cmpA").value, dish_b: $("#cmpB").value,
    portion_a: parseFloat($("#cmpAP").value) || 1,
    portion_b: parseFloat($("#cmpBP").value) || 1,
  };
  let data;
  try { data = await api("/api/compare", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); }
  catch { out.innerHTML = `<div class="empty"><div class="empty__title">Could not compare those.</div></div>`; return; }

  const A = data.a.macros.values, B = data.b.macros.values;
  const lowerIsBetter = ["kcal", "carbs_g", "fat_g"];
  const metrics = Object.entries(MACRO_META).map(([k, meta]) => {
    const av = A[k], bv = B[k];
    const aBetter = av != null && bv != null && (lowerIsBetter.includes(k) ? av < bv : av > bv);
    return `<div class="cmp-metric ${aBetter ? "is-better" : "is-worse"}">
        <span class="cmp-metric__k">${meta.key}</span>
        <span class="cmp-metric__v">${fmtMacro(A, k, meta)}</span>
      </div>`;
  }).join("");
  const metricsB = Object.entries(MACRO_META).map(([k, meta]) => {
    const av = A[k], bv = B[k];
    const bBetter = av != null && bv != null && (lowerIsBetter.includes(k) ? bv < av : bv > av);
    return `<div class="cmp-metric ${bBetter ? "is-better" : "is-worse"}">
        <span class="cmp-metric__k">${meta.key}</span>
        <span class="cmp-metric__v">${fmtMacro(B, k, meta)}</span>
      </div>`;
  }).join("");

  const kcalA = A.kcal || 0, kcalB = B.kcal || 0;
  const diff = Math.abs(kcalA - kcalB);
  const lighter = kcalA < kcalB ? title(body.dish_a) : title(body.dish_b);
  const heavier = kcalA < kcalB ? title(body.dish_b) : title(body.dish_a);
  const verdict = `<div class="cmp-verdict">
      <div class="cmp-verdict__t">${lighter} is the lighter plate</div>
      <div class="cmp-verdict__d">About ${Math.round(diff)} kcal fewer per serving than ${heavier}${
        diff ? ` — roughly ${(diff / 250).toFixed(1)}× a 250 kcal snack` : ""}. Remember these are ranges, not readings.</div>
    </div>`;

  out.innerHTML = `
    <div class="cmp-grid">
      <div class="cmp-card">
        <div class="cmp-card__dish">${esc(title(body.dish_a))}</div>
        <div class="cmp-card__por">${body.portion_a}× portion</div>
        ${metrics}
      </div>
      <div class="cmp-card">
        <div class="cmp-card__dish">${esc(title(body.dish_b))}</div>
        <div class="cmp-card__por">${body.portion_b}× portion</div>
        ${metricsB}
      </div>
    </div>
    ${verdict}`;
}

function fmtMacro(vals, k, meta) {
  if (vals[k] == null) return "—";
  return `${Math.round(vals[k])} <small>${meta.unit}</small>`;
}

/* ═══════════════════════════════ METHOD ════════════════════════════════ */
async function loadAccuracy() {
  const grid = $("#accuracyGrid");
  const foot = $("#accuracyFoot");
  try {
    const d = await api("/api/accuracy");
    if (!d.available) {
      grid.innerHTML = `<p class="accuracy__foot">No evaluation run yet. Run <code>python -m eval.evaluate --folder eval_set</code> to generate one.</p>`;
      return;
    }
    const pct = (x) => `${(x * 100).toFixed(1)}%`;
    grid.innerHTML = `
      <div class="accuracy__cell"><div class="accuracy__k">Top-1 accuracy</div><div class="accuracy__v accuracy__v--big">${pct(d.top1_accuracy)}</div></div>
      <div class="accuracy__cell"><div class="accuracy__k">Top-3 accuracy</div><div class="accuracy__v">${pct(d.top3_accuracy)}</div></div>
      <div class="accuracy__cell"><div class="accuracy__k">Nutrition coverage</div><div class="accuracy__v">${pct(d.nutrition_coverage)}</div></div>
      <div class="accuracy__cell"><div class="accuracy__k">Latency</div><div class="accuracy__v">${Math.round(d.avg_latency_ms)}<small style="font-size:.8rem;color:var(--mute)"> ms</small></div></div>`;
    foot.textContent = `Model ${d.model} · scored on ${d.evaluated} images (${d.source}). Refusal threshold ${Math.round(d.confidence_threshold * 100)}%.`;
  } catch {
    grid.innerHTML = "";
    foot.textContent = "Could not load benchmark results.";
  }
}

/* ═══════════════════════════════ HELP ══════════════════════════════════ */
function openHelp() { $("#helpSheet").hidden = false; $("[data-close]").focus?.(); }
function closeHelp() { $("#helpSheet").hidden = true; }

function pickFiles(batch) {
  const input = $("#fileInput");
  input.multiple = !!batch;
  input.dataset.batch = batch ? "1" : "";
  input.click();
}

/* ═══════════════════════════════ BOOT ══════════════════════════════════ */
async function boot() {
  // theme: stored override beats server setting
  let theme = "light";
  try { theme = localStorage.getItem("ml-theme") || "light"; } catch { /* ignore */ }
  applyTheme(theme);
  try {
    const s = await api("/api/settings");
    if (!localStorage.getItem("ml-theme") && s.theme) applyTheme(s.theme);
    state.goal = s.daily_goal;
  } catch { /* ignore */ }

  $$(".nav__item").forEach((b) => (b.onclick = () => setView(b.dataset.nav)));
  $(".wordmark").onclick = (e) => { e.preventDefault(); setView("analyze"); };
  $("#themeBtn").onclick = toggleTheme;

  // mode switch
  $$(".modeswitch__btn").forEach((b) => (b.onclick = () => setMode(b.dataset.mode)));

  const plate = $("#plate");
  const input = $("#fileInput");
  plate.onclick = (e) => { if (e.target.closest("button, a, input, select")) return; pickFiles(state.mode === "batch"); };
  $("#plateEmpty").onclick = () => pickFiles(state.mode === "batch");
  input.onchange = () => {
    if (!input.files.length) return;
    if (input.multiple) addBatchFiles(input.files);
    else showFile(input.files[0]);
    input.value = "";
  };

  ["dragenter", "dragover"].forEach((ev) =>
    plate.addEventListener(ev, (e) => { e.preventDefault(); plate.classList.add("is-drag"); }));
  ["dragleave", "drop"].forEach((ev) =>
    plate.addEventListener(ev, (e) => { e.preventDefault(); plate.classList.remove("is-drag"); }));
  plate.addEventListener("drop", (e) => {
    const files = [...(e.dataTransfer?.files || [])];
    if (!files.length) return;
    // Honour the current mode: batch queues even a single drop.
    if (files.length > 1 || state.mode === "batch") {
      setMode("batch");
      addBatchFiles(files);
    } else {
      showFile(files[0]);
    }
  });

  // samples
  try {
    const { samples } = await api("/api/samples");
    if (samples.length) {
      $("#samples").hidden = false;
      $("#samplesRow").innerHTML = samples
        .map((s) => `<button class="sample" data-s="${esc(s)}" title="${esc(s)}"><img src="/samples/${encodeURIComponent(s)}" alt="${esc(s)}" /></button>`)
        .join("");
      $$("#samplesRow .sample").forEach((btn) => (btn.onclick = async () => {
        const res = await fetch(`/samples/${encodeURIComponent(btn.dataset.s)}`);
        const blob = await res.blob();
        showFile(new File([blob], btn.dataset.s, { type: blob.type }));
      }));
    }
  } catch { /* no samples */ }

  try { state.dishes = (await api("/api/dishes")).dishes; } catch { /* ignore */ }

  // keyboard shortcuts
  document.addEventListener("keydown", (e) => {
    const tag = e.target?.tagName;
    if (tag && ["INPUT", "SELECT", "TEXTAREA"].includes(tag)) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const map = { "1": "analyze", "2": "patterns", "3": "compare", "4": "method" };
    if (map[e.key]) { setView(map[e.key]); return; }
    if (e.key === "d" || e.key === "D") { toggleTheme(); return; }
    if (e.key === "/") { e.preventDefault(); pickFiles(state.mode === "batch"); return; }
    if (e.key === "?") { openHelp(); return; }
    if (e.key === "Escape") closeHelp();
  });
  $$("[data-close]").forEach((el) => (el.onclick = closeHelp));

  pollStatus();
  setView(location.hash.replace("#", "") || "analyze");
  if (state.view === "analyze") loadAccuracy();
}

boot();
