"""Generador de escenarios de prueba con semilla.

Estrategia de datos:

1. Conjunto base (escenario A): primero se ubican las clases en horarios y salones
   sin conflictos (la "solución de referencia") y después se generan las
   solicitudes de cada estudiante a partir de esa programación: clases que no se
   cruzan entre sí y sin exceder cupos, con prioridades entre 1 y 3. Así se sabe
   que atender todas las solicitudes es posible. Luego, a cada clase se le
   agregan otras horas de inicio permitidas, sin quitar la original.

2. Escenarios B a F: se derivan del conjunto base con una modificación puntual,
   y cada uno trae en "expected" lo que debe cumplir la salida.

3. Escalabilidad: el mismo procedimiento con más estudiantes y recursos en
   proporción, con varias semillas por tamaño.

La misma semilla produce siempre los mismos archivos.
"""

import copy
import json
import random
from pathlib import Path
from typing import Any

from .. import config
from ..models.time_mask import TimeGrid

COURSE_CATALOG: list[tuple[str, str]] = [
    ("INF101", "Algoritmos y Complejidad"),
    ("INF102", "Estructuras de Datos Avanzadas"),
    ("INF103", "Bases de Datos Relacionales"),
    ("INF104", "Laboratorio de Redes y Seguridad"),
    ("INF105", "Sistemas Operativos Distribuidos"),
    ("INF106", "Inteligencia Artificial y Grafos"),
    ("INF107", "Optimización Combinatoria"),
    ("INF108", "Taller de Desarrollo de Software"),
    ("MAT201", "Cálculo en Varias Variables"),
    ("MAT202", "Álgebra Lineal Computacional"),
    ("MAT203", "Probabilidad y Procesos Estocásticos"),
    ("MAT204", "Matemática Discreta"),
    ("FIS301", "Física para Computación"),
    ("FIS302", "Laboratorio de Física Experimental"),
    ("INF401", "Compiladores y Lenguajes"),
    ("INF402", "Criptografía y Seguridad"),
    ("INF403", "Arquitectura de Computadores"),
    ("INF404", "Computación Gráfica"),
    ("INF405", "Ingeniería de Requerimientos"),
    ("INF406", "Minería de Datos"),
    ("INF407", "Computación Cuántica"),
    ("INF408", "Robótica Autónoma"),
    ("HUM101", "Ética en Inteligencia Artificial"),
    ("HUM102", "Comunicación Científica"),
    ("GES201", "Gestión de Proyectos Tecnológicos"),
]

PROFESSOR_NAMES: list[str] = [
    "Dr. Alan Turing", "Dra. Ada Lovelace", "Dr. John von Neumann",
    "Dra. Grace Hopper", "Dr. Claude Shannon", "Dra. Margaret Hamilton",
    "Dr. Donald Knuth", "Dra. Barbara Liskov", "Dr. Edsger Dijkstra",
    "Dra. Katherine Johnson", "Dr. Ken Thompson", "Dra. Radia Perlman",
    "Dr. Dennis Ritchie", "Dra. Frances Allen", "Dr. Tim Berners-Lee",
    "Dra. Shafi Goldwasser", "Dr. Leslie Lamport", "Dra. Karen Spärck Jones",
    "Dr. Richard Karp", "Dra. Judea Pearl", "Dr. Stephen Cook",
    "Dra. Daphne Koller", "Dr. Michael Rabin", "Dra. Cynthia Dwork",
    "Dr. Robert Tarjan", "Dra. Jennifer Chayes", "Dr. Andrew Yao",
    "Dra. Fei-Fei Li", "Dr. Manuel Blum", "Dra. Lenore Blum",
]

DEFAULT_SEED = 2026
BASE_SIZE = {"students": 20, "professors": 5, "classes": 8, "rooms": 10}


