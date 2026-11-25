"use strict";

const el = (id) => document.getElementById(id);
const number = (v, digits = 1, unit = "") => Number.isFinite(v) ? v.toFixed(digits) + unit : "—";
const nice = (v) => typeof v === "string" ? v.replaceAll("_", " ").toLowerCase().replace(/^./, c => c.toUpperCase()) : "—";
const point = p => !!p && Number.isFinite(p.e) && Number.isFinite(p.n);
const coords = (p) => point(p) ? number(p.e, 0, " E") + " / " + number(p.n, 0, " N") : "—";
const clock = (s) => Number.isFinite(s) ? Math.floor(s / 60) + ":" + String(Math.floor(s % 60)).padStart(2, "0") : "—";
const display = (id, text) => {
  el(id).textContent = text ?? "—";
};
const finiteMax = (collection, fn) => collection.reduce((a, x) => Number.isFinite(fn(x)) ? Math.max(a, fn(x)) : a, -Infinity);
let scenario = null;
let snapshot = {};
let connected = false;
let busy = false;
let runId;
let samples = [];
let replay = null;
let frameIndex = 0;
let replayTicker;
let view = null;
let geometry;
let dragging;
let formDraft;

function notice(message = "") {
  display("notice", message);
  el("notice").hidden = !message;
}
async function api(path, method = "GET", data) {
  const options = {
    method,
    cache: "no-store",
    signal: AbortSignal.timeout(method === "POST" ? 35000 : 5000)
  };
  if (data !== undefined) {
    options.headers = {
      "Content-Type": "application/json"
    };
    options.body = JSON.stringify(data);
  }
  const response = await fetch(path, options);
  if (!response.ok) {
    const error = await response.text();
    let detail;
    try {
      const body = JSON.parse(error);
      detail = body.error || body.detail;
    } catch {}
    throw Error(detail || error || response.statusText);
  }
  return response.status === 204 ? null : response.json();
}
const fields = [
  ["Run", [
    ["name", "Scenario name"],
    ["seed", "Radio seed"],
    ["speedup", "Firmware speed multiplier"],
    ["timeout_s", "Run timeout (s)"]
  ]],
  ["Virtual diver", [
    ["diver_e_m", "Initial east (m)"],
    ["diver_n_m", "Initial north (m)"],
    ["drift_e_mps", "Diver drift over ground · east (km/h)"],
    ["drift_n_mps", "Diver drift over ground · north (km/h)"]
  ]],
  ["Rendezvous", [
    ["target_e_m", "Target east (m)"],
    ["target_n_m", "Target north (m)"],
    ["exclusion_m", "Exclusion radius (m)"],
    ["uncertainty_m", "Position uncertainty (m)"]
  ]],
  ["Radio", [
    ["latency_s", "One-way delay (s)"],
    ["loss", "Packet loss (%)"],
    ["freshness_s", "Fix freshness limit (s)"]
  ]]
];

function showForm(data) {
  boatDesign.fill(data);
  if (!data || Array.isArray(data) || typeof data !== "object") throw Error("Select a scenario JSON object.");
  formDraft = {
    ...data
  };
  el("fields").replaceChildren();
  for (const [name, group] of fields) {
    const set = document.createElement("fieldset");
    const legend = document.createElement("legend");
    legend.textContent = name;
    set.append(legend);
    for (const [key, label] of group) {
      if (!(key in data)) continue;
      const wrapper = document.createElement("label");
      wrapper.textContent = label;
      const input = document.createElement("input");
      input.name = key;
      input.type = key === "name" ? "text" : "number";
      input.value = input.type === "number" ? editorNumber(key, data[key]) : data[key];
      input.step = ["seed", "speedup"].includes(key) ? "1" : "any";
      if (key === "loss") {
        input.min = "0";
        input.max = "100";
      } else if (key === "drift_e_mps" || key === "drift_n_mps") {
        input.min = "-10.8";
        input.max = "10.8";
      }
      input.required = true;
      wrapper.append(input);
      set.append(wrapper);
    }
    if (set.children.length > 1) el("fields").append(set);
  }
}

function formValue() {
  if (!el("scenario-form").reportValidity()) throw Error("Check the marked field.");
  const values = {
    ...formDraft, ...boatDesign.read(formDraft.boat_design)
  };
  el("fields").querySelectorAll("input").forEach(input => {
    values[input.name] = input.type === "number"
      ? scenarioNumber(input.name, input.valueAsNumber, formDraft[input.name]) : input.value.trim();
  });
  return values;
}

