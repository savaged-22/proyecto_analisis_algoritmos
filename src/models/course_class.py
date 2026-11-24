"""Entidad CourseClass: una oferta concreta de clase que debe ubicarse en un horario y un salón."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CourseClass:
    """Clase ofertada.

    Datos de entrada:
        id: Identificador único de la clase (ej. 'INF101-1').
        professor_id: Profesor responsable (definido previamente).
        capacity: Cupo máximo de estudiantes (R5).
        duration_hours: Duración en horas consecutivas, 1 o 2 (R6).
        allowed_starts: Slots donde la clase puede iniciar (R8).
        course_id: Asignatura a la que pertenece (solo informativo).
        course_name: Nombre legible de la asignatura.
        required_room_type: Tipo de salón exigido ('' = cualquiera).

    Calculado al cargar el escenario:
        demand: Número de estudiantes que la solicitaron.

    Resultado del algoritmo:
        assigned_slot / assigned_room_id / time_mask: horario y salón asignados.
        enrolled_students: Estudiantes inscritos.
    """
    id: str
    professor_id: str
    capacity: int
    duration_hours: int
    allowed_starts: list[int]
    course_id: str = ""
    course_name: str = ""
    required_room_type: str = ""
    demand: int = 0
    assigned_slot: int | None = None
    assigned_room_id: str | None = None
    time_mask: int = 0
    enrolled_students: list[str] = field(default_factory=list)

    @property
    def is_scheduled(self) -> bool:
        """Una clase se programa completa (horario y salón) o no se programa (R10)."""
        return self.assigned_slot is not None and self.assigned_room_id is not None

    @property
    def min_room_capacity(self) -> int:
        """Capacidad mínima del salón: no hace falta un salón más grande que los
        estudiantes que pueden llegar a inscribirse, min(cupo, demanda)."""
        return min(self.capacity, self.demand)

    @property
    def available_capacity(self) -> int:
        """Cupos remanentes."""
        return max(0, self.capacity - len(self.enrolled_students))

    def reset_schedule(self) -> None:
        self.assigned_slot = None
        self.assigned_room_id = None
        self.time_mask = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "course_id": self.course_id,
            "course_name": self.course_name,
            "professor_id": self.professor_id,
            "capacity": self.capacity,
            "duration_hours": self.duration_hours,
            "allowed_starts": list(self.allowed_starts),
            "required_room_type": self.required_room_type,
            "demand": self.demand,
            "assigned_slot": self.assigned_slot,
            "assigned_room_id": self.assigned_room_id,
            "time_mask": self.time_mask,
            "enrolled_students": list(self.enrolled_students),
        }
