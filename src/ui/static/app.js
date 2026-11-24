"use strict";
/* Interfaz del algoritmo de asignación de horarios.
 * Toda la lógica del algoritmo vive en Python; esta página solo edita el escenario,
 * pide la ejecución a /api/run y muestra la traza paso a paso. */

const state = { scenario: null, trace: null, dirty: false, step: 0, student: null, playing: null };

const HOUR_COLORS = ["#8ecae6", "#ffb703", "#90be6d", "#f4a261", "#cdb4db",
                     "#f28482", "#84a59d", "#ffd6a5", "#a0c4ff", "#bdb2ff", "#caffbf", "#fdffb6"];

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------
function h(tag, props, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "className") el.className = value;
    else if (key === "style") el.style.cssText = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

function svg(tag, attrs, ...children) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  for (const c of children) el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return el;
}

function badge(text, kind) { return h("span", { className: `badge ${kind}` }, text); }

function setStatus(text, kind) {
  const el = document.getElementById("status");
  el.textContent = text;
  el.className = `status ${kind || ""}`;
}

function grid() { return state.trace.grid; }
function hoursPerDay() { return grid().end_hour - grid().start_hour; }
function slotHour(slot) { return grid().start_hour + (slot % hoursPerDay()); }
function slotLabel(slot) {
  const g = grid();
  const text = `${String(slotHour(slot)).padStart(2, "0")}:00`;
  return g.num_days > 1 ? `${g.day_names[Math.floor(slot / hoursPerDay())].slice(0, 3)} ${text}` : text;
}
function hourColor(slot) { return HOUR_COLORS[(slot % hoursPerDay()) % HOUR_COLORS.length]; }
function classById(id) { return state.trace.graph.nodes.find(n => n.id === id); }

// "8-11, 14" <-> [8, 9, 10, 11, 14]; también acepta JSON ({"Lunes": [8, 9]})
function parseHours(text) {
  text = text.trim();
  if (!text) return undefined;
  if (text.startsWith("{") || text.startsWith("[")) return JSON.parse(text);
  const hours = [];
  for (const token of text.split(",").map(t => t.trim()).filter(Boolean)) {
    const m = token.match(/^(\d+)\s*-\s*(\d+)$/);
    if (m) { for (let x = +m[1]; x <= +m[2]; x++) hours.push(x); }
    else if (/^\d+$/.test(token)) hours.push(+token);
    else throw new Error(`Hora no válida: "${token}"`);
  }
  return hours;
}
function formatHours(spec) {
  if (spec === undefined || spec === null) return "";
  if (!Array.isArray(spec)) return JSON.stringify(spec);
  const sorted = [...spec].sort((a, b) => a - b);
  const parts = [];
  for (let i = 0; i < sorted.length; i++) {
    let j = i;
    while (j + 1 < sorted.length && sorted[j + 1] === sorted[j] + 1) j++;
    parts.push(j > i ? `${sorted[i]}-${sorted[j]}` : `${sorted[i]}`);
    i = j;
  }
  return parts.join(", ");
}
// "ALG:3, BD:1" <-> [{class_id: "ALG", priority: 3}, ...]
function parseRequests(text) {
  return text.split(",").map(t => t.trim()).filter(Boolean).map(token => {
    const [cid, prio] = token.split(":").map(x => x.trim());
    if (!cid || !/^\d+$/.test(prio || "")) throw new Error(`Solicitud no válida: "${token}" (use CLASE:prioridad)`);
    return { class_id: cid, priority: +prio };
  });
}
function formatRequests(reqs) { return (reqs || []).map(r => `${r.class_id}:${r.priority}`).join(", "); }

// ---------------------------------------------------------------------------
// Carga y ejecución
// ---------------------------------------------------------------------------
async function init() {
  const info = await (await fetch("/api/scenarios")).json();
  const scenarioSelect = document.getElementById("scenario-select");
  info.scenarios.forEach(name => scenarioSelect.append(h("option", { value: name }, name)));
  const modeSelect = document.getElementById("mode-select");
  const modeNames = { auto: "automático", heuristica: "heurística (DSATUR)", backtracking: "backtracking sin cota",
                      exacto: "ramificación y poda", fuerza_bruta: "fuerza bruta" };
  info.modes.forEach(m => modeSelect.append(h("option", { value: m }, modeNames[m] || m)));
  modeSelect.value = info.default_mode;

  scenarioSelect.addEventListener("change", () => loadScenario(scenarioSelect.value));
  modeSelect.addEventListener("change", run);
  document.getElementById("run-button").addEventListener("click", run);
  document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => showTab(tab.dataset.tab)));
  await loadScenario(info.scenarios[0]);
}