function canEdit() {
  return !replay && !busy && connected && snapshot.status === "IDLE";
}
async function applyScenario(value) {
  if (!canEdit()) throw Error("Reset the simulator before editing the scenario.");
  busy = true;
  renderControls();
  try {
    await api("/api/scenario", "PUT", value);
    scenario = await api("/api/scenario");
    view = null;
    notice("Scenario updated.");
  } finally {
    busy = false;
    render();
  }
}
el("open-editor").onclick = () => {
  if (!canEdit() || !scenario) return;
  showForm(scenario);
  display("form-status", "");
  el("editor").showModal();
};
el("discard").onclick = el("close-editor").onclick = () => el("editor").close();
el("scenario-file").onchange = async (event) => {
  try {
    const file = event.target.files[0];
    if (file.size > 65536) throw Error("Scenario exceeds 64 KiB.");
    const value = JSON.parse(await file.text());
    if (value.schema_version !== 1 || fields.flatMap(g => g[1]).some(([k]) => k in scenario && !(k in value))) {
      throw Error("Select a complete version 1 Remora scenario.");
    }
    showForm(value);
    display("form-status", "Loaded into the editor. Apply to use this scenario.");
  } catch (error) {
    display("form-status", error.message);
  }
  event.target.value = "";
};
el("save-file").onclick = () => {
  try {
    const value = formValue();
    const link = document.createElement("a");
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {
      type: "application/json"
    }));
    link.href = url;
    link.download = "remora-scenario.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1200);
  } catch (error) {
    display("form-status", error.message);
  }
};
el("scenario-form").onsubmit = async (event) => {
  event.preventDefault();
  try {
    await applyScenario(formValue());
    el("editor").close();
  } catch (error) {
    display("form-status", error.message);
  }
};
document.querySelectorAll("[data-action]").forEach(button => {
  button.onclick = async () => {
    if (busy || replay || !connected || !snapshot.actions?.includes(button.dataset.action)) return;
    busy = true;
    renderControls();
    try {
      const fresh = await api("/api/action", "POST", {action: button.dataset.action});
      if (fresh.status === "IDLE") scenario = await api("/api/scenario");
      notice("");
      ingest(fresh);
    } catch (error) {
      notice(error.message);
    } finally {
      busy = false;
      render();
    }
  };
});

function renderControls() {
  for (const b of document.querySelectorAll("[data-action]")) {
    b.disabled = !!replay || busy || !connected || !snapshot.actions?.includes(b.dataset.action);
  }
  el("open-editor").disabled = !canEdit() || !scenario;
  el("open-editor").title = canEdit() ? "Change hull, steering, motor and wind" : "Reset the run to edit the next scenario";
  if (location.hash === "#boat-setup" && canEdit() && scenario) {
    history.replaceState(null, "", location.pathname);
    queueMicrotask(() => el("open-editor").click());
  }
  el("placement").disabled = !canEdit();
  if (!canEdit()) el("placement").value = "";
  const replayInput = el("replay-file");
  replayInput.disabled = !replay && connected && ["RUNNING", "STARTING"].includes(snapshot.status);
  el("json-export").hidden = el("csv-export").hidden = !!replay || !connected || !snapshot.run_id;
}

function ingest(state) {
  if (!state || typeof state.status !== "string") throw Error("Unrecognized simulator state.");
  if (state.run_id && state.run_id === runId && state.sim_s < snapshot.sim_s) return;
  if (state.run_id !== runId) {
    samples = [];
    view = null;
  }
  runId = state.run_id;
  snapshot = state;
  if (state.status !== "IDLE" && point(state.boat) && state.sim_s !== samples.at(-1)?.sim_s) {
    samples.push(state);
    if (samples.length > 5000) samples = samples.filter((_, i) => i % 2 === 0);
  }
}
async function followSimulator() {
  let stream;
  let watchdog;
  try {
    if (!replay) {
      const fresh = await api("/api/state");
      const config = await api("/api/scenario");
      if (!busy && !replay) {
        scenario = config;
        connected = true;
        ingest(fresh);
        render();
      }
    }
    const url = new URL("/api/events", location.href);
    url.protocol = location.protocol === "https:" ? "wss:" : "ws:";
    stream = new WebSocket(url);
    await new Promise(resolve => {
      function expire() {
        clearTimeout(watchdog);
        watchdog = setTimeout(() => stream.close(), 5000);
      }
      expire();
      stream.onclose = resolve;
      stream.onmessage = event => {
        expire();
        if (busy || replay) return;
        try {
          const fresh = JSON.parse(event.data);
          if (!scenario || (fresh.status === "IDLE" && snapshot.status !== "IDLE")) {
            stream.close();
            return;
          }
          connected = true;
          ingest(fresh);
          render();
        } catch {
          stream.close();
        }
      };
    });
  } catch {
    // Retry while the local server starts or restarts.
  } finally {
    clearTimeout(watchdog);
    connected = false;
    render();
    setTimeout(followSimulator, 900);
  }
}

