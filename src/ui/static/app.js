"use strict";
/* Interfaz del algoritmo de asignación de horarios.
 * Toda la lógica del algoritmo vive en Python; esta página solo edita el escenario,
 * pide la ejecución a /api/run y muestra la traza paso a paso. */

const state = { scenario: null, trace: null, dirty: false, step: 0, student: null, playing: null, saveBar: null };

const HOUR_COLORS = ["#8ecae6", "#ffb703", "#90be6d", "#f4a261", "#cdb4db",
                     "#f28482", "#84a59d", "#ffd6a5", "#a0c4ff", "#bdb2ff", "#caffbf", "#fdffb6"];

// Las cinco secciones de la barra lateral, en el orden en que corre el algoritmo.
const SECTIONS = [
  { id: "datos", title: "Datos", icon: "tabla" },
  { id: "grafo", title: "Grafo", icon: "grafo" },
  { id: "fase1", title: "Ubicar clases", icon: "calendario" },
  { id: "fase2", title: "Inscribir", icon: "usuarios" },
  { id: "resultados", title: "Resultados", icon: "grafica" },
];

// Íconos de línea de un solo trazo (24×24, trazo 1.75, puntas redondas); toman el color del texto.
const ICONS = {
  menu: ["M4 6h16", "M4 12h16", "M4 18h16"],
  cerrar: ["M6 6l12 12", "M18 6 6 18"],
  mas: ["M12 5v14", "M5 12h14"],
  izquierda: ["m15 18-6-6 6-6"],
  derecha: ["m9 18 6-6-6-6"],
  inicio: ["m11 18-6-6 6-6", "m19 18-6-6 6-6"],
  fin: ["m5 18 6-6-6-6", "m13 18 6-6-6-6"],
  reproducir: ["M7 4v16l13-8Z"],
  pausa: ["M8 5v14", "M16 5v14"],
  tabla: ["M4 5h16v14H4Z", "M4 10h16", "M10 10v9"],
  grafo: ["M6 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z", "M18 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
          "M12 21a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z", "M8 6h8", "M7 7.8l4 9.4", "M17 7.8l-4 9.4"],
  calendario: ["M8 2v4", "M16 2v4", "M3 9h18", "M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z"],
  usuarios: ["M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2", "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z",
             "M22 21v-2a4 4 0 0 0-3-3.9", "M16 3.1a4 4 0 0 1 0 7.8"],
  grafica: ["M3 3v18h18", "M7 15l4-4 3 3 5-6"],
  ejecutar: ["M5 3v18l15-9Z"],
};

// Pseudocódigo de cada algoritmo, tal como lo hace el código en Python.
const PSEUDO_DSATUR = `mientras haya clases sin decidir:
    c ← la clase con menos horas disponibles          # la más restringida
    para cada hora h permitida para c:
        si el profesor de c está libre en h:
            costo(h) ← Σ pesos de las clases vecinas ya ubicadas que se cruzan con h
    si no hay ninguna (hora, salón) válida:
        c queda sin programar
    si no:
        ubicar c en la hora de menor costo y en el salón que mejor le sirve`;

const PSEUDO_BB = `mejor ← solución de DSATUR                           # cota inicial
buscar(nivel = 0, costo = 0)

buscar(nivel, costo):
    si costo + cota_inferior(clases que faltan) ≥ costo(mejor):
        podar                                          # esta rama no puede mejorar
    si nivel = M:
        mejor ← solución actual;  volver
    c ← clases[nivel]                                  # las más restringidas primero
    para cada hora h válida para c, de la más barata a la más cara:
        ubicar c en h con un salón libre
        buscar(nivel + 1, costo + cruces(c, h))
        quitar c                                       # retroceder
    buscar(nivel + 1, costo + costo_sin_programar(c))  # última opción`;

const PSEUDO_BT = `mejor ← solución de DSATUR
buscar(nivel = 0, costo = 0)

buscar(nivel, costo):
    si nivel = M:
        si costo < costo(mejor): mejor ← solución actual
        volver
    c ← clases[nivel]
    para cada hora h válida para c:                    # poda solo por reglas:
        ubicar c en h con un salón libre               # profesor libre y salón posible
        buscar(nivel + 1, costo + cruces(c, h))
        quitar c                                       # retroceder
    buscar(nivel + 1, costo + costo_sin_programar(c))`;

const PSEUDO_FB = `mejor ← ninguna
para cada combinación de (hora, salón) o "sin programar" de todas las clases:
    si la combinación cumple todas las reglas:
        si costo(combinación) < costo(mejor):
            mejor ← combinación`;

const PSEUDO_DP = `ordenar las clases del estudiante por hora de fin        # Θ(n log n)
para j = 1..n:
    p(j) ← búsqueda binaria: cuántas terminan antes
           de que j empiece                              # Θ(log n)
OPT[0] ← 0
para j = 1..n:
    OPT[j] ← max( OPT[j−1],  w_j + OPT[p(j)] )
j ← n                                                    # reconstruir
mientras j > 0:
    si w_j + OPT[p(j)] ≥ OPT[j−1]:  tomar j;  j ← p(j)
    si no:  j ← j − 1`;

