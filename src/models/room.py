"""Entidad Room para modelar salones, laboratorios y auditorios."""

from dataclasses import dataclass, field
from typing import Any
from .time_mask import FULL_WEEK_MASK


@dataclass
class Room:
    """Representa un aula o espacio físico universitario.

    Atributos:
        id: Identificador único del salón (ej. 'AULA-101', 'LAB-SIS-1').
        name: Nombre descriptivo del aula.
        capacity: Capacidad máxima de estudiantes que puede albergar.
        room_type: Tipo de salón ('teoria', 'laboratorio', 'auditorio', etc.).
        availability_mask: Máscara de bits con horarios en los que el salón está habilitado.
        assigned_mask: Máscara de bits con los horarios actualmente ocupados por clases.
    """
    id: str
    name: str
    capacity: int
    room_type: str = "teoria"
    availability_mask: int = FULL_WEEK_MASK
    assigned_mask: int = 0

    def can_accommodate(self, class_capacity: int, required_type: str = "") -> bool:
        """Verifica si el salón cumple con la capacidad y el tipo requerido por una clase."""
        if self.capacity < class_capacity:
            return False
        if required_type and self.room_type.lower() != required_type.lower():
            return False
        return True

    def is_free(self, time_mask: int) -> bool:
        """Determina si el salón está disponible en la máscara temporal indicada."""
        is_allowed = (self.availability_mask & time_mask) == time_mask
        is_unoccupied = (self.assigned_mask & time_mask) == 0
        return is_allowed and is_unoccupied

    def book(self, time_mask: int) -> None:
        """Reserva el salón en los slots indicados por la máscara."""
        if not self.is_free(time_mask):
            raise ValueError(f"El salón {self.id} ya se encuentra ocupado o no disponible en ese horario.")
        self.assigned_mask |= time_mask

    def release(self, time_mask: int) -> None:
        """Libera los slots del salón especificados por la máscara."""
        self.assigned_mask &= ~time_mask

    def to_dict(self) -> dict[str, Any]:
        """Serializa la entidad a un diccionario compatible con JSON."""
        return {
            "id": self.id,
            "name": self.name,
            "capacity": self.capacity,
            "room_type": self.room_type,
            "availability_mask": self.availability_mask,
            "assigned_mask": self.assigned_mask
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Room":
        """Instancia un Room desde un diccionario."""
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            capacity=int(data["capacity"]),
            room_type=str(data.get("room_type", "teoria")),
            availability_mask=int(data.get("availability_mask", FULL_WEEK_MASK)),
            assigned_mask=int(data.get("assigned_mask", 0))
        )
