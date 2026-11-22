"""Fase 2: Red de flujo de costo mínimo (Min-Cost Max-Flow) para inscripciones estudiantiles.

Modela la asignación de cupos como un problema de flujo de costo mínimo con restricciones
de compatibilidad horaria:
- Vértices:
    - Fuente (SRC)
    - Estudiantes (STUDENT_{id})
    - Solicitudes de materia (REQ_{student_id}_{course_id})
    - Clases / Secciones (CLASS_{class_id})
    - Sumidero (SNK)
- Capacidades:
    - SRC -> Estudiante: Cantidad máxima de materias a cursar.
    - Estudiante -> Solicitud: 1 (a lo sumo una sección por asignatura).
    - Solicitud -> Clase: 1 (si la clase pertenece a la asignatura).
    - Clase -> SNK: Capacidad máxima del aula/sección.
- Costos:
    - Reflejan la prioridad de la solicitud y el mérito/promedio del estudiante.
    - Menor costo = Mayor prioridad de asignación.
- Restricción temporal:
    - Durante el aumento de flujo sucesivo (Successive Shortest Path), se garantiza
      que un estudiante no sea asignado a dos clases con solapamiento en sus time_masks.
"""

from collections import deque
from dataclasses import dataclass
from typing import Any
from ..models.course_class import CourseClass
from ..models.student import Student
from ..models.time_mask import masks_overlap


@dataclass
class FlowEdge:
    """Arista dirigida para la red de flujo residual."""
    u: str
    v: str
    capacity: int
    flow: int
    cost: int
    rev_index: int
    class_id: str | None = None
    student_id: str | None = None


class MinCostFlowNetwork:
    """Implementación de Red de Flujo Residual para Min-Cost Flow."""

    def __init__(self) -> None:
        self.adj: dict[str, list[FlowEdge]] = {}

    def add_node(self, node: str) -> None:
        """Registra un nodo en la red si no existe."""
        if node not in self.adj:
            self.adj[node] = []

    def add_edge(
        self,
        u: str,
        v: str,
        capacity: int,
        cost: int,
        class_id: str | None = None,
        student_id: str | None = None
    ) -> None:
        """Agrega una arista directa y su correspondiente arista residual."""
        self.add_node(u)
        self.add_node(v)

        forward_edge = FlowEdge(
            u=u,
            v=v,
            capacity=capacity,
            flow=0,
            cost=cost,
            rev_index=len(self.adj[v]),
            class_id=class_id,
            student_id=student_id
        )
        backward_edge = FlowEdge(
            u=v,
            v=u,
            capacity=0,
            flow=0,
            cost=-cost,
            rev_index=len(self.adj[u]),
            class_id=class_id,
            student_id=student_id
        )

        self.adj[u].append(forward_edge)
        self.adj[v].append(backward_edge)


