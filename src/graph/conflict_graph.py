"""Grafo no dirigido ponderado de conflictos entre clases.

Cada vértice es una clase. Las aristas indican pares de clases que no conviene
(o no se puede) ubicar a la misma hora:

1. Conflicto duro: las dos clases tienen el mismo profesor. No pueden cruzarse (R2).
2. Conflicto blando: algún estudiante solicitó ambas clases. Si se cruzan, ese
   estudiante pierde al menos la de menor prioridad (R3). El peso de la arista
   es la suma, sobre esos estudiantes, de min(prioridad_a, prioridad_b).

Programar las clases sin cruces equivale a colorear este grafo con las horas de
la jornada como colores; por eso el problema hereda la dificultad de la
coloración de grafos.
"""

from typing import Any, Final

from ..models.course_class import CourseClass
from ..models.student import Student

HARD_CONFLICT_WEIGHT: Final[float] = 1_000_000.0


class ConflictGraph:
    """Grafo no dirigido ponderado de conflictos entre clases."""

    def __init__(self) -> None:
        self.vertices: dict[str, CourseClass] = {}
        self.adj: dict[str, dict[str, float]] = {}
        self.hard_conflicts: set[frozenset[str]] = set()

    def add_vertex(self, course_class: CourseClass) -> None:
        if course_class.id not in self.vertices:
            self.vertices[course_class.id] = course_class
            self.adj[course_class.id] = {}

    def add_edge(self, u_id: str, v_id: str, weight: float, is_hard: bool = False) -> None:
        """Agrega una arista o suma peso a una existente.

        Una arista dura tiene peso fijo HARD_CONFLICT_WEIGHT; una blanda acumula
        el peso de cada estudiante que pide ambas clases.
        """
        if u_id == v_id:
            return
        if u_id not in self.vertices or v_id not in self.vertices:
            raise KeyError(f"Los vértices {u_id} y/o {v_id} no existen en el grafo de conflictos.")

        if is_hard:
            self.hard_conflicts.add(frozenset((u_id, v_id)))
            self.adj[u_id][v_id] = HARD_CONFLICT_WEIGHT
            self.adj[v_id][u_id] = HARD_CONFLICT_WEIGHT
        else:
            self.adj[u_id][v_id] = self.adj[u_id].get(v_id, 0.0) + weight
            self.adj[v_id][u_id] = self.adj[v_id].get(u_id, 0.0) + weight

    def is_hard_conflict(self, u_id: str, v_id: str) -> bool:
        return frozenset((u_id, v_id)) in self.hard_conflicts

    def get_weight(self, u_id: str, v_id: str) -> float:
        return self.adj.get(u_id, {}).get(v_id, 0.0)

    def get_neighbors(self, u_id: str) -> dict[str, float]:
        return self.adj.get(u_id, {})

    def degree(self, u_id: str) -> int:
        return len(self.adj.get(u_id, {}))

    def weighted_degree(self, u_id: str) -> float:
        return sum(self.adj.get(u_id, {}).values())

    def hard_degree(self, u_id: str) -> int:
        return sum(1 for v_id in self.adj.get(u_id, {}) if self.is_hard_conflict(u_id, v_id))

    def get_statistics(self) -> dict[str, Any]:
        """Estadísticas topológicas del grafo."""
        v_count = len(self.vertices)
        if v_count == 0:
            return {"vertices": 0, "total_edges": 0, "hard_edges": 0, "soft_edges": 0, "density": 0.0}

        total_edges = sum(len(neighbors) for neighbors in self.adj.values()) // 2
        hard_edges = len(self.hard_conflicts)
        max_possible_edges = v_count * (v_count - 1) / 2
        density = total_edges / max_possible_edges if max_possible_edges > 0 else 0.0
        max_deg_node = max(self.vertices, key=self.degree)

        return {
            "vertices": v_count,
            "total_edges": total_edges,
            "hard_edges": hard_edges,
            "soft_edges": total_edges - hard_edges,
            "density": round(density, 4),
            "max_degree_node": max_deg_node,
            "max_degree": self.degree(max_deg_node),
        }


def build_conflict_graph(classes: list[CourseClass], students: list[Student]) -> ConflictGraph:
    """Construye el grafo de conflictos.

    Complejidad: O(M^2 + S * R^2), con M clases, S estudiantes y R solicitudes
    por estudiante (pares de profesores + pares de solicitudes de cada estudiante).
    """
    graph = ConflictGraph()
    for cls in classes:
        graph.add_vertex(cls)

    # 1. Conflictos duros: mismo profesor
    for i in range(len(classes)):
        for j in range(i + 1, len(classes)):
            if classes[i].professor_id == classes[j].professor_id:
                graph.add_edge(classes[i].id, classes[j].id, HARD_CONFLICT_WEIGHT, is_hard=True)

    # 2. Conflictos blandos: pares de clases solicitadas por un mismo estudiante
    for student in students:
        reqs = student.requests
        for i in range(len(reqs)):
            for j in range(i + 1, len(reqs)):
                a, b = reqs[i], reqs[j]
                if not graph.is_hard_conflict(a.class_id, b.class_id):
                    graph.add_edge(a.class_id, b.class_id, weight=min(a.priority, b.priority))

    return graph