# ======================================================================
# Conjunto base
# ======================================================================
def build_base_scenario(
    seed: int = DEFAULT_SEED,
    n_students: int = BASE_SIZE["students"],
    n_professors: int = BASE_SIZE["professors"],
    n_classes: int = BASE_SIZE["classes"],
    n_rooms: int = BASE_SIZE["rooms"],
    name: str = "A_factible",
) -> dict[str, Any]:
    """Construye el conjunto base: una programación factible conocida y solicitudes derivadas de ella."""
    rng = random.Random(seed)
    grid = TimeGrid()  # versión inicial: un día, 8:00 a 18:00
    hours = list(range(grid.start_hour, grid.end_hour))

    # 1. Salones y profesores
    rooms = [
        {"id": f"AULA-{i:02d}", "name": f"Salón {i:02d}",
         "capacity": rng.choice([20, 25, 30, 35, 40]), "availability": list(hours)}
        for i in range(1, n_rooms + 1)
    ]
    professors = [
        {"id": f"PROF-{i:02d}", "name": _professor_name(i)}
        for i in range(1, n_professors + 1)
    ]

    # 2. Clases ubicadas sin conflictos (solución de referencia)
    room_busy = {r["id"]: 0 for r in rooms}
    prof_busy = {p["id"]: 0 for p in professors}
    prof_order = [p["id"] for p in professors]
    rng.shuffle(prof_order)

    classes: list[dict[str, Any]] = []
    reference: dict[str, dict[str, Any]] = {}
    for i in range(n_classes):
        code, course_name = COURSE_CATALOG[i % len(COURSE_CATALOG)]
        class_id = f"{code}-{i // len(COURSE_CATALOG) + 1}"
        prof_id = prof_order[i % len(prof_order)]
        duration = 2 if rng.random() < 0.6 else 1

        placement = _random_free_placement(rng, grid, duration, rooms, room_busy, prof_busy[prof_id])
        if placement is None and duration == 2:
            duration = 1
            placement = _random_free_placement(rng, grid, duration, rooms, room_busy, prof_busy[prof_id])
        if placement is None:
            raise ValueError("No hay espacio para ubicar todas las clases; agregue salones o profesores.")

        slot, room = placement
        mask = grid.create_slot_mask(slot, duration)
        room_busy[room["id"]] |= mask
        prof_busy[prof_id] |= mask

        start_hour = grid.slot_to_day_hour(slot)[1]
        other_starts = [h for h in hours if h != start_hour and h + duration <= grid.end_hour]
        allowed = sorted({start_hour, *rng.sample(other_starts, rng.randint(1, 3))})

        classes.append({
            "id": class_id,
            "course_id": code,
            "course_name": course_name,
            "professor_id": prof_id,
            "capacity": min(room["capacity"], rng.choice([10, 15, 20, 25])),
            "duration_hours": duration,
            "allowed_starts": allowed,
        })
        reference[class_id] = {"start_hour": start_hour, "room_id": room["id"], "mask": mask}

    # 3. Disponibilidad de profesores: sus horas de referencia + horas extra al azar
    for p in professors:
        busy_hours = _mask_hours(grid, prof_busy[p["id"]])
        p["availability"] = sorted({*busy_hours, *(h for h in hours if rng.random() < 0.6)})

    # 4. Solicitudes derivadas de la programación de referencia
    seats = {c["id"]: c["capacity"] for c in classes}
    students: list[dict[str, Any]] = []
    enrollments: dict[str, list[str]] = {}
    for i in range(1, n_students + 1):
        student_id = f"EST-{i:03d}"
        wanted = rng.randint(2, 4)
        picked: list[str] = []
        taken_mask = 0
        for c in rng.sample(classes, len(classes)):
            if len(picked) == wanted:
                break
            mask = reference[c["id"]]["mask"]
            if seats[c["id"]] > 0 and not taken_mask & mask:
                picked.append(c["id"])
                taken_mask |= mask
                seats[c["id"]] -= 1
        students.append({
            "id": student_id,
            "name": f"Estudiante {i:03d}",
            "requests": [{"class_id": cid, "priority": rng.randint(config.MIN_PRIORITY, config.MAX_PRIORITY)}
                         for cid in picked],
        })
        enrollments[student_id] = picked

    scenario = {
        "metadata": {
            "name": name,
            "seed": seed,
            "description": (
                f"Conjunto base: {n_students} estudiantes, {n_professors} profesores, "
                f"{n_classes} clases y {n_rooms} salones. Construido desde una programación "
                "sin conflictos, por lo que todas las solicitudes se pueden atender."
            ),
        },
        "parameters": grid.to_dict(),
        "rooms": rooms,
        "professors": professors,
        "classes": classes,
        "students": students,
        "expected": {
            "description": "Programación factible: se pueden atender todas las solicitudes sin incumplir R1-R10.",
            "violations": 0,
            "best_coverage_percent": 100.0,
            "reference_solution": {
                "classes": {cid: {"start_hour": r["start_hour"], "room_id": r["room_id"]}
                            for cid, r in reference.items()},
                "enrollments": enrollments,
            },
        },
    }
    return scenario