class StudentEnrollmentMCMF:
    """Coordinador de Fase 2: Inscripción de estudiantes mediante Min-Cost Max-Flow."""

    SRC: str = "SRC"
    SNK: str = "SNK"

    def __init__(
        self,
        classes: list[CourseClass],
        students: list[Student]
    ) -> None:
        self.classes = {c.id: c for c in classes}
        self.students = {s.id: s for s in students}
        self.network = MinCostFlowNetwork()

        # Mapeo auxiliar de curso -> clases disponibles
        self.course_classes: dict[str, list[CourseClass]] = {}
        for c in classes:
            if c.is_scheduled:
                self.course_classes.setdefault(c.course_id, []).append(c)

    def build_network(self) -> None:
        """Construye la red dirigida de flujo con costos basados en prioridades."""
        net = self.network
        net.add_node(self.SRC)
        net.add_node(self.SNK)

        # 1. SRC -> Estudiante
        for student in self.students.values():
            s_node = f"STU_{student.id}"
            max_courses = len(student.requests)
            net.add_edge(self.SRC, s_node, capacity=max_courses, cost=0)

            # 2. Estudiante -> Solicitud de materia
            for req in student.requests:
                req_node = f"REQ_{student.id}_{req.course_id}"
                net.add_edge(s_node, req_node, capacity=1, cost=0)

                # 3. Solicitud -> Secciones programadas del curso
                available_sections = self.course_classes.get(req.course_id, [])
                for cls in available_sections:
                    cls_node = f"CLS_{cls.id}"

                    # Función de costo:
                    # - Menor costo para mayor prioridad del requerimiento (req.priority: 1, 2, 3...)
                    # - Menor costo para mayor promedio/puntaje del estudiante
                    # - Bonificación si coincide con el profesor preferido
                    base_cost = 100
                    priority_penalty = (req.priority - 1) * 30
                    merit_discount = int((student.priority_score - 1.0) * 15)
                    pref_prof_discount = 20 if (req.preferred_professor_id == cls.professor_id) else 0

                    edge_cost = max(1, base_cost + priority_penalty - merit_discount - pref_prof_discount)

                    net.add_edge(
                        req_node,
                        cls_node,
                        capacity=1,
                        cost=edge_cost,
                        class_id=cls.id,
                        student_id=student.id
                    )

        # 4. Clase -> SNK
        for cls in self.classes.values():
            if cls.is_scheduled:
                cls_node = f"CLS_{cls.id}"
                net.add_edge(cls_node, self.SNK, capacity=cls.capacity, cost=0)

    def solve(self) -> dict[str, Any]:
        """Ejecuta el algoritmo Successive Shortest Path (SSP) con verificación de no colisión temporal.

        Returns:
            Diccionario con métricas de asignación, flujo total y costo mínimo.
        """
        self.build_network()

        # Limpiar asignaciones previas
        for s in self.students.values():
            s.reset_enrollments()
        for c in self.classes.values():
            c.enrolled_students.clear()

        total_flow = 0
        total_cost = 0

        # Máscaras de horario acumuladas por estudiante para chequeo O(1) de colisión
        student_masks: dict[str, int] = {s_id: 0 for s_id in self.students}

        while True:
            # Buscar el camino de aumento de costo mínimo libre de conflictos para el estudiante
            path, student_id, cls_id = self._find_conflict_free_shortest_path(student_masks)
            if not path or student_id is None or cls_id is None:
                break

            # Aumentar 1 unidad de flujo a lo largo del camino
            target_class = self.classes[cls_id]
            student = self.students[student_id]

            for edge in path:
                edge.flow += 1
                rev_edge = self.network.adj[edge.v][edge.rev_index]
                rev_edge.flow -= 1
                total_cost += edge.cost

            total_flow += 1

            # Asignar formalmente al estudiante y actualizar su máscara de horarios
            student.enroll(target_class)
            student_masks[student_id] |= target_class.time_mask

        # Métricas de satisfacción
        total_requests = sum(len(s.requests) for s in self.students.values())
        satisfaction_rate = (total_flow / total_requests * 100.0) if total_requests > 0 else 0.0

        return {
            "total_flow": total_flow,
            "total_requests": total_requests,
            "satisfaction_rate": round(satisfaction_rate, 2),
            "total_cost": total_cost,
            "unsatisfied_requests": total_requests - total_flow
        }

    def _find_conflict_free_shortest_path(
        self,
        student_masks: dict[str, int]
    ) -> tuple[list[FlowEdge] | None, str | None, str | None]:
        """Encuentra mediante SPFA el camino de costo mínimo desde SRC a SNK sin conflictos horarios."""
        dist: dict[str, float] = {node: float("inf") for node in self.network.adj}
        parent_edge: dict[str, FlowEdge | None] = {node: None for node in self.network.adj}
        path_student: dict[str, str | None] = {node: None for node in self.network.adj}
        path_class: dict[str, str | None] = {node: None for node in self.network.adj}
        in_queue: dict[str, bool] = {node: False for node in self.network.adj}

        dist[self.SRC] = 0.0
        queue: deque[str] = deque([self.SRC])
        in_queue[self.SRC] = True

        while queue:
            u = queue.popleft()
            in_queue[u] = False

            curr_dist = dist[u]
            curr_stu = path_student[u]
            curr_cls = path_class[u]

            for edge in self.network.adj[u]:
                residual_cap = edge.capacity - edge.flow
                if residual_cap <= 0:
                    continue

                v = edge.v
                cand_cost = curr_dist + edge.cost

                # Determinar el estudiante asociado a este camino
                edge_stu = edge.student_id or curr_stu
                if u == self.SRC and v.startswith("STU_"):
                    edge_stu = v.replace("STU_", "")

                # Determinar la clase involucrada y verificar compatibilidad horaria
                edge_cls = edge.class_id or curr_cls
                if edge.class_id is not None and edge_stu is not None:
                    # Validar que la clase no choque con lo ya matriculado por el estudiante
                    cls_obj = self.classes[edge.class_id]
                    if masks_overlap(student_masks[edge_stu], cls_obj.time_mask):
                        # Conflicto de horario: esta arista no es viable para este estudiante
                        continue

                if cand_cost < dist[v]:
                    dist[v] = cand_cost
                    parent_edge[v] = edge
                    path_student[v] = edge_stu
                    path_class[v] = edge_cls

                    if not in_queue[v]:
                        queue.append(v)
                        in_queue[v] = True

        if dist[self.SNK] == float("inf"):
            return None, None, None

        # Reconstruir camino desde SNK hasta SRC
        path: list[FlowEdge] = []
        curr = self.SNK
        target_student = path_student[self.SNK]
        target_class = path_class[self.SNK]

        while curr != self.SRC:
            edge = parent_edge[curr]
            if edge is None:
                return None, None, None
            path.append(edge)
            curr = edge.u

        path.reverse()
        return path, target_student, target_class
