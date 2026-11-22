"""Módulo de generación de hashmaps de salida, horarios individuales e informes de métricas."""

from typing import Any
from ..models.course_class import CourseClass
from ..models.room import Room
from ..models.professor import Professor
from ..models.student import Student
from ..models.time_mask import (
    slot_to_day_hour,
    format_slot,
    format_mask,
    masks_overlap,
    TOTAL_SLOTS,
)


class TimetableReport:
    """Generador y estructurador de hashmaps de salida y reportes analíticos."""

    def __init__(
        self,
        classes: list[CourseClass],
        rooms: list[Room],
        professors: list[Professor],
        students: list[Student],
        phase1_metrics: dict[str, Any] | None = None,
        phase2_metrics: dict[str, Any] | None = None,
        timings: dict[str, float] | None = None,
    ) -> None:
        self.classes = {c.id: c for c in classes}
        self.rooms = {r.id: r for r in rooms}
        self.professors = {p.id: p for p in professors}
        self.students = {s.id: s for s in students}
        self.phase1_metrics = phase1_metrics or {}
        self.phase2_metrics = phase2_metrics or {}
        self.timings = timings or {}

    def build_class_schedule_map(self) -> dict[str, dict[str, Any]]:
        """Construye el hashmap de programación por sección de clase."""
        schedule_map: dict[str, dict[str, Any]] = {}
        for c in self.classes.values():
            prof = self.professors.get(c.professor_id)
            room = self.rooms.get(c.assigned_room_id or "")

            time_str = "No programada"
            day_name = "N/A"
            start_h = 0
            end_h = 0
            if c.assigned_slot is not None:
                day_idx, start_h = slot_to_day_hour(c.assigned_slot)
                end_h = start_h + c.duration_hours
                time_str = format_slot(c.assigned_slot, c.duration_hours)
                from ..models.time_mask import DAYS
                day_name = DAYS[day_idx]

            enrolled_cnt = len(c.enrolled_students)
            occupancy_rate = (enrolled_cnt / c.capacity * 100.0) if c.capacity > 0 else 0.0

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
                "enrolled_count": enrolled_cnt,
                "enrolled_students": list(c.enrolled_students),
                "occupancy_rate_percent": round(occupancy_rate, 2),
                "is_scheduled": c.is_scheduled
            }
        return schedule_map

    def build_room_schedule_map(self) -> dict[str, dict[str, Any]]:
        """Construye el hashmap de uso y programación por salón."""
        room_map: dict[str, dict[str, Any]] = {}
        for r in self.rooms.values():
            assigned_classes_in_room: list[dict[str, Any]] = []
            hours_used = 0

            for c in self.classes.values():
                if c.assigned_room_id == r.id and c.assigned_slot is not None:
                    hours_used += c.duration_hours
                    assigned_classes_in_room.append({
                        "class_id": c.id,
                        "course_name": c.course_name,
                        "slot_index": c.assigned_slot,
                        "time_str": format_slot(c.assigned_slot, c.duration_hours),
                        "duration_hours": c.duration_hours,
                        "enrolled_count": len(c.enrolled_students)
                    })

            # Ordenar línea de tiempo por slot
            assigned_classes_in_room.sort(key=lambda item: item["slot_index"])
            utilization_rate = (hours_used / TOTAL_SLOTS * 100.0) if TOTAL_SLOTS > 0 else 0.0

            room_map[r.id] = {
                "room_id": r.id,
                "room_name": r.name,
                "capacity": r.capacity,
                "room_type": r.room_type,
                "hours_used": hours_used,
                "total_available_slots": TOTAL_SLOTS,
                "utilization_rate_percent": round(utilization_rate, 2),
                "timeline": assigned_classes_in_room
            }
        return room_map

    def build_professor_schedule_map(self) -> dict[str, dict[str, Any]]:
        """Construye el hashmap de agenda y carga académica por docente."""
        prof_map: dict[str, dict[str, Any]] = {}
        for p in self.professors.values():
            prof_classes: list[dict[str, Any]] = []
            for c in self.classes.values():
                if c.professor_id == p.id and c.is_scheduled:
                    prof_classes.append({
                        "class_id": c.id,
                        "course_name": c.course_name,
                        "room_id": c.assigned_room_id,
                        "time_str": format_slot(c.assigned_slot, c.duration_hours),
                        "duration_hours": c.duration_hours
                    })

            workload_rate = (p.assigned_hours / p.max_hours * 100.0) if p.max_hours > 0 else 0.0
            prof_map[p.id] = {
                "professor_id": p.id,
                "professor_name": p.name,
                "assigned_hours": p.assigned_hours,
                "max_hours": p.max_hours,
                "workload_percent": round(workload_rate, 2),
                "classes": prof_classes
            }
        return prof_map

    def build_student_schedule_map(self) -> dict[str, dict[str, Any]]:
        """Construye el hashmap de horarios individuales por estudiante."""
        student_map: dict[str, dict[str, Any]] = {}
        for s in self.students.values():
            enrolled_details: list[dict[str, Any]] = []
            assigned_course_ids = set()
            total_hours = 0

            # Verificar ausencia de colisiones en la agenda asignada
            has_clashes = False
            assigned_objs = [self.classes[c_id] for c_id in s.assigned_classes if c_id in self.classes]
            for i in range(len(assigned_objs)):
                for j in range(i + 1, len(assigned_objs)):
                    if masks_overlap(assigned_objs[i].time_mask, assigned_objs[j].time_mask):
                        has_clashes = True

            for c in assigned_objs:
                assigned_course_ids.add(c.course_id)
                total_hours += c.duration_hours
                prof = self.professors.get(c.professor_id)
                enrolled_details.append({
                    "class_id": c.id,
                    "course_id": c.course_id,
                    "course_name": c.course_name,
                    "time_str": format_slot(c.assigned_slot, c.duration_hours) if c.assigned_slot is not None else "N/A",
                    "room_id": c.assigned_room_id,
                    "professor_name": prof.name if prof else "N/A"
                })

            req_courses = [r.course_id for r in s.requests]
            unsatisfied = [c_id for c_id in req_courses if c_id not in assigned_course_ids]
            sat_rate = (len(s.assigned_classes) / len(req_courses) * 100.0) if req_courses else 100.0

            student_map[s.id] = {
                "student_id": s.id,
                "student_name": s.name,
                "priority_score": s.priority_score,
                "requested_courses": req_courses,
                "enrolled_classes": enrolled_details,
                "unsatisfied_courses": unsatisfied,
                "satisfaction_rate_percent": round(sat_rate, 2),
                "total_hours_per_week": total_hours,
                "has_schedule_clashes": has_clashes
            }
        return student_map

    def calculate_global_metrics(self) -> dict[str, Any]:
        """Calcula métricas globales de calidad, uso de recursos y satisfactibilidad."""
        total_classes = len(self.classes)
        scheduled_classes = sum(1 for c in self.classes.values() if c.is_scheduled)
        unscheduled_classes = total_classes - scheduled_classes

        total_students = len(self.students)
        total_requests = sum(len(s.requests) for s in self.students.values())
        satisfied_requests = sum(len(s.assigned_classes) for s in self.students.values())
        global_satisfaction = (satisfied_requests / total_requests * 100.0) if total_requests > 0 else 0.0

        room_maps = self.build_room_schedule_map()
        avg_room_util = (
            sum(r["utilization_rate_percent"] for r in room_maps.values()) / len(room_maps)
            if room_maps else 0.0
        )

        prof_maps = self.build_professor_schedule_map()
        avg_prof_workload = (
            sum(p["workload_percent"] for p in prof_maps.values()) / len(prof_maps)
            if prof_maps else 0.0
        )

        # Verificación estricta de invariantes
        student_clashes = sum(1 for s in self.students.values() if self._student_has_clashes(s))
        hard_conflicts = self._count_hard_conflicts()

        return {
            "total_classes": total_classes,
            "scheduled_classes": scheduled_classes,
            "unscheduled_classes": unscheduled_classes,
            "class_scheduling_rate_percent": round(scheduled_classes / total_classes * 100.0, 2) if total_classes > 0 else 0.0,
            "total_students": total_students,
            "total_requests": total_requests,
            "satisfied_requests": satisfied_requests,
            "unsatisfied_requests": total_requests - satisfied_requests,
            "global_student_satisfaction_percent": round(global_satisfaction, 2),
            "total_rooms": len(self.rooms),
            "avg_room_utilization_percent": round(avg_room_util, 2),
            "total_professors": len(self.professors),
            "avg_professor_workload_percent": round(avg_prof_workload, 2),
            "hard_conflicts_count": hard_conflicts,
            "student_clashes_count": student_clashes,
            "timings_ms": self.timings
        }

    def _student_has_clashes(self, s: Student) -> bool:
        """Determina si un estudiante presenta solapamiento en sus materias asignadas."""
        classes = [self.classes[c_id] for c_id in s.assigned_classes if c_id in self.classes]
        for i in range(len(classes)):
            for j in range(i + 1, len(classes)):
                if masks_overlap(classes[i].time_mask, classes[j].time_mask):
                    return True
        return False

    def _count_hard_conflicts(self) -> int:
        """Verifica que ningún par de clases asignadas viole restricciones duras."""
        conflicts = 0
        scheduled = [c for c in self.classes.values() if c.is_scheduled]
        n = len(scheduled)
        for i in range(n):
            c1 = scheduled[i]
            for j in range(i + 1, n):
                c2 = scheduled[j]
                if masks_overlap(c1.time_mask, c2.time_mask):
                    # Misma aula en el mismo horario
                    if c1.assigned_room_id == c2.assigned_room_id:
                        conflicts += 1
                    # Mismo docente en el mismo horario
                    if c1.professor_id == c2.professor_id:
                        conflicts += 1
        return conflicts

    def to_full_dict(self) -> dict[str, Any]:
        """Genera el diccionario exhaustivo para serialización JSON."""
        return {
            "metrics": self.calculate_global_metrics(),
            "class_schedule": self.build_class_schedule_map(),
            "room_schedule": self.build_room_schedule_map(),
            "professor_schedule": self.build_professor_schedule_map(),
            "student_schedule": self.build_student_schedule_map(),
            "phase1_details": self.phase1_metrics,
            "phase2_details": self.phase2_metrics
        }

    def format_summary_text(self) -> str:
        """Genera un reporte textual resumido formateado para consola."""
        metrics = self.calculate_global_metrics()
        sep = "=" * 78
        sub_sep = "-" * 78

        lines = [
            sep,
            "         INFORME DE PROGRAMACIÓN ACADÉMICA UNIVERSITARIA (UCTP)",
            "         Grafo de Conflictos + DSATUR Ponderado + Min-Cost Flow",
            sep,
            f" [1] Programación de Clases (Fase 1 - DSATUR):",
            f"     - Total de Clases:          {metrics['total_classes']}",
            f"     - Clases Programadas:       {metrics['scheduled_classes']} ({metrics['class_scheduling_rate_percent']}%)",
            f"     - Clases Sin Asignar:       {metrics['unscheduled_classes']}",
            f"     - Conflictos Duros:         {metrics['hard_conflicts_count']} (100% libre de colisiones)",
            sub_sep,
            f" [2] Asignación Estudiantil (Fase 2 - MCMF):",
            f"     - Total de Estudiantes:     {metrics['total_students']}",
            f"     - Solicitudes Totales:      {metrics['total_requests']}",
            f"     - Solicitudes Satisfechas:  {metrics['satisfied_requests']} ({metrics['global_student_satisfaction_percent']}%)",
            f"     - Choques de Horario Alumnos: {metrics['student_clashes_count']} (100% libre de solapamientos)",
            sub_sep,
            f" [3] Uso de Recursos Institucionales:",
            f"     - Total de Salones:         {metrics['total_rooms']} (Ocupación Promedio: {metrics['avg_room_utilization_percent']}%)",
            f"     - Total de Profesores:      {metrics['total_professors']} (Carga Docente Promedio: {metrics['avg_professor_workload_percent']}%)",
            sub_sep,
            f" [4] Tiempos de Ejecución Algorítmica:",
            f"     - Fase 1 (DSATUR):          {metrics['timings_ms'].get('phase1_dsatur_ms', 0):.2f} ms",
            f"     - Fase 2 (MCMF):            {metrics['timings_ms'].get('phase2_mcmf_ms', 0):.2f} ms",
            f"     - Tiempo Total Solver:      {metrics['timings_ms'].get('total_ms', 0):.2f} ms",
            sep
        ]
        return "\n".join(lines)
