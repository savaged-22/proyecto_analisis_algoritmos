"""Reporte de resultados.

Construye, a partir del estado final de las entidades:
- la solución en el formato que lee el verificador ("solution"),
- los horarios por clase, salón, profesor y estudiante (con el motivo de cada
  solicitud pendiente),
- las métricas del informe: cobertura, satisfacción de prioridades (global y por
  nivel), incumplimientos de R1-R10, uso de recursos y tiempos.
"""

from typing import Any

from .. import config
from ..models.course_class import CourseClass
from ..models.professor import Professor
from ..models.room import Room
from ..models.student import Request, Student
from ..models.time_mask import TimeGrid, masks_overlap
from ..verify.verifier import RULES, VerificationResult

# Motivos de una solicitud pendiente, en el orden en que se revisan
REASON_UNSCHEDULED = "clase no programada"
REASON_AVAILABILITY = "fuera de la disponibilidad del estudiante"
REASON_CROSS = "cruce"
REASON_FULL = "cupo agotado"
REASON_OTHER = "sin asignar (había cupo y no había cruce)"


class TimetableReport:
    """Estructura la salida del sistema y calcula sus métricas."""

    def __init__(
        self,
        classes: list[CourseClass],
        rooms: list[Room],
        professors: list[Professor],
        students: list[Student],
        grid: TimeGrid,
        phase1_metrics: dict[str, Any] | None = None,
        phase2_metrics: dict[str, Any] | None = None,
        timings: dict[str, float] | None = None,
        scenario_name: str = "",
    ) -> None:
        self.classes = {c.id: c for c in classes}
        self.rooms = {r.id: r for r in rooms}
        self.professors = {p.id: p for p in professors}
        self.students = {s.id: s for s in students}
        self.grid = grid
        self.phase1_metrics = phase1_metrics or {}
        self.phase2_metrics = phase2_metrics or {}
        self.timings = timings or {}
        self.scenario_name = scenario_name
        self.verification: VerificationResult | None = None

    # ==================================================================
    # Solución (lo que revisa el verificador)
    # ==================================================================
    def build_solution(self) -> dict[str, Any]:
        """Programación final en un formato simple e independiente del algoritmo."""
        scheduled, unscheduled = [], []
        for c in self.classes.values():
            if not c.is_scheduled:
                unscheduled.append(c.id)
                continue
            day, start = self.grid.slot_to_day_hour(c.assigned_slot)
            scheduled.append({
                "class_id": c.id,
                "professor_id": c.professor_id,
                "day": self.grid.day_names[day],
                "start_hour": start,
                "end_hour": start + c.duration_hours,
                "room_id": c.assigned_room_id,
                "students": list(c.enrolled_students),
            })
        return {"classes": scheduled, "unscheduled_classes": unscheduled}

    # ==================================================================
    # Motivo de una solicitud pendiente
    # ==================================================================
    def pending_reason(self, student: Student, request: Request) -> str:
        """Explica por qué una solicitud quedó pendiente, mirando solo el resultado final."""
        cls = self.classes[request.class_id]
        if not cls.is_scheduled:
            return REASON_UNSCHEDULED
        if (student.availability_mask & cls.time_mask) != cls.time_mask:
            return REASON_AVAILABILITY
        priorities = {r.class_id: r.priority for r in student.requests}
        crossing = [self.classes[cid] for cid in student.assigned_classes
                    if masks_overlap(self.classes[cid].time_mask, cls.time_mask)]
        if crossing:
            detail = ", ".join(f"{c.id} (prioridad {priorities.get(c.id, '?')})" for c in crossing)
            return f"{REASON_CROSS} con {detail}"
        if len(cls.enrolled_students) >= self._effective_capacity(cls):
            return REASON_FULL
        return REASON_OTHER

    def _effective_capacity(self, cls: CourseClass) -> int:
        """Cupo real de la clase: el menor entre su cupo y la capacidad del salón (R4, R5)."""
        room = self.rooms.get(cls.assigned_room_id or "")
        return min(cls.capacity, room.capacity) if room else cls.capacity

    # ==================================================================
    # Horarios por clase, salón, profesor y estudiante
    # ==================================================================
    def build_class_schedule_map(self) -> dict[str, dict[str, Any]]:
        """Programación por clase."""
        schedule_map: dict[str, dict[str, Any]] = {}
        for c in self.classes.values():
            prof = self.professors.get(c.professor_id)
            room = self.rooms.get(c.assigned_room_id or "")

            time_str, day_name, start_h, end_h = "No programada", None, None, None
            if c.is_scheduled:
                day_idx, start_h = self.grid.slot_to_day_hour(c.assigned_slot)
                end_h = start_h + c.duration_hours
                time_str = self.grid.format_slot(c.assigned_slot, c.duration_hours)
                day_name = self.grid.day_names[day_idx]

            enrolled_cnt = len(c.enrolled_students)
            schedule_map[c.id] = {
                "class_id": c.id,
                "course_id": c.course_id,
                "course_name": c.course_name,
                "professor_id": c.professor_id,
                "professor_name": prof.name if prof else "Desconocido",
                "room_id": c.assigned_room_id,
                "room_name": room.name if room else "Sin asignar",
                "slot_index": c.assigned_slot,
                "day": day_name,
                "start_hour": start_h,
                "end_hour": end_h,
                "duration_hours": c.duration_hours,
                "time_str": time_str,
                "capacity": c.capacity,
                "demand": c.demand,
                "enrolled_count": enrolled_cnt,
                "enrolled_students": list(c.enrolled_students),
                "occupancy_rate_percent": round(enrolled_cnt / c.capacity * 100.0, 2),
                "is_scheduled": c.is_scheduled,
            }
        return schedule_map

    def build_room_schedule_map(self) -> dict[str, dict[str, Any]]:
        """Uso de cada salón a lo largo de la jornada."""
        room_map: dict[str, dict[str, Any]] = {}
        for r in self.rooms.values():
            timeline: list[dict[str, Any]] = []
            hours_used = 0
            for c in self.classes.values():
                if c.assigned_room_id == r.id and c.is_scheduled:
                    hours_used += c.duration_hours
                    timeline.append({
                        "class_id": c.id,
                        "course_name": c.course_name,
                        "slot_index": c.assigned_slot,
                        "time_str": self.grid.format_slot(c.assigned_slot, c.duration_hours),
                        "duration_hours": c.duration_hours,
                        "enrolled_count": len(c.enrolled_students),
                    })
            timeline.sort(key=lambda item: item["slot_index"])
            room_map[r.id] = {
                "room_id": r.id,
                "room_name": r.name,
                "capacity": r.capacity,
                "room_type": r.room_type,
                "hours_used": hours_used,
                "total_available_slots": self.grid.total_slots,
                "utilization_rate_percent": round(hours_used / self.grid.total_slots * 100.0, 2),
                "timeline": timeline,
            }
        return room_map

    def build_professor_schedule_map(self) -> dict[str, dict[str, Any]]:
        """Agenda y carga de cada profesor."""
        prof_map: dict[str, dict[str, Any]] = {}
        for p in self.professors.values():
            prof_classes = [
                {
                    "class_id": c.id,
                    "course_name": c.course_name,
                    "room_id": c.assigned_room_id,
                    "time_str": self.grid.format_slot(c.assigned_slot, c.duration_hours),
                    "duration_hours": c.duration_hours,
                }
                for c in self.classes.values() if c.professor_id == p.id and c.is_scheduled
            ]
            available_hours = bin(p.availability_mask).count("1")
            prof_map[p.id] = {
                "professor_id": p.id,
                "professor_name": p.name,
                "assigned_hours": p.assigned_hours,
                "available_hours": available_hours,
                "max_hours": p.max_hours,
                "workload_percent": round(p.assigned_hours / available_hours * 100.0, 2) if available_hours else 0.0,
                "classes": prof_classes,
            }
        return prof_map

    def build_student_schedule_map(self) -> dict[str, dict[str, Any]]:
        """Horario de cada estudiante: clases que logró cursar y solicitudes pendientes con su motivo."""
        student_map: dict[str, dict[str, Any]] = {}
        for s in self.students.values():
            priorities = {r.class_id: r.priority for r in s.requests}
            enrolled = []
            for cid in s.assigned_classes:
                c = self.classes[cid]
                prof = self.professors.get(c.professor_id)
                enrolled.append({
                    "class_id": c.id,
                    "course_name": c.course_name,
                    "priority": priorities.get(c.id),
                    "time_str": self.grid.format_slot(c.assigned_slot, c.duration_hours),
                    "room_id": c.assigned_room_id,
                    "professor_name": prof.name if prof else "N/A",
                })
            enrolled.sort(key=lambda e: self.classes[e["class_id"]].assigned_slot)

            pending = [
                {"class_id": r.class_id, "priority": r.priority, "reason": self.pending_reason(s, r)}
                for r in s.requests if r.class_id not in s.assigned_classes
            ]
            student_map[s.id] = {
                "student_id": s.id,
                "student_name": s.name,
                "requests": [r.to_dict() for r in s.requests],
                "enrolled_classes": enrolled,
                "pending_requests": pending,
                "attended_priority_sum": sum(priorities[cid] for cid in s.assigned_classes),
                "requested_priority_sum": sum(priorities.values()),
                "hours_in_class": sum(self.classes[cid].duration_hours for cid in s.assigned_classes),
            }
        return student_map

    # ==================================================================
    # Métricas del informe
    # ==================================================================
    def calculate_global_metrics(self) -> dict[str, Any]:
        """Métricas del informe de resultados."""
        total_classes = len(self.classes)
        unscheduled = [c.id for c in self.classes.values() if not c.is_scheduled]

        requests = [(s, r) for s in self.students.values() for r in s.requests]
        attended = [(s, r) for s, r in requests if r.class_id in s.assigned_classes]
        total_requests, attended_count = len(requests), len(attended)

        received_priority = sum(r.priority for _, r in requests)
        attended_priority = sum(r.priority for _, r in attended)

        by_priority: dict[str, dict[str, Any]] = {}
        for level in sorted(config.PRIORITY_LEVELS, reverse=True):
            level_total = sum(1 for _, r in requests if r.priority == level)
            level_attended = sum(1 for _, r in attended if r.priority == level)
            by_priority[str(level)] = {
                "requests": level_total,
                "attended": level_attended,
                "percent": _percent(level_attended, level_total),
            }

        pending_by_reason: dict[str, int] = {}
        for s, r in requests:
            if r.class_id not in s.assigned_classes:
                key = self.pending_reason(s, r).split(" con ")[0]
                pending_by_reason[key] = pending_by_reason.get(key, 0) + 1

        room_maps = self.build_room_schedule_map()
        prof_maps = self.build_professor_schedule_map()

        return {
            "scenario": self.scenario_name,
            "total_classes": total_classes,
            "scheduled_classes": total_classes - len(unscheduled),
            "unscheduled_classes": len(unscheduled),
            "unscheduled_class_ids": unscheduled,
            "total_students": len(self.students),
            "total_requests": total_requests,
            "attended_requests": attended_count,
            "pending_requests": total_requests - attended_count,
            "coverage_percent": _percent(attended_count, total_requests),
            "received_priority_sum": received_priority,
            "attended_priority_sum": attended_priority,
            "priority_satisfaction_percent": _percent(attended_priority, received_priority),
            "by_priority": by_priority,
            "pending_by_reason": pending_by_reason,
            "violations_total": self.verification.total if self.verification else None,
            "violations_by_rule": self.verification.count_by_rule() if self.verification else None,
            "total_rooms": len(self.rooms),
            "avg_room_utilization_percent": _average(r["utilization_rate_percent"] for r in room_maps.values()),
            "total_professors": len(self.professors),
            "avg_professor_workload_percent": _average(p["workload_percent"] for p in prof_maps.values()),
            "timings_ms": self.timings,
        }

    def to_full_dict(self) -> dict[str, Any]:
        """Salida completa para exportar a JSON."""
        return {
            "metrics": self.calculate_global_metrics(),
            "solution": self.build_solution(),
            "verification": self.verification.to_dict() if self.verification else None,
            "class_schedule": self.build_class_schedule_map(),
            "room_schedule": self.build_room_schedule_map(),
            "professor_schedule": self.build_professor_schedule_map(),
            "student_schedule": self.build_student_schedule_map(),
            "phase1_details": self.phase1_metrics,
            "phase2_details": self.phase2_metrics,
        }

    def format_summary_text(self) -> str:
        """Informe legible para consola."""
        m = self.calculate_global_metrics()
        t = m["timings_ms"]
        sep, sub = "=" * 78, "-" * 78

        levels = " · ".join(
            f"P{lvl}: {d['attended']}/{d['requests']} ({d['percent']}%)" for lvl, d in m["by_priority"].items()
        )
        reasons = " · ".join(f"{k}: {v}" for k, v in m["pending_by_reason"].items()) or "ninguna"
        unscheduled = ", ".join(m["unscheduled_class_ids"]) or "ninguna"

        lines = [
            sep,
            f" INFORME DE RESULTADOS{' - ' + m['scenario'] if m['scenario'] else ''}",
            sep,
            " [1] Programación de clases",
            f"     Programadas:              {m['scheduled_classes']}/{m['total_classes']}",
            f"     Sin programar:            {unscheduled}",
            sub,
            " [2] Solicitudes",
            f"     Recibidas:                {m['total_requests']}",
            f"     Atendidas:                {m['attended_requests']}",
            f"     Pendientes:               {m['pending_requests']}",
            f"     Cobertura:                {m['coverage_percent']}%",
            f"     Pendientes por motivo:    {reasons}",
            sub,
            " [3] Prioridades (suma atendida / suma recibida)",
            f"     Satisfacción:             {m['attended_priority_sum']}/{m['received_priority_sum']} "
            f"({m['priority_satisfaction_percent']}%)",
            f"     Por nivel:                {levels}",
            sub,
            " [4] Restricciones obligatorias (verificador independiente)",
        ]
        if self.verification is None:
            lines.append("     No verificada")
        else:
            lines.append(f"     Incumplimientos:          {self.verification.total}")
            for rule, count in self.verification.count_by_rule().items():
                if count:
                    lines.append(f"       {rule} {RULES[rule]}: {count}")
        lines += [
            sub,
            " [5] Recursos y tiempos",
            f"     Ocupación de salones:     {m['avg_room_utilization_percent']}% promedio",
            f"     Carga de profesores:      {m['avg_professor_workload_percent']}% de su disponibilidad",
            f"     Fase 1: {t.get('phase1_ms', 0):.2f} ms · Fase 2: {t.get('phase2_ms', 0):.2f} ms"
            f" · Total: {t.get('total_ms', 0):.2f} ms",
            sep,
        ]
        return "\n".join(lines)


def _percent(part: float, total: float) -> float:
    return round(part / total * 100.0, 2) if total else 100.0


def _average(values) -> float:
    values = list(values)
    return round(sum(values) / len(values), 2) if values else 0.0