function showTab(name) {
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".panel").forEach(p => p.classList.toggle("active", p.id === `tab-${name}`));
}

async function loadScenario(name) {
  const res = await fetch(`/api/scenario?name=${encodeURIComponent(name)}`);
  state.scenario = await res.json();
  state.student = null;
  renderData();
  await run();
}

async function run() {
  stopPlaying();
  setStatus("Ejecutando…", "");
  const mode = document.getElementById("mode-select").value;
  const res = await fetch("/api/run", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario: state.scenario, mode }),
  });
  const data = await res.json();
  if (!res.ok) { setStatus(`No se pudo ejecutar: ${data.error}`, "error"); return; }
  state.trace = data;
  state.dirty = false;
  state.step = data.phase1.dsatur_steps.length;
  if (!state.student || !data.phase2.dp[state.student]) state.student = Object.keys(data.phase2.dp)[0] || null;
  const m = data.result.metrics;
  setStatus(`Listo: ${m.scheduled_classes}/${m.total_classes} clases programadas · ${m.attended_requests}/${m.total_requests} ` +
            `solicitudes atendidas (${m.coverage_percent}%) · ${m.violations_total} incumplimientos de R1-R10`, "ok");
  renderGraph(); renderPhase1(); renderPhase2(); renderResults();
}

function markDirty() {
  state.dirty = true;
  setStatus("Datos modificados: pulse Ejecutar para recalcular.", "dirty");
}

// ---------------------------------------------------------------------------
// 1. Datos (tablas editables)
// ---------------------------------------------------------------------------
const TABLES = [
  { key: "rooms", title: "Salones", blank: () => ({ id: "AULA-NUEVA", name: "Salón nuevo", capacity: 30 }), cols: [
    { key: "id", label: "Id" }, { key: "name", label: "Nombre" }, { key: "capacity", label: "Capacidad", type: "int" },
    { key: "room_type", label: "Tipo" }, { key: "availability", label: "Disponibilidad (horas)", type: "hours" }] },
  { key: "professors", title: "Profesores", blank: () => ({ id: "PROF-NUEVO", name: "Profesor nuevo" }), cols: [
    { key: "id", label: "Id" }, { key: "name", label: "Nombre" },
    { key: "availability", label: "Disponibilidad (horas)", type: "hours" }, { key: "max_hours", label: "Máx. horas", type: "int" }] },
  { key: "classes", title: "Clases", blank: () => ({ id: "NUEVA", professor_id: "", capacity: 20, duration_hours: 1 }), cols: [
    { key: "id", label: "Id" }, { key: "course_name", label: "Nombre" }, { key: "professor_id", label: "Profesor" },
    { key: "capacity", label: "Cupo", type: "int" }, { key: "duration_hours", label: "Horas", type: "int" },
    { key: "allowed_starts", label: "Horas de inicio permitidas", type: "hours" },
    { key: "required_room_type", label: "Tipo de salón" }] },
  { key: "students", title: "Estudiantes", blank: () => ({ id: "EST-NUEVO", name: "Estudiante nuevo", requests: [] }), cols: [
    { key: "id", label: "Id" }, { key: "name", label: "Nombre" },
    { key: "requests", label: "Solicitudes (CLASE:prioridad, 3 = más alta)", type: "requests" },
    { key: "availability", label: "Disponibilidad (horas)", type: "hours" }] },
];

