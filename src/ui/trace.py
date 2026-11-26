"""Traza de una ejecución: todo lo que la interfaz necesita para mostrar el algoritmo paso a paso.

No cambia el algoritmo: lee lo que el orquestador ya dejó registrado (el grafo,
los pasos de DSATUR, los primeros nodos del backtracking, la tabla de la DP de
cada estudiante y los cupos negados) y lo junta en un diccionario serializable.
"""

from typing import Any

from .. import config
from ..models.time_mask import mask_to_slots
from ..solver.orchestrator import TimetableOrchestrator
from ..verify.expectations import check_expectations
from ..verify.verifier import RULES


def build_trace(orch: TimetableOrchestrator, result: dict[str, Any]) -> dict[str, Any]:
    grid = orch.grid
    graph = orch.conflict_graph
    p1 = result["phase1_details"]

    nodes = [{
        "id": c.id, "name": c.course_name, "professor_id": c.professor_id,
        "duration": c.duration_hours, "demand": c.demand, "capacity": c.capacity,
        "slot": c.assigned_slot, "room_id": c.assigned_room_id,
        "start_hour": grid.slot_to_day_hour(c.assigned_slot)[1] if c.is_scheduled else None,
    } for c in orch.classes]
    edges = []
    ids = [c.id for c in orch.classes]
    for i, u in enumerate(ids):
        for v in ids[i + 1:]:
            if v in graph.get_neighbors(u):
                hard = graph.is_hard_conflict(u, v)
                edges.append({"u": u, "v": v, "hard": hard, "weight": None if hard else graph.get_weight(u, v)})

    solver = orch.enrollment_solver
    dp = {}
    for s in orch.students:
        res = solver.dp_results.get(s.id) if solver else None
        if res is None:
            continue
        priorities = {r.class_id: r.priority for r in s.requests}
        dp[s.id] = {
            "items": [{
                "class_id": it.key, "start": it.start, "end": it.end, "weight": it.weight,
                "priority": priorities[it.key],
                "time": grid.format_slot(it.start, it.end - it.start),
            } for it in res.items],
            "p": res.p,
            "opt": res.opt,
            "chosen": res.chosen_keys,
        }

    return {
        "scenario": orch.scenario.metadata,
        "grid": {**grid.to_dict(), "day_names": grid.day_names},
        "rooms": [{"id": r.id, "name": r.name, "capacity": r.capacity, "room_type": r.room_type,
                   "available_slots": mask_to_slots(r.availability_mask)} for r in orch.rooms],
        "graph": {"nodes": nodes, "edges": edges, "stats": graph.get_statistics()},
        "phase1": {
            "mode": p1["mode"], "requested_mode": p1["requested_mode"],
            "dsatur_steps": p1["dsatur_steps"],
            "heuristic_cost": p1["heuristic_cost"], "cost": p1["cost"],
            "search": p1["search"], "optimal": p1["optimal"],
            "search_trace": p1.get("search_trace", []), "search_order": p1.get("search_order", []),
            "trace_limit": config.TRACE_LIMIT,
            "heuristic_ms": p1["heuristic_ms"], "search_ms": p1.get("search_ms"),
        },
        "phase2": {
            "stats": result["phase2_details"],
            "dp": dp,
            "rejections": [vars(r) for r in solver.rejections] if solver else [],
            "weight_rule": "w = prioridad · (N + 1) + 1",
            "total_requests": orch.scenario.total_requests,
        },
        "result": {k: result[k] for k in ("metrics", "verification", "class_schedule", "student_schedule",
                                         "room_schedule", "solution", "algorithms")},
        "rules": RULES,
        "expectations": [c.to_dict() for c in check_expectations(orch.scenario, result)],
    }
