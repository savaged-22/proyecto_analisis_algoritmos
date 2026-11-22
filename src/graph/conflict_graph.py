"""Grafo no dirigido ponderado de conflictos entre clases universitarias.

Modela las incompatibilidades horarias entre pares de secciones de clase:
1. Conflictos Duros (Hard Conflicts): Mismo docente o secciones del mismo curso.
   Impiden estrictamente cualquier solapamiento temporal.
2. Conflictos Blandos (Soft Conflicts): Demanda estudiantil compartida.
   Dos asignaturas solicitadas por los mismos estudiantes reciben una arista cuyo
   peso es proporcional a la cantidad de estudiantes y sus prioridades/promedios.
"""

from typing import Final, Any
from ..models.course_class import CourseClass
from ..models.student import Student

HARD_CONFLICT_WEIGHT: Final[float] = 1_000_000.0


class ConflictGraph:
    """Grafo no dirigido ponderado para detección y cuantificación de conflictos entre clases."""

    def __init__(self) -> None:
        self.vertices: dict[str, CourseClass] = {}
        self.adj: dict[str, dict[str, float]] = {}
        self.hard_conflicts: set[frozenset[str]] = set()

    def add_vertex(self, course_class: CourseClass) -> None:
        """Registra un vértice correspondiente a una sección de clase."""
        if course_class.id not in self.vertices:
            self.vertices[course_class.id] = course_class
            self.adj[course_class.id] = {}

    def add_edge(self, u_id: str, v_id: str, weight: float, is_hard: bool = False) -> None:
        """Añade o incrementa una arista de conflicto entre dos clases.

        Args:
            u_id: ID de la primera clase.
            v_id: ID de la segunda clase.
            weight: Peso numérico del conflicto (soft weight).
            is_hard: Indica si es un conflicto estricto (mismo docente o mismo curso).
        """
        if u_id == v_id:
            return
        if u_id not in self.vertices or v_id not in self.vertices:
            raise KeyError(f"Los vértices {u_id} y/o {v_id} no existen en el grafo de conflictos.")

        edge_key = frozenset((u_id, v_id))
        if is_hard:
            self.hard_conflicts.add(edge_key)
            eff_weight = HARD_CONFLICT_WEIGHT
        else:
            eff_weight = weight

        # Actualizar adyacencia u -> v y v -> u
        curr_u = self.adj[u_id].get(v_id, 0.0)
        curr_v = self.adj[v_id].get(u_id, 0.0)
        self.adj[u_id][v_id] = max(curr_u + eff_weight, HARD_CONFLICT_WEIGHT if is_hard else curr_u + eff_weight)
        self.adj[v_id][u_id] = max(curr_v + eff_weight, HARD_CONFLICT_WEIGHT if is_hard else curr_v + eff_weight)

    def is_hard_conflict(self, u_id: str, v_id: str) -> bool:
        """Indica si existe una restricción dura que prohíba coincidencia temporal."""
        return frozenset((u_id, v_id)) in self.hard_conflicts

    def get_weight(self, u_id: str, v_id: str) -> float:
        """Retorna el peso del conflicto entre u y v (0.0 si no son adyacentes)."""
        return self.adj.get(u_id, {}).get(v_id, 0.0)

    def get_neighbors(self, u_id: str) -> dict[str, float]:
        """Retorna el diccionario de vecinos de u_id con sus respectivos pesos."""
        return self.adj.get(u_id, {})

    def degree(self, u_id: str) -> int:
        """Número de aristas incidentes en u_id."""
        return len(self.adj.get(u_id, {}))

    def weighted_degree(self, u_id: str) -> float:
        """Suma de pesos de los conflictos incidentes en u_id."""
        return sum(self.adj.get(u_id, {}).values())

    def hard_degree(self, u_id: str) -> int:
        """Número de conflictos duros que afectan a u_id."""
        return sum(1 for v_id in self.adj.get(u_id, {}) if self.is_hard_conflict(u_id, v_id))

    def get_statistics(self) -> dict[str, Any]:
        """Calcula estadísticas topológicas del grafo de conflictos."""
        v_count = len(self.vertices)
        if v_count == 0:
            return {"vertices": 0, "edges": 0, "hard_edges": 0, "soft_edges": 0, "density": 0.0}

        total_edges = sum(len(neighbors) for neighbors in self.adj.values()) // 2
        hard_edges = len(self.hard_conflicts)
        soft_edges = max(0, total_edges - hard_edges)
        max_possible_edges = (v_count * (v_count - 1)) / 2
        density = (total_edges / max_possible_edges) if max_possible_edges > 0 else 0.0

        max_deg_node = max(self.vertices.keys(), key=self.degree, default="")
        max_wdeg_node = max(self.vertices.keys(), key=self.weighted_degree, default="")

        return {
            "vertices": v_count,
            "total_edges": total_edges,
            "hard_edges": hard_edges,
            "soft_edges": soft_edges,
            "density": round(density, 4),
            "max_degree_node": max_deg_node,
            "max_degree": self.degree(max_deg_node) if max_deg_node else 0,
            "max_weighted_degree_node": max_wdeg_node,
            "max_weighted_degree": round(self.weighted_degree(max_wdeg_node), 2) if max_wdeg_node else 0.0
        }


