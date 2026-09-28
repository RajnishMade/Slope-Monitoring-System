"use strict";

/* ===========================================================
   Slope Stability — single-page frontend
   Views: landing · current-status (Option 1) · monitor (Option 2)
   =========================================================== */

const App = document.getElementById("app");
const NavRight = document.getElementById("nav-right");
const Toasts = document.getElementById("toasts");
const POLL_MS = 2500;
const SIM_MS = 2000;

const State = {
  meta: null,
  slopes: [],
  mon: { slopeId: null, poll: null, sim: null, simPhase: 0, alerted: false },
};

/* ----------------------------- utils ----------------------------- */
const api = {
  async get(u) { const r = await fetch(u); if (!r.ok) throw new Error(await r.text()); return r.json(); },
  async post(u, b) { const r = await fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }); if (!r.ok) throw new Error((await r.json()).detail || r.status); return r.json(); },
  async del(u) { const r = await fetch(u, { method: "DELETE" }); if (!r.ok) throw new Error(r.status); return r.json(); },
};
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmtTime = (ts) => { try { return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }); } catch { return "—"; } };
const num = (v, d = 2) => (v === null || v === undefined || isNaN(v) ? "—" : Number(v).toFixed(d));
function classify(fos, thr, warn) { if (fos <= thr) return "ALERT"; if (fos <= thr * warn) return "WARNING"; return "STABLE"; }
function color(status) { return (State.meta && State.meta.status.colors[status]) || "#8fa1c0"; }

function toast(title, sub, kind = "") {
  const t = document.createElement("div");
  t.className = "toast " + kind;
  t.innerHTML = `<div class="tt">${kind === "alert" ? "⚠️ " : ""}${esc(title)}</div><div class="ts">${esc(sub)}</div>`;
  Toasts.appendChild(t);
  setTimeout(() => { t.style.opacity = "0"; setTimeout(() => t.remove(), 300); }, 6000);
}

function setLive(on, text) {
  NavRight.innerHTML = on === null ? "" :
    `<span class="live ${on ? "" : "off"}"><span class="dot"></span>${esc(text)}</span>`;
}

/* teardown timers when navigating away */
function teardown() {
  if (State.mon.poll) clearInterval(State.mon.poll);
  if (State.mon.sim) clearInterval(State.mon.sim);
  State.mon.poll = State.mon.sim = null;
}

/* ----------------------------- router ----------------------------- */
async function boot() {
  try { State.meta = await api.get("/api/meta"); }
  catch (e) { App.innerHTML = `<div class="glass card">Failed to reach server: ${esc(e.message)}</div>`; return; }
  document.getElementById("nav-home").onclick = () => (location.hash = "#/");
  window.addEventListener("hashchange", route);
  route();
}

