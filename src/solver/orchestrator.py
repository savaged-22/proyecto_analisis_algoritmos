"""Orquestador único que coordina la carga de datos, Fase 1 (DSATUR), Fase 2 (MCMF) y reportes."""

import json
import time
from pathlib import Path
from typing import Any

from ..data.scenario import Scenario, load_scenario_dict, load_scenario_file
from ..models.time_mask import masks_overlap
from ..graph.conflict_graph import build_conflict_graph
from ..graph.dsatur_coloring import DSATURColoringSolver
from ..graph.min_cost_flow import StudentEnrollmentMCMF
from ..graph.report import TimetableReport


class TimetableOrchestrator:
    """Orquestador central del sistema de programación académica y asignación de cursos."""

    def __init__(self) -> None:
        self.scenario: Scenario | None = None
        self.phase1_results: dict[str, Any] = {}
        self.phase2_results: dict[str, Any] = {}
        self.timings: dict[str, float] = {}
        self.report: TimetableReport | None = None

    # Accesos directos a las entidades del escenario cargado
    @property
    def grid(self):
        return self._require_scenario().grid

    @property
    def rooms(self):
        return self._require_scenario().rooms

    @property
    def professors(self):
        return self._require_scenario().professors

    @property
    def classes(self):
        return self._require_scenario().classes

    @property
    def students(self):
        return self._require_scenario().students

    def _require_scenario(self) -> Scenario:
        if self.scenario is None:
            raise RuntimeError("Primero se debe cargar un escenario.")
        return self.scenario

    def load_scenario_dict(self, data: dict[str, Any]) -> None:
        """Carga y valida un escenario a partir de un diccionario."""
        self.scenario = load_scenario_dict(data)

    def load_scenario_file(self, file_path: str | Path) -> None:
        """Carga y valida un archivo de escenario JSON."""
        self.scenario = load_scenario_file(file_path)

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
            professors=self.professors,
            grid=self.grid
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
            grid=self.grid,
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
            # Validar que solo esté en clases que solicitó (R9)
            requested = {r.class_id for r in s.requests}
            for c in s_classes:
                if c.id not in requested:
                    raise ValueError(f"Violación Estudiante: {s.id} quedó en {c.id} sin haberla solicitado.")

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