const PSEUDO_REPARTO = `cada estudiante arma su horario con la DP
repetir:
    para cada clase con más inscritos que su cupo:
        se queda con los de mayor prioridad
        (a igual prioridad, el primero de la lista)
        a los demás se les niega esa clase
    los rechazados vuelven a correr su DP sin esa clase
hasta que ninguna clase supere su cupo
ofrecer los cupos libres a quien mejore con ellos`;

const PSEUDO_VERIF = `para cada clase programada:
    revisar duración, jornada, horas permitidas,
    salón disponible y profesor disponible
para cada par de clases que se cruzan:
    mismo salón → incumple;  mismo profesor → incumple
para cada estudiante:
    solo clases que pidió, sin cruces y dentro de cupo
contar incumplimientos                       # O(M² + S·K²)`;

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

function icon(name, size = 16) {
  const el = svg("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
    "stroke-width": 1.75, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true", focusable: "false" });
  for (const d of ICONS[name]) el.append(svg("path", { d }));
  return h("span", { className: "icono-svg" }, el);
}

// Insignia: el estado se lee por la palabra; el punto lo refuerza con su color.
const TONES = { ok: "exito", bad: "peligro", warn: "aviso", info: "info", muted: "neutro" };
function badge(text, kind) { return h("span", { className: "insignia", "data-tono": TONES[kind] || kind }, text); }

function setStatus(text, kind) {
  const tone = { ok: "exito", error: "error", dirty: "advertencia" }[kind] || "";
  document.getElementById("estado-ejecucion").replaceChildren(text ? h("div", { className: `aviso ${tone}` }, text) : "");
}

function pageHeader(sectionId, title, description, ...extra) {
  const index = SECTIONS.findIndex(s => s.id === sectionId);
  return h("div", { className: "encabezado-pagina" },
    h("div", { className: "titulos" },
      h("p", { className: "migas" }, `Paso ${index + 1} de ${SECTIONS.length} · ${state.scenario?.metadata?.name || "escenario"}`),
      h("h2", {}, title, ...extra),
      description ? h("p", {}, description) : null));
}

function pseudocode(text) {
  return h("figure", { className: "pseudocodigo" }, h("figcaption", {}, "Pseudocódigo"), h("pre", {}, text));
}

function panel(title, ...children) {
  return h("section", { className: "panel" }, title ? h("h3", {}, title) : null, ...children);
}

function figure(name, value, note) {
  return h("div", { className: "cifra" }, h("span", { className: "nombre" }, name),
    h("span", { className: "valor" }, value), note ? h("span", { className: "nota" }, note) : null);
}

function table(headers, rows, numericColumns = [], extraClass = "") {
  return h("div", { className: "tabla-contenedor" }, h("table", { className: `tabla ${extraClass}`.trim() },
    h("thead", {}, h("tr", {}, ...headers.map((t, i) => h("th", { className: numericColumns.includes(i) ? "numero" : null }, t)))),
    h("tbody", {}, ...rows)));
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
// Marco: barra lateral, secciones y cajón en pantallas angostas
// ---------------------------------------------------------------------------
function buildShell() {
  document.getElementById("boton-menu").append(icon("menu", 20));
  document.getElementById("boton-cerrar-menu").append(icon("cerrar", 20));
  document.getElementById("run-button").prepend(icon("ejecutar"));
  document.getElementById("menu-secciones").replaceChildren(...SECTIONS.map(s =>
    h("li", {}, h("a", { href: `#/${s.id}`, "data-seccion": s.id, onclick: closeMenu }, icon(s.icon), s.title))));

  document.getElementById("boton-menu").addEventListener("click", openMenu);
  document.getElementById("boton-cerrar-menu").addEventListener("click", closeMenu);
  document.getElementById("fondo-cajon").addEventListener("click", closeMenu);
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeMenu(); });
  window.addEventListener("hashchange", showSection);
  showSection();
}