function renderData() {
  const panel = document.getElementById("tab-datos");
  panel.replaceChildren();
  const sc = state.scenario;
  panel.append(h("div", { className: "card explain" },
    h("h2", {}, sc.metadata?.name || "Escenario"),
    h("p", {}, sc.metadata?.description || ""),
    sc.expected?.description ? h("p", {}, h("strong", {}, "Resultado esperado: "), sc.expected.description) : null,
    h("p", { className: "muted" }, "Puede cambiar cualquier dato y pulsar Ejecutar. Horas: \"8-11, 14\". " +
      "Solicitudes: \"ALG:3, BD:1\". Un campo de horas vacío significa toda la jornada.")));

  const params = sc.parameters || (sc.parameters = {});
  panel.append(h("div", { className: "card" }, h("h2", {}, "Jornada"),
    h("div", { className: "toolbar" },
      ...[["num_days", "Días", 1], ["start_hour", "Hora inicial", 8], ["end_hour", "Hora final", 18]].map(([key, label, def]) =>
        h("label", {}, `${label} `, h("input", { type: "number", value: params[key] ?? def, style: "width:5rem",
          oninput: e => { params[key] = +e.target.value; markDirty(); } }))))));

  for (const table of TABLES) panel.append(renderEditableTable(table));

  const textarea = h("textarea", {}, JSON.stringify(sc, null, 2));
  panel.append(h("details", { className: "card" }, h("summary", {}, "Editar el escenario como JSON"),
    textarea,
    h("div", { className: "toolbar" }, h("button", { onclick: () => {
      try { state.scenario = JSON.parse(textarea.value); renderData(); markDirty(); }
      catch (err) { setStatus(`JSON no válido: ${err.message}`, "error"); }
    } }, "Aplicar JSON"))));
}

function renderEditableTable(table) {
  const rows = state.scenario[table.key] || (state.scenario[table.key] = []);
  const body = h("tbody");
  rows.forEach((row, index) => {
    const cells = table.cols.map(col => {
      let value = row[col.key];
      if (col.type === "hours") value = formatHours(value);
      else if (col.type === "requests") value = formatRequests(value);
      const input = h("input", { value: value ?? "" });
      input.addEventListener("change", () => {
        try {
          const raw = input.value;
          let parsed;
          if (col.type === "int") parsed = raw.trim() === "" ? undefined : parseInt(raw, 10);
          else if (col.type === "hours") parsed = parseHours(raw);
          else if (col.type === "requests") parsed = parseRequests(raw);
          else parsed = raw.trim() === "" ? undefined : raw.trim();
          if (parsed === undefined) delete row[col.key]; else row[col.key] = parsed;
          input.style.borderColor = "";
          markDirty();
        } catch (err) {
          input.style.borderColor = "var(--bad)";
          setStatus(err.message, "error");
        }
      });
      return h("td", {}, input);
    });
    cells.push(h("td", {}, h("button", { className: "small", title: "Eliminar fila",
      onclick: () => { rows.splice(index, 1); renderData(); markDirty(); } }, "✕")));
    body.append(h("tr", {}, ...cells));
  });
  return h("div", { className: "card" },
    h("div", { className: "toolbar" }, h("h2", { style: "margin:0" }, `${table.title} (${rows.length})`),
      h("button", { className: "small", onclick: () => { rows.push(table.blank()); renderData(); markDirty(); } }, "+ Agregar")),
    h("div", { style: "overflow-x:auto" }, h("table", {},
      h("thead", {}, h("tr", {}, ...table.cols.map(c => h("th", {}, c.label)), h("th", {}, ""))), body)));
}