function route() {
  teardown();
  const h = location.hash || "#/";
  const parts = h.replace(/^#\//, "").split("/");
  if (parts[0] === "status") return renderStatus();
  if (parts[0] === "monitor") return renderMonitor(parts[1] || null);
  return renderLanding();
}

/* ============================ LANDING ============================ */
function renderLanding() {
  setLive(null);
  App.innerHTML = `
    <section class="view">
      <div class="page-head">
        <div class="eyebrow">Planar failure · TabPFN factor of safety</div>
        <h1>Slope stability, in real time.</h1>
        <p>Assess a slope on demand, or monitor it continuously from live sensor data.</p>
      </div>
      <div class="choose">
        <button class="glass choice" data-go="#/status">
          <div class="ic">▤</div>
          <h2>Current Slope Status</h2>
          <p>Enter the slope parameters by hand and get an instant Factor-of-Safety assessment. Save it with an alert threshold and a unique Slope ID.</p>
          <span class="go">Start assessment <span class="arrow">→</span></span>
        </button>
        <button class="glass choice" data-go="#/monitor">
          <div class="ic">◉</div>
          <h2>Real-Time Monitoring</h2>
          <p>Pick a saved slope and watch its Factor of Safety evolve as ESP32 sensor data streams in. Get alerted the moment it nears your threshold.</p>
          <span class="go">Open monitoring <span class="arrow">→</span></span>
        </button>
      </div>
    </section>`;
  App.querySelectorAll("[data-go]").forEach((b) => (b.onclick = () => (location.hash = b.dataset.go)));
}

/* ====================== OPTION 1: CURRENT STATUS ====================== */
function fieldHTML(f) {
  const badge = f.dynamic ? `<span class="badge-io">sensor · ${esc(f.sensor)}</span>` : "";
  const unit = f.unit ? ` <span class="unit">(${esc(f.unit)})</span>` : "";
  return `<div class="field">
      <label for="f-${f.key}">${esc(f.label)}${unit} ${badge}</label>
      <input type="number" id="f-${f.key}" value="${f.default}" min="${f.min}" max="${f.max}" step="${f.step}" />
    </div>`;
}

function renderStatus() {
  setLive(null);
  const feats = State.meta.features;
  const statics = feats.filter((f) => !f.dynamic);
  const dynamics = feats.filter((f) => f.dynamic);
  App.innerHTML = `
    <section class="view">
      <div class="page-head">
        <div class="eyebrow">Current Slope Status · manual assessment</div>
        <h1>Assess a slope</h1>
        <p>Enter the exact parameters the model requires. Predict the Factor of Safety, then save it with an alert threshold.</p>
      </div>

      <div class="glass card">
        <div class="card-title">Slope identity</div>
        <div class="grid-2">
          <div class="field"><label for="f-name">Name / location <span class="unit">(optional)</span></label>
            <input type="text" id="f-name" placeholder="e.g. East Face — Km 42" /></div>
        </div>
      </div>

      <div class="glass card">
        <div class="card-title">Geometry &amp; material (static)</div>
        <div class="grid-3">${statics.map(fieldHTML).join("")}</div>
      </div>

      <div class="glass card">
        <div class="card-title">Initial conditions (dynamic in monitoring)</div>
        <div class="grid-2">${dynamics.map(fieldHTML).join("")}</div>
        <p class="hint" style="margin-top:12px">In Real-Time Monitoring these two come live from the ESP32 (water sensor → water level, vibration → seismic coefficient). The other parameters stay fixed for the slope.</p>
      </div>

      <div style="display:flex; gap:12px; margin-top:20px; flex-wrap:wrap">
        <button class="btn btn-primary" id="btn-predict">Predict Factor of Safety</button>
        <button class="btn btn-ghost" id="btn-reset">Reset</button>
      </div>

      <div class="glass card result-card" id="result" style="display:none; margin-top:22px"></div>
    </section>`;

  App.querySelector("#btn-reset").onclick = () => renderStatus();
  App.querySelector("#btn-predict").onclick = onPredict;
}

function readParams() {
  const params = {};
  for (const f of State.meta.features) {
    const v = parseFloat(document.getElementById("f-" + f.key).value);
    if (isNaN(v)) { toast("Missing value", `Please enter ${f.label}.`); return null; }
    params[f.key] = v;
  }
  return params;
}

async function onPredict() {
  const params = readParams();
  if (!params) return;
  const btn = App.querySelector("#btn-predict");
  btn.disabled = true; btn.textContent = "Predicting…";
  try {
    const { fos } = await api.post("/api/predict", { params });
    showResult(fos, params);
  } catch (e) { toast("Prediction failed", e.message); }
  finally { btn.disabled = false; btn.textContent = "Predict Factor of Safety"; }
}

function showResult(fos, params) {
  const warn = State.meta.status.warn_ratio;
  const res = App.querySelector("#result");
  const defThr = Math.max(0.8, Math.round(fos * 0.85 * 100) / 100);
  res.style.display = "block";
  res.innerHTML = `
    <div class="card-title" style="text-align:left">Predicted result</div>
    <div class="fos-hero" style="justify-content:center; margin:6px 0 4px">
      <span class="num" id="rc-fos">${num(fos, 3)}</span>
      <span style="color:var(--ink-3)">FoS</span>
    </div>
    <div id="rc-pill" style="margin-bottom:22px"></div>
    <div class="card-title" style="text-align:left">Set alert threshold</div>
    <div class="grid-2" style="max-width:520px; margin:0 auto; text-align:left">
      <div class="field"><label for="f-thr">Alert when FoS falls to / below</label>
        <input type="number" id="f-thr" value="${defThr}" min="0.1" max="${(fos).toFixed(2)}" step="0.01" /></div>
      <div class="field"><label>Resulting status at baseline</label>
        <div style="padding-top:6px" id="thr-status"></div></div>
    </div>
    <div style="display:flex; gap:12px; justify-content:center; margin-top:24px; flex-wrap:wrap">
      <button class="btn btn-primary" id="btn-save">Save slope &amp; generate ID</button>
    </div>`;
  res.scrollIntoView({ behavior: "smooth", block: "nearest" });

  const thrInput = res.querySelector("#f-thr");
  const updateStatus = () => {
    const thr = parseFloat(thrInput.value) || 0;
    const st = classify(fos, thr, warn);
    res.querySelector("#thr-status").innerHTML = pillHTML(st);
    const p = res.querySelector("#rc-pill"); p.innerHTML = pillHTML(st);
  };
  thrInput.oninput = updateStatus;
  updateStatus();

  res.querySelector("#btn-save").onclick = async () => {
    const threshold = parseFloat(thrInput.value);
    if (isNaN(threshold) || threshold <= 0) { toast("Invalid threshold", "Enter a positive number."); return; }
    const name = document.getElementById("f-name").value.trim();
    try {
      const slope = await api.post("/api/slopes", { name, params, threshold });
      showSaved(slope);
    } catch (e) { toast("Save failed", e.message); }
  };
}

function pillHTML(status) { return `<span class="pill ${status}"><span class="dot"></span>${status}</span>`; }

function showSaved(slope) {
  const res = App.querySelector("#result");
  res.innerHTML = `
    <div class="ic" style="margin:0 auto 14px; width:54px;height:54px;border-radius:16px;display:grid;place-items:center;font-size:26px;background:linear-gradient(135deg,rgba(48,209,88,0.25),rgba(41,151,255,0.15));border:1px solid var(--glass-brd)">✓</div>
    <div class="card-title" style="text-align:center">Slope saved</div>
    <div class="rc-id">${esc(slope.slope_id)}</div>
    <p style="color:var(--ink-2); margin:6px 0 20px">${esc(slope.name)}</p>
    <div class="stat-row" style="max-width:620px;margin:0 auto">
      <div class="glass stat"><div class="k">Baseline FoS</div><div class="v small">${num(slope.baseline_fos, 3)}</div></div>
      <div class="glass stat"><div class="k">Threshold</div><div class="v small">${num(slope.threshold, 2)}</div></div>
      <div class="glass stat"><div class="k">Status</div><div class="v small">${pillHTML(slope.status)}</div></div>
    </div>
    <div style="display:flex; gap:12px; justify-content:center; margin-top:24px; flex-wrap:wrap">
      <button class="btn btn-primary" id="btn-goto">Open in monitoring →</button>
      <button class="btn btn-ghost" id="btn-new">New assessment</button>
    </div>`;
  res.querySelector("#btn-goto").onclick = () => (location.hash = "#/monitor/" + slope.slope_id);
  res.querySelector("#btn-new").onclick = () => renderStatus();
  toast("Slope saved", `${slope.slope_id} · threshold ${num(slope.threshold, 2)}`);
}

/* ====================== OPTION 2: MONITORING ====================== */
async function renderMonitor(slopeId) {
  setLive(false, "Idle");
  try { State.slopes = (await api.get("/api/slopes")).slopes; }
  catch (e) { App.innerHTML = `<div class="glass card">Failed to load slopes: ${esc(e.message)}</div>`; return; }

  if (!State.slopes.length) {
    App.innerHTML = `<section class="view"><div class="page-head"><h1>Real-Time Monitoring</h1></div>
      <div class="glass card empty">No slopes yet. Create one in <a href="#/status" style="color:var(--cyan)">Current Slope Status</a> first.</div></section>`;
    return;
  }
  const sel = State.slopes.find((s) => s.slope_id === slopeId) || State.slopes[0];
  State.mon.slopeId = sel.slope_id;
  State.mon.alerted = false;

  const opts = State.slopes.map((s) => `<option value="${s.slope_id}" ${s.slope_id === sel.slope_id ? "selected" : ""}>${esc(s.slope_id)} — ${esc(s.name)}</option>`).join("");

  App.innerHTML = `
    <section class="view">
      <div class="alert-banner" id="alert-banner">
        <span class="ab-ic">⚠️</span>
        <div><div class="ab-t" id="ab-title">Alert</div><div class="ab-s" id="ab-sub"></div></div>
      </div>

      <div class="monitor-head">
        <div class="slope-title">
          <h1 id="m-name">${esc(sel.name)}</h1>
          <span class="slope-id-chip" id="m-id">${esc(sel.slope_id)}</span>
        </div>
        <div class="controls">
          <select id="m-select">${opts}</select>
          <button class="btn btn-sm" id="m-sim">▶ Start simulated feed</button>
        </div>
      </div>

      <div class="stat-row" style="margin-bottom:18px">
        <div class="glass stat" id="stat-fos"><div class="k">Current FoS</div><div class="fos-hero"><span class="num" id="v-fos">—</span></div><div class="sub" id="v-fos-sub"></div></div>
        <div class="glass stat"><div class="k">Alert threshold</div><div class="v" id="v-thr">—</div><div class="sub">user-defined limit</div></div>
        <div class="glass stat"><div class="k">Status</div><div class="v small" id="v-status">—</div><div class="sub" id="v-status-sub"></div></div>
      </div>

      <div class="glass card chart-card" id="chart-card">
        <div class="chart-head">
          <div class="card-title" style="margin:0">Factor of Safety vs Time</div>
          <div class="hint" id="chart-note"></div>
        </div>
        <div class="chart-wrap" id="chart-wrap"></div>
      </div>

      <div class="two-col" style="margin-top:18px">
        <div class="glass card">
          <div class="card-title">Sensor data</div>
          <div class="sensors" id="sensors"></div>
          <p class="hint" style="margin-top:14px"><span class="badge-io">model input</span> feeds the FoS prediction. Others are monitoring telemetry.</p>
        </div>
        <div class="glass card">
          <div class="card-title">Monitoring information</div>
          <div id="info"></div>
          <div style="display:flex; gap:10px; margin-top:16px; flex-wrap:wrap">
            <button class="btn btn-sm btn-danger" id="m-del">Delete slope</button>
          </div>
        </div>
      </div>
    </section>`;

  App.querySelector("#m-select").onchange = (e) => (location.hash = "#/monitor/" + e.target.value);
  App.querySelector("#m-sim").onclick = toggleSim;
  App.querySelector("#m-del").onclick = async () => {
    if (!confirm(`Delete ${sel.slope_id}? This removes its history.`)) return;
    try { await api.del("/api/slopes/" + sel.slope_id); toast("Deleted", sel.slope_id); location.hash = "#/monitor"; }
    catch (e) { toast("Delete failed", e.message); }
  };

  await refreshMonitor();
  State.mon.poll = setInterval(refreshMonitor, POLL_MS);
}

async function refreshMonitor() {
  const id = State.mon.slopeId;
  let data;
  try { data = await api.get(`/api/slopes/${id}/readings?limit=120`); }
  catch { return; }
  // bail if we navigated away or switched slopes while the request was in flight
  if (State.mon.slopeId !== id || !document.getElementById("v-fos")) return;
  const warn = State.meta.status.warn_ratio;
  const rd = data.readings;
  const latest = rd[rd.length - 1] || null;
  const thr = data.threshold;

  // stats
  const fos = latest ? latest.fos : data.baseline_fos;
  const status = latest ? latest.status : classify(fos, thr, warn);
  const vfos = document.getElementById("v-fos");
  vfos.textContent = num(fos, 3); vfos.className = "num " + status;
  document.getElementById("v-thr").textContent = num(thr, 2);
  document.getElementById("v-status").innerHTML = pillHTML(status);
  document.getElementById("stat-fos").classList.toggle("alert-glow", status === "ALERT");

  // connection / freshness
  const ageMs = latest ? Date.now() - new Date(latest.ts).getTime() : Infinity;
  const live = ageMs < 8000;
  const source = latest ? latest.source : "none";
  setLive(live, live ? "LIVE" : "Idle");
  document.getElementById("v-fos-sub").textContent = latest ? `updated ${fmtTime(latest.ts)}` : "no data yet";
  document.getElementById("v-status-sub").textContent = status === "ALERT" ? "threshold crossed" : status === "WARNING" ? "approaching threshold" : "within safe margin";
  document.getElementById("chart-note").textContent = `${rd.length} readings · window`;

  renderSensors(latest);
  renderInfo(latest, data, live, source);
  renderChart(document.getElementById("chart-wrap"), rd, thr, data.baseline_fos, warn);
  handleAlert(status, latest, thr);
}

function renderSensors(latest) {
  const s = latest ? latest.sensors : {};
  const wl = latest ? latest.water_level : null;
  const kh = latest ? latest.seismic_kh : null;
  const tiles = State.meta.sensors.map((def) => {
    const raw = s ? s[def.key] : undefined;
    const badge = def.model_input ? `<span class="badge-io">model input</span>` : "";
    let sub = "";
    if (def.maps_to === "water_level" && wl != null) sub = `→ water_level ${num(wl, 2)}`;
    if (def.maps_to === "seismic_kh" && kh != null) sub = `→ kₕ ${num(kh, 3)}`;
    return `<div class="sensor">
        <div class="s-top"><span class="s-label">${esc(def.label)}</span>${badge}</div>
        <div class="s-val">${raw === undefined ? "—" : num(raw, def.key === "vibration" ? 3 : 2)}<span class="u">${esc(def.unit)}</span></div>
        ${sub ? `<div class="hint" style="margin-top:4px">${sub}</div>` : ""}
      </div>`;
  }).join("");
  document.getElementById("sensors").innerHTML = tiles;
}

function renderInfo(latest, data, live, source) {
  const srcClass = source === "esp32" ? "src-esp32" : source === "simulated" ? "src-simulated" : "src-none";
  const srcLabel = source === "esp32" ? "ESP32 (hardware)" : source === "simulated" ? "Simulated (mock)" : "—";
  document.getElementById("info").innerHTML = `
    <div class="info-row"><span class="k">Last updated</span><span class="val">${latest ? fmtTime(latest.ts) : "—"}</span></div>
    <div class="info-row"><span class="k">Data source</span><span class="src-badge ${srcClass}">${srcLabel}</span></div>
    <div class="info-row"><span class="k">Connection</span><span class="val" style="color:${live ? "var(--green)" : "var(--ink-3)"}">${live ? "● Connected" : "○ Idle"}</span></div>
    <div class="info-row"><span class="k">Monitoring status</span><span class="val">${State.mon.sim ? "Simulating" : live ? "Receiving" : "Standby"}</span></div>
    <div class="info-row"><span class="k">Baseline FoS</span><span class="val">${num(data.baseline_fos, 3)}</span></div>
    <div class="info-row"><span class="k">Readings in window</span><span class="val">${data.readings.length}</span></div>`;
}

function handleAlert(status, latest, thr) {
  const banner = document.getElementById("alert-banner");
  const isAlert = status === "ALERT";
  banner.classList.toggle("show", isAlert);
  document.getElementById("chart-card").classList.toggle("alert-glow", isAlert);
  if (isAlert) {
    document.getElementById("ab-title").textContent = `${State.mon.slopeId} — Alert threshold reached`;
    document.getElementById("ab-sub").textContent = `Predicted FoS ${num(latest.fos, 3)} ≤ threshold ${num(thr, 2)}. Immediate review recommended.`;
    if (!State.mon.alerted) { toast(`${State.mon.slopeId} in ALERT`, `FoS ${num(latest.fos, 3)} ≤ ${num(thr, 2)}`, "alert"); State.mon.alerted = true; }
  } else if (status === "STABLE") {
    State.mon.alerted = false;
  }
}

/* ---------------- simulated sensor feed (clearly mock) ---------------- */
function toggleSim() {
  const btn = document.getElementById("m-sim");
  if (State.mon.sim) {
    clearInterval(State.mon.sim); State.mon.sim = null;
    btn.textContent = "▶ Start simulated feed"; btn.classList.remove("btn-primary");
    toast("Simulation stopped", "No longer sending mock data.");
    return;
  }
  State.mon.simPhase = 0;
  btn.textContent = "■ Stop simulated feed"; btn.classList.add("btn-primary");
  toast("Simulated feed", "Sending mock sensor data (source: simulated).");
  const tick = async () => {
    const p = State.mon.simPhase++;
    // water rises and falls over a ~60-step cycle to exercise the threshold
    const cyc = (1 - Math.cos((p % 60) / 60 * 2 * Math.PI)) / 2; // 0..1..0
    const jit = () => (Math.random() - 0.5);
    const water = Math.max(0, Math.min(1, 0.03 + 0.72 * cyc + 0.02 * jit()));
    const vibration = Math.max(0, Math.min(0.4, 0.004 + 0.10 * cyc + 0.01 * jit()));
    const tilt = Math.max(0, 0.3 + 4 * cyc + 0.3 * jit());
    const displacement = Math.max(0, 1 + 18 * cyc + jit());
    const crack = Math.max(0, 0.2 + 3 * cyc + 0.2 * jit());
    try {
      await api.post("/api/ingest", { slope_id: State.mon.slopeId, source: "simulated", water, vibration, tilt, displacement, crack });
    } catch (e) { /* ignore transient */ }
  };
  tick();
  State.mon.sim = setInterval(tick, SIM_MS);
}

/* ------------------------------- SVG chart ------------------------------- */
function smoothPath(pts) {
  if (!pts.length) return "";
  if (pts.length < 2) return `M ${pts[0][0]} ${pts[0][1]}`;
  let d = `M ${pts[0][0]} ${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || pts[i + 1];
    const c1x = p1[0] + (p2[0] - p0[0]) / 6, c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6, c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C ${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`;
  }
  return d;
}

