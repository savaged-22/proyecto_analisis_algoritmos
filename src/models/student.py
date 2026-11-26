"""Entidades Student y Request: solicitudes de los estudiantes y sus inscripciones."""

from dataclasses import dataclass, field
from typing import Any

from .course_class import CourseClass


@dataclass
class Request:
    """Solicitud (estudiante, clase).

    Atributos:
        class_id: Clase solicitada.
        priority: Importancia académica de 1 a 3 (3 es la más alta).
    """
    class_id: str
    priority: int

    def to_dict(self) -> dict[str, Any]:
        return {"class_id": self.class_id, "priority": self.priority}


@dataclass
class Student:
    """Estudiante con sus solicitudes.

    Atributos:
        id: Identificador único (ej. 'EST-001').
        name: Nombre.
        requests: Solicitudes del estudiante.
        availability_mask: Bloques en los que puede asistir (por defecto, toda la jornada).
        assigned_classes: Clases en las que quedó inscrito (resultado).
        schedule_mask: Bloques ocupados por sus clases inscritas (resultado).
    """
    id: str
    name: str
    requests: list[Request]
    availability_mask: int
    assigned_classes: list[str] = field(default_factory=list)
    schedule_mask: int = 0

    def can_enroll(self, course_class: CourseClass) -> bool:
        """La clase está programada, cabe en su disponibilidad y no cruza con su agenda (R3). O(1)."""
        if not course_class.is_scheduled:
            return False
        fits_availability = (self.availability_mask & course_class.time_mask) == course_class.time_mask
        return fits_availability and (self.schedule_mask & course_class.time_mask) == 0

    def enroll(self, course_class: CourseClass) -> None:
        if not self.can_enroll(course_class):
            raise ValueError(f"Conflicto de horario: el estudiante {self.id} no puede inscribir {course_class.id}.")
        self.assigned_classes.append(course_class.id)
        self.schedule_mask |= course_class.time_mask
        if self.id not in course_class.enrolled_students:
            course_class.enrolled_students.append(self.id)

    def unenroll(self, course_class: CourseClass) -> None:
        if course_class.id in self.assigned_classes:
            self.assigned_classes.remove(course_class.id)
        if self.id in course_class.enrolled_students:
            course_class.enrolled_students.remove(self.id)
        self.schedule_mask &= ~course_class.time_mask

    def reset_enrollments(self) -> None:
        self.assigned_classes.clear()
        self.schedule_mask = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "requests": [req.to_dict() for req in self.requests],
            "availability_mask": self.availability_mask,
            "assigned_classes": list(self.assigned_classes),
            "schedule_mask": self.schedule_mask,
        }
