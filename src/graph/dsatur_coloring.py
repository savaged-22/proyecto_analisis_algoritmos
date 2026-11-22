"""Fase 1: Coloración DSATUR ponderada con listas de candidatos (h, s).

Implementa el algoritmo de Grado de Saturación (Brélaz, 1979) adaptado a UCTP:
- Cada clase es un vértice.
- Un 'color' es una tupla (h, s), donde 'h' es un slot de inicio y 's' es un aula.
- En cada paso se selecciona la clase no asignada con mayor grado de saturación
  (número de horarios distintos ocupados por sus vecinos en el grafo de conflictos).
- Se desempatan candidatos mediante el grado ponderado de conflictos y duración.
- Se selecciona el par (h, s) factible que minimiza la penalización por solapamientos
  blandos con otras asignaturas deseadas por los mismos estudiantes.
"""

from typing import Any
from ..models.course_class import CourseClass
from ..models.room import Room
from ..models.professor import Professor
from ..models.time_mask import (
    create_slot_mask,
    masks_overlap,
    get_all_candidate_slots,
    format_slot,
)
from .conflict_graph import ConflictGraph, HARD_CONFLICT_WEIGHT


class DSATURColoringSolver:
    """Solucionador de Fase 1 basado en coloración de grafos DSATUR ponderada."""

    def __init__(
        self,
        conflict_graph: ConflictGraph,
        rooms: list[Room],
        professors: list[Professor],
    ) -> None:
        self.graph = conflict_graph
        self.rooms = {r.id: r for r in rooms}
        self.professors = {p.id: p for p in professors}
        self.classes = self.graph.vertices

        # Mapeo de slots candidatos por duración
        self.candidate_slots_by_duration: dict[int, list[tuple[int, int]]] = {
            1: get_all_candidate_slots(1),
            2: get_all_candidate_slots(2),
        }

    def solve(self) -> dict[str, Any]:
        """Ejecuta el algoritmo DSATUR ponderado sobre todas las clases no asignadas.

        Returns:
            Diccionario con resumen de ejecución: clases programadas, no programadas
            y penalización total de conflictos blandos acumulada.
        """
        unassigned: set[str] = set(self.classes.keys())
        scheduled_classes: list[CourseClass] = []
        unscheduled_classes: list[str] = []
        total_soft_penalty: float = 0.0

        # Conjunto de colores (slots) usados por los vecinos de cada vértice
        neighbor_slots: dict[str, set[int]] = {c_id: set() for c_id in unassigned}

        while unassigned:
            # 1. Seleccionar la clase con mayor grado de saturación
            selected_id = self._select_next_class(unassigned, neighbor_slots)
            u = self.classes[selected_id]
            unassigned.remove(selected_id)

            # 2. Encontrar el mejor par (h, s) para u
            best_assignment = self._find_best_assignment(u)

            if best_assignment is None:
                unscheduled_classes.append(selected_id)
                continue

            slot, mask, room, penalty = best_assignment
            total_soft_penalty += penalty

            # 3. Aplicar asignación a la clase, al salón y al docente
            u.assigned_slot = slot
            u.assigned_room_id = room.id
            u.time_mask = mask

            room.book(mask)
            prof = self.professors.get(u.professor_id)
            if prof:
                prof.assign_class(mask, u.duration_hours)

            scheduled_classes.append(u)

            # 4. Actualizar saturación de vecinos no asignados
            for neighbor_id in self.graph.get_neighbors(selected_id):
                if neighbor_id in unassigned:
                    neighbor_slots[neighbor_id].add(slot)

        return {
            "scheduled_count": len(scheduled_classes),
            "unscheduled_count": len(unscheduled_classes),
            "unscheduled_ids": unscheduled_classes,
            "total_soft_penalty": round(total_soft_penalty, 2),
            "success": len(unscheduled_classes) == 0,
        }

    def _select_next_class(
        self,
        unassigned: set[str],
        neighbor_slots: dict[str, set[int]]
    ) -> str:
        """Selecciona el vértice con mayor grado de saturación aplicando desempates lexicográficos."""
        def key_func(c_id: str) -> tuple[int, float, int, int]:
            cls = self.classes[c_id]
            sat_degree = len(neighbor_slots[c_id])
            w_degree = self.graph.weighted_degree(c_id)
            duration = cls.duration_hours
            capacity = cls.capacity
            return (sat_degree, w_degree, duration, capacity)

        return max(unassigned, key=key_func)

    def _find_best_assignment(
        self,
        cls: CourseClass
    ) -> tuple[int, int, Room, float] | None:
        """Busca en el espacio de listas (h, s) el par que satisfaga restricciones duras y minimice el costo."""
        prof = self.professors.get(cls.professor_id)
        if not prof:
            return None

        candidates = self.candidate_slots_by_duration.get(cls.duration_hours, [])
        best_choice: tuple[int, int, Room, float] | None = None
        min_penalty = float("inf")

        # Obtener vecinos ya programados
        scheduled_neighbors: list[tuple[CourseClass, float, bool]] = []
        for n_id, weight in self.graph.get_neighbors(cls.id).items():
            neighbor = self.classes[n_id]
            if neighbor.is_scheduled:
                is_hard = self.graph.is_hard_conflict(cls.id, n_id)
                scheduled_neighbors.append((neighbor, weight, is_hard))

        # Evaluar pares (h, s)
        for slot, mask in candidates:
            # Restricción dura: Docente disponible en el horario
            if not prof.is_available(mask, cls.duration_hours):
                continue

            # Restricción dura: No solapamiento con vecinos con conflicto duro
            has_hard_overlap = False
            for neighbor, _, is_hard in scheduled_neighbors:
                if is_hard and masks_overlap(mask, neighbor.time_mask):
                    has_hard_overlap = True
                    break
            if has_hard_overlap:
                continue

            # Calcular penalización de conflictos blandos para este slot
            slot_soft_penalty = 0.0
            for neighbor, weight, is_hard in scheduled_neighbors:
                if not is_hard and masks_overlap(mask, neighbor.time_mask):
                    slot_soft_penalty += weight

            # Buscar salón compatible libre
            for room in self.rooms.values():
                if not room.can_accommodate(cls.capacity, cls.required_room_type):
                    continue
                if not room.is_free(mask):
                    continue

                # Penalización por desperdicio de capacidad de aula (ajuste fino)
                room_waste_penalty = (room.capacity - cls.capacity) * 0.01
                total_candidate_penalty = slot_soft_penalty + room_waste_penalty

                if total_candidate_penalty < min_penalty:
                    min_penalty = total_candidate_penalty
                    best_choice = (slot, mask, room, slot_soft_penalty)
                    # Si no hay penalización blanda y el aula ajusta muy bien, es una opción excelente
                    if min_penalty == 0.0:
                        return best_choice

        return best_choice