function renderChart(wrap, readings, thr, baseline, warn) {
  const W = 820, H = 300, padL = 46, padR = 18, padT = 18, padB = 30;
  if (!readings.length) { wrap.innerHTML = `<div class="empty">Waiting for data… start the simulated feed or send ESP32 data.</div>`; return; }

  const fosVals = readings.map((r) => r.fos);
  const lo = Math.min(...fosVals, thr) - 0.1;
  const hi = Math.max(...fosVals, thr * warn, baseline) + 0.1;
  const yMin = Math.max(0, lo), yMax = hi;
  const n = readings.length;
  const X = (i) => padL + (n === 1 ? (W - padL - padR) / 2 : (i / (n - 1)) * (W - padL - padR));
  const Y = (v) => padT + (1 - (v - yMin) / (yMax - yMin)) * (H - padT - padB);

  const pts = readings.map((r, i) => [X(i), Y(r.fos)]);
  const curve = smoothPath(pts);
  const area = `${curve} L ${X(n - 1)} ${H - padB} L ${X(0)} ${H - padB} Z`;

  // y ticks
  const ticks = 4; let yAxis = "";
  for (let t = 0; t <= ticks; t++) {
    const v = yMin + (t / ticks) * (yMax - yMin), y = Y(v);
    yAxis += `<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="rgba(255,255,255,0.06)"/>
      <text x="${padL - 8}" y="${y + 3}" text-anchor="end" fill="rgba(235,240,250,0.4)" font-size="11">${v.toFixed(2)}</text>`;
  }
  // x labels: first / mid / last
  const xIdx = n === 1 ? [0] : [0, Math.floor((n - 1) / 2), n - 1];
  const xAxis = xIdx.map((i) => `<text x="${X(i)}" y="${H - 8}" text-anchor="middle" fill="rgba(235,240,250,0.4)" font-size="11">${fmtTime(readings[i].ts)}</text>`).join("");

  const yThr = Y(thr), yWarn = Y(thr * warn), last = readings[n - 1];
  const lastColor = color(last.status);

  wrap.innerHTML = `
  <svg viewBox="0 0 ${W} ${H}" role="img">
    <defs>
      <linearGradient id="areaG" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${lastColor}" stop-opacity="0.35"/>
        <stop offset="100%" stop-color="${lastColor}" stop-opacity="0"/>
      </linearGradient>
      <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
    </defs>
    <rect x="${padL}" y="${yThr}" width="${W - padL - padR}" height="${H - padB - yThr}" fill="rgba(255,69,58,0.07)"/>
    <rect x="${padL}" y="${yWarn}" width="${W - padL - padR}" height="${yThr - yWarn}" fill="rgba(255,159,10,0.06)"/>
    ${yAxis}${xAxis}
    <path d="${area}" fill="url(#areaG)"/>
    <path d="${curve}" fill="none" stroke="${lastColor}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)"/>
    <line x1="${padL}" y1="${yThr}" x2="${W - padR}" y2="${yThr}" stroke="var(--red)" stroke-width="1.5" stroke-dasharray="6 5"/>
    <text x="${W - padR}" y="${yThr - 7}" text-anchor="end" fill="var(--red)" font-size="11" font-weight="600">Alert threshold ${thr.toFixed(2)}</text>
    <circle cx="${X(n - 1)}" cy="${Y(last.fos)}" r="5" fill="${lastColor}" filter="url(#glow)"/>
    <g id="hoverG" style="opacity:0">
      <line id="hoverLine" y1="${padT}" y2="${H - padB}" stroke="rgba(255,255,255,0.3)" stroke-width="1"/>
      <circle id="hoverDot" r="4.5" fill="#fff" stroke="rgba(0,0,0,0.4)"/>
    </g>
    <rect id="hoverArea" x="${padL}" y="${padT}" width="${W - padL - padR}" height="${H - padT - padB}" fill="transparent" style="cursor:crosshair"/>
  </svg>
  <div class="tooltip" id="tip"></div>`;

  // hover interaction
  const svg = wrap.querySelector("svg");
  const tip = wrap.querySelector("#tip");
  const hg = wrap.querySelector("#hoverG");
  const hl = wrap.querySelector("#hoverLine");
  const hd = wrap.querySelector("#hoverDot");
  const area2 = wrap.querySelector("#hoverArea");
  const move = (evt) => {
    const rect = svg.getBoundingClientRect();
    const cx = (evt.touches ? evt.touches[0].clientX : evt.clientX) - rect.left;
    const sx = cx / rect.width * W; // to viewBox units
    let i = Math.round((sx - padL) / ((W - padL - padR) || 1) * (n - 1));
    i = Math.max(0, Math.min(n - 1, i));
    const r = readings[i], px = X(i), py = Y(r.fos);
    hg.style.opacity = "1"; hl.setAttribute("x1", px); hl.setAttribute("x2", px);
    hd.setAttribute("cx", px); hd.setAttribute("cy", py); hd.setAttribute("fill", color(r.status));
    tip.style.opacity = "1";
    tip.style.left = (px / W * rect.width) + "px";
    tip.style.top = (py / H * rect.height) + "px";
    tip.innerHTML = `<b>FoS ${r.fos.toFixed(3)}</b> · ${r.status}<br><span style="color:var(--ink-3)">${fmtTime(r.ts)}</span>`;
  };
  area2.addEventListener("mousemove", move);
  area2.addEventListener("touchmove", (e) => { move(e); }, { passive: true });
  area2.addEventListener("mouseleave", () => { hg.style.opacity = "0"; tip.style.opacity = "0"; });
}

boot();

/* -------------- background image slideshow -------------- */
(function initSlideshow() {
  const slides = document.querySelectorAll(".bg-slide");
  if (!slides.length) return;
  let cur = 0;
  setInterval(() => {
    slides[cur].classList.remove("active");
    cur = (cur + 1) % slides.length;
    slides[cur].classList.add("active");
  }, 8000);
})();
