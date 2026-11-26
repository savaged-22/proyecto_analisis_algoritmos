"""Orquestador: carga el escenario y ejecuta fase 1, fase 2, verificación y reporte."""

import json
import time
from pathlib import Path
from typing import Any

from ..data.scenario import Scenario, load_scenario_dict, load_scenario_file
from ..graph.conflict_graph import build_conflict_graph
from .. import config
from ..phase1.scheduler import schedule_classes
from ..phase2.enrollment import EnrollmentSolver
from ..report.complexity import algorithms_used
from ..report.report import TimetableReport
from ..verify.verifier import verify_solution


class TimetableOrchestrator:
    """Orquestador central del sistema de programación académica y asignación de cursos."""

    def __init__(self) -> None:
        self.scenario: Scenario | None = None
        self.phase1_results: dict[str, Any] = {}
        self.phase2_results: dict[str, Any] = {}
        self.timings: dict[str, float] = {}
        self.report: TimetableReport | None = None
        self.enrollment_solver: EnrollmentSolver | None = None
        self.conflict_graph = None
        self.result: dict[str, Any] | None = None

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

    def run(self, phase1_mode: str = config.DEFAULT_PHASE1_MODE) -> dict[str, Any]:
        """Ejecuta la fase 1, la fase 2, el reporte y la verificación independiente.

        Returns:
            Diccionario estructurado con el resultado global y todas las asignaciones.
        """
        t0_total = time.perf_counter()

        # -------------------------------------------------------------
        # 1. Construcción del Grafo de Conflictos
        # -------------------------------------------------------------
        t0_graph = time.perf_counter()
        conflict_graph = build_conflict_graph(self.classes, self.students)
        self.conflict_graph = conflict_graph
        t1_graph = time.perf_counter()
        self.timings["conflict_graph_ms"] = round((t1_graph - t0_graph) * 1000.0, 3)

        # -------------------------------------------------------------
        # 2. Fase 1: ubicar clases en (hora, salón) con DSATUR y, si aplica, backtracking
        # -------------------------------------------------------------
        t0_p1 = time.perf_counter()
        self.phase1_results = schedule_classes(
            classes=self.classes,
            rooms=self.rooms,
            professors=self.professors,
            students=self.students,
            grid=self.grid,
            graph=conflict_graph,
            mode=phase1_mode,
        )
        t1_p1 = time.perf_counter()
        self.timings["phase1_ms"] = round((t1_p1 - t0_p1) * 1000.0, 3)

        # -------------------------------------------------------------
        # 3. Fase 2: inscripción (DP por estudiante + reparto de cupos)
        # -------------------------------------------------------------
        t0_p2 = time.perf_counter()
        self.enrollment_solver = EnrollmentSolver(
            classes=self.classes,
            students=self.students,
            rooms=self.rooms,
            total_requests=self.scenario.total_requests,
        )
        self.phase2_results = self.enrollment_solver.solve()
        t1_p2 = time.perf_counter()
        self.timings["phase2_ms"] = round((t1_p2 - t0_p2) * 1000.0, 3)

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
            timings=self.timings,
            scenario_name=str(self.scenario.metadata.get("name", "")),
        )

        # -------------------------------------------------------------
        # 5. Verificación independiente de R1-R10 sobre la solución final
        # -------------------------------------------------------------
        self.report.verification = verify_solution(self.scenario, self.report.build_solution())
        self.report.algorithms = algorithms_used(self.scenario, self.phase1_results, self.phase2_results,
                                                 self.timings, conflict_graph.get_statistics())

        self.result = self.report.to_full_dict()
        return self.result

    def export_solution(self, output_path: str | Path) -> None:
        """Guarda la solución completa en un archivo JSON."""
        if self.report is None:
            raise RuntimeError("Debe ejecutar run() antes de exportar la solución.")

        path = Path(output_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.result, f, indent=2, ensure_ascii=False)

    def get_summary_text(self) -> str:
        """Retorna el informe legible para consola."""
        if self.report is None:
            return "No se ha ejecutado ninguna optimización."
        return self.report.format_summary_text()
