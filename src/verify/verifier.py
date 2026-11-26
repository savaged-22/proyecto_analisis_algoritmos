"""Verificador independiente de las restricciones obligatorias R1-R10.

Recibe el escenario de entrada y la solución tal como se exporta (la sección
"solution" del JSON de salida) y cuenta los incumplimientos. No usa nada del
algoritmo: recalcula cada horario desde la hora de inicio y fin escritas en la
solución, así que también sirve para revisar una solución hecha a mano.

Formato de la solución:

    {
      "classes": [{"class_id", "day", "start_hour", "end_hour", "room_id", "students": [...]}],
      "unscheduled_classes": ["..."]
    }

Complejidad: O(M^2 + S * K^2), con M clases programadas, S estudiantes y K
clases por estudiante. Es polinomial: comprobar una solución es fácil aunque
encontrar la mejor sea difícil, que es lo que ubica al problema (en su versión
de decisión) dentro de NP.
"""

from dataclasses import dataclass, field
from typing import Any

from ..data.scenario import Scenario
from ..models.time_mask import TimeGrid, masks_overlap

RULES: dict[str, str] = {
    "R1": "Disponibilidad del salón",
    "R2": "Disponibilidad del profesor",
    "R3": "Disponibilidad del estudiante",
    "R4": "Capacidad del salón",
    "R5": "Capacidad de la clase",
    "R6": "Duración",
    "R7": "Jornada académica",
    "R8": "Horarios permitidos",
    "R9": "Correspondencia de solicitudes",
    "R10": "Integridad de las asignaciones",
}


@dataclass
class Violation:
    rule: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "rule_name": RULES[self.rule], "message": self.message}


@dataclass
class VerificationResult:
    violations: list[Violation] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.violations)

    @property
    def is_valid(self) -> bool:
        return not self.violations

    def count_by_rule(self) -> dict[str, int]:
        counts = {rule: 0 for rule in RULES}
        for v in self.violations:
            counts[v.rule] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_violations": self.total,
            "by_rule": self.count_by_rule(),
            "violations": [v.to_dict() for v in self.violations],
        }


@dataclass
class _Placed:
    """Clase programada según la solución, con su horario recalculado."""
    class_id: str
    room_id: str
    mask: int
    students: list[str]
    text: str


