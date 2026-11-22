"""Orquestador único que coordina la carga de datos, Fase 1 (DSATUR), Fase 2 (MCMF) y reportes."""

import json
import time
from pathlib import Path
from typing import Any

from ..models.room import Room
from ..models.professor import Professor
from ..models.course_class import CourseClass
from ..models.student import Student, Request
from ..models.time_mask import masks_overlap
from ..graph.conflict_graph import build_conflict_graph
from ..graph.dsatur_coloring import DSATURColoringSolver
from ..graph.min_cost_flow import StudentEnrollmentMCMF
from ..graph.report import TimetableReport


class TimetableOrchestrator:
    """Orquestador central del sistema de programación académica y asignación de cursos."""

    def __init__(self) -> None:
        self.rooms: list[Room] = []
        self.professors: list[Professor] = []
        self.classes: list[CourseClass] = []
        self.students: list[Student] = []

        self.phase1_results: dict[str, Any] = {}
        self.phase2_results: dict[str, Any] = {}
        self.timings: dict[str, float] = {}
        self.report: TimetableReport | None = None

    def load_scenario_dict(self, data: dict[str, Any]) -> None:
        """Carga las entidades a partir de un diccionario estructurado."""
        self.rooms = [Room.from_dict(r) for r in data.get("rooms", [])]
        self.professors = [Professor.from_dict(p) for p in data.get("professors", [])]

        # Lectura de clases (pueden venir en lista 'classes' o dentro de 'courses')
        self.classes = []
        if "classes" in data:
            self.classes = [CourseClass.from_dict(c) for c in data["classes"]]
        elif "courses" in data:
            for course in data["courses"]:
                c_id = str(course["id"])
                c_name = str(course.get("name", c_id))
                for sec in course.get("sections", []):
                    sec_data = dict(sec)
                    sec_data.setdefault("course_id", c_id)
                    sec_data.setdefault("course_name", c_name)
                    self.classes.append(CourseClass.from_dict(sec_data))

        self.students = [Student.from_dict(s) for s in data.get("students", [])]

    def load_scenario_file(self, file_path: str | Path) -> None:
        """Carga un archivo de escenario JSON validando su existencia y formato."""
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Archivo de escenario no encontrado: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.load_scenario_dict(data)

    def run(self) -> dict[str, Any]:
        """Ejecuta secuencialmente la Fase 1, Fase 2 y la validación de integridad.

        Returns:
            Diccionario estructurado con el resultado global y todas las asignaciones.
        """
        t0_total = time.perf_counter()

        # -------------------------------------------------------------
        # 1. Construcción del Grafo de Conflictos
        # -------------------------------------------------------------
        t0_graph = time.perf_counter()
        conflict_graph = build_conflict_graph(self.classes, self.students)
        t1_graph = time.perf_counter()
        self.timings["conflict_graph_ms"] = round((t1_graph - t0_graph) * 1000.0, 3)

        # -------------------------------------------------------------
        # 2. Fase 1: Coloración DSATUR Ponderada con Listas (h, s)
        # -------------------------------------------------------------
        t0_p1 = time.perf_counter()
        dsatur_solver = DSATURColoringSolver(
            conflict_graph=conflict_graph,
            rooms=self.rooms,
            professors=self.professors
        )
        self.phase1_results = dsatur_solver.solve()
        t1_p1 = time.perf_counter()
        self.timings["phase1_dsatur_ms"] = round((t1_p1 - t0_p1) * 1000.0, 3)

        # Validación de invariantes de Fase 1
        self._validate_phase1()

        # -------------------------------------------------------------
        # 3. Fase 2: Red de Flujo de Costo Mínimo (MCMF)
        # -------------------------------------------------------------
        t0_p2 = time.perf_counter()
        mcmf_solver = StudentEnrollmentMCMF(
            classes=self.classes,
            students=self.students
        )
        self.phase2_results = mcmf_solver.solve()
        t1_p2 = time.perf_counter()
        self.timings["phase2_mcmf_ms"] = round((t1_p2 - t0_p2) * 1000.0, 3)

        # Validación de invariantes de Fase 2
        self._validate_phase2()

        # -------------------------------------------------------------
        # 4. Generación de Reporte y Métricas
        # -------------------------------------------------------------
        t1_total = time.perf_counter()
        self.timings["total_ms"] = round((t1_total - t0_total) * 1000.0, 3)

        self.report = TimetableReport(
            classes=self.classes,
            rooms=self.rooms,
            professors=self.professors,
            students=self.students,
            phase1_metrics=self.phase1_results,
            phase2_metrics=self.phase2_results,
            timings=self.timings
        )

        return self.report.to_full_dict()

    def _validate_phase1(self) -> None:
        """Verifica que las asignaciones de Fase 1 cumplan estrictamente todas las restricciones duras."""
        scheduled = [c for c in self.classes if c.is_scheduled]
        n = len(scheduled)

        for i in range(n):
            c1 = scheduled[i]
            for j in range(i + 1, n):
                c2 = scheduled[j]
                if masks_overlap(c1.time_mask, c2.time_mask):
                    if c1.assigned_room_id == c2.assigned_room_id:
                        raise ValueError(
                            f"Violación de Salón: Las clases {c1.id} y {c2.id} "
                            f"comparten el aula {c1.assigned_room_id} en el mismo horario."
                        )
                    if c1.professor_id == c2.professor_id:
                        raise ValueError(
                            f"Violación Docente: El profesor {c1.professor_id} tiene asignadas "
                            f"simultáneamente las clases {c1.id} y {c2.id}."
                        )

    def _validate_phase2(self) -> None:
        """Verifica que la asignación de estudiantes cumpla capacidades y no contenga traslapes."""
        for c in self.classes:
            if len(c.enrolled_students) > c.capacity:
                raise ValueError(
                    f"Violación de Capacidad: La clase {c.id} tiene {len(c.enrolled_students)} "
                    f"estudiantes, superando su límite de {c.capacity}."
                )

        classes_by_id = {c.id: c for c in self.classes}
        for s in self.students:
            s_classes = [classes_by_id[c_id] for c_id in s.assigned_classes if c_id in classes_by_id]
            # Validar que no haya dos secciones del mismo curso
            seen_courses = set()
            for c in s_classes:
                if c.course_id in seen_courses:
                    raise ValueError(
                        f"Violación Estudiante: El alumno {s.id} está inscrito en múltiples secciones "
                        f"del curso {c.course_id}."
                    )
                seen_courses.add(c.course_id)

            # Validar que no haya solapamiento horario
            for i in range(len(s_classes)):
                for j in range(i + 1, len(s_classes)):
                    if masks_overlap(s_classes[i].time_mask, s_classes[j].time_mask):
                        raise ValueError(
                            f"Violación Estudiante: El alumno {s.id} tiene choque de horario entre "
                            f"{s_classes[i].id} y {s_classes[j].id}."
                        )

    def export_solution(self, output_path: str | Path) -> None:
        """Guarda la solución completa en un archivo JSON."""
        if self.report is None:
            raise RuntimeError("Debe ejecutar run() antes de exportar la solución.")

        path = Path(output_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        full_data = self.report.to_full_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(full_data, f, indent=2, ensure_ascii=False)

    def get_summary_text(self) -> str:
        """Retorna el informe legible para consola."""
        if self.report is None:
            return "No se ha ejecutado ninguna optimización."
        return self.report.format_summary_text()
