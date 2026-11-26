"""Comparación del resultado con la salida esperada de cada escenario.

Cada escenario de prueba (generator.py, inicial.json) trae en "expected" lo que debe
cumplir la salida. Este módulo revisa esas condiciones sobre el resultado del
algoritmo y devuelve una lista de comprobaciones (nombre, ¿cumple?, detalle).

Las comprobaciones marcadas como "óptimo" (best_*) solo se exigen cuando la
fase 1 se resolvió con búsqueda exacta: la heurística no garantiza alcanzarlas.
"""

from dataclasses import dataclass
from typing import Any

from ..report.report import REASON_FULL


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    only_if_optimal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail,
                "only_if_optimal": self.only_if_optimal}


def check_expectations(scenario, result: dict[str, Any]) -> list[Check]:
    """Revisa las condiciones de scenario.expected sobre el resultado de TimetableOrchestrator.run()."""
    exp = scenario.expected
    metrics = result["metrics"]
    unscheduled = set(metrics["unscheduled_class_ids"])
    classes = {c.id: c for c in scenario.classes}
    students = {s.id: s for s in scenario.students}
    checks: list[Check] = []

    def add(name: str, passed: bool, detail: str, only_if_optimal: bool = False) -> None:
        checks.append(Check(name, bool(passed), detail, only_if_optimal))

    if "violations" in exp:
        add("Incumplimientos de R1-R10", metrics["violations_total"] == exp["violations"],
            f"{metrics['violations_total']} (esperado {exp['violations']})")

    if "best_coverage_percent" in exp:
        add("Cobertura", metrics["coverage_percent"] >= exp["best_coverage_percent"],
            f"{metrics['coverage_percent']}% (alcanzable {exp['best_coverage_percent']}%)", only_if_optimal=True)

    if "scheduled_classes" in exp:
        add("Clases programadas", metrics["scheduled_classes"] == exp["scheduled_classes"],
            f"{metrics['scheduled_classes']} (esperado {exp['scheduled_classes']})", only_if_optimal=True)

    if "unscheduled_classes" in exp:
        add("Clases sin programar", sorted(unscheduled) == sorted(exp["unscheduled_classes"]),
            f"{sorted(unscheduled)} (esperado {sorted(exp['unscheduled_classes'])})", only_if_optimal=True)

    if "best_scheduled_classes" in exp:
        add("Clases programadas (óptimo)", metrics["scheduled_classes"] == exp["best_scheduled_classes"],
            f"{metrics['scheduled_classes']} (óptimo {exp['best_scheduled_classes']})", only_if_optimal=True)

    if "competing_classes" in exp:
        kept = [cid for cid in exp["competing_classes"] if cid not in unscheduled]
        add("Clases que compiten por salón", len(kept) <= exp["max_competing_scheduled"],
            f"programadas {kept} (máximo {exp['max_competing_scheduled']})")

    if "window_hours" in exp:
        busiest = max(
            sum(1 for c in classes.values() if c.is_scheduled and c.time_mask & scenario.grid.hours_to_mask([h]))
            for h in exp["window_hours"]
        )
        add("Clases simultáneas en la franja con dos salones", busiest <= exp["max_classes_in_window"],
            f"{busiest} (máximo {exp['max_classes_in_window']})")

    if "exactly_one_scheduled_of" in exp:
        kept = [cid for cid in exp["exactly_one_scheduled_of"] if cid not in unscheduled]
        add("Profesor con una sola hora", len(kept) == 1, f"programadas {kept} (debe ser una)")
        if exp.get("best_kept_class"):
            add("Se conserva la de mayor prioridad", kept == [exp["best_kept_class"]],
                f"{kept} (óptimo {exp['best_kept_class']})", only_if_optimal=True)

    if "students_keep" in exp:
        for sid, keep in exp["students_keep"].items():
            add(f"{sid} conserva la de mayor prioridad", students[sid].assigned_classes == [keep],
                f"inscrito en {students[sid].assigned_classes} (esperado {[keep]})")

    if "best_pending_for_capacity" in exp:
        cid = exp["class_id"]
        pending = [p for s in result["student_schedule"].values() for p in s["pending_requests"]
                   if p["class_id"] == cid and p["reason"] == REASON_FULL]
        add("No se supera el cupo", len(classes[cid].enrolled_students) <= exp["capacity"],
            f"{len(classes[cid].enrolled_students)} inscritos (cupo {exp['capacity']})")
        add("Pendientes por cupo agotado", len(pending) == exp["best_pending_for_capacity"],
            f"{len(pending)} (esperado {exp['best_pending_for_capacity']})", only_if_optimal=True)

    if "pending_for_capacity" in exp:
        for cid, expected in exp["pending_for_capacity"].items():
            pending = [p for s in result["student_schedule"].values() for p in s["pending_requests"]
                       if p["class_id"] == cid and p["reason"] == REASON_FULL]
            add(f"Pendientes por cupo en {cid}", len(pending) == expected,
                f"{len(pending)} (esperado {expected})", only_if_optimal=True)

    if "overloaded_classes" in exp:
        kept = [cid for cid in exp["overloaded_classes"] if cid not in unscheduled]
        add("Clases del profesor sobrecargado", len(kept) <= exp["max_scheduled_of_overloaded"],
            f"{len(kept)} programadas (caben {exp['max_scheduled_of_overloaded']})")
        add("Se listan las clases sin programar", len(unscheduled) >= 1, f"sin programar: {sorted(unscheduled)}")

    return checks


def failed_checks(scenario, result: dict[str, Any]) -> list[Check]:
    """Comprobaciones que fallan, teniendo en cuenta si la fase 1 fue exacta."""
    optimal = bool(result["phase1_details"].get("optimal"))
    return [c for c in check_expectations(scenario, result) if not c.passed and (optimal or not c.only_if_optimal)]
