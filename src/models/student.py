"""Entidades Student y Request para modelar las solicitudes y asignaciones estudiantiles."""

from dataclasses import dataclass, field
from typing import Any
from .course_class import CourseClass


@dataclass
class Request:
    """Solicitud de inscripción de una materia por parte de un estudiante.

    Atributos:
        course_id: Código de la asignatura solicitada (ej. 'MAT101').
        priority: Prioridad del estudiante para esta materia (1: máxima, 2: secundaria, etc.).
        preferred_professor_id: ID del docente de preferencia si aplica, o None.
    """
    course_id: str
    priority: int = 1
    preferred_professor_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serializa la solicitud."""
        return {
            "course_id": self.course_id,
            "priority": self.priority,
            "preferred_professor_id": self.preferred_professor_id
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Request":
        """Instancia un Request desde un diccionario."""
        return cls(
            course_id=str(data["course_id"]),
            priority=int(data.get("priority", 1)),
            preferred_professor_id=data.get("preferred_professor_id")
        )


@dataclass
class Student:
    """Representa a un estudiante universitario y sus solicitudes de matrícula.

    Atributos:
        id: Identificador único del alumno (ej. 'EST-001').
        name: Nombre completo del estudiante.
        priority_score: Puntaje de mérito o promedio académico (ej. 3.0 a 5.0).
                        A mayor puntaje, mayor prioridad en la asignación de cupos.
        requests: Lista de solicitudes de asignaturas deseadas.
        assigned_classes: Lista de IDs de CourseClass en las que quedó inscrito.
        schedule_mask: Máscara de bits acumulada con los horarios de sus clases matriculadas.
    """
    id: str
    name: str
    priority_score: float = 1.0
    requests: list[Request] = field(default_factory=list)
    assigned_classes: list[str] = field(default_factory=list)
    schedule_mask: int = 0

    def can_enroll(self, course_class: CourseClass) -> bool:
        """Determina en O(1) si la clase no genera conflicto de horario con su agenda actual."""
        if not course_class.is_scheduled:
            return False
        return (self.schedule_mask & course_class.time_mask) == 0

    def enroll(self, course_class: CourseClass) -> None:
        """Matricula al estudiante en la clase actualizando su máscara y la lista del curso."""
        if not self.can_enroll(course_class):
            raise ValueError(f"Conflicto de horario: el estudiante {self.id} no puede matricular {course_class.id}.")
        self.assigned_classes.append(course_class.id)
        self.schedule_mask |= course_class.time_mask
        if self.id not in course_class.enrolled_students:
            course_class.enrolled_students.append(self.id)

    def unenroll(self, course_class: CourseClass) -> None:
        """Desmatricula al estudiante de la clase."""
        if course_class.id in self.assigned_classes:
            self.assigned_classes.remove(course_class.id)
        if self.id in course_class.enrolled_students:
            course_class.enrolled_students.remove(self.id)
        # Recalcular la máscara limpia
        self.schedule_mask &= ~course_class.time_mask

    def reset_enrollments(self) -> None:
        """Limpia las inscripciones del estudiante."""
        self.assigned_classes.clear()
        self.schedule_mask = 0

    def to_dict(self) -> dict[str, Any]:
        """Serializa la entidad a un diccionario compatible con JSON."""
        return {
            "id": self.id,
            "name": self.name,
            "priority_score": self.priority_score,
            "requests": [req.to_dict() for req in self.requests],
            "assigned_classes": list(self.assigned_classes),
            "schedule_mask": self.schedule_mask
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Student":
        """Instancia un Student a partir de un diccionario."""
        requests_raw = data.get("requests", [])
        parsed_requests = [Request.from_dict(r) for r in requests_raw]
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            priority_score=float(data.get("priority_score", 1.0)),
            requests=parsed_requests,
            assigned_classes=list(data.get("assigned_classes", [])),
            schedule_mask=int(data.get("schedule_mask", 0))
        )