// ---------------------------------------------------------------------------
// 2. Grafo de conflictos coloreado
// ---------------------------------------------------------------------------
function renderGraph() {
  const panel = document.getElementById("tab-grafo");
  panel.replaceChildren();
  const { nodes, edges, stats } = state.trace.graph;
  const W = 680, H = 560, cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 - 70;
  const pos = {};
  nodes.forEach((n, i) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * i) / Math.max(1, nodes.length);
    pos[n.id] = { x: cx + R * Math.cos(angle), y: cy + R * Math.sin(angle) };
  });
  const maxW = Math.max(1, ...edges.filter(e => !e.hard).map(e => e.weight));
  const canvas = svg("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}` });
  const info = h("div", {}, h("p", { className: "muted" }, "Haga clic en una clase para ver sus conflictos."));

  for (const e of edges) {
    const a = pos[e.u], b = pos[e.v];
    const line = svg("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y,
      stroke: e.hard ? "#b3261e" : "#8a96a3", "stroke-width": e.hard ? 3 : 1 + 6 * e.weight / maxW,
      "stroke-opacity": e.hard ? 0.9 : 0.45, "stroke-dasharray": e.hard ? "" : "" , "data-u": e.u, "data-v": e.v });
    line.append(svg("title", {}, e.hard ? `${e.u} – ${e.v}: mismo profesor (no pueden cruzarse)`
                                        : `${e.u} – ${e.v}: peso ${e.weight} (estudiantes que piden ambas)`));
    canvas.append(line);
  }
  for (const n of nodes) {
    const p = pos[n.id];
    const scheduled = n.slot !== null;
    const group = svg("g", { style: "cursor:pointer" });
    group.append(svg("circle", { cx: p.x, cy: p.y, r: 30, fill: scheduled ? hourColor(n.slot) : "#fff",
      stroke: scheduled ? "#1d232b" : "#b3261e", "stroke-width": scheduled ? 1.2 : 2, "stroke-dasharray": scheduled ? "" : "5 3" }));
    group.append(svg("text", { x: p.x, y: p.y + 4, "text-anchor": "middle", "font-size": 12, "font-weight": 700 }, n.id));
    group.append(svg("text", { x: p.x, y: p.y + 46, "text-anchor": "middle", "font-size": 11, fill: "#5d6875" },
      scheduled ? `${slotLabel(n.slot)} · ${n.room_id}` : "sin programar"));
    group.addEventListener("click", () => showNodeInfo(n, edges, info, canvas));
    canvas.append(group);
  }

  const usedSlots = [...new Set(nodes.filter(n => n.slot !== null).map(n => n.slot % hoursPerDay()))].sort((a, b) => a - b);
  panel.append(h("div", { className: "grid-side" },
    h("div", { className: "card" }, h("h2", {}, "Grafo de conflictos coloreado con las horas"),
      h("div", { className: "graph-wrap" }, canvas),
      h("div", { className: "legend" },
        h("span", {}, h("span", { className: "swatch", style: "background:#b3261e" }), "conflicto duro (mismo profesor)"),
        h("span", {}, h("span", { className: "swatch", style: "background:#8a96a3" }), "conflicto blando (grosor = peso)"),
        ...usedSlots.map(s => h("span", {}, h("span", { className: "swatch", style: `background:${hourColor(s)}` }),
          `${grid().start_hour + s}:00`)))),
    h("div", {},
      h("div", { className: "card explain" }, h("h2", {}, "Cómo leer el grafo"),
        h("p", {}, "Cada vértice es una clase. Una arista roja une clases del mismo profesor: no pueden ir a la misma hora. " +
          "Una arista gris une clases que algún estudiante pidió juntas; su peso es la suma de min(prioridad_a, prioridad_b)."),
        h("p", {}, "Ubicar las clases equivale a colorear el grafo usando las horas como colores: por eso el problema " +
          "es NP-difícil (se reduce desde k-coloración). El color de cada vértice es la hora que recibió.")),
      h("div", { className: "card" }, h("h2", {}, "Estadísticas"),
        h("ul", { className: "list" },
          h("li", {}, `${stats.vertices} vértices, ${stats.total_edges} aristas`),
          h("li", {}, `${stats.hard_edges} duras y ${stats.soft_edges} blandas`),
          h("li", {}, `densidad ${stats.density}`))),
      h("div", { className: "card" }, h("h2", {}, "Clase seleccionada"), info))));
}

function showNodeInfo(node, edges, info, canvas) {
  canvas.querySelectorAll("line").forEach(l => {
    const touches = l.dataset.u === node.id || l.dataset.v === node.id;
    l.setAttribute("stroke-opacity", touches ? 1 : 0.08);
  });
  const neighbors = edges.filter(e => e.u === node.id || e.v === node.id)
    .map(e => ({ id: e.u === node.id ? e.v : e.u, hard: e.hard, weight: e.weight }));
  info.replaceChildren(
    h("p", {}, h("strong", {}, `${node.id} · ${node.name}`)),
    h("p", { className: "muted" }, `${node.professor_id} · ${node.duration} h · demanda ${node.demand} · cupo ${node.capacity}`),
    h("p", {}, node.slot !== null ? `Programada ${slotLabel(node.slot)} en ${node.room_id}` : "Sin programar"),
    h("ul", { className: "list" }, ...neighbors.map(n => h("li", {},
      n.hard ? badge("duro", "bad") : badge(`peso ${n.weight}`, "muted"), ` ${n.id}`))),
    h("button", { className: "small", onclick: () => canvas.querySelectorAll("line").forEach(l =>
      l.setAttribute("stroke-opacity", l.getAttribute("stroke") === "#b3261e" ? 0.9 : 0.45)) }, "Ver todo"));
}

