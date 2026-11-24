"""Fase 1 por fuerza bruta: probar todas las programaciones posibles.

Cada clase puede ir en cualquiera de sus horas permitidas con cualquier salón, o
quedar sin programar: |D_i| = H_i · A + 1 opciones. Se generan todas las
combinaciones (producto cartesiano), se descartan las que incumplen alguna
restricción y se queda la de menor costo.

    hojas = Π |D_i|          tiempo = O(Π |D_i| · M^2)

Es exponencial en el número de clases, por eso solo se permite en instancias
diminutas (ver config.BRUTE_FORCE_MAX_LEAVES). Sirve para dos cosas: comprobar
que el backtracking encuentra el mismo óptimo y mostrar cuánto trabajo ahorran
las podas.
"""

import itertools
import math

from .. import config
from ..models.course_class import CourseClass
from ..models.professor import Professor
from ..models.room import Room
from ..models.time_mask import TimeGrid
from .cost import Assignment, CostBreakdown, ScheduleCost


class InstanceTooLargeError(ValueError):
    """La instancia tiene demasiadas combinaciones para la fuerza bruta."""


class BruteForceScheduler:
    def __init__(
        self,
        classes: list[CourseClass],
        rooms: list[Room],
        professors: list[Professor],
        grid: TimeGrid,
        cost: ScheduleCost,
        max_leaves: int = config.BRUTE_FORCE_MAX_LEAVES,
    ) -> None:
        self.classes = list(classes)
        self.rooms = {r.id: r for r in rooms}
        self.professors = {p.id: p for p in professors}
        self.grid = grid
        self.cost = cost
        self.domains = [
            [(slot, room_id) for slot in c.allowed_starts for room_id in self.rooms] + [None]
            for c in self.classes
        ]
        self.leaves = math.prod(len(d) for d in self.domains)
        if self.leaves > max_leaves:
            raise InstanceTooLargeError(
                f"La fuerza bruta tendría que revisar {self.leaves:,} combinaciones "
                f"(límite {max_leaves:,}). Use el modo exacto (backtracking con poda)."
            )
        self.valid_leaves = 0

    def solve(self) -> tuple[Assignment, CostBreakdown]:
        best: Assignment | None = None
        best_cost: CostBreakdown | None = None
        ids = [c.id for c in self.classes]
        for combo in itertools.product(*self.domains):
            assignment = dict(zip(ids, combo))
            masks = self._valid_masks(assignment)
            if masks is None:
                continue
            self.valid_leaves += 1
            breakdown = self.cost.breakdown(assignment, masks)
            if best_cost is None or breakdown.total < best_cost.total:
                best, best_cost = assignment, breakdown
        return best, best_cost

    def _valid_masks(self, assignment: Assignment) -> dict[str, int] | None:
        """Máscaras de las clases programadas, o None si la combinación incumple una restricción."""
        masks: dict[str, int] = {}
        room_busy = {rid: 0 for rid in self.rooms}
        prof_busy = {pid: 0 for pid in self.professors}
        for c in self.classes:
            choice = assignment[c.id]
            if choice is None:
                continue
            slot, room_id = choice
            room, prof = self.rooms[room_id], self.professors[c.professor_id]
            mask = self.grid.create_slot_mask(slot, c.duration_hours)
            if not room.can_accommodate(c.min_room_capacity, c.required_room_type):
                return None
            if (room.availability_mask & mask) != mask or room_busy[room_id] & mask:
                return None                                     # R8, R1
            if (prof.availability_mask & mask) != mask or prof_busy[prof.id] & mask:
                return None                                     # R2
            room_busy[room_id] |= mask
            prof_busy[prof.id] |= mask
            masks[c.id] = mask
        return masks