function currentSection() {
  const id = location.hash.replace(/^#\/?/, "");
  return SECTIONS.some(s => s.id === id) ? id : "datos";
}

function showSection() {
  const id = currentSection();
  for (const s of SECTIONS) document.getElementById(`vista-${s.id}`).hidden = s.id !== id;
  document.querySelectorAll("#menu-secciones a").forEach(a => {
    if (a.dataset.seccion === id) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  document.getElementById("titulo-barra").textContent = `Horarios · ${SECTIONS.find(s => s.id === id).title}`;
}

function openMenu() {
  document.getElementById("marco").classList.add("menu-abierto");
  document.getElementById("fondo-cajon").hidden = false;
  document.getElementById("boton-menu").setAttribute("aria-expanded", "true");
}

function closeMenu() {
  document.getElementById("marco").classList.remove("menu-abierto");
  document.getElementById("fondo-cajon").hidden = true;
  document.getElementById("boton-menu").setAttribute("aria-expanded", "false");
}

// ---------------------------------------------------------------------------
// Carga y ejecución
// ---------------------------------------------------------------------------
async function init() {
  buildShell();
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
  await loadScenario(info.scenarios[0]);
}

async function loadScenario(name) {
  const res = await fetch(`/api/scenario?name=${encodeURIComponent(name)}`);
  state.scenario = await res.json();
  state.student = null;
  state.dirty = false;
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
  if (state.saveBar) state.saveBar.hidden = true;
  state.step = data.phase1.dsatur_steps.length;
  if (!state.student || !data.phase2.dp[state.student]) state.student = Object.keys(data.phase2.dp)[0] || null;
  const m = data.result.metrics;
  setStatus(`Listo: ${m.scheduled_classes}/${m.total_classes} clases programadas · ${m.attended_requests}/${m.total_requests} ` +
            `solicitudes atendidas (${m.coverage_percent}%) · ${m.violations_total} restricciones obligatorias incumplidas`, "ok");
  document.getElementById("resumen-lateral").textContent =
    `${m.attended_requests}/${m.total_requests} solicitudes · ${m.violations_total} restricciones incumplidas`;
  renderGraph(); renderPhase1(); renderPhase2(); renderResults();
}

function markDirty() {
  state.dirty = true;
  if (state.saveBar) state.saveBar.hidden = false;
  setStatus("Datos modificados: pulse Ejecutar para recalcular.", "dirty");
}

// ---------------------------------------------------------------------------
// 1. Datos (tablas editables)
// ---------------------------------------------------------------------------
const HOURS_HINT = "ej. 8-11, 14 · vacío = toda la jornada";

const TABLES = [
  { key: "rooms", title: "Salones", help: "Capacidad, tipo y horas en que se puede usar cada salón.",
    blank: () => ({ id: "AULA-NUEVA", capacity: 30 }), cols: [
    { key: "id", label: "Id" }, { key: "capacity", label: "Capacidad", type: "int" },
    { key: "room_type", label: "Tipo", hint: "ej. laboratorio · vacío = aula" },
    { key: "availability", label: "Disponibilidad (horas)", type: "hours", hint: HOURS_HINT }] },
  { key: "professors", title: "Profesores", help: "Horas en que cada profesor puede dictar clase.",
    blank: () => ({ id: "PROF-NUEVO", name: "Profesor nuevo" }), cols: [
    { key: "id", label: "Id" }, { key: "name", label: "Nombre" },
    { key: "availability", label: "Disponibilidad (horas)", type: "hours", hint: HOURS_HINT }] },
  { key: "classes", title: "Clases", help: "Profesor, cupo, duración y horas de inicio permitidas de cada clase.",
    blank: () => ({ id: "NUEVA", professor_id: "", capacity: 20, duration_hours: 1 }), cols: [
    { key: "id", label: "Id" }, { key: "course_name", label: "Nombre" }, { key: "professor_id", label: "Profesor" },
    { key: "capacity", label: "Cupo", type: "int" }, { key: "duration_hours", label: "Horas", type: "int" },
    { key: "allowed_starts", label: "Horas de inicio permitidas", type: "hours", hint: HOURS_HINT },
    { key: "required_room_type", label: "Tipo de salón", hint: "ej. laboratorio · vacío = cualquiera" }] },
  { key: "students", title: "Estudiantes", help: "Solicitudes de cada estudiante con su prioridad (3 = más alta).",
    blank: () => ({ id: "EST-NUEVO", name: "Estudiante nuevo", requests: [] }), cols: [
    { key: "id", label: "Id" }, { key: "name", label: "Nombre" },
    { key: "requests", label: "Solicitudes", type: "requests", hint: "CLASE:prioridad, ej. ALG:3, BD:1 · 3 = más alta" }] },
];

function renderData() {
  const view = document.getElementById("vista-datos");
  view.replaceChildren();
  const sc = state.scenario;

  view.append(pageHeader("datos", "Datos", "Entradas del problema: jornada, salones, profesores, clases y estudiantes."));

  const blocks = h("div", { className: "pila" });

  const params = sc.parameters || (sc.parameters = {});
  blocks.append(panel("Jornada",
    h("div", { className: "fila-campos" },
      ...[["num_days", "Días de la semana", 1], ["start_hour", "Hora inicial", 8], ["end_hour", "Hora final", 18]].map(([key, label, def]) =>
        h("div", { className: "campo" }, h("label", { for: `jornada-${key}` }, label),
          h("input", { id: `jornada-${key}`, type: "number", value: params[key] ?? def,
            oninput: e => { params[key] = +e.target.value; markDirty(); } })))),
    h("p", { className: "ayuda", style: "margin-top:var(--esp-2)" }, "Días de la semana: 1 programa una sola jornada " +
      "(la versión inicial del diseño); con 5 se programa de lunes a viernes.")));

  for (const t of TABLES) blocks.append(renderEditableTable(t));

  view.append(blocks);

  state.saveBar = h("div", { className: "barra-guardado", hidden: !state.dirty },
    h("span", { className: "estado-guardado" }, "Datos modificados: pulse Ejecutar para recalcular."),
    h("button", { className: "boton", type: "button", onclick: run }, icon("ejecutar"), "Ejecutar"));
  view.append(state.saveBar);
}

function renderEditableTable(t) {
  const rows = state.scenario[t.key] || (state.scenario[t.key] = []);
  const body = h("tbody");
  rows.forEach((row, index) => {
    const cells = t.cols.map(col => {
      let value = row[col.key];
      if (col.type === "hours") value = formatHours(value);
      else if (col.type === "requests") value = formatRequests(value);
      const input = h("input", { className: "control", value: value ?? "", "aria-label": `${col.label} de ${row.id ?? "la fila"}` });
      input.addEventListener("change", () => {
        try {
          const raw = input.value;
          let parsed;
          if (col.type === "int") parsed = raw.trim() === "" ? undefined : parseInt(raw, 10);
          else if (col.type === "hours") parsed = parseHours(raw);
          else if (col.type === "requests") parsed = parseRequests(raw);
          else parsed = raw.trim() === "" ? undefined : raw.trim();
          if (parsed === undefined) delete row[col.key]; else row[col.key] = parsed;
          input.removeAttribute("aria-invalid");
          markDirty();
        } catch (err) {
          input.setAttribute("aria-invalid", "true");
          setStatus(err.message, "error");
        }
      });
      return h("td", {}, input);
    });
    cells.push(h("td", { className: "accion" }, h("button", { className: "boton fantasma icono pequeno", type: "button",
      "aria-label": "Eliminar fila", title: "Eliminar fila",
      onclick: () => { rows.splice(index, 1); renderData(); markDirty(); } }, icon("cerrar"))));
    body.append(h("tr", {}, ...cells));
  });
  return h("section", { className: "panel" },
    h("div", { className: "cabeza-panel" },
      h("div", {}, h("h3", {}, `${t.title} (${rows.length})`), h("p", { className: "ayuda" }, t.help)),
      h("button", { className: "boton secundario pequeno", type: "button",
        onclick: () => { rows.push(t.blank()); renderData(); markDirty(); } }, icon("mas"), "Agregar")),
    h("div", { className: "tabla-contenedor sin-marco", "data-densidad": "compacta", style: "margin-top:var(--esp-3)" },
      h("table", { className: "tabla" },
        h("thead", {}, h("tr", {}, ...t.cols.map(c => h("th", {}, c.label, c.hint ? h("span", { className: "pista-columna" }, c.hint) : null)),
          h("th", {}, h("span", { className: "solo-lectores" }, "Acciones")))),
        body)));
}

// ---------------------------------------------------------------------------
// 2. Grafo de conflictos coloreado (el dibujo del SVG es el mismo)
// ---------------------------------------------------------------------------
function renderGraph() {
  const view = document.getElementById("vista-grafo");
  view.replaceChildren();
  const { nodes, edges, stats } = state.trace.graph;
  const W = 680, H = 560, cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 - 70;
  const pos = {};
  nodes.forEach((n, i) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * i) / Math.max(1, nodes.length);
    pos[n.id] = { x: cx + R * Math.cos(angle), y: cy + R * Math.sin(angle) };
  });
  const maxW = Math.max(1, ...edges.filter(e => !e.hard).map(e => e.weight));
  const canvas = svg("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}` });
  const info = h("div", {}, h("p", { className: "ayuda" }, "Haga clic en una clase para ver sus conflictos."));

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

  view.append(
    pageHeader("grafo", "Grafo de conflictos", "Qué clases no se pueden o no conviene ubicar a la misma hora."),
    h("div", { className: "rejilla lateral-derecha" },
      panel("Grafo",
        h("div", { className: "lienzo-grafo" }, canvas)),
      h("div", { className: "pila" },
        panel(null,
          h("div", { className: "texto-tarjeta" },
            h("p", {}, "Cada círculo es una clase. Su color y el texto de abajo dicen a qué hora y en qué salón quedó; " +
              "si está en blanco y punteado, no se pudo programar."),
            h("p", {}, "Una línea roja une dos clases del mismo profesor. No es un choque: es una regla que dice que esas " +
              "dos clases no pueden ir a la misma hora. Si los dos círculos tienen colores distintos, la regla se cumplió."),
            h("p", {}, "Una línea gris une dos clases que algún estudiante pidió juntas. Conviene que queden a horas " +
              "distintas; entre más gruesa, más prioridad se perdería si se cruzan."),
            h("p", {}, "Ubicar las clases es colorear este grafo usando las horas como colores. Por eso el problema es " +
              "NP-difícil: se reduce desde la k-coloración de grafos."))),
        panel("Estadísticas", h("dl", { className: "datos" },
          h("dt", {}, "Clases (vértices)"), h("dd", {}, stats.vertices),
          h("dt", {}, "Líneas (aristas)"), h("dd", {}, stats.total_edges),
          h("dt", {}, "Rojas (mismo profesor)"), h("dd", {}, stats.hard_edges),
          h("dt", {}, "Grises (estudiantes)"), h("dd", {}, stats.soft_edges))),
        panel("Clase seleccionada", info))));
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
    h("p", { className: "ayuda" }, `${node.professor_id} · ${node.duration} h · demanda ${node.demand} · cupo ${node.capacity}`),
    h("p", { style: "margin:var(--esp-2) 0" }, node.slot !== null ? `Programada ${slotLabel(node.slot)} en ${node.room_id}` : "Sin programar"),
    h("ul", { className: "lista" }, ...neighbors.map(n => h("li", {},
      n.hard ? badge("duro", "bad") : badge(`peso ${n.weight}`, "muted"), ` ${n.id}`))),
    h("button", { className: "boton secundario pequeno", type: "button", style: "margin-top:var(--esp-3)",
      onclick: () => canvas.querySelectorAll("line").forEach(l =>
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
    const row = h("tr", {}, h("td", { className: "salon" }, `${room.id} `, h("span", { className: "tenue" }, `(${room.capacity})`)));
    for (let s = 0; s < total;) {
      const p = mine.find(x => x.slot === s);
      if (p) {
        row.append(h("td", { colspan: p.duration },
          h("div", { className: `celda-clase${p.class_id === highlightId ? " nueva" : ""}`, style: `background:${hourColor(p.slot)}`,
            title: `${p.class_id} ${slotLabel(p.slot)}` }, p.class_id)));
        s += p.duration;
      } else {
        row.append(h("td", {}, available.has(s) ? "" : h("div", { className: "celda-clase bloqueada", title: "salón no disponible" }, "—")));
        s += 1;
      }
    }
    body.append(row);
  }
  return h("div", { className: "horario" }, h("table", {}, h("thead", {}, header), body));
}

function finalPlacements() {
  return state.trace.graph.nodes.filter(n => n.slot !== null)
    .map(n => ({ class_id: n.id, slot: n.slot, room_id: n.room_id, duration: n.duration }));
}

// ---------------------------------------------------------------------------
// 3. Fase 1: DSATUR paso a paso y búsqueda exacta
// ---------------------------------------------------------------------------
function renderPhase1() {
  const view = document.getElementById("vista-fase1");
  view.replaceChildren();
  const p1 = state.trace.phase1;
  const modeText = { heuristica: "heurística DSATUR", exacto: "ramificación y poda (exacto)",
                     backtracking: "backtracking sin cota", fuerza_bruta: "fuerza bruta" }[p1.mode];
  const search = p1.search || {};

  view.append(pageHeader("fase1", "Ubicar clases",
    `Estrategia usada: ${modeText}${p1.requested_mode === "auto" ? " (elegida automáticamente)" : ""}.`,
    p1.optimal === true ? badge("óptimo probado", "ok") : null,
    p1.optimal === false ? badge("mejor hallado (límite de nodos)", "warn") : null));

  // Los puntos de costo solo se muestran cuando la búsqueda mejoró a DSATUR.
  const improved = p1.mode !== "heuristica" && p1.heuristic_cost.total !== p1.cost.total;
  const figures = improved
    ? [figure("Costo con DSATUR", `${p1.heuristic_cost.total} pts`, "menos es mejor"),
       figure("Costo final", `${p1.cost.total} pts`, "la búsqueda lo mejoró")]
    : [];
  if (search.nodes !== undefined) {
    figures.push(figure("Nodos visitados", search.nodes.toLocaleString("es"),
      `${search.improvements} mejoras · ${search.room_reassignments} reacomodos de salones`));
    figures.push(figure("Podados por cota", search.pruned_by_bound.toLocaleString("es")));
  } else if (search.leaves !== undefined) {
    figures.push(figure("Combinaciones revisadas", search.leaves.toLocaleString("es")));
    figures.push(figure("Combinaciones válidas", search.valid_leaves.toLocaleString("es")));
  }

  const blocks = h("div", { className: "pila" },
    h("div", { className: "aviso" }, "Se busca la ubicación con menor costo, medido en puntos (menos es mejor): ",
      h("span", { className: "formula" }, "BASE · clases sin programar + prioridad de las no programadas + Σ pesos de cruces"),
      p1.mode !== "heuristica" && !improved ? h("p", {}, "En este escenario DSATUR ya había encontrado la mejor " +
        "ubicación; la búsqueda solo lo confirmó.") : null),
    figures.length ? h("div", { className: "cifras" }, ...figures) : null);

  // DSATUR paso a paso
  const steps = p1.dsatur_steps;
  const k = Math.min(state.step, steps.length);
  const placed = steps.slice(0, k).filter(s => s.result === "programada").map(s => ({
    class_id: s.class_id, slot: s.slot, room_id: s.room_id, duration: classById(s.class_id).duration }));
  const current = k > 0 ? steps[k - 1] : null;
  const go = n => { stopPlaying(); state.step = Math.max(0, Math.min(steps.length, n)); renderPhase1(); };
  const stepButton = (label, iconName, target) => h("button", { className: "boton secundario pequeno", type: "button",
    onclick: () => go(target) }, icon(iconName), label);

  blocks.append(h("section", { className: "panel" },
    h("h3", {}, "DSATUR paso a paso"),
    h("p", { className: "ayuda", style: "margin-bottom:var(--esp-3)" }, "En cada paso se toma la clase con menos horas " +
      "disponibles (la más restringida) y se le da la hora con menos cruces y el salón que mejor le sirve. No retrocede."),
    pseudocode(PSEUDO_DSATUR),
    h("div", { className: "pasos" },
      stepButton("Inicio", "inicio", 0), stepButton("Anterior", "izquierda", k - 1),
      stepButton("Siguiente", "derecha", k + 1), stepButton("Final", "fin", steps.length),
      h("button", { className: "boton secundario pequeno", type: "button", "aria-pressed": state.playing ? "true" : "false",
        onclick: () => togglePlay(steps.length) }, icon(state.playing ? "pausa" : "reproducir"), state.playing ? "Pausa" : "Reproducir"),
      h("span", { className: "contador" }, `paso ${k} de ${steps.length}`)),
    h("div", { className: "rejilla lateral-derecha" },
      h("div", {}, current ? renderDsaturStep(current) : h("p", { className: "ayuda" }, "Pulse Siguiente para empezar.")),
      h("div", {}, h("h4", { style: "margin-bottom:var(--esp-2)" }, "Orden de selección"),
        h("ol", { className: "lista orden-seleccion" },
          ...steps.map((s, i) => h("li", { className: i === k - 1 ? "actual" : (i >= k ? "pendiente" : null) },
            `${s.class_id} → `, s.result === "programada" ? `${s.time} en ${s.room_id}` : badge("sin programar", "bad")))))),
    h("h4", { style: "margin:var(--esp-5) 0 var(--esp-2)" }, "Horario después de este paso"),
    renderTimetable(placed, current?.class_id)));

  // Búsqueda (exacta, backtracking o fuerza bruta)
  if (p1.mode === "fuerza_bruta") {
    blocks.append(h("section", { className: "panel" },
      h("h3", {}, "Fuerza bruta"),
      h("p", { className: "ayuda" }, "Prueba todas las combinaciones posibles y se queda con la de menor costo."),
      pseudocode(PSEUDO_FB)));
  } else if (p1.search_trace && p1.search_trace.length) {
    const tones = { "podada": "warn", "mejor solución": "ok", "hoja": "muted", "explorada": "info" };
    const exact = p1.mode === "exacto";
    blocks.append(h("section", { className: "panel" },
      h("h3", {}, exact ? "Árbol de búsqueda (ramificación y poda)" : "Árbol de búsqueda (backtracking sin cota)"),
      pseudocode(exact ? PSEUDO_BB : PSEUDO_BT),
      h("p", { className: "ayuda" }, `Orden de las clases (un nivel por clase): ${p1.search_order.join(" → ")}. ` +
        "Cada línea es un nodo: la decisión tomada, el costo acumulado y la cota (costo + mínimo de lo que falta). " +
        "Si la cota alcanza a la mejor solución conocida, la rama se poda."),
      search.nodes > p1.search_trace.length ? h("p", { className: "ayuda" },
        `Se muestran los primeros ${p1.search_trace.length} de ${search.nodes} nodos.`) : null,
      h("div", { className: "arbol", style: "margin-top:var(--esp-3)" }, ...p1.search_trace.map(node =>
        h("div", { style: `padding-left:${node.depth * 18}px` },
          h("span", {}, node.class_id ? `${node.class_id} = ${node.choice}` : "raíz",
            `  costo ${node.cost}`, node.bound !== undefined ? `  cota ${node.bound}` : "",
            node.best_known !== null ? `  mejor ${node.best_known}` : ""),
          badge(node.status, tones[node.status] || "muted"))))));
  }

  blocks.append(panel("Programación final de las clases", renderTimetable(finalPlacements(), null)));
  view.append(blocks);
}

function renderDsaturStep(step) {
  return h("div", {},
    h("h4", {}, `Clase elegida: ${step.class_id}`),
    h("p", { className: "ayuda", style: "margin:var(--esp-1) 0 var(--esp-3)" },
      `Horas disponibles: ${step.available_starts} · horas bloqueadas por vecinos blandos: ${step.soft_saturation}`),
    table(["Hora", "Estado", "Costo cruces", "Cruza con", "Salón"],
      (step.candidates || []).map(c => h("tr", { className: step.slot === c.slot ? "elegida" : (c.status !== "posible" ? "tenue" : null) },
        h("td", { className: "hora" }, c.time), h("td", {}, c.status === "posible" ? badge("posible", "ok") : badge(c.status, "muted")),
        h("td", { className: "numero" }, c.penalty ?? "—"), h("td", {}, (c.crosses || []).join(", ") || "—"),
        h("td", {}, c.room_id || "—"))), [2]),
    h("p", { style: "margin-top:var(--esp-3)" }, step.result === "programada" ? `Resultado: ${step.time} en ${step.room_id}`
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
  const view = document.getElementById("vista-fase2");
  view.replaceChildren();
  const p2 = state.trace.phase2;
  const schedules = state.trace.result.student_schedule;
  const N = p2.total_requests;

  view.append(pageHeader("fase2", "Inscribir",
    "Con las horas ya fijas, cada estudiante arma su mejor horario con programación dinámica."));

  const blocks = h("div", { className: "pila" },
    h("div", { className: "aviso" },
      h("p", {}, "Las clases que pidió un estudiante son intervalos. Se ordenan por hora de fin (Θ(n log n)), se calcula " +
        "p(j) con búsqueda binaria (Θ(log n)) y se llena la tabla ", h("span", { className: "formula" }, "OPT[j] = max( OPT[j−1] , w_j + OPT[p(j)] )")),
      h("p", {}, `Peso de cada solicitud: ${p2.weight_rule}, con N = ${N}. Así la DP maximiza la suma de prioridades ` +
        "y, a igual suma, el número de clases.")),
    h("div", { className: "rejilla dos" },
      panel("Programación dinámica (cada estudiante)", pseudocode(PSEUDO_DP)),
      panel("Reparto de cupos (todos los estudiantes)", pseudocode(PSEUDO_REPARTO))),
    h("div", { className: "cifras" },
      figure("Rondas de reparto", p2.stats.rounds),
      figure("Cupos negados", p2.stats.rejections),
      figure("Mejoras del relleno", p2.stats.fill_improvements),
      figure("Solicitudes atendidas", `${p2.stats.attended_requests}/${N}`)));

  const select = sid => { state.student = sid; renderPhase2(); };
  const list = table(["Estudiante", "Atendidas"], Object.values(schedules).map(s => h("tr", {
      className: s.student_id === state.student ? "elegida" : null, tabindex: "0",
      "aria-selected": s.student_id === state.student ? "true" : "false",
      onclick: () => select(s.student_id),
      onkeydown: e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(s.student_id); } } },
    h("td", {}, s.student_id), h("td", { className: "numero" }, `${s.enrolled_classes.length}/${s.requests.length}`))), [1]);
  list.classList.add("lista-estudiantes");

  const detail = h("div", { className: "pila" });
  const sid = state.student;
  if (sid && schedules[sid]) {
    const dp = p2.dp[sid];
    const sched = schedules[sid];
    detail.append(h("section", { className: "panel" },
      h("h3", {}, `Tabla de la DP de ${sid}`),
      dp && dp.items.length ? renderDpTable(dp) : h("p", { className: "ayuda" }, "No tuvo clases candidatas en la DP."),
      h("div", { className: "rejilla dos", style: "margin-top:var(--esp-4)" },
        h("div", {}, h("h4", { style: "margin-bottom:var(--esp-2)" }, "Horario resultante"),
          sched.enrolled_classes.length ? h("ul", { className: "lista" }, ...sched.enrolled_classes.map(c =>
            h("li", {}, `${c.class_id} (prioridad ${c.priority}) · ${c.time_str} · ${c.room_id}`)))
            : h("p", { className: "ayuda" }, "Sin clases inscritas.")),
        sched.pending_requests.length ? h("div", {}, h("h4", { style: "margin-bottom:var(--esp-2)" }, "Solicitudes pendientes"),
          h("ul", { className: "lista" }, ...sched.pending_requests.map(p =>
            h("li", {}, `${p.class_id} (prioridad ${p.priority}): `, badge(p.reason, "warn"))))) : null)));
  }
  if (p2.rejections.length) {
    detail.append(h("section", { className: "panel" },
      h("h3", {}, "Cupos negados durante el reparto"),
      h("p", { className: "ayuda", style: "margin-bottom:var(--esp-2)" }, "Cuando una clase recibe más estudiantes que su cupo, " +
        "se queda con los de mayor prioridad; los demás vuelven a correr su DP sin esa clase."),
      h("ul", { className: "lista" }, ...p2.rejections.map(r =>
        h("li", {}, `Ronda ${r.round}: ${r.student_id} sin cupo en ${r.class_id} (prioridad ${r.priority})`)))));
  }
  blocks.append(h("div", { className: "rejilla lateral-izquierda" }, list, detail));
  view.append(blocks);
}

function renderDpTable(dp) {
  const rows = [h("tr", { className: "tenue" }, h("td", {}, "0"), h("td", {}, "—"), h("td", {}, ""), h("td", {}, ""),
    h("td", { className: "numero" }, ""), h("td", { className: "numero" }, ""), h("td", {}, "caso base"), h("td", { className: "numero" }, "0"), h("td", {}, ""))];
  dp.items.forEach((it, idx) => {
    const j = idx + 1, p = dp.p[j];
    const skip = dp.opt[j - 1], take = it.weight + dp.opt[p];
    const pLabel = p === 0 ? "0" : `${p} (${dp.items[p - 1].class_id})`;
    rows.push(h("tr", { className: dp.chosen.includes(it.class_id) ? "elegida" : null },
      h("td", {}, j), h("td", {}, it.class_id), h("td", { className: "hora" }, it.time), h("td", {}, it.priority),
      h("td", { className: "numero" }, it.weight), h("td", { className: "numero" }, pLabel),
      h("td", { className: "mono" }, `max(${skip}, ${it.weight} + ${dp.opt[p]} = ${take})`),
      h("td", { className: "numero" }, dp.opt[j]),
      h("td", {}, dp.chosen.includes(it.class_id) ? badge("tomada", "ok") : "")));
  });
  return h("div", {},
    table(["j", "Clase", "Horario", "Prioridad", "w_j", "p(j)", "OPT[j−1] vs w_j + OPT[p(j)]", "OPT[j]", ""], rows, [4, 5, 7], "formulas"),
    h("p", { className: "ayuda", style: "margin-top:var(--esp-2)" }, `Mejor suma de pesos: ${dp.opt[dp.opt.length - 1]}. ` +
      "La solución se reconstruye desde la última fila: si tomar j es al menos tan bueno, se toma y se salta a p(j)."));
}

// ---------------------------------------------------------------------------
// 5. Resultados
// ---------------------------------------------------------------------------
function renderResults() {
  const view = document.getElementById("vista-resultados");
  view.replaceChildren();
  const { metrics: m, verification: v, class_schedule: classes } = state.trace.result;

  view.append(pageHeader("resultados", "Resultados",
    "Informe de la ejecución: cobertura, prioridades, restricciones obligatorias y algoritmos usados."));

  const levels = Object.entries(m.by_priority).sort((a, b) => b[0] - a[0]).map(([level, d]) =>
    h("div", { className: "nivel" },
      h("span", {}, `Prioridad ${level}`), h("span", { className: "numero" }, `${d.attended}/${d.requests}`),
      h("span", { className: "pista" }, h("span", { className: "barra", style: `width:${d.percent}%` })),
      h("span", { className: "numero" }, `${d.percent}%`)));
  const reasons = Object.entries(m.pending_by_reason);

  const blocks = h("div", { className: "pila" },
    h("div", { className: "cifras" },
      figure("Cobertura", `${m.coverage_percent}%`, `${m.attended_requests} de ${m.total_requests} solicitudes`),
      figure("Satisfacción de prioridades", `${m.priority_satisfaction_percent}%`, `${m.attended_priority_sum} de ${m.received_priority_sum}`),
      figure("Restricciones incumplidas", m.violations_total, "verificador independiente"),
      figure("Clases programadas", `${m.scheduled_classes}/${m.total_classes}`,
        m.unscheduled_class_ids.length ? `sin programar: ${m.unscheduled_class_ids.join(", ")}` : "todas")),
    h("div", { className: "rejilla dos" },
      panel("Atención por nivel de prioridad",
        h("div", { className: "niveles" }, ...levels),
        h("h4", { style: "margin:var(--esp-5) 0 var(--esp-2)" }, "Pendientes por motivo"),
        reasons.length ? h("dl", { className: "datos" }, ...reasons.flatMap(([r, n]) => [h("dt", {}, r), h("dd", {}, n)]))
          : h("p", { className: "ayuda" }, "Ninguna.")),
      panel("Restricciones obligatorias",
        table(["Restricción", "Estado"], Object.entries(v.by_rule).map(([rule, count]) => h("tr", {},
          h("td", {}, state.trace.rules[rule] || rule),
          h("td", {}, count ? badge("no cumple", "bad") : badge("cumple", "ok"))))),
        ...v.violations.map(x => h("div", { className: "aviso error", style: "margin-top:var(--esp-2)" }, `${x.rule}: ${x.message}`)),
        h("h4", { style: "margin:var(--esp-4) 0 var(--esp-2)" }, "Cómo se verifica"),
        pseudocode(PSEUDO_VERIF))));

  blocks.append(panel("Algoritmos usados y complejidad",
    h("p", { className: "ayuda", style: "margin-bottom:var(--esp-3)" }, "M clases, S estudiantes, R solicitudes por estudiante, " +
      "A salones, H horas de inicio permitidas por clase, d vecinos de una clase en el grafo, K clases por estudiante."),
    table(["Paso", "Algoritmo", "Complejidad", "En este escenario"], state.trace.result.algorithms.map(a => h("tr", {},
      h("td", {}, h("strong", {}, a.step)),
      h("td", {}, h("div", {}, a.algorithm), h("div", { className: "ayuda" }, a.technique),
        a.why && a.why !== "Siempre." ? h("div", { className: "ayuda" }, a.why) : null,
        a.problem ? h("div", { className: "ayuda" }, a.problem) : null),
      h("td", { className: "complejidad" }, a.complexity),
      h("td", {}, h("div", {}, a.instance), h("div", { className: "ayuda" }, a.measured)))))));

  blocks.append(panel("Programación de clases",
    table(["Clase", "Nombre", "Horario", "Salón", "Profesor", "Inscritos", "Cupo", "Demanda"],
      Object.values(classes).map(c => h("tr", { className: c.is_scheduled ? null : "tenue" },
        h("td", {}, c.class_id), h("td", {}, c.course_name), h("td", {}, c.time_str), h("td", {}, c.room_id || "—"),
        h("td", {}, c.professor_name), h("td", { className: "numero" }, c.enrolled_count), h("td", { className: "numero" }, c.capacity),
        h("td", { className: "numero" }, c.demand))), [5, 6, 7])));
  view.append(blocks);
}

init().catch(err => setStatus(`Error al iniciar: ${err.message}`, "error"));