// ---------------------------------------------------------------------------
// Horario: salones x horas
// ---------------------------------------------------------------------------
function renderTimetable(placements, highlightId) {
  const g = grid(), total = g.num_days * hoursPerDay();
  const header = h("tr", {}, h("th", {}, "Salón"), ...Array.from({ length: total }, (_, s) => h("th", {}, slotLabel(s))));
  const body = h("tbody");
  for (const room of state.trace.rooms) {
    const available = new Set(room.available_slots);
    const mine = placements.filter(p => p.room_id === room.id);
    const row = h("tr", {}, h("td", { className: "room" }, `${room.id} `, h("span", { className: "muted" }, `(${room.capacity})`)));
    for (let s = 0; s < total;) {
      const p = mine.find(x => x.slot === s);
      if (p) {
        row.append(h("td", { colspan: p.duration },
          h("div", { className: `cell-class${p.class_id === highlightId ? " new" : ""}`, style: `background:${hourColor(p.slot)}`,
            title: `${p.class_id} ${slotLabel(p.slot)}` }, p.class_id)));
        s += p.duration;
      } else {
        row.append(h("td", {}, available.has(s) ? "" : h("div", { className: "cell-class blocked", title: "salón no disponible" }, "—")));
        s += 1;
      }
    }
    body.append(row);
  }
  return h("div", { className: "timetable" }, h("table", {}, h("thead", {}, header), body));
}

function finalPlacements() {
  return state.trace.graph.nodes.filter(n => n.slot !== null)
    .map(n => ({ class_id: n.id, slot: n.slot, room_id: n.room_id, duration: n.duration }));
}

// ---------------------------------------------------------------------------
// 3. Fase 1: DSATUR paso a paso y búsqueda exacta
// ---------------------------------------------------------------------------
function renderPhase1() {
  const panel = document.getElementById("tab-fase1");
  panel.replaceChildren();
  const p1 = state.trace.phase1;
  const modeText = { heuristica: "heurística DSATUR", exacto: "ramificación y poda (exacto)",
                     backtracking: "backtracking sin cota", fuerza_bruta: "fuerza bruta" }[p1.mode];
  const search = p1.search || {};
  panel.append(h("div", { className: "card explain" },
    h("h2", {}, `Estrategia usada: ${modeText}${p1.requested_mode === "auto" ? " (elegida automáticamente)" : ""}`),
    h("p", {}, "Costo que se minimiza: ", h("span", { className: "formula" },
      "BASE · clases sin programar + prioridad de las no programadas + Σ pesos de cruces")),
    h("p", {}, `Costo con DSATUR: ${p1.heuristic_cost.total} · costo final: ${p1.cost.total}`,
      p1.optimal === true ? " · " : "", p1.optimal === true ? badge("óptimo probado", "ok") : "",
      p1.optimal === false ? badge("mejor hallado (límite de nodos)", "warn") : ""),
    search.nodes !== undefined ? h("p", {}, `Búsqueda: ${search.nodes} nodos visitados, ${search.pruned_by_bound} podados por cota, ` +
      `${search.improvements} mejoras, ${search.room_reassignments} reacomodos de salones.`) : null,
    search.leaves !== undefined ? h("p", {}, `Fuerza bruta: ${search.leaves.toLocaleString("es")} combinaciones revisadas, ` +
      `${search.valid_leaves.toLocaleString("es")} válidas.`) : null));

  // DSATUR paso a paso
  const steps = p1.dsatur_steps;
  const k = Math.min(state.step, steps.length);
  const placed = steps.slice(0, k).filter(s => s.result === "programada").map(s => ({
    class_id: s.class_id, slot: s.slot, room_id: s.room_id, duration: classById(s.class_id).duration }));
  const current = k > 0 ? steps[k - 1] : null;
  const go = n => { stopPlaying(); state.step = Math.max(0, Math.min(steps.length, n)); renderPhase1(); };
  const playButton = h("button", { onclick: () => togglePlay(steps.length) }, state.playing ? "⏸ Pausa" : "▶ Reproducir");

  panel.append(h("div", { className: "card" },
    h("h2", {}, "DSATUR paso a paso"),
    h("p", { className: "muted" }, "En cada paso se toma la clase con menos horas disponibles (la más restringida) y se le da " +
      "la hora con menos cruces y el salón más pequeño que le sirve. No retrocede."),
    h("div", { className: "stepper" },
      h("button", { onclick: () => go(0) }, "⏮"), h("button", { onclick: () => go(k - 1) }, "◀ Anterior"),
      h("button", { onclick: () => go(k + 1) }, "Siguiente ▶"), h("button", { onclick: () => go(steps.length) }, "⏭"),
      playButton, h("span", { className: "counter" }, `paso ${k} de ${steps.length}`)),
    h("div", { className: "grid2" },
      h("div", {}, current ? renderDsaturStep(current) : h("p", { className: "muted" }, "Pulse Siguiente para empezar.")),
      h("div", {}, h("h3", {}, "Orden de selección"), h("ol", { className: "list" },
        ...steps.map((s, i) => h("li", { style: i === k - 1 ? "font-weight:700" : (i >= k ? "color:#9aa5b1" : "") },
          `${s.class_id} → `, s.result === "programada" ? `${s.time} en ${s.room_id}` : badge("sin programar", "bad")))))),
    h("h3", {}, "Horario después de este paso"),
    renderTimetable(placed, current?.class_id)));

  // Búsqueda exacta
  if (p1.search_trace && p1.search_trace.length) {
    const colors = { "podada": "warn", "mejor solución": "ok", "hoja": "muted", "explorada": "info" };
    panel.append(h("div", { className: "card" },
      h("h2", {}, "Árbol de búsqueda (ramificación y poda)"),
      h("p", { className: "muted" }, `Orden de las clases (un nivel por clase): ${p1.search_order.join(" → ")}. ` +
        "Cada línea es un nodo: la decisión tomada, el costo acumulado y la cota (costo + mínimo de lo que falta). " +
        "Si la cota alcanza a la mejor solución conocida, la rama se poda."),
      search.nodes > p1.search_trace.length ? h("p", { className: "muted" },
        `Se muestran los primeros ${p1.search_trace.length} de ${search.nodes} nodos.`) : null,
      h("div", { className: "tree" }, ...p1.search_trace.map(node => h("div", { style: `padding-left:${node.depth * 18}px` },
        node.class_id ? `${node.class_id} = ${node.choice}` : "raíz",
        `  costo ${node.cost}`, node.bound !== undefined ? `  cota ${node.bound}` : "",
        node.best_known !== null ? `  mejor ${node.best_known}  ` : "  ",
        badge(node.status, colors[node.status] || "muted"))))));
  }

  panel.append(h("div", { className: "card" }, h("h2", {}, "Programación final de la fase 1"),
    renderTimetable(finalPlacements(), null)));
}

