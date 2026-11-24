"""Entidad Room: salón, su capacidad y su disponibilidad."""

from dataclasses import dataclass
from typing import Any


@dataclass
class Room:
    """Salón o espacio físico.

    Atributos:
        id: Identificador único (ej. 'AULA-01').
        name: Nombre descriptivo.
        capacity: Capacidad máxima de estudiantes (R4).
        availability_mask: Bloques en los que el salón se puede usar (R8).
        room_type: Tipo de salón ('' = genérico, 'laboratorio', ...).
        assigned_mask: Bloques ya ocupados por clases (R1).
    """
    id: str
    name: str
    capacity: int
    availability_mask: int
    room_type: str = ""
    assigned_mask: int = 0

    def can_accommodate(self, min_capacity: int, required_type: str = "") -> bool:
        """El salón sirve para la clase: capacidad suficiente y tipo correcto."""
        if self.capacity < min_capacity:
            return False
        if required_type and self.room_type.lower() != required_type.lower():
            return False
        return True

    def is_free(self, time_mask: int) -> bool:
        """El salón está habilitado y desocupado en ese horario (R1, R8)."""
        is_allowed = (self.availability_mask & time_mask) == time_mask
        is_unoccupied = (self.assigned_mask & time_mask) == 0
        return is_allowed and is_unoccupied

    def book(self, time_mask: int) -> None:
        if not self.is_free(time_mask):
            raise ValueError(f"El salón {self.id} ya está ocupado o no está disponible en ese horario.")
        self.assigned_mask |= time_mask

    def release(self, time_mask: int) -> None:
        self.assigned_mask &= ~time_mask

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "capacity": self.capacity,
            "room_type": self.room_type,
            "availability_mask": self.availability_mask,
            "assigned_mask": self.assigned_mask,
        }
