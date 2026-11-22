"""Entidad CourseClass para modelar una sección o clase de una asignatura."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CourseClass:
    """Representa una clase o sección específica de un curso que requiere programación.

    Atributos:
        id: Identificador único de la sección (ej. 'MAT101-1', 'FIS202-A').
        course_id: Código general de la materia (ej. 'MAT101').
        course_name: Nombre legible de la asignatura (ej. 'Cálculo Diferencial').
        professor_id: Identificador del docente a cargo.
        capacity: Límite máximo de inscripciones estudiantiles.
        duration_hours: Duración en horas consecutivas de la sesión (1 o 2 horas).
        required_room_type: Tipo de aula requerida ('teoria', 'laboratorio', etc.).
        assigned_slot: Índice de slot temporal asignado (0 a 49), o None si no está asignado.
        assigned_room_id: ID del aula asignada, o None si no está asignada.
        time_mask: Máscara de bits del bloque horario asignado.
        enrolled_students: Lista de IDs de estudiantes matriculados en esta sección.
    """
    id: str
    course_id: str
    course_name: str
    professor_id: str
    capacity: int
    duration_hours: int = 2
    required_room_type: str = "teoria"
    assigned_slot: int | None = None
    assigned_room_id: str | None = None
    time_mask: int = 0
    enrolled_students: list[str] = field(default_factory=list)

    @property
    def is_scheduled(self) -> bool:
        """Indica si la clase ya cuenta con salón y horario asignado."""
        return self.assigned_slot is not None and self.assigned_room_id is not None and self.time_mask > 0

    @property
    def available_capacity(self) -> int:
        """Retorna los cupos remanentes en la clase."""
        return max(0, self.capacity - len(self.enrolled_students))

    def reset_schedule(self) -> None:
        """Reinicia la asignación de horario y salón."""
        self.assigned_slot = None
        self.assigned_room_id = None
        self.time_mask = 0

    def to_dict(self) -> dict[str, Any]:
        """Serializa la entidad a un formato diccionario."""
        return {
            "id": self.id,
            "course_id": self.course_id,
            "course_name": self.course_name,
            "professor_id": self.professor_id,
            "capacity": self.capacity,
            "duration_hours": self.duration_hours,
            "required_room_type": self.required_room_type,
            "assigned_slot": self.assigned_slot,
            "assigned_room_id": self.assigned_room_id,
            "time_mask": self.time_mask,
            "enrolled_students": list(self.enrolled_students)
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CourseClass":
        """Crea una instancia de CourseClass a partir de un diccionario."""
        return cls(
            id=str(data["id"]),
            course_id=str(data["course_id"]),
            course_name=str(data.get("course_name", data["course_id"])),
            professor_id=str(data["professor_id"]),
            capacity=int(data.get("capacity", 30)),
            duration_hours=int(data.get("duration_hours", 2)),
            required_room_type=str(data.get("required_room_type", "teoria")),
            assigned_slot=data.get("assigned_slot"),
            assigned_room_id=data.get("assigned_room_id"),
            time_mask=int(data.get("time_mask", 0)),
            enrolled_students=list(data.get("enrolled_students", []))
        )