function activeScenario() {
  return replay?.scenario || scenario || {};
}

function preview() {
  return !replay && snapshot.status === "IDLE";
}

function geometryPoints() {
  const c = activeScenario();
  if (preview()) return {
    boat: {
      e: 0,
      n: 0
    },
    diver: {
      e: c.diver_e_m,
      n: c.diver_n_m
    },
    target: {
      e: c.target_e_m,
      n: c.target_n_m
    }
  };
  return {
    boat: snapshot.boat,
    diver: snapshot.diver,
    target: snapshot.target
  };
}
const series = [
  ["Ground speed", "km/h", s => Number.isFinite(s.boat?.speed_mps) ? s.boat.speed_mps * KMH_PER_MPS : null],
  ["Total motor thrust", "lbf", s => Number.isFinite(s.boat?.plant?.thrust_n) ? s.boat.plant.thrust_n / NEWTONS_PER_LBF : null],
  ["Model energy", "Wh", s => s.boat?.plant?.energy_wh],
  ["Battery voltage", "V", s => s.boat?.voltage_v],
  ["Battery current", "A", s => s.boat?.current_a],
  ["Charge remaining", "%", s => s.boat?.soc_pct],
  ["Motor demand", "%", s => s.boat?.throttle_pct],
  ["Heading", "°", s => s.boat?.heading_deg],
  ["Diver separation", "m", s => s.separation_m],
  ["Rendezvous error", "m", s => point(s.boat) && point(s.target) ? Math.hypot(s.boat.e - s.target.e, s.boat.n - s.target.n) : null],
  ["Radio latency", "s", s => s.radio?.latency_s],
  ["Radio loss", "%", s => Number.isFinite(s.radio?.loss) ? 100 * s.radio.loss : null]
];
series.forEach(([name, unit], index) => el("series").add(new Option(name + " (" + unit + ")", index)));
el("series").onchange = () => drawChart();

function renderRendezvousUpdate(s, handheld, downlink) {
  const active = ["TRANSIT_TO_RENDEZVOUS", "RENDEZVOUS_HOLD"].includes(s.state);
  const update = s.radio?.update;
  const button = document.querySelector('[data-action="update_rendezvous"]');
  button.hidden = !handheld || !!replay;
  let blocked = s.update_block_reason;
  if (active && !replay && !Object.hasOwn(s, "update_block_reason")) {
    blocked = "This run uses an older simulator. Start a new run on the updated simulator to change the meeting point.";
  } else if (!active && !replay) {
    blocked = s.status === "IDLE" ? "Start the simulation and request pickup to enable coordinate updates."
      : s.state === "STATION_KEEPING" ? "Request pickup to enable coordinate updates."
      : "Coordinate updates are available during pickup and rendezvous hold.";
  }
  if (!connected && !replay) blocked = "Waiting for the local simulator connection.";
  button.title = blocked || "Send one fresh diver position to update the separated meeting point";
  const hasMeeting = handheld && active && downlink.meeting_active === true &&
    Number.isFinite(downlink.meeting_range_m) && Number.isFinite(downlink.meeting_bearing_deg);
  el("active-meeting").hidden = !hasMeeting;
  if (hasMeeting) {
    display("active-meeting", "Last reported meeting point · " + number(downlink.meeting_range_m, 0, " m") +
      " from you at " + number(downlink.meeting_bearing_deg, 0, "° true") + ".");
  }

  const status = el("update-status");
  status.hidden = !handheld || (!update && !blocked);
  if (status.hidden) return;
  if (!update) {
    if (status.textContent !== blocked) status.textContent = blocked;
    return;
  }
  const states = {
    sent: "sent by handheld",
    received: "received by boat",
    executing: "execution confirmed by boat",
    rejected: "refused by boat",
    unconfirmed: "unconfirmed"
  };
  const label = states[update.status] || nice(update.status);
  const requested = {e: update.target_e, n: update.target_n};
  const text = "Last rendezvous update " + update.sequence + " · " + label +
    (point(requested) ? " · Requested point E " + number(requested.e, 0, " m") + ", N " + number(requested.n, 0, " m") : "") +
    (update.reason ? " · " + update.reason : "") +
    (blocked && blocked !== update.reason ? " · " + blocked : "");
  if (status.textContent !== text) status.textContent = text;
}

