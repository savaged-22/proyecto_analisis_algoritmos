"""Entidad Professor: docente, su disponibilidad y su carga asignada."""

from dataclasses import dataclass
from typing import Any


@dataclass
class Professor:
    """Docente universitario.

    Atributos:
        id: Identificador único (ej. 'PROF-01').
        name: Nombre completo.
        availability_mask: Bloques en los que puede dictar clase (R2).
        max_hours: Tope opcional de horas a dictar (None = sin tope).
        assigned_hours / assigned_mask: Carga ya asignada por el algoritmo.
    """
    id: str
    name: str
    availability_mask: int
    max_hours: int | None = None
    assigned_hours: int = 0
    assigned_mask: int = 0

    def is_available(self, time_mask: int, duration_hours: int) -> bool:
        """El profesor puede dictar en ese horario: está disponible, no tiene otra
        clase a la misma hora y no supera su tope de horas (R2)."""
        is_free_time = (self.availability_mask & time_mask) == time_mask
        is_not_overlapping = (self.assigned_mask & time_mask) == 0
        fits_quota = self.max_hours is None or self.assigned_hours + duration_hours <= self.max_hours
        return is_free_time and is_not_overlapping and fits_quota

    def assign_class(self, time_mask: int, duration_hours: int) -> None:
        if not self.is_available(time_mask, duration_hours):
            raise ValueError(f"El profesor {self.id} no puede asumir la clase en este horario.")
        self.assigned_mask |= time_mask
        self.assigned_hours += duration_hours

    def unassign_class(self, time_mask: int, duration_hours: int) -> None:
        self.assigned_mask &= ~time_mask
        self.assigned_hours = max(0, self.assigned_hours - duration_hours)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "max_hours": self.max_hours,
            "availability_mask": self.availability_mask,
            "assigned_hours": self.assigned_hours,
            "assigned_mask": self.assigned_mask,
        }