# ======================================================================
# Escenarios B a F, derivados del conjunto base
# ======================================================================
def scenario_b_rooms(base: dict[str, Any], seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """B: tres clases solo pueden iniciar a la misma hora y en esa franja solo quedan dos salones."""
    rng = random.Random(seed + 2)
    sc = _derive(base, "B_salones")
    grid = _grid(sc)
    ref = _reference_masks(base, grid)

    competitors, hour = _pick_classes_sharing_hour(rng, grid, sc["classes"], ref, count=3)
    window = 0
    for c in competitors:
        c["allowed_starts"] = [hour]
        window |= grid.create_slot_mask(grid.day_hour_to_slot(0, hour), c["duration_hours"])
        _make_professor_available(sc, c["professor_id"], grid, window)

    # A esa hora solo quedan habilitados los dos salones más grandes; los demás pierden esa franja.
    competitor_ids = {c["id"] for c in competitors}
    need = max(_min_room_capacity(sc, c) for c in competitors)
    by_capacity = sorted(sc["rooms"], key=lambda r: (-r["capacity"], r["id"]))
    kept = [r["id"] for r in by_capacity if r["capacity"] >= need][:2]
    if len(kept) < 2:
        raise ValueError("El conjunto base no tiene dos salones con capacidad suficiente para el escenario B.")
    window_hours = set(_mask_hours(grid, window))
    for r in sc["rooms"]:
        if r["id"] not in kept:
            r["availability"] = [h for h in r["availability"] if h not in window_hours]

    ids = sorted(competitor_ids)
    sc["expected"] = {
        "description": (
            f"Las clases {', '.join(ids)} solo pueden iniciar a las {hour}:00 y en esa franja solo hay "
            f"dos salones habilitados ({', '.join(kept)}). Ningún salón puede tener dos clases a la vez, "
            "así que en esa franja caben a lo sumo dos clases y al menos una de las tres queda sin programar."
        ),
        "violations": 0,
        "competing_classes": ids,
        "window_hours": sorted(window_hours),
        "rooms_in_window": kept,
        "max_classes_in_window": 2,
        "max_competing_scheduled": 2,
    }
    return sc


def scenario_c_professor(base: dict[str, Any], seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """C: un profesor tiene una sola hora disponible para dos de sus clases."""
    rng = random.Random(seed + 3)
    sc = _derive(base, "C_profesor")
    grid = _grid(sc)

    by_prof: dict[str, list[dict[str, Any]]] = {}
    for c in sc["classes"]:
        by_prof.setdefault(c["professor_id"], []).append(c)
    candidates = sorted(pid for pid, cs in by_prof.items() if len(cs) == 2)
    if not candidates:
        raise ValueError("El conjunto base no tiene un profesor con exactamente dos clases.")
    prof_id = rng.choice(candidates)
    c1, c2 = by_prof[prof_id]

    hour = rng.choice(range(grid.start_hour, grid.end_hour))
    for c in (c1, c2):
        c["duration_hours"] = 1
        c["allowed_starts"] = sorted(set(c["allowed_starts"]) | {hour})
    for p in sc["professors"]:
        if p["id"] == prof_id:
            p["availability"] = [hour]

    weight = {c["id"]: _priority_sum(sc, c["id"]) for c in (c1, c2)}
    preferred = None if weight[c1["id"]] == weight[c2["id"]] else max(weight, key=weight.get)
    sc["expected"] = {
        "description": (
            f"{prof_id} solo puede dictar de {hour}:00 a {hour + 1}:00 y tiene dos clases de una hora "
            f"({c1['id']} y {c2['id']}). Solo una puede programarse; las solicitudes de la otra quedan "
            "pendientes con motivo 'clase no programada'. La óptima conserva la de mayor suma de prioridades."
        ),
        "violations": 0,
        "exactly_one_scheduled_of": [c1["id"], c2["id"]],
        "priority_sums": weight,
        "best_kept_class": preferred,
        "best_scheduled_classes": len(sc["classes"]) - 1,
    }
    return sc


def scenario_d_students(base: dict[str, Any], seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """D: estudiantes que piden dos clases que forzosamente se cruzan."""
    rng = random.Random(seed + 4)
    sc = _derive(base, "D_estudiantes")
    grid = _grid(sc)
    ref = _reference_masks(base, grid)

    (c1, c2), hour = _pick_classes_sharing_hour(rng, grid, sc["classes"], ref, count=2)
    for c in (c1, c2):
        c["allowed_starts"] = [hour]
        c["capacity"] += 3
        _make_professor_available(
            sc, c["professor_id"], grid,
            grid.create_slot_mask(grid.day_hour_to_slot(0, hour), c["duration_hours"]))

    plan = [("EST-D01", 3, 1), ("EST-D02", 1, 3), ("EST-D03", 2, 1)]
    keeps: dict[str, str] = {}
    for sid, p1, p2 in plan:
        sc["students"].append({
            "id": sid,
            "name": f"Estudiante {sid[-3:]}",
            "requests": [{"class_id": c1["id"], "priority": p1}, {"class_id": c2["id"], "priority": p2}],
        })
        keeps[sid] = c1["id"] if p1 > p2 else c2["id"]

    sc["expected"] = {
        "description": (
            f"{c1['id']} y {c2['id']} solo pueden iniciar a las {hour}:00, así que se cruzan. "
            "Los estudiantes EST-D01..D03 piden ambas con prioridades distintas: cada uno debe quedar "
            "solo en la de mayor prioridad, y la otra pendiente con motivo 'cruce'."
        ),
        "violations": 0,
        "overlapping_classes": [c1["id"], c2["id"]],
        "students_keep": keeps,
    }
    return sc


def scenario_e_capacity(base: dict[str, Any], seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """E: una clase con menos cupos que estudiantes que la solicitan."""
    sc = _derive(base, "E_capacidad")
    demand = {c["id"]: 0 for c in sc["classes"]}
    for s in sc["students"]:
        for r in s["requests"]:
            demand[r["class_id"]] += 1
    target_id = max(demand, key=lambda cid: (demand[cid], cid))
    if demand[target_id] < 3:
        raise ValueError("Ninguna clase tiene demanda suficiente para el escenario E.")
    target = next(c for c in sc["classes"] if c["id"] == target_id)
    target["capacity"] = demand[target_id] - 2

    sc["expected"] = {
        "description": (
            f"{target_id} tiene {demand[target_id]} solicitudes y su cupo baja a {target['capacity']}. "
            "Sin otros conflictos, exactamente dos solicitudes de esa clase quedan pendientes por "
            "'cupo agotado', y ninguna clase supera su cupo."
        ),
        "violations": 0,
        "class_id": target_id,
        "demand": demand[target_id],
        "capacity": target["capacity"],
        "best_pending_for_capacity": 2,
    }
    return sc


def scenario_f_impossible(base: dict[str, Any], seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """F: un profesor con seis clases de dos horas en una jornada de diez horas."""
    sc = _derive(base, "F_imposible")
    grid = _grid(sc)
    if len(sc["classes"]) < 6:
        raise ValueError("El escenario F necesita al menos seis clases.")
    prof_id = sc["professors"][0]["id"]
    loaded = sc["classes"][:6]
    for c in loaded:
        c["professor_id"] = prof_id
        c["duration_hours"] = 2
        c.pop("allowed_starts", None)  # cualquier hora de la jornada
    sc["professors"][0]["availability"] = list(range(grid.start_hour, grid.end_hour))
    # Las demás clases de ese profesor pasan a un profesor nuevo, para que solo él tenga seis.
    others = [c for c in sc["classes"][6:] if c["professor_id"] == prof_id]
    if others:
        sc["professors"].append({"id": "PROF-F", "name": "Profesor de apoyo",
                                 "availability": list(range(grid.start_hour, grid.end_hour))})
        for c in others:
            c["professor_id"] = "PROF-F"
    fits = grid.hours_per_day // 2

    sc["expected"] = {
        "description": (
            f"{prof_id} tiene seis clases de dos horas, pero en una jornada de {grid.hours_per_day} horas "
            f"caben a lo sumo {fits}. Al menos una queda sin programar; el sistema debe listarla, marcar "
            "sus solicitudes como pendientes y no producir una programación inválida."
        ),
        "violations": 0,
        "overloaded_professor": prof_id,
        "overloaded_classes": [c["id"] for c in loaded],
        "max_scheduled_of_overloaded": fits,
        "best_scheduled_classes": len(sc["classes"]) - (6 - fits),
    }
    return sc


SCENARIO_BUILDERS = [
    scenario_b_rooms,
    scenario_c_professor,
    scenario_d_students,
    scenario_e_capacity,
    scenario_f_impossible,
]


# ======================================================================
# Escalabilidad
# ======================================================================
def build_scale_scenario(n_students: int, seed: int) -> dict[str, Any]:
    """Escenario A con más estudiantes y recursos en proporción al conjunto base (20/5/8/10)."""
    factor = n_students / BASE_SIZE["students"]
    return build_base_scenario(
        seed=seed,
        n_students=n_students,
        n_professors=max(BASE_SIZE["professors"], round(BASE_SIZE["professors"] * factor)),
        n_classes=max(BASE_SIZE["classes"], round(BASE_SIZE["classes"] * factor)),
        n_rooms=max(BASE_SIZE["rooms"], round(BASE_SIZE["rooms"] * factor)),
        name=f"escala_{n_students:03d}_s{seed}",
    )


def build_conflict_scenario(n_students: int, seed: int, extra_requests: int = 2, starts_per_class: int = 2,
                            ) -> dict[str, Any]:
    """Escenario de escalabilidad con conflictos inevitables, para medir a la heurística contra el óptimo.

    Parte del escenario de escalabilidad y le agrega a cada estudiante 'extra_requests' solicitudes al azar
    (que ya no salen de la programación de referencia, así que pueden cruzarse) y deja a cada clase con
    solo 'starts_per_class' horas de inicio permitidas. Los cupos suben a 40 para que la dificultad venga
    de los horarios y no de la capacidad.
    """
    data = build_scale_scenario(n_students, seed)
    rng = random.Random(seed * 7919 + n_students)
    class_ids = [c["id"] for c in data["classes"]]
    for s in data["students"]:
        have = {r["class_id"] for r in s["requests"]}
        options = [cid for cid in class_ids if cid not in have]
        for cid in rng.sample(options, min(extra_requests, len(options))):
            s["requests"].append({"class_id": cid, "priority": rng.randint(config.MIN_PRIORITY, config.MAX_PRIORITY)})
    for c in data["classes"]:
        if len(c["allowed_starts"]) > starts_per_class:
            c["allowed_starts"] = sorted(rng.sample(c["allowed_starts"], starts_per_class))
        c["capacity"] = max(c["capacity"], 40)
    data["metadata"]["name"] = f"conflictos_{n_students:03d}_s{seed}"
    data["metadata"]["description"] = (
        "Escenario de escalabilidad con solicitudes extra al azar y menos horas permitidas: "
        "hay cruces inevitables y la solución óptima no se conoce de antemano."
    )
    data["expected"] = {"description": "Sin solución esperada conocida; se compara la heurística con el exacto.",
                        "violations": 0}
    return data


# ======================================================================
# Escritura de archivos
# ======================================================================
def write_standard_scenarios(out_dir: Path, seed: int = DEFAULT_SEED) -> list[Path]:
    """Escribe el conjunto base (A) y los escenarios B a F."""
    out_dir.mkdir(parents=True, exist_ok=True)
    base = build_base_scenario(seed)
    scenarios = [base] + [builder(base, seed) for builder in SCENARIO_BUILDERS]
    return [_write(out_dir, sc) for sc in scenarios]


def write_scale_scenarios(out_dir: Path, sizes: list[int], seeds: list[int]) -> list[Path]:
    """Escribe los escenarios de escalabilidad (un archivo por tamaño y semilla)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    return [_write(out_dir, build_scale_scenario(n, seed)) for n in sizes for seed in seeds]


def _write(out_dir: Path, scenario: dict[str, Any]) -> Path:
    path = out_dir / f"{scenario['metadata']['name']}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scenario, f, indent=2, ensure_ascii=False)
    return path


# ======================================================================
# Utilidades internas
# ======================================================================
def _professor_name(i: int) -> str:
    base = PROFESSOR_NAMES[(i - 1) % len(PROFESSOR_NAMES)]
    return base if i <= len(PROFESSOR_NAMES) else f"{base} ({i})"


def _random_free_placement(rng, grid, duration, rooms, room_busy, prof_mask):
    """Elige al azar un (slot, salón) libre para una clase, o None si no existe."""
    options = []
    for slot in grid.candidate_starts(duration):
        mask = grid.create_slot_mask(slot, duration)
        if prof_mask & mask:
            continue
        options.extend((slot, r) for r in rooms if not room_busy[r["id"]] & mask)
    return rng.choice(options) if options else None


def _mask_hours(grid: TimeGrid, mask: int) -> list[int]:
    hours = grid.mask_to_hours(mask)
    return hours if isinstance(hours, list) else [h for hs in hours.values() for h in hs]


def _derive(base: dict[str, Any], name: str) -> dict[str, Any]:
    sc = copy.deepcopy(base)
    sc["metadata"]["name"] = name
    sc["metadata"]["description"] = f"Derivado del conjunto base ({base['metadata']['name']})."
    sc["expected"] = {}
    return sc


def _grid(sc: dict[str, Any]) -> TimeGrid:
    return TimeGrid(**sc["parameters"])


def _reference_masks(base: dict[str, Any], grid: TimeGrid) -> dict[str, dict[str, Any]]:
    """Horario y salón de referencia de cada clase del conjunto base, con su máscara."""
    durations = {c["id"]: c["duration_hours"] for c in base["classes"]}
    result = {}
    for cid, r in base["expected"]["reference_solution"]["classes"].items():
        slot = grid.day_hour_to_slot(0, r["start_hour"])
        result[cid] = {"room_id": r["room_id"], "mask": grid.create_slot_mask(slot, durations[cid])}
    return result


def _pick_classes_sharing_hour(rng, grid, classes, ref, count):
    """Elige 'count' clases de profesores distintos y una hora en la que todas pueden iniciar
    sin chocar con las demás clases de sus profesores en la solución de referencia."""
    by_prof: dict[str, list[dict[str, Any]]] = {}
    for c in classes:
        by_prof.setdefault(c["professor_id"], []).append(c)
    if len(by_prof) < count:
        raise ValueError(f"Se necesitan al menos {count} profesores distintos.")

    for _ in range(200):
        chosen = [rng.choice(by_prof[pid]) for pid in rng.sample(sorted(by_prof), count)]
        longest = max(c["duration_hours"] for c in chosen)
        for hour in rng.sample(range(grid.start_hour, grid.end_hour - longest + 1),
                               grid.hours_per_day - longest + 1):
            slot = grid.day_hour_to_slot(0, hour)
            if all(_professor_free_elsewhere(c, grid.create_slot_mask(slot, c["duration_hours"]), classes, ref)
                   for c in chosen):
                return chosen, hour
    raise ValueError("No se encontró una hora compartida para las clases elegidas.")


def _professor_free_elsewhere(cls, mask, classes, ref) -> bool:
    return all(not ref[o["id"]]["mask"] & mask
               for o in classes if o["professor_id"] == cls["professor_id"] and o["id"] != cls["id"])


def _make_professor_available(sc, prof_id, grid, mask) -> None:
    for p in sc["professors"]:
        if p["id"] == prof_id:
            p["availability"] = sorted(set(p["availability"]) | set(_mask_hours(grid, mask)))


def _min_room_capacity(sc, cls) -> int:
    demand = sum(1 for s in sc["students"] for r in s["requests"] if r["class_id"] == cls["id"])
    return min(cls["capacity"], demand)


def _priority_sum(sc, class_id: str) -> int:
    return sum(r["priority"] for s in sc["students"] for r in s["requests"] if r["class_id"] == class_id)