function renderDsaturStep(step) {
  return h("div", {},
    h("h3", {}, `Clase elegida: ${step.class_id}`),
    h("p", {}, `Horas disponibles: ${step.available_starts} · horas bloqueadas por vecinos blandos: ${step.soft_saturation}`),
    h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Hora"), h("th", {}, "Estado"), h("th", { className: "num" }, "Costo cruces"),
      h("th", {}, "Cruza con"), h("th", {}, "Salón"))),
      h("tbody", {}, ...(step.candidates || []).map(c => h("tr", { className: step.slot === c.slot ? "highlight" : (c.status !== "posible" ? "dim" : "") },
        h("td", {}, c.time), h("td", {}, c.status === "posible" ? badge("posible", "ok") : badge(c.status, "muted")),
        h("td", { className: "num" }, c.penalty ?? "—"), h("td", {}, (c.crosses || []).join(", ") || "—"),
        h("td", {}, c.room_id || "—"))))),
    h("p", {}, step.result === "programada" ? `Resultado: ${step.time} en ${step.room_id}`
      : h("span", {}, "Resultado: ", badge("sin programar: no hay hora y salón válidos", "bad"))));
}

function togglePlay(total) {
  if (state.playing) { stopPlaying(); renderPhase1(); return; }
  if (state.step >= total) state.step = 0;
  state.playing = setInterval(() => {
    if (state.step >= total) { stopPlaying(); renderPhase1(); return; }
    state.step += 1;
    renderPhase1();
  }, 1100);
  renderPhase1();
}
function stopPlaying() { if (state.playing) { clearInterval(state.playing); state.playing = null; } }

