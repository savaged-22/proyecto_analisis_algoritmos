"""Fase 2: inscripción de estudiantes en las clases ya programadas.

Algoritmo (heurístico, con una DP exacta por estudiante):

1. Cada estudiante arma su mejor horario con la DP de intervalos ponderados,
   usando solo clases programadas, dentro de su disponibilidad y que no le hayan
   negado antes. El peso de cada solicitud es el de config.request_weight, así
   que la DP maximiza la suma de prioridades y, a igual suma, el número de clases.

2. Si una clase recibe más estudiantes que su cupo real, min(cupo, capacidad del
   salón), se queda con los que la pidieron con mayor prioridad; a igual
   prioridad, con el que aparece primero en la entrada. A los demás se les niega
   esa clase.

3. Los estudiantes a los que se les negó alguna clase vuelven al paso 1 sin ella
   (pueden armar otra combinación). Se repite hasta que ninguna clase supere su
   cupo. Termina porque cada ronda niega al menos una solicitud y las negaciones
   nunca se deshacen.

4. Relleno: si al final quedaron cupos libres (por ejemplo, porque alguien soltó
   una clase al replanificar), cada estudiante vuelve a correr la DP con sus
   clases actuales más las que aún tienen cupo, y cambia su horario solo si mejora.
   Termina porque cada cambio aumenta estrictamente el objetivo.

Garantías: nunca hay cruces ni sobrecupo, y el horario de cada estudiante es
óptimo para las clases que tuvo disponibles. El reparto de cupos entre
estudiantes es una heurística: no garantiza el óptimo global.

Complejidad: cada DP cuesta O(R log R) (R = solicitudes del estudiante); cada
ronda, O(S · R log R). El número de rondas está acotado por el total de
solicitudes, aunque en la práctica son pocas (se reporta en las métricas).
"""

from dataclasses import dataclass
from typing import Any

from .. import config
from ..models.course_class import CourseClass
from ..models.room import Room
from ..models.student import Student
from .interval_dp import DPResult, Interval, weighted_interval_scheduling


@dataclass
class Rejection:
    """Registro de un cupo negado (para el reporte y la traza)."""
    round: int
    student_id: str
    class_id: str
    priority: int


class EnrollmentSolver:
    """Reparte cupos entre estudiantes usando la DP por estudiante."""

    def __init__(
        self,
        classes: list[CourseClass],
        students: list[Student],
        rooms: list[Room],
        total_requests: int,
    ) -> None:
        self.classes = {c.id: c for c in classes}
        self.students = list(students)
        self.rooms = {r.id: r for r in rooms}
        self.total_requests = total_requests
        self.order = {s.id: i for i, s in enumerate(self.students)}
        self.priority = {(s.id, r.class_id): r.priority for s in self.students for r in s.requests}

        self.capacity = {
            c.id: min(c.capacity, self.rooms[c.assigned_room_id].capacity)
            for c in classes if c.is_scheduled
        }
        self.denied: dict[str, set[str]] = {s.id: set() for s in self.students}
        self.plans: dict[str, list[str]] = {s.id: [] for s in self.students}
        self.dp_results: dict[str, DPResult] = {}
        self.rejections: list[Rejection] = []

    # ------------------------------------------------------------------
    def solve(self) -> dict[str, Any]:
        for s in self.students:
            s.reset_enrollments()
        for c in self.classes.values():
            c.enrolled_students.clear()

        rounds = self._negotiate()
        improvements = self._fill_free_seats()

        for s in self.students:
            for class_id in self.plans[s.id]:
                s.enroll(self.classes[class_id])

        objective = sum(self._weight(sid, cid) for sid, plan in self.plans.items() for cid in plan)
        return {
            "rounds": rounds,
            "rejections": len(self.rejections),
            "fill_improvements": improvements,
            "objective": objective,
            "attended_requests": sum(len(plan) for plan in self.plans.values()),
        }

    # ------------------------------------------------------------------
    # Pasos 1-3: cada estudiante planea con la DP; las clases llenas niegan cupos
    # ------------------------------------------------------------------
    def _negotiate(self) -> int:
        to_plan = [s.id for s in self.students]
        rounds = 0
        while to_plan:
            rounds += 1
            for sid in to_plan:
                self._plan(sid, allowed=lambda cid, sid=sid: cid not in self.denied[sid])

            holders: dict[str, list[str]] = {}
            for sid, plan in self.plans.items():
                for cid in plan:
                    holders.setdefault(cid, []).append(sid)

            replan: set[str] = set()
            for cid, students in holders.items():
                if len(students) <= self.capacity[cid]:
                    continue
                ranked = sorted(students, key=lambda sid: (-self.priority[(sid, cid)], self.order[sid]))
                for sid in ranked[self.capacity[cid]:]:
                    self.denied[sid].add(cid)
                    self.rejections.append(Rejection(rounds, sid, cid, self.priority[(sid, cid)]))
                    replan.add(sid)
            to_plan = sorted(replan, key=self.order.get)
        return rounds

    # ------------------------------------------------------------------
    # Paso 4: aprovechar cupos que quedaron libres
    # ------------------------------------------------------------------
    def _fill_free_seats(self) -> int:
        occupancy = {cid: 0 for cid in self.capacity}
        for plan in self.plans.values():
            for cid in plan:
                occupancy[cid] += 1

        improvements = 0
        changed = True
        while changed:
            changed = False
            for s in self.students:
                current = set(self.plans[s.id])
                old_weight = sum(self._weight(s.id, cid) for cid in current)
                old_plan, old_result = list(self.plans[s.id]), self.dp_results.get(s.id)
                result = self._plan(
                    s.id, allowed=lambda cid, current=current: cid in current or occupancy[cid] < self.capacity[cid])
                if result.best_weight > old_weight:
                    for cid in current:
                        occupancy[cid] -= 1
                    for cid in self.plans[s.id]:
                        occupancy[cid] += 1
                    improvements += 1
                    changed = True
                else:
                    self.plans[s.id] = old_plan
                    if old_result is not None:
                        self.dp_results[s.id] = old_result
        return improvements

    # ------------------------------------------------------------------
    def _plan(self, student_id: str, allowed) -> DPResult:
        """Corre la DP del estudiante sobre sus clases candidatas y guarda su plan."""
        student = self.students[self.order[student_id]]
        intervals = []
        for req in student.requests:
            cls = self.classes[req.class_id]
            if not cls.is_scheduled or not allowed(cls.id):
                continue
            if (student.availability_mask & cls.time_mask) != cls.time_mask:
                continue
            intervals.append(Interval(
                key=cls.id,
                start=cls.assigned_slot,
                end=cls.assigned_slot + cls.duration_hours,
                weight=self._weight(student_id, cls.id),
            ))
        result = weighted_interval_scheduling(intervals)
        self.dp_results[student_id] = result
        self.plans[student_id] = result.chosen_keys
        return result

    def _weight(self, student_id: str, class_id: str) -> int:
        return config.request_weight(self.priority[(student_id, class_id)], self.total_requests)