function render() {
  const s = snapshot;
  const {
    boat,
    diver,
    target
  } = geometryPoints();
  const b = s.boat || {};
  const radio = s.radio || {};
  const downlink = radio.telemetry || {};
  const c = activeScenario();
  display("scenario-name", c.name ? c.name + " · Seed " + c.seed + " · " + c.speedup + "× firmware time" : "Connecting to the local simulator…");
  display("boat-summary", boatDesign.summary(c));
  const oneTap = c.authorization === "handheld_pickup";
  const handheld = oneTap || c.authorization === "diver_handheld";
  renderRendezvousUpdate(s, handheld, downlink);
  const stationButton = document.querySelector('[data-action="station_keep"]');
  stationButton.title = s.station_block_reason || (s.state === "STATION_KEEPING" ? "Already holding this station" : "Hold the current area");
  display("operator-title", handheld ? "Simulation monitor · empty boat" : "Surface operator");
  document.querySelector('[data-action="approve"]').hidden = handheld;
  document.querySelector('[data-action="reject"]').hidden = handheld;
  const offer = handheld && Number.isFinite(downlink.meeting_range_m);
  el("offer").hidden = !handheld || !["IDLE", "STATION_KEEPING", "PICKUP_REQUESTED"].includes(s.state);
  display("offer", offer ? "Proposed meeting point: " + number(downlink.meeting_range_m, 0, " m") +
    " from you at " + number(downlink.meeting_bearing_deg, 0, "° true") + ". Request pickup sends the boat here." :
    oneTap ? (s.offer_block_reason || "Waiting for the radio to deliver a reachable meeting point.") :
    s.state === "PICKUP_REQUESTED" ? "Request received. Waiting for a meeting-point offer over the radio." :
    "Request pickup to receive a meeting point on this handheld.");
  display("source", replay ? "Replay" : !connected ? "Disconnected" : preview() ? "Setup preview" : nice(s.status));
  el("source").dataset.replay = String(!!replay);
  display("fidelity", s.fidelity === "L1" ? "L1 · Native motorboat" : s.fidelity === "L2" ? "L2 · Uncalibrated lancha" : s.fidelity || "—");
  display("clock", clock(s.sim_s));
  const pending = s.state === "PICKUP_REQUESTED";
  display("mission", pending ? (handheld && !replay ? "Pickup requested" : nice(s.state)) : s.departure_turn ? "Turning toward rendezvous" : nice(s.state));
  display("mode", b.mode || "—");
  display("heartbeat-age", number(b.heartbeat_age_s, 1, " s"));
  display("fix-age", number(radio.fix_age_s, 1, " s"));
  display("arming", typeof b.armed === "boolean" ? b.armed ? "Armed" : "Disarmed" : "—");
  display("isolation", typeof s.isolation === "string" ? nice(s.isolation) : "Unavailable");
  display("ack", radio.ack || "Awaiting radio reply");
  display("remote-range", number(downlink.range_m, 0, " m") + " / " + number(downlink.bearing_deg, 0, "°"));
  display("remote-energy", number(downlink.voltage_v, 1, " V") + " / " + clock(downlink.eta_s));
  display("remote-age", Number.isFinite(downlink.t) && Number.isFinite(s.sim_s) ? number(Math.max(0, s.sim_s - downlink.t), 1, " s") : "—");
  const previewRange = preview() && point(diver) ? Math.hypot(diver.e, diver.n) : null;
  display("separation", number(preview() ? previewRange : s.separation_m, 0, " m"));
  display("speed", number(Number.isFinite(b.speed_mps) ? KMH_PER_MPS * b.speed_mps : null, 1, " km/h"));
  display("heading", number(b.heading_deg, 0, "°"));
  display("course", number(b.course_deg, 0, "°"));
  const bearing = point(b) && point(target) && Math.hypot(target.e-b.e, target.n-b.n) >= 1
    ? (Math.atan2(target.e-b.e, target.n-b.n) * 180 / Math.PI + 360) % 360 : null;
  display("target-bearing", number(bearing, 0, "°"));
  display("battery", number(b.voltage_v, 1, " V"));
  display("position-info", "Metres from the simulated origin. Boat " + coords(boat) + " · Diver " + coords(diver) + " · Rendezvous " + coords(target));
  const feedback = s.state === "ABORT" ? [s.fault, s.station_block_reason || "Station keep here will hold the current position."].filter(Boolean).join(" · ") : s.fault || s.approval_block_reason;
  display("fault", feedback || "");
  el("fault").hidden = !feedback;
  const allEvents = replay ? (replay.events || []).filter(e => e.t <= s.sim_s) : s.events || [];
  const list = document.createDocumentFragment();
  for (const item of allEvents.slice(-60).reverse()) {
    const li = document.createElement("li");
    const t = document.createElement("time");
    t.textContent = clock(item.t);
    const label = document.createElement("span");
    label.textContent = item.message;
    li.append(t, label);
    list.append(li);
  }
  if (!allEvents.length) {
    const row = document.createElement("p");
    row.className = "caption";
    row.textContent = "No events recorded.";
    list.append(row);
  }
  el("events").replaceChildren(list);
  const m = s.metrics || {};
  const metrics = [];
  const outcome = s.result?.outcome || (replay && frameIndex === replay.samples.length - 1 ? replay.result?.outcome : null);
  if (outcome) metrics.push(nice(outcome));
  if (Number.isFinite(m.minimum_separation_m)) metrics.push("Minimum separation " + number(m.minimum_separation_m, 0, " m"));
  if (Number.isFinite(m.time_to_rendezvous_s)) metrics.push("Rendezvous time " + clock(m.time_to_rendezvous_s));
  if (Number.isFinite(m.energy_used_wh)) metrics.push("Energy " + number(m.energy_used_wh, 1, " Wh"));
  display("metrics", metrics.join(" · "));
  el("metrics").hidden = !metrics.length;
  renderControls();
  drawMap();
  drawChart();
}

