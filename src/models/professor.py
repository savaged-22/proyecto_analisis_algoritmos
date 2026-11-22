"""Entidad Professor para modelar docentes, su carga horaria y disponibilidad."""

from dataclasses import dataclass
from typing import Any
from .time_mask import FULL_WEEK_MASK


@dataclass
class Professor:
    """Representa a un docente universitario.

    Atributos:
        id: Identificador único del profesor (ej. 'PROF-01').
        name: Nombre completo del profesor.
        max_hours: Horas lectivas semanales máximas que puede dictar.
        availability_mask: Horarios en que el profesor tiene disponibilidad para impartir clases.
        assigned_hours: Horas lectivas actualmente programadas.
        assigned_mask: Máscara temporal de las clases asignadas al docente.
    """
    id: str
    name: str
    max_hours: int = 20
    availability_mask: int = FULL_WEEK_MASK
    assigned_hours: int = 0
    assigned_mask: int = 0

    def is_available(self, time_mask: int, duration_hours: int) -> bool:
        """Verifica si el docente puede dictar una clase en la máscara dada sin sobrepasar su carga máxima."""
        is_free_time = (self.availability_mask & time_mask) == time_mask
        is_not_overlapping = (self.assigned_mask & time_mask) == 0
        fits_quota = (self.assigned_hours + duration_hours) <= self.max_hours
        return is_free_time and is_not_overlapping and fits_quota

    def assign_class(self, time_mask: int, duration_hours: int) -> None:
        """Asigna un bloque de horario al docente e incrementa sus horas registradas."""
        if not self.is_available(time_mask, duration_hours):
            raise ValueError(f"El profesor {self.id} no puede asumir la clase en este horario.")
        self.assigned_mask |= time_mask
        self.assigned_hours += duration_hours

    def unassign_class(self, time_mask: int, duration_hours: int) -> None:
        """Remueve la asignación horaria al docente."""
        self.assigned_mask &= ~time_mask
        self.assigned_hours = max(0, self.assigned_hours - duration_hours)

    def to_dict(self) -> dict[str, Any]:
        """Serializa la entidad a un diccionario."""
        return {
            "id": self.id,
            "name": self.name,
            "max_hours": self.max_hours,
            "availability_mask": self.availability_mask,
            "assigned_hours": self.assigned_hours,
            "assigned_mask": self.assigned_mask
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Professor":
        """Instancia un Professor a partir de un diccionario."""
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            max_hours=int(data.get("max_hours", 20)),
            availability_mask=int(data.get("availability_mask", FULL_WEEK_MASK)),
            assigned_hours=int(data.get("assigned_hours", 0)),
            assigned_mask=int(data.get("assigned_mask", 0))
        )
