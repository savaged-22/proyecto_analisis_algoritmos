"""Fase 1: elige la estrategia para ubicar las clases y aplica el resultado.

Estrategias (config.PHASE1_MODES):
- heuristica:   DSATUR. Polinomial, sin garantía de óptimo.
- exacto:       backtracking con ramificación y poda, arrancando desde DSATUR.
- backtracking: backtracking sin cota (solo poda por restricciones), para comparar.
- fuerza_bruta: todas las combinaciones, solo para instancias diminutas.
- auto:         exacto si hay a lo sumo config.EXACT_MAX_CLASSES clases; si no, heurística.

Siempre se corre DSATUR primero: es la solución final en modo heurístico y la
solución inicial (cota) en los modos exactos. Así también se puede reportar qué
tan lejos quedó la heurística del óptimo.
"""

import time
from typing import Any

from .. import config
from ..graph.conflict_graph import ConflictGraph
from ..models.course_class import CourseClass
from ..models.professor import Professor
from ..models.room import Room
from ..models.student import Student
from ..models.time_mask import TimeGrid
from .backtracking import BacktrackingScheduler
from .brute_force import BruteForceScheduler
from .cost import Assignment, ScheduleCost
from .dsatur import DSATURColoringSolver


def schedule_classes(
    classes: list[CourseClass],
    rooms: list[Room],
    professors: list[Professor],
    students: list[Student],
    grid: TimeGrid,
    graph: ConflictGraph,
    mode: str = config.DEFAULT_PHASE1_MODE,
) -> dict[str, Any]:
    """Ubica las clases según el modo pedido, deja el resultado en las entidades y devuelve un resumen."""
    if mode not in config.PHASE1_MODES:
        raise ValueError(f"Modo '{mode}' desconocido. Opciones: {', '.join(config.PHASE1_MODES)}")
    cost = ScheduleCost(graph, students)

    # 1. DSATUR (solución final en modo heurístico, cota inicial en los exactos)
    _reset(classes, rooms, professors)
    t0 = time.perf_counter()
    dsatur = DSATURColoringSolver(graph, rooms, professors, grid)
    dsatur_summary = dsatur.solve()
    dsatur_ms = (time.perf_counter() - t0) * 1000.0
    heuristic = read_assignment(classes)
    heuristic_cost = cost.breakdown(heuristic, _masks(classes, heuristic, grid))

    resolved = mode
    if mode == "auto":
        resolved = "exacto" if len(classes) <= config.EXACT_MAX_CLASSES else "heuristica"

    result: dict[str, Any] = {
        "requested_mode": mode,
        "mode": resolved,
        "heuristic_cost": heuristic_cost.to_dict(),
        "heuristic_ms": round(dsatur_ms, 3),
        "dsatur_steps": dsatur.steps,
        "search": None,
        "optimal": None,
    }

    if resolved == "heuristica":
        final, final_cost = heuristic, heuristic_cost
    else:
        t0 = time.perf_counter()
        if resolved == "fuerza_bruta":
            solver = BruteForceScheduler(classes, rooms, professors, grid, cost)
            final, final_cost = solver.solve()
            result["search"] = {"leaves": solver.leaves, "valid_leaves": solver.valid_leaves}
            result["optimal"] = True
        else:
            solver = BacktrackingScheduler(classes, rooms, professors, grid, cost,
                                           use_bound=(resolved == "exacto"))
            final, final_cost, proven = solver.solve(initial=heuristic)
            result["search"] = solver.stats.to_dict()
            result["optimal"] = proven
        result["search_ms"] = round((time.perf_counter() - t0) * 1000.0, 3)
        apply_assignment(final, classes, rooms, professors, grid)

    unscheduled = [cid for cid, a in final.items() if a is None]
    result.update({
        "cost": final_cost.to_dict(),
        "scheduled_count": len(classes) - len(unscheduled),
        "unscheduled_count": len(unscheduled),
        "unscheduled_ids": unscheduled,
        "dsatur_summary": dsatur_summary,
    })
    return result


def read_assignment(classes: list[CourseClass]) -> Assignment:
    """Programación actual de las clases como diccionario clase -> (slot, salón) o None."""
    return {c.id: (c.assigned_slot, c.assigned_room_id) if c.is_scheduled else None for c in classes}


def apply_assignment(
    assignment: Assignment,
    classes: list[CourseClass],
    rooms: list[Room],
    professors: list[Professor],
    grid: TimeGrid,
) -> None:
    """Escribe una programación en las entidades (clases, salones y profesores)."""
    _reset(classes, rooms, professors)
    rooms_by_id = {r.id: r for r in rooms}
    profs_by_id = {p.id: p for p in professors}
    for c in classes:
        choice = assignment.get(c.id)
        if choice is None:
            continue
        slot, room_id = choice
        mask = grid.create_slot_mask(slot, c.duration_hours)
        c.assigned_slot, c.assigned_room_id, c.time_mask = slot, room_id, mask
        rooms_by_id[room_id].book(mask)
        profs_by_id[c.professor_id].assign_class(mask, c.duration_hours)


def _reset(classes: list[CourseClass], rooms: list[Room], professors: list[Professor]) -> None:
    for c in classes:
        c.reset_schedule()
    for r in rooms:
        r.assigned_mask = 0
    for p in professors:
        p.assigned_mask = 0
        p.assigned_hours = 0


def _masks(classes: list[CourseClass], assignment: Assignment, grid: TimeGrid) -> dict[str, int]:
    durations = {c.id: c.duration_hours for c in classes}
    return {cid: grid.create_slot_mask(a[0], durations[cid]) for cid, a in assignment.items() if a is not None}