function canvasContext(id) {
  const canvas = el(id);
  const w = canvas.clientWidth,
    h = canvas.clientHeight;
  const ratio = Math.min(devicePixelRatio || 1, 2);
  const width = Math.round(w * ratio),
    height = Math.round(h * ratio);
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, w, h);
  return {
    ctx,
    w,
    h
  };
}

function line(ctx, x1, y1, x2, y2, color, width = 1) {
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.stroke();
}

function flowArrow(ctx, x, y, east, north, label, colour) {
  if (Math.hypot(east, north) < 0.001) return;
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(Math.atan2(east, north));
  line(ctx, 0, 8, 0, -8, colour, 2);
  line(ctx, 0, -8, 4, -2, colour, 2);
  line(ctx, 0, -8, -4, -2, colour, 2);
  ctx.restore();
  ctx.fillStyle = colour;
  ctx.font = "11px system-ui";
  ctx.fillText(label, x + 14, y + 4);
}

function stepSize(raw) {
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const scaled = raw / magnitude;
  return (scaled < 1.6 ? 1 : scaled < 3.5 ? 2 : scaled < 7.6 ? 5 : 10) * magnitude;
}

function availableSamples() {
  return replay ? replay.samples.slice(0, frameIndex + 1) : samples;
}

function drawMap() {
  const {
    ctx,
    w,
    h
  } = canvasContext("map");
  if (w < 1 || h < 1) return;
  const {
    boat,
    diver,
    target
  } = geometryPoints();
  const c = activeScenario();
  const radius = (Number.isFinite(c.exclusion_m) ? c.exclusion_m : 0) + (Number.isFinite(c.uncertainty_m) ? c.uncertainty_m : 0);
  const points = [boat, diver, target].filter(point);
  const history = availableSamples();
  if (history.length && point(history[0].boat)) points.push(history[0].boat);
  if (point(diver)) points.push({
    e: diver.e - radius,
    n: diver.n - radius
  }, {
    e: diver.e + radius,
    n: diver.n + radius
  });
  if (!points.length) points.push({
    e: 0,
    n: 0
  });
  const emin = Math.min(...points.map(p => p.e)),
    emax = Math.max(...points.map(p => p.e));
  const nmin = Math.min(...points.map(p => p.n)),
    nmax = Math.max(...points.map(p => p.n));
  const camera = view || {
    e: (emin + emax) / 2,
    n: (nmin + nmax) / 2,
    scale: Math.max((emax - emin) / Math.max(1, w - 116), (nmax - nmin) / Math.max(1, h - 110), 110 / w)
  };
  const scale = camera.scale;
  const x = e => w / 2 + (e - camera.e) / scale;
  const y = n => h / 2 - (n - camera.n) / scale;
  geometry = {
    ...camera,
    w,
    h
  };
  ctx.fillStyle = "#123339";
  ctx.fillRect(0, 0, w, h);
  const step = stepSize(82 * scale),
    west = camera.e - w * scale / 2,
    south = camera.n - h * scale / 2;
  ctx.font = "10px Consolas,monospace";
  ctx.fillStyle = "#adc5bb";
  for (let e = Math.ceil(west / step) * step; e < west + w * scale; e += step) {
    line(ctx, x(e), 0, x(e), h, e === 0 ? "#436963" : "#29504f");
    if (x(e) > 45 && x(e) < w - 110) ctx.fillText(Math.round(e) + " E", x(e) + 3, h - 9);
  }
  for (let n = Math.ceil(south / step) * step; n < south + h * scale; n += step) {
    line(ctx, 0, y(n), w, y(n), n === 0 ? "#436963" : "#29504f");
    if (y(n) > 55 && y(n) < h - 40) ctx.fillText(Math.round(n) + " N", 5, y(n) - 3);
  }
  ctx.fillStyle = "#d4e4dc";
  ctx.font = "bold 12px Consolas,monospace";
  ctx.fillText("N", w - 24, 20);
  line(ctx, w - 20, 26, w - 20, 45, "#c6dccc", 1.6);
  line(ctx, w - 20, 26, w - 24, 32, "#c6dccc", 1.6);
  line(ctx, w - 20, 26, w - 16, 32, "#c6dccc", 1.6);
  const design = c.boat_design;
  if (design?.model === "lancha") {
    const rad = design.wind_from_deg * Math.PI / 180;
    flowArrow(ctx, w / 2 - 48, 18, -design.wind_speed_mps * Math.sin(rad), -design.wind_speed_mps * Math.cos(rad),
      "Wind " + number(design.wind_speed_mps * KMH_PER_MPS, 1, " km/h"), "#c3e5fb");
    flowArrow(ctx, w / 2 - 48, 41, design.current_e_mps, design.current_n_mps,
      "Current " + number(Math.hypot(design.current_e_mps, design.current_n_mps) * KMH_PER_MPS, 1, " km/h"), "#b8e5c6");
  }
  if (point(diver) && radius > 0) {
    ctx.beginPath();
    ctx.arc(x(diver.e), y(diver.n), radius / scale, 0, 2 * Math.PI);
    ctx.fillStyle = "rgba(246,157,113,.13)";
    ctx.fill();
    ctx.strokeStyle = "#d89270";
    ctx.lineWidth = 1.2;
    ctx.setLineDash([5, 4]);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  function path(key, color) {
    ctx.beginPath();
    let inLine = false;
    for (let i = 0; i < history.length; i++) {
      const p = history[i][key];
      if (!point(p)) {
        inLine = false;
        continue;
      }
      if (inLine) ctx.lineTo(x(p.e), y(p.n));
      else ctx.moveTo(x(p.e), y(p.n));
      inLine = true;
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.stroke();
  }
  path("boat", "#7de0b3");
  path("diver", "#f8a47c");
  if (point(diver) && Number.isFinite(c.drift_e_mps) && Number.isFinite(c.drift_n_mps) && Math.hypot(c.drift_e_mps, c.drift_n_mps) > 0) {
    ctx.setLineDash([3, 3]);
    line(ctx, x(diver.e), y(diver.n), x(diver.e + 60 * c.drift_e_mps), y(diver.n + 60 * c.drift_n_mps), "#f8a47c");
    ctx.setLineDash([]);
  }

  function label(p, txt, color, offset) {
    const width = ctx.measureText(txt).width;
    const tx = Math.min(w - width - 5, Math.max(4, x(p.e) + 12)),
      ty = Math.max(14, Math.min(h - 6, y(p.n) + offset));
    ctx.lineWidth = 4;
    ctx.strokeStyle = "#123339";
    ctx.strokeText(txt, tx, ty);
    ctx.fillStyle = color;
    ctx.fillText(txt, tx, ty);
  }
  ctx.font = "600 12px system-ui";
  if (point(snapshot.station)) {
    const station = snapshot.station;
    ctx.beginPath();
    ctx.arc(x(station.e), y(station.n), 9, 0, 2*Math.PI);
    ctx.strokeStyle = "#b8e5c6";
    ctx.stroke();
    label(station, "Station", "#b8e5c6", 20);
  }
  if (point(target)) {
    ctx.save();
    ctx.translate(x(target.e), y(target.n));
    ctx.rotate(Math.PI / 4);
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#edcc70";
    ctx.strokeRect(-5, -5, 10, 10);
    ctx.restore();
    label(target, "Rendezvous", "#edcc70", 17);
  }
  if (point(diver)) {
    ctx.beginPath();
    ctx.arc(x(diver.e), y(diver.n), 5, 0, 2 * Math.PI);
    ctx.fillStyle = "#f8a47c";
    ctx.fill();
    label(diver, "Diver", "#ffbb9b", -9);
  }
  if (point(boat)) {
    ctx.save();
    ctx.translate(x(boat.e), y(boat.n));
    ctx.fillStyle = "#7de0b3";
    ctx.strokeStyle = "#123339";
    ctx.lineWidth = 1.5;
    if (Number.isFinite(boat.heading_deg)) {
      ctx.rotate(boat.heading_deg * Math.PI / 180);
      ctx.beginPath();
      ctx.moveTo(0, -10);
      ctx.lineTo(7, 8);
      ctx.lineTo(0, 5);
      ctx.lineTo(-7, 8);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    } else {
      ctx.fillRect(-5, -5, 10, 10);
    }
    ctx.restore();
    label(boat, preview() ? "Boat start" : "Boat", "#9ce6bc", 7);
  }
  const bar = stepSize(70 * scale),
    bx = 12,
    by = h - 26;
  ctx.fillStyle = "#123339";
  ctx.fillRect(bx - 2, by - 15, bar / scale + 8, 20);
  line(ctx, bx, by, bx + bar / scale, by, "#c6dccc", 2);
  ctx.font = "10px Consolas,monospace";
  ctx.fillStyle = "#d4e4dc";
  ctx.fillText(number(bar, bar < 1 ? 1 : 0, " m"), bx, by - 4);
}

function zoom(factor) {
  if (!geometry) return;
  view = {
    e: geometry.e,
    n: geometry.n,
    scale: Math.max(.025, Math.min(1000, geometry.scale * factor))
  };
  drawMap();
}
el("zoom-in").onclick = () => zoom(0.7);
el("zoom-out").onclick = () => zoom(1 / 0.7);
el("fit").onclick = () => {
  view = null;
  drawMap();
};
const map = el("map");
map.onpointerdown = (event) => {
  if (event.button !== 0 || !geometry) return;
  dragging = {
    x: event.clientX,
    y: event.clientY,
    camera: {
      ...geometry
    }
  };
  map.setPointerCapture(event.pointerId);
};
map.onpointermove = (event) => {
  if (!dragging) return;
  const dx = event.clientX - dragging.x,
    dy = event.clientY - dragging.y;
  if (Math.hypot(dx, dy) <= 4 && !dragging.moved) return;
  dragging.moved = true;
  view = {
    e: dragging.camera.e - dx * dragging.camera.scale,
    n: dragging.camera.n + dy * dragging.camera.scale,
    scale: dragging.camera.scale
  };
  drawMap();
};
map.onpointercancel = () => {
  dragging = null;
};
map.onpointerup = async (event) => {
  if (!dragging) return;
  const moved = dragging.moved;
  dragging = null;
  const key = el("placement").value;
  if (moved || !key || !canEdit()) return;
  const rect = map.getBoundingClientRect();
  const e = geometry.e + (event.clientX - rect.left - geometry.w / 2) * geometry.scale;
  const n = geometry.n - (event.clientY - rect.top - geometry.h / 2) * geometry.scale;
  try {
    await applyScenario({
      ...scenario,
      [key + "_e_m"]: Math.round(e),
      [key + "_n_m"]: Math.round(n)
    });
  } catch (error) {
    notice(error.message);
  }
};

function drawChart() {
  const {
    ctx,
    w,
    h
  } = canvasContext("chart");
  if (w < 1 || h < 1) return;
  const [name, unit, get] = series[Number(el("series").value) || 0];
  const seen = availableSamples();
  const data = seen.filter(s => Number.isFinite(s.sim_s) && Number.isFinite(get(s)));
  if (!data.length) {
    display("series-summary", "Awaiting " + name.toLowerCase() + " samples.");
    return;
  }
  const start = data[0].sim_s,
    end = data.at(-1).sim_s;
  const min = -finiteMax(data, s => -get(s)),
    max = finiteMax(data, get);
  const pad = Math.max((max - min) * .12, Math.abs(max) * .015, .1);
  const low = min - pad,
    high = max + pad;
  const x = t => 48 + (t - start) / Math.max(.01, end - start) * (w - 62);
  const y = v => 9 + (high - v) / (high - low) * (h - 40);
  ctx.font = "10px Consolas,monospace";
  ctx.fillStyle = "#50655e";
  for (let i = 0; i < 3; i++) {
    const val = low + (high - low) * i / 2;
    line(ctx, 44, y(val), w - 14, y(val), "#d6e0d7");
    ctx.fillText(number(val, 1), 3, y(val) + 3);
  }
  for (const evt of (replay?.events || snapshot.events || [])) {
    if (evt.t < start || evt.t > end || !Number.isFinite(evt.t)) continue;
    ctx.setLineDash([3, 4]);
    line(ctx, x(evt.t), 8, x(evt.t), h - 28, "#bb906b");
    ctx.setLineDash([]);
  }
  ctx.beginPath();
  seen.forEach((s, i) => {
    if (!Number.isFinite(get(s)) || !Number.isFinite(s.sim_s)) return;
    if (i === 0 || !Number.isFinite(get(seen[i - 1]))) ctx.moveTo(x(s.sim_s), y(get(s)));
    else ctx.lineTo(x(s.sim_s), y(get(s)));
  });
  ctx.strokeStyle = "#216657";
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(x(end), y(get(data.at(-1))), 3, 0, 2 * Math.PI);
  ctx.fillStyle = "#216657";
  ctx.fill();
  ctx.fillStyle = "#50655e";
  ctx.fillText(clock(start), 44, h - 8);
  ctx.fillText(clock(end), w - 49, h - 8);
  display("series-summary", name + " · " + number(get(data.at(-1)), 1, " " + unit) + " · Observed range " + number(min) + "–" + number(max, 1, " " + unit));
}


function replayFrame(index) {
  frameIndex = Math.max(0, Math.min(index, replay.samples.length - 1));
  snapshot = replay.samples[frameIndex];
  el("timeline").value = frameIndex;
  render();
}

function pauseReplay() {
  clearTimeout(replayTicker);
  replayTicker = null;
  display("play", "Play");
}

function advanceReplay() {
  if (!replay || frameIndex >= replay.samples.length - 1) {
    pauseReplay();
    return;
  }
  const dt = replay.samples[frameIndex + 1].sim_s - replay.samples[frameIndex].sim_s;
  replayTicker = setTimeout(() => {
    if (!replay) return;
    replayFrame(frameIndex + 1);
    advanceReplay();
  }, Math.min(2147483647, Math.max(1, dt * 1000)));
}

function showReplayTools(show) {
  for (const id of ["play", "timeline-label", "return"]) el(id).hidden = !show;
}
el("play").onclick = () => {
  if (replayTicker) {
    pauseReplay();
    return;
  }
  if (frameIndex >= replay.samples.length - 1) replayFrame(0);
  display("play", "Pause");
  advanceReplay();
};
el("timeline").oninput = () => {
  pauseReplay();
  replayFrame(Number(el("timeline").value));
};
el("replay-file").onchange = async event => {
  const input = event.target;
  try {
    const file = input.files[0];
    if (file.size > 64 * 1024 * 1024) throw Error("Replay exceeds 64 MiB.");
    const data = JSON.parse(await file.text());
    const withinPlot = p => !p || (point(p) && Math.abs(p.e) < 1e7 && Math.abs(p.n) < 1e7);
    const validSample = (s, i) => s && Number.isFinite(s.sim_s) && typeof s.status === "string" &&
      (i === 0 || s.sim_s >= data.samples[i - 1].sim_s) && [s.boat, s.diver, s.target].every(withinPlot);
    if (data.schema_version !== 1 || !data.scenario || !(data.scenario.exclusion_m >= 0 && data.scenario.exclusion_m <= 1000) ||
      !(data.scenario.uncertainty_m >= 0 && data.scenario.uncertainty_m <= 200) ||
      !Array.isArray(data.samples) || !data.samples.length || !data.samples.every(validSample) ||
      !Array.isArray(data.events) || !data.events.every(e => e && Number.isFinite(e.t) && typeof e.message === "string")) throw Error("Select an exported Remora run with time-ordered samples and events.");
    if (!replay && connected && ["STARTING", "RUNNING"].includes(snapshot.status)) throw Error("Finish or reset the active simulator run first.");
    pauseReplay();
    replay = data;
    view = null;
    el("timeline").max = data.samples.length - 1;
    showReplayTools(true);
    notice("Reading " + file.name + " · Replay controls use recorded simulation time.");
    replayFrame(0);
  } catch (error) {
    notice(error.message);
  } finally {
    input.value = "";
  }
};
el("return").onclick = () => {
  pauseReplay();
  replay = null;
  runId = undefined;
  samples = [];
  snapshot = {};
  scenario = null;
  connected = false;
  view = null;
  showReplayTools(false);
  notice("");
  render();
};
new ResizeObserver(() => {
  drawMap();
  drawChart();
}).observe(el("map").parentElement);
new ResizeObserver(drawChart).observe(el("chart"));
followSimulator();