// ---------------------------------------------------------------------------
// 4. Fase 2: DP por estudiante
// ---------------------------------------------------------------------------
function renderPhase2() {
  const panel = document.getElementById("tab-fase2");
  panel.replaceChildren();
  const p2 = state.trace.phase2;
  const schedules = state.trace.result.student_schedule;
  const N = p2.total_requests;

  panel.append(h("div", { className: "card explain" },
    h("h2", {}, "Programación dinámica: selección de intervalos ponderados"),
    h("p", {}, "Con las horas ya fijas, las clases que pidió un estudiante son intervalos. Se ordenan por hora de fin " +
      "(Θ(n log n)), se calcula p(j) con búsqueda binaria (Θ(log n)) y se llena la tabla:"),
    h("p", {}, h("span", { className: "formula" }, "OPT[j] = max( OPT[j−1] , w_j + OPT[p(j)] )")),
    h("p", {}, `Peso de cada solicitud: ${p2.weight_rule}, con N = ${N}. Así la DP maximiza la suma de prioridades ` +
      "y, a igual suma, el número de clases."),
    h("p", {}, `Reparto de cupos: ${p2.stats.rounds} ronda(s), ${p2.stats.rejections} cupo(s) negado(s), ` +
      `${p2.stats.fill_improvements} mejora(s) en el relleno final.`)));

  const list = h("div", { className: "card" }, h("h2", {}, "Estudiantes"),
    h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Estudiante"), h("th", { className: "num" }, "Atendidas"))),
      h("tbody", {}, ...Object.values(schedules).map(s => h("tr", {
        className: s.student_id === state.student ? "highlight" : "", style: "cursor:pointer",
        onclick: () => { state.student = s.student_id; renderPhase2(); } },
        h("td", {}, s.student_id), h("td", { className: "num" }, `${s.enrolled_classes.length}/${s.requests.length}`))))));

  const detail = h("div", {});
  const sid = state.student;
  if (sid && schedules[sid]) {
    const dp = p2.dp[sid];
    const sched = schedules[sid];
    detail.append(h("div", { className: "card" }, h("h2", {}, `Tabla de la DP de ${sid}`),
      dp && dp.items.length ? renderDpTable(dp) : h("p", { className: "muted" }, "No tuvo clases candidatas en la DP."),
      h("h3", {}, "Horario resultante"),
      h("ul", { className: "list" }, ...sched.enrolled_classes.map(c =>
        h("li", {}, `${c.class_id} (prioridad ${c.priority}) · ${c.time_str} · ${c.room_id}`))),
      sched.pending_requests.length ? h("h3", {}, "Solicitudes pendientes") : null,
      sched.pending_requests.length ? h("ul", { className: "list" }, ...sched.pending_requests.map(p =>
        h("li", {}, `${p.class_id} (prioridad ${p.priority}): `, badge(p.reason, "warn")))) : null));
  }
  if (p2.rejections.length) {
    detail.append(h("div", { className: "card" }, h("h2", {}, "Cupos negados durante el reparto"),
      h("p", { className: "muted" }, "Cuando una clase recibe más estudiantes que su cupo, se queda con los de mayor prioridad; " +
        "los demás vuelven a correr su DP sin esa clase."),
      h("ul", { className: "list" }, ...p2.rejections.map(r =>
        h("li", {}, `Ronda ${r.round}: ${r.student_id} sin cupo en ${r.class_id} (prioridad ${r.priority})`)))));
  }
  panel.append(h("div", { className: "grid-side", style: "grid-template-columns:minmax(220px,1fr) minmax(0,3fr)" }, list, detail));
}

function renderDpTable(dp) {
  const rows = [h("tr", { className: "dim" }, h("td", {}, "0"), h("td", {}, "—"), h("td", {}, ""), h("td", {}, ""),
    h("td", { className: "num" }, ""), h("td", { className: "num" }, ""), h("td", {}, "caso base"), h("td", { className: "num" }, "0"), h("td", {}, ""))];
  dp.items.forEach((it, idx) => {
    const j = idx + 1, p = dp.p[j];
    const skip = dp.opt[j - 1], take = it.weight + dp.opt[p];
    const pLabel = p === 0 ? "0" : `${p} (${dp.items[p - 1].class_id})`;
    rows.push(h("tr", { className: dp.chosen.includes(it.class_id) ? "highlight" : "" },
      h("td", {}, j), h("td", {}, it.class_id), h("td", {}, it.time), h("td", {}, it.priority),
      h("td", { className: "num" }, it.weight), h("td", { className: "num" }, pLabel),
      h("td", { className: "mono" }, `max(${skip}, ${it.weight} + ${dp.opt[p]} = ${take})`),
      h("td", { className: "num" }, dp.opt[j]),
      h("td", {}, dp.chosen.includes(it.class_id) ? badge("tomada", "ok") : "")));
  });
  return h("div", {}, h("table", {},
    h("thead", {}, h("tr", {}, h("th", {}, "j"), h("th", {}, "Clase"), h("th", {}, "Horario"), h("th", {}, "Prioridad"),
      h("th", { className: "num" }, "w_j"), h("th", { className: "num" }, "p(j)"), h("th", {}, "OPT[j−1] vs w_j + OPT[p(j)]"),
      h("th", { className: "num" }, "OPT[j]"), h("th", {}, ""))),
    h("tbody", {}, ...rows)),
    h("p", { className: "muted" }, `Mejor suma de pesos: ${dp.opt[dp.opt.length - 1]}. ` +
      "La solución se reconstruye desde la última fila: si tomar j es al menos tan bueno, se toma y se salta a p(j)."));
}