def build_conflict_graph(
    classes: list[CourseClass],
    students: list[Student]
) -> ConflictGraph:
    """Construye el grafo de conflictos integrando restricciones duras y blandas.

    Complejidad: O(M^2 + S * R^2) donde M es el número de clases, S el número de
    estudiantes y R el número promedio de solicitudes por estudiante.

    Args:
        classes: Lista de todas las secciones de clase a programar.
        students: Lista de estudiantes con sus solicitudes de cursos.

    Returns:
        Instancia de ConflictGraph lista para la coloración DSATUR.
    """
    graph = ConflictGraph()
    for cls in classes:
        graph.add_vertex(cls)

    # 1. Conflictos Duros: Mismo profesor y secciones del mismo curso
    num_classes = len(classes)
    for i in range(num_classes):
        c1 = classes[i]
        for j in range(i + 1, num_classes):
            c2 = classes[j]

            # Mismo profesor: prohibido estrictamente coincidir
            if c1.professor_id == c2.professor_id:
                graph.add_edge(c1.id, c2.id, weight=HARD_CONFLICT_WEIGHT, is_hard=True)
            # Mismo curso, distinta sección: conviene no solaparlas para que los estudiantes tengan opciones
            elif c1.course_id == c2.course_id:
                graph.add_edge(c1.id, c2.id, weight=HARD_CONFLICT_WEIGHT, is_hard=True)

    # 2. Mapeo de cursos a sus clases asociadas para rápida indexación
    course_to_classes: dict[str, list[CourseClass]] = {}
    for cls in classes:
        course_to_classes.setdefault(cls.course_id, []).append(cls)

    # 3. Conflictos Blandos: Solicitudes cruzadas de estudiantes
    for student in students:
        req_list = student.requests
        num_reqs = len(req_list)
        if num_reqs < 2:
            continue

        p_score = max(0.5, student.priority_score)
        for i in range(num_reqs):
            r1 = req_list[i]
            c1_classes = course_to_classes.get(r1.course_id, [])
            for j in range(i + 1, num_reqs):
                r2 = req_list[j]
                if r1.course_id == r2.course_id:
                    continue
                c2_classes = course_to_classes.get(r2.course_id, [])

                # Ponderación basada en prioridad de solicitud y mérito del alumno
                req_weight = (10.0 / (r1.priority + r2.priority)) * p_score

                # Añadir conflicto blando entre todas las secciones de r1 y r2
                for cls_a in c1_classes:
                    for cls_b in c2_classes:
                        # Si ya es un conflicto duro, se mantiene duro
                        if not graph.is_hard_conflict(cls_a.id, cls_b.id):
                            graph.add_edge(cls_a.id, cls_b.id, weight=req_weight, is_hard=False)

    return graph
