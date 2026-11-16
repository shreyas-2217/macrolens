/* MacroLens front end — vanilla JS, no framework.
   Renders the belief strip and range bars, which are the whole point. */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const state = {
  view: "analyze",
  file: null,
  result: null,     // { predictions, best, confident, threshold, macros }
  macros: null,     // recomputed on portion change
  dish: null,
  portion: 1.0,
  dishes: [],
  corrected: false,
};

const MACRO_META = {
  // ref = a typical per-serving ceiling, so the gauge has an honest scale
  kcal:      { key: "Calories", unit: "kcal", ref: 800, big: true },
  protein_g: { key: "Protein",  unit: "g",    ref: 60 },
  carbs_g:   { key: "Carbs",    unit: "g",    ref: 100 },
  fat_g:     { key: "Fat",      unit: "g",    ref: 50 },
};

/* ── helpers ─────────────────────────────────────────────────────────── */
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const title = (s) => String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

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

/* ── routing ─────────────────────────────────────────────────────────── */
function setView(view) {
  state.view = view;
  $$(".nav__item").forEach((b) => {
    if (b.dataset.nav === view) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  $$(".view").forEach((s) => (s.hidden = s.dataset.view !== view));
  if (history.replaceState) history.replaceState(null, "", `#${view}`);
  else location.hash = view;
  if (view === "patterns") loadPatterns();
  if (view === "method") loadAccuracy();
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

/* ── upload ──────────────────────────────────────────────────────────── */
function showFile(file) {
  state.file = file;
  state.corrected = false;
  const img = $("#plateImg");
  const url = URL.createObjectURL(file);
  img.src = url;
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
    const live = $("#readoutLive");
    live.innerHTML = `<div class="label__unknown"><strong>That photo did not load.</strong><br>${esc(err.message)} Try another image.</div>`;
  }
}

/* ── the result render ───────────────────────────────────────────────── */
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

  live.innerHTML = `
    ${verdict}
    <div class="dish">
      <div class="dish__name" id="dishName">${esc(title(state.dish))}</div>
      <div class="dish__row">
        <span class="dish__sub">${state.result.macros.known ? "in nutrition table" : "no nutrition data"}</span>
        <button class="dish__change" id="changeDish">wrong? change dish</button>
      </div>
    </div>
    <div class="belief">
      <div class="belief__head">
        <span class="belief__label">Model's belief — all 101 dishes</span>
        <span class="belief__label">top 5 shown</span>
      </div>
      <div class="belief__bare">${bars}</div>
      <div class="belief__legend">${legend}</div>
    </div>
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

  const rows = Object.entries(MACRO_META).map(([k, meta]) => {
    const v = m.values[k];
    const band = m.ranges[k];
    if (v == null) return "";
    const ref = meta.ref;

    let valHtml = `<b>${Math.round(v)}</b> <small>${meta.unit}</small>`;
    let gaugeHtml = "";
    if (band) {
      valHtml = `<b>${Math.round(band[0])}–${Math.round(band[1])}</b> <small>${meta.unit}</small>`;
      const lo = Math.max(0, Math.min(100, (band[0] / ref) * 100));
      const hi = Math.max(0, Math.min(100, (band[1] / ref) * 100));
      const mid = Math.max(0, Math.min(100, (v / ref) * 100));
      gaugeHtml = `<div class="gauge" role="img" aria-label="${meta.key} between ${Math.round(band[0])} and ${Math.round(band[1])} ${meta.unit}">
          <div class="gauge__track">
            <div class="gauge__band" style="left:${lo}%;right:${100 - hi}%"></div>
            <div class="gauge__needle" style="left:${mid}%"></div>
          </div>
        </div>`;
    } else {
      // no band (rare): show the single filled value as a plain bar
      const pct = Math.max(2, Math.min(100, (v / ref) * 100));
      gaugeHtml = `<div class="gauge"><div class="gauge__track"><div class="gauge__band" style="left:0;right:${100 - pct}%"></div></div></div>`;
    }

    return `<div class="label__row">
        <span class="label__key">${meta.key}</span>
        <span class="label__fig">${gaugeHtml}<span class="label__val">${valHtml}</span></span>
      </div>`;
  }).join("");

  mount.innerHTML = `
    <div class="label">${rows}</div>
    <p class="label__note">${esc(m.note)}</p>`;
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
  nameEl.outerHTML = `<select class="dish__name" id="dishSelect" style="width:100%;border:1px solid var(--line);border-radius:12px;padding:11px 13px;font:inherit;font-family:var(--font-display);font-size:1.25rem;color:var(--espresso);background:var(--bone)">${options}</select>`;
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
  } catch (err) {
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

/* ── patterns ────────────────────────────────────────────────────────── */
async function loadPatterns() {
  const body = $("#patternsBody");
  let data;
  try { data = await api("/api/patterns"); }
  catch { body.innerHTML = `<div class="empty"><div class="empty__title">Could not load your log.</div></div>`; return; }

  const s = data.summary;
  if (!s.meals) {
    body.innerHTML = `<div class="empty">
        <div class="empty__title">Nothing logged yet</div>
        <div class="empty__body">Analyze a meal and hit “Log this meal” — your patterns appear here.</div>
        <button class="btn btn--primary" id="toAnalyze">Analyze a meal</button>
      </div>`;
    $("#toAnalyze").onclick = () => setView("analyze");
    return;
  }

  const stats = `
    <div class="stat-grid">
      ${statCell("Meals logged", s.meals)}
      ${statCell("Avg calories", Math.round(s.avg_kcal), "per meal")}
      ${statCell("Avg confidence", Math.round(s.avg_confidence * 100) + "%")}
      ${statCell("You corrected the model", s.corrections, s.corrections === 1 ? "time" : "times")}
    </div>`;

  const daily = data.daily.length ? data.daily : [];
  const maxKcal = Math.max(...daily.map((d) => d.kcal || 0), 1);
  const bars = daily
    .map((d) => {
      const h = Math.max(4, ((d.kcal || 0) / maxKcal) * 100);
      const day = new Date(d.day).toLocaleDateString(undefined, { day: "numeric" });
      return `<div class="bars__col" title="${d.day}: ${Math.round(d.kcal)} kcal">
                <span class="bars__val">${Math.round(d.kcal)}</span>
                <div class="bars__bar" style="height:${h}%"></div>
                <span class="bars__lab">${day}</span>
              </div>`;
    })
    .join("");
  const dailyPanel = `<div class="panel">
      <div class="panel__title">Calories per day</div>
      <div class="panel__sub">Last 14 days · summed from your log</div>
      <div class="bars">${bars || '<span class="bars__lab">no recent meals</span>'}</div>
    </div>`;

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

  const topRows = data.topDishes
    .map((d, i) => `<div class="dish-row">
        <span class="dish-row__rank">${String(i + 1).padStart(2, "0")}</span>
        <span class="dish-row__name">${esc(d.display)}</span>
        <span class="dish-row__count">${d.count}×</span>
        <span class="dish-row__kcal">≈ ${Math.round(d.avg_kcal)} kcal</span>
      </div>`)
    .join("");

  body.innerHTML = `<div class="patterns">
      ${stats}
      <div class="panels">${dailyPanel}${macroPanel}</div>
      <div class="dish-row-heading"></div>
      <div class="panel dishes"><div class="panel__title">Most-logged dishes</div><div class="panel__sub">Ranked by frequency</div>${topRows}</div>
    </div>`;
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

/* ── accuracy (method view) ──────────────────────────────────────────── */
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

/* ── boot ────────────────────────────────────────────────────────────── */
async function boot() {
  // dice field behind the plate (subtle, on-brand)
  startField();

  $$(".nav__item").forEach((b) => (b.onclick = () => setView(b.dataset.nav)));
  $(".wordmark").onclick = (e) => { e.preventDefault(); setView("analyze"); };

  const plate = $("#plate");
  const input = $("#fileInput");
  const trigger = () => input.click();
  plate.onclick = (e) => { if (e.target.closest("button, a, input, select")) return; trigger(); };
  $("#plateEmpty").onclick = trigger;
  input.onchange = () => { if (input.files[0]) showFile(input.files[0]); };

  ["dragenter", "dragover"].forEach((ev) =>
    plate.addEventListener(ev, (e) => { e.preventDefault(); plate.classList.add("is-drag"); }));
  ["dragleave", "drop"].forEach((ev) =>
    plate.addEventListener(ev, (e) => { e.preventDefault(); plate.classList.remove("is-drag"); }));
  plate.addEventListener("drop", (e) => {
    const f = e.dataTransfer?.files?.[0];
    if (f) showFile(f);
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

  pollStatus();
  setView(location.hash.replace("#", "") || "analyze");
  if (state.view === "analyze") loadAccuracy(); // preload for method view
}

/* ── ambient steam rising off the empty plate ────────────────────────── */
function startField() {
  const canvas = $("#plateField");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  let w, h, wisps = [];
  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  function size() {
    const r = canvas.getBoundingClientRect();
    w = r.width; h = r.height;
    canvas.width = w * dpr; canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const count = Math.max(4, Math.round(w / 110));
    wisps = Array.from({ length: count }, () => ({
      x: (0.18 + Math.random() * 0.64) * w,
      y: Math.random() * h,
      r: 10 + Math.random() * 22,
      rise: 0.15 + Math.random() * 0.35,
      drift: (Math.random() - 0.5) * 0.25,
      a: 0.03 + Math.random() * 0.05,
      phase: Math.random() * Math.PI * 2,
    }));
  }

  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let t = 0;
  function frame() {
    ctx.clearRect(0, 0, w, h);
    t += 0.006;
    for (const s of wisps) {
      if (!reduce) {
        s.y -= s.rise;
        s.x += s.drift + Math.sin(t + s.phase) * 0.18;
        if (s.y + s.r < 0) { s.y = h + s.r; s.x = (0.18 + Math.random() * 0.64) * w; }
      }
      const g = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, s.r);
      g.addColorStop(0, `rgba(74,107,31,${s.a})`);
      g.addColorStop(1, "rgba(74,107,31,0)");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
    if (!reduce) requestAnimationFrame(frame);
  }

  size();
  window.addEventListener("resize", size);
  frame();
}

boot();
