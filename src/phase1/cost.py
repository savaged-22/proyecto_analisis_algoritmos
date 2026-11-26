"""Costo de una programación de clases (lo que minimiza la fase 1).

La fase 1 todavía no inscribe estudiantes, así que estima cuánta prioridad se
perdería con una programación dada:

1. Clase sin programar: se pierden todas sus solicitudes. Cuesta la suma de sus
   prioridades, más una base grande para que programar más clases siempre sea
   mejor (una clase queda sin programar solo si no hay hora y salón válidos).
2. Dos clases pedidas por un mismo estudiante que se cruzan: ese estudiante
   pierde al menos la de menor prioridad. Cuesta el peso de la arista blanda del
   grafo de conflictos, que es la suma de min(prioridad_a, prioridad_b).

    costo = BASE · (clases sin programar) + prioridad de las no programadas + peso de los cruces

Todos los términos son no negativos y cada decisión solo suma, así que el costo
de una programación parcial nunca baja al completarla. Eso es lo que permite
podar en el backtracking: si una rama ya cuesta tanto como la mejor solución
conocida, no puede mejorarla.
"""

from dataclasses import dataclass

from ..graph.conflict_graph import ConflictGraph
from ..models.student import Student

Assignment = dict[str, tuple[int, str] | None]   # clase -> (slot de inicio, salón) o None


@dataclass(frozen=True)
class CostBreakdown:
    unscheduled_classes: int
    unscheduled_priority: int
    overlap_weight: float
    total: float

    def to_dict(self) -> dict[str, float]:
        return {
            "unscheduled_classes": self.unscheduled_classes,
            "unscheduled_priority": self.unscheduled_priority,
            "overlap_weight": self.overlap_weight,
            "total": self.total,
        }


class ScheduleCost:
    """Calcula el costo de una programación y su incremento al ubicar una clase."""

    def __init__(self, graph: ConflictGraph, students: list[Student]) -> None:
        self.graph = graph
        self.class_value: dict[str, int] = {cid: 0 for cid in graph.vertices}
        for s in students:
            for r in s.requests:
                self.class_value[r.class_id] += r.priority

        # Aristas blandas de cada clase (las duras se controlan con el horario del profesor)
        self.soft_neighbors: dict[str, dict[str, float]] = {
            cid: {n: w for n, w in graph.get_neighbors(cid).items() if not graph.is_hard_conflict(cid, n)}
            for cid in graph.vertices
        }
        total_soft = sum(sum(n.values()) for n in self.soft_neighbors.values()) / 2
        self.unscheduled_base = sum(self.class_value.values()) + total_soft + 1

    def unscheduled_cost(self, class_id: str) -> float:
        """Costo de dejar la clase sin programar."""
        return self.unscheduled_base + self.class_value[class_id]

    def overlap_cost(self, class_id: str, mask: int, placed_masks: dict[str, int]) -> float:
        """Costo de ubicar la clase en 'mask' dadas las clases ya ubicadas: sus cruces blandos."""
        return sum(w for n, w in self.soft_neighbors[class_id].items()
                   if n in placed_masks and placed_masks[n] & mask)

    def breakdown(self, assignment: Assignment, masks: dict[str, int]) -> CostBreakdown:
        """Costo de una programación completa, separado por componente.

        masks: máscara de cada clase programada (las de assignment distintas de None).
        """
        unscheduled = [cid for cid, a in assignment.items() if a is None]
        placed = [cid for cid, a in assignment.items() if a is not None]
        overlap = 0.0
        for i, a in enumerate(placed):
            for b in placed[i + 1:]:
                w = self.soft_neighbors[a].get(b, 0.0)
                if w and masks[a] & masks[b]:
                    overlap += w
        lost = sum(self.class_value[cid] for cid in unscheduled)
        total = len(unscheduled) * self.unscheduled_base + lost + overlap
        return CostBreakdown(len(unscheduled), lost, overlap, total)