def verify_solution(scenario: Scenario, solution: dict[str, Any]) -> VerificationResult:
    """Cuenta los incumplimientos de R1-R10 de una solución sobre un escenario."""
    result = VerificationResult()

    def fail(rule: str, message: str) -> None:
        result.violations.append(Violation(rule, message))

    grid = scenario.grid
    classes = {c.id: c for c in scenario.classes}
    rooms = {r.id: r for r in scenario.rooms}
    professors = {p.id: p for p in scenario.professors}
    students = {s.id: s for s in scenario.students}

    # ------------------------------------------------------------------
    # Cada clase programada por separado: R6, R7, R8, R10 y disponibilidad (R2)
    # ------------------------------------------------------------------
    placed: list[_Placed] = []
    seen: set[str] = set()
    for entry in solution.get("classes", []):
        cid = str(entry.get("class_id"))
        if cid not in classes:
            fail("R10", f"La solución programa una clase que no existe: {cid}")
            continue
        if cid in seen:
            fail("R10", f"La clase {cid} aparece programada más de una vez")
            continue
        seen.add(cid)
        cls = classes[cid]

        room_id = entry.get("room_id")
        room = rooms.get(room_id)
        if room is None:
            fail("R10", f"La clase {cid} no tiene un salón válido (salón: {room_id})")
        elif cls.required_room_type and room.room_type.lower() != cls.required_room_type.lower():
            fail("R10", f"La clase {cid} exige salón tipo '{cls.required_room_type}' y quedó en {room_id}")

        mask = _block_mask(grid, entry, cid, fail)
        if mask is None:
            continue

        start, end = int(entry["start_hour"]), int(entry["end_hour"])
        if end - start != cls.duration_hours:
            fail("R6", f"La clase {cid} dura {cls.duration_hours} h y quedó de {start}:00 a {end}:00")

        start_slot = grid.day_hour_to_slot(grid.day_names.index(entry.get("day", grid.day_names[0])), start)
        if start_slot not in cls.allowed_starts:
            fail("R8", f"La clase {cid} no puede iniciar a las {start}:00 (no es una hora permitida)")

        prof = professors.get(cls.professor_id)
        if prof is not None and (prof.availability_mask & mask) != mask:
            fail("R2", f"{cls.professor_id} no está disponible para dictar {cid} ({grid.format_mask(mask)})")
        if room is not None and (room.availability_mask & mask) != mask:
            fail("R8", f"El salón {room_id} no está disponible para {cid} ({grid.format_mask(mask)})")

        enrolled = [str(s) for s in entry.get("students", [])]
        if len(enrolled) != len(set(enrolled)):
            fail("R10", f"La clase {cid} lista un estudiante más de una vez")
        if room is not None and len(enrolled) > room.capacity:
            fail("R4", f"{cid} tiene {len(enrolled)} estudiantes y el salón {room_id} admite {room.capacity}")
        if len(enrolled) > cls.capacity:
            fail("R5", f"{cid} tiene {len(enrolled)} estudiantes y su cupo es {cls.capacity}")

        placed.append(_Placed(cid, str(room_id), mask, enrolled, grid.format_mask(mask)))

    # Toda clase de la entrada debe estar programada o listada como no programada (R10)
    unscheduled = {str(c) for c in solution.get("unscheduled_classes", [])}
    for cid in sorted(unscheduled & seen):
        fail("R10", f"La clase {cid} aparece como programada y como no programada")
    for cid in sorted(set(classes) - seen - unscheduled):
        fail("R10", f"La clase {cid} no aparece ni programada ni como no programada")

    # ------------------------------------------------------------------
    # Pares de clases programadas: R1 (salón) y R2 (profesor)
    # ------------------------------------------------------------------
    for i, a in enumerate(placed):
        for b in placed[i + 1:]:
            if not masks_overlap(a.mask, b.mask):
                continue
            if a.room_id == b.room_id:
                fail("R1", f"{a.class_id} ({a.text}) y {b.class_id} ({b.text}) comparten el salón {a.room_id}")
            prof_a, prof_b = classes[a.class_id].professor_id, classes[b.class_id].professor_id
            if prof_a == prof_b:
                fail("R2", f"{prof_a} dicta {a.class_id} y {b.class_id} al mismo tiempo")

    # ------------------------------------------------------------------
    # Estudiantes: R9 (solo clases solicitadas) y R3 (sin cruces, dentro de su disponibilidad)
    # ------------------------------------------------------------------
    schedule: dict[str, list[_Placed]] = {}
    for p in placed:
        for sid in p.students:
            student = students.get(sid)
            if student is None:
                fail("R10", f"La clase {p.class_id} tiene un estudiante que no existe: {sid}")
                continue
            if p.class_id not in {r.class_id for r in student.requests}:
                fail("R9", f"{sid} quedó en {p.class_id} sin haberla solicitado")
            if (student.availability_mask & p.mask) != p.mask:
                fail("R3", f"{sid} no está disponible para {p.class_id} ({p.text})")
            schedule.setdefault(sid, []).append(p)

    for sid, taken in schedule.items():
        for i, a in enumerate(taken):
            for b in taken[i + 1:]:
                if masks_overlap(a.mask, b.mask):
                    fail("R3", f"{sid} tiene un cruce entre {a.class_id} ({a.text}) y {b.class_id} ({b.text})")

    return result


def _block_mask(grid: TimeGrid, entry: dict[str, Any], cid: str, fail) -> int | None:
    """Máscara del bloque [start_hour, end_hour) del día indicado; None si el horario es inválido (R7)."""
    day = entry.get("day", grid.day_names[0])
    try:
        start, end = int(entry["start_hour"]), int(entry["end_hour"])
    except (KeyError, TypeError, ValueError):
        fail("R10", f"La clase {cid} no tiene un horario válido")
        return None
    if day not in grid.day_names:
        fail("R7", f"La clase {cid} quedó en un día que no hace parte de la jornada: {day}")
        return None
    if start < grid.start_hour or end > grid.end_hour or start >= end:
        fail("R7", f"La clase {cid} quedó de {start}:00 a {end}:00, fuera de la jornada "
                   f"{grid.start_hour}:00-{grid.end_hour}:00")
        return None
    day_idx = grid.day_names.index(day)
    first = grid.day_hour_to_slot(day_idx, start)
    return ((1 << (end - start)) - 1) << first
