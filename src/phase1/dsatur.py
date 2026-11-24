"""Fase 1, heurística: coloración DSATUR ponderada con listas de candidatos (hora, salón).

Algoritmo de grado de saturación (Brélaz, 1979) adaptado a horarios:
- Cada clase es un vértice del grafo de conflictos y un "color" es una hora de inicio.
- Cada clase tiene su propia lista de colores posibles (sus horas permitidas), así
  que la saturación se mide como en la coloración por listas: cuántos colores le
  quedan. Los vecinos con el mismo profesor ya programados le quitan horas.
- En cada paso se programa la clase más restringida: la que tiene menos horas
  disponibles; a igual número, la de más horas bloqueadas por vecinos blandos
  (pedidos por los mismos estudiantes, con bitmask: popcount del OR de sus
  máscaras), mayor grado ponderado, mayor duración y mayor demanda.
- Para esa clase se evalúan sus horas permitidas y los salones libres, y se elige
  el par (hora, salón) con menor costo de cruces blandos; a igual costo, el salón
  que menos capacidad desperdicia.
- Si no hay ningún par válido, la clase queda sin programar. No hay retroceso.

Complejidad: O(M^2 · H) para elegir las clases (M pasos, cada uno revisa las
horas de las pendientes) más O(M · H · (d + A)) para evaluar candidatos, con H
horas permitidas, d vecinos y A salones.
"""

from typing import Any

from ..graph.conflict_graph import ConflictGraph
from ..models.course_class import CourseClass
from ..models.professor import Professor
from ..models.room import Room
from ..models.time_mask import TimeGrid, masks_overlap


class DSATURColoringSolver:
    """Solucionador heurístico de la fase 1."""

    def __init__(
        self,
        conflict_graph: ConflictGraph,
        rooms: list[Room],
        professors: list[Professor],
        grid: TimeGrid,
    ) -> None:
        self.graph = conflict_graph
        self.rooms = {r.id: r for r in rooms}
        self.professors = {p.id: p for p in professors}
        self.classes = self.graph.vertices
        self.grid = grid
        # El grado ponderado no cambia durante la ejecución: se calcula una sola vez
        self.weighted_degree = {cid: self.graph.weighted_degree(cid) for cid in self.classes}
        self.steps: list[dict[str, Any]] = []

    def solve(self) -> dict[str, Any]:
        """Programa todas las clases que pueda y devuelve un resumen."""
        unassigned: set[str] = set(self.classes)
        soft_blocked: dict[str, int] = {cid: 0 for cid in unassigned}
        unscheduled: list[str] = []
        total_soft_penalty = 0.0
        self.steps = []

        while unassigned:
            # 1. Clase más restringida
            selected_id = self._select_next_class(unassigned, soft_blocked)
            u = self.classes[selected_id]
            unassigned.remove(selected_id)
            step = {
                "class_id": selected_id,
                "available_starts": self._available_starts(u),
                "soft_saturation": soft_blocked[selected_id].bit_count(),
            }

            # 2. Mejor par (hora, salón)
            best = self._find_best_assignment(u)
            step["candidates"] = self._last_candidates
            if best is None:
                unscheduled.append(selected_id)
                self.steps.append({**step, "result": "sin programar"})
                continue

            slot, mask, room, penalty = best
            total_soft_penalty += penalty
            u.assigned_slot = slot
            u.assigned_room_id = room.id
            u.time_mask = mask
            room.book(mask)
            self.professors[u.professor_id].assign_class(mask, u.duration_hours)
            self.steps.append({**step, "result": "programada", "slot": slot,
                               "time": self.grid.format_slot(slot, u.duration_hours),
                               "room_id": room.id, "soft_penalty": penalty})

            # 3. Actualizar la saturación blanda de los vecinos pendientes (la dura se
            #    refleja sola: el profesor ya tiene ocupada esa franja)
            for neighbor_id in self.graph.get_neighbors(selected_id):
                if neighbor_id in unassigned and not self.graph.is_hard_conflict(selected_id, neighbor_id):
                    soft_blocked[neighbor_id] |= mask

        return {
            "scheduled_count": len(self.classes) - len(unscheduled),
            "unscheduled_count": len(unscheduled),
            "unscheduled_ids": unscheduled,
            "total_soft_penalty": round(total_soft_penalty, 2),
            "success": not unscheduled,
        }

    def _select_next_class(self, unassigned: set[str], soft_blocked: dict[str, int]) -> str:
        """Clase más restringida, con desempates lexicográficos (y por id, para que sea determinista)."""
        def key(cid: str) -> tuple:
            cls = self.classes[cid]
            return (-self._available_starts(cls), soft_blocked[cid].bit_count(),
                    self.weighted_degree[cid], cls.duration_hours, cls.demand, cid)
        return max(unassigned, key=key)

    def _available_starts(self, cls: CourseClass) -> int:
        """Horas permitidas en las que el profesor todavía puede dictar la clase (colores que le quedan)."""
        prof = self.professors[cls.professor_id]
        return sum(1 for slot in cls.allowed_starts
                   if prof.is_available(self.grid.create_slot_mask(slot, cls.duration_hours), cls.duration_hours))

    def _find_best_assignment(self, cls: CourseClass) -> tuple[int, int, Room, float] | None:
        """Par (hora, salón) válido de menor costo para la clase, o None si no hay ninguno."""
        prof = self.professors[cls.professor_id]
        scheduled_neighbors = [
            (self.classes[n_id], weight)
            for n_id, weight in self.graph.get_neighbors(cls.id).items()
            if self.classes[n_id].is_scheduled and not self.graph.is_hard_conflict(cls.id, n_id)
        ]

        best: tuple[int, int, Room, float] | None = None
        best_key = (float("inf"), float("inf"))
        self._last_candidates = []   # lo evaluado en cada hora, para mostrarlo en la interfaz
        for slot in cls.allowed_starts:
            mask = self.grid.create_slot_mask(slot, cls.duration_hours)
            candidate = {"slot": slot, "time": self.grid.format_slot(slot, cls.duration_hours)}
            self._last_candidates.append(candidate)
            # Restricción dura: profesor disponible y sin otra clase a esa hora (R2)
            if not prof.is_available(mask, cls.duration_hours):
                candidate["status"] = "profesor no disponible u ocupado"
                continue
            soft_penalty = sum(w for n, w in scheduled_neighbors if masks_overlap(mask, n.time_mask))
            candidate["penalty"] = soft_penalty
            candidate["crosses"] = [n.id for n, _ in scheduled_neighbors if masks_overlap(mask, n.time_mask)]

            slot_best = None
            for room in self.rooms.values():
                if not room.can_accommodate(cls.min_room_capacity, cls.required_room_type):
                    continue
                if not room.is_free(mask):
                    continue
                if slot_best is None or room.capacity < slot_best.capacity:
                    slot_best = room
                candidate_key = (soft_penalty, room.capacity - cls.min_room_capacity)
                if candidate_key < best_key:
                    best_key = candidate_key
                    best = (slot, mask, room, soft_penalty)
            candidate["status"] = "posible" if slot_best else "sin salón libre"
            candidate["room_id"] = slot_best.id if slot_best else None
        return best