// ---------------------------------------------------------------------------
// 5. Resultados
// ---------------------------------------------------------------------------
function renderResults() {
  const panel = document.getElementById("tab-resultados");
  panel.replaceChildren();
  const { metrics: m, verification: v, class_schedule: classes } = state.trace.result;
  const kpi = (label, value, sub) => h("div", { className: "kpi" }, h("div", { className: "label" }, label),
    h("div", { className: "value" }, value), sub ? h("div", { className: "sub" }, sub) : null);

  panel.append(h("div", { className: "kpis" },
    kpi("Cobertura", `${m.coverage_percent}%`, `${m.attended_requests} de ${m.total_requests} solicitudes`),
    kpi("Satisfacción de prioridades", `${m.priority_satisfaction_percent}%`, `${m.attended_priority_sum} de ${m.received_priority_sum}`),
    kpi("Incumplimientos R1-R10", m.violations_total, "verificador independiente"),
    kpi("Clases programadas", `${m.scheduled_classes}/${m.total_classes}`,
      m.unscheduled_class_ids.length ? `sin programar: ${m.unscheduled_class_ids.join(", ")}` : "todas")));

  const levels = Object.entries(m.by_priority).sort((a, b) => b[0] - a[0]).map(([level, d]) => h("tr", {},
    h("td", {}, `Prioridad ${level}`), h("td", { className: "num" }, `${d.attended}/${d.requests}`),
    h("td", { style: "width:45%" }, h("div", { className: "bar" }, h("span", { style: `width:${d.percent}%` }))),
    h("td", { className: "num" }, `${d.percent}%`)));
  const reasons = Object.entries(m.pending_by_reason).map(([r, n]) => h("li", {}, `${r}: ${n}`));

  const rules = Object.entries(v.by_rule).map(([rule, count]) => h("tr", {},
    h("td", {}, rule), h("td", { className: "num" }, count), h("td", {}, count ? badge("incumple", "bad") : badge("cumple", "ok"))));

  panel.append(h("div", { className: "grid2" },
    h("div", { className: "card" }, h("h2", {}, "Atención por nivel de prioridad"), h("table", {}, h("tbody", {}, ...levels)),
      h("h3", {}, "Pendientes por motivo"), reasons.length ? h("ul", { className: "list" }, ...reasons) : h("p", { className: "muted" }, "Ninguna.")),
    h("div", { className: "card" }, h("h2", {}, "Restricciones obligatorias"), h("table", {}, h("tbody", {}, ...rules)),
      ...v.violations.map(x => h("p", {}, badge(x.rule, "bad"), ` ${x.message}`)))));

  if (state.trace.expectations.length) {
    const optimal = state.trace.phase1.optimal === true;
    panel.append(h("div", { className: "card" }, h("h2", {}, "Comparación con el resultado esperado"),
      h("table", {}, h("tbody", {}, ...state.trace.expectations.map(c => h("tr", {},
        h("td", {}, c.passed ? badge("✓", "ok") : (c.only_if_optimal && !optimal ? badge("no exigido", "muted") : badge("✗", "bad"))),
        h("td", {}, c.name), h("td", { className: "muted" }, c.detail, c.only_if_optimal ? " · requiere fase 1 exacta" : "")))))));
  }

  panel.append(h("div", { className: "card" }, h("h2", {}, "Programación de clases"),
    h("table", {}, h("thead", {}, h("tr", {}, ...["Clase", "Nombre", "Horario", "Salón", "Profesor", "Inscritos", "Cupo", "Demanda"].map(t => h("th", {}, t)))),
      h("tbody", {}, ...Object.values(classes).map(c => h("tr", { className: c.is_scheduled ? "" : "dim" },
        h("td", {}, c.class_id), h("td", {}, c.course_name), h("td", {}, c.time_str), h("td", {}, c.room_id || "—"),
        h("td", {}, c.professor_name), h("td", { className: "num" }, c.enrolled_count), h("td", { className: "num" }, c.capacity),
        h("td", { className: "num" }, c.demand)))))));
}

init().catch(err => setStatus(`Error al iniciar: ${err.message}`, "error"));
