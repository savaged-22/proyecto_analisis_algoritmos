"""Lectura y validación de escenarios JSON.

Formato de un escenario (todas las horas son horas de inicio de bloques de 1 h):

{
  "parameters": {"num_days": 1, "start_hour": 8, "end_hour": 18},      (opcional)
  "rooms":      [{"id", "name", "capacity", "availability"?, "room_type"?}],
  "professors": [{"id", "name", "availability"?, "max_hours"?}],
  "classes":    [{"id", "professor_id", "capacity", "duration_hours",
                  "allowed_starts"?, "course_id"?, "course_name"?, "required_room_type"?}],
  "students":   [{"id", "name", "requests": [{"class_id", "priority"}], "availability"?}],
  "metadata":   {...},  "expected": {...}                                (opcionales)
}

"availability" y "allowed_starts" aceptan una lista de horas, que aplica a todos
los días (ej. [8, 9, 10]), o un diccionario por día (ej. {"Lunes": [8, 9]}).
Si se omiten, se asume toda la jornada.

La lista de estudiantes de cada clase no es un dato de entrada: se deduce de las
solicitudes, así no hay dos listas que puedan contradecirse.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import config
from ..models import CourseClass, Professor, Request, Room, Student, TimeGrid


class ScenarioError(ValueError):
    """El escenario tiene datos inválidos o inconsistentes."""


@dataclass
class Scenario:
    """Instancia completa del problema, lista para el algoritmo."""
    grid: TimeGrid
    rooms: list[Room]
    professors: list[Professor]
    classes: list[CourseClass]
    students: list[Student]
    metadata: dict[str, Any] = field(default_factory=dict)
    expected: dict[str, Any] = field(default_factory=dict)

    @property
    def total_requests(self) -> int:
        return sum(len(s.requests) for s in self.students)


def load_scenario_file(path: str | Path) -> Scenario:
    """Lee un archivo JSON de escenario y lo valida."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Archivo de escenario no encontrado: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return load_scenario_dict(data)


def load_scenario_dict(data: dict[str, Any]) -> Scenario:
    """Construye un Scenario a partir de un diccionario y valida su consistencia."""
    params = data.get("parameters", {})
    try:
        grid = TimeGrid(
            num_days=int(params.get("num_days", config.DEFAULT_NUM_DAYS)),
            start_hour=int(params.get("start_hour", config.DEFAULT_START_HOUR)),
            end_hour=int(params.get("end_hour", config.DEFAULT_END_HOUR)),
        )
    except ValueError as exc:
        raise ScenarioError(f"Parámetros de jornada inválidos: {exc}") from exc

    rooms = [_parse_room(r, grid) for r in data.get("rooms", [])]
    professors = [_parse_professor(p, grid) for p in data.get("professors", [])]
    classes = [_parse_class(c, grid) for c in data.get("classes", [])]
    students = [_parse_student(s, grid) for s in data.get("students", [])]

    _check_unique_ids("salón", rooms)
    _check_unique_ids("profesor", professors)
    _check_unique_ids("clase", classes)
    _check_unique_ids("estudiante", students)

    professor_ids = {p.id for p in professors}
    for c in classes:
        if c.professor_id not in professor_ids:
            raise ScenarioError(f"La clase {c.id} tiene un profesor inexistente: {c.professor_id}")

    classes_by_id = {c.id: c for c in classes}
    for s in students:
        seen: set[str] = set()
        for req in s.requests:
            if req.class_id not in classes_by_id:
                raise ScenarioError(f"El estudiante {s.id} solicita una clase inexistente: {req.class_id}")
            if req.class_id in seen:
                raise ScenarioError(f"El estudiante {s.id} solicita dos veces la clase {req.class_id}")
            seen.add(req.class_id)
            classes_by_id[req.class_id].demand += 1

    return Scenario(
        grid=grid,
        rooms=rooms,
        professors=professors,
        classes=classes,
        students=students,
        metadata=dict(data.get("metadata", {})),
        expected=dict(data.get("expected", {})),
    )


# ----------------------------------------------------------------------
# Lectura de cada entidad
# ----------------------------------------------------------------------
def _parse_room(d: dict[str, Any], grid: TimeGrid) -> Room:
    rid = _required(d, "id", "salón")
    return Room(
        id=rid,
        name=str(d.get("name", rid)),
        capacity=_positive_int(d, "capacity", f"salón {rid}"),
        availability_mask=_hours_mask(d.get("availability"), grid, f"salón {rid}"),
        room_type=str(d.get("room_type", "")),
    )


def _parse_professor(d: dict[str, Any], grid: TimeGrid) -> Professor:
    pid = _required(d, "id", "profesor")
    max_hours = d.get("max_hours")
    return Professor(
        id=pid,
        name=str(d.get("name", pid)),
        availability_mask=_hours_mask(d.get("availability"), grid, f"profesor {pid}"),
        max_hours=int(max_hours) if max_hours is not None else None,
    )


def _parse_class(d: dict[str, Any], grid: TimeGrid) -> CourseClass:
    cid = _required(d, "id", "clase")
    duration = int(d.get("duration_hours", 1))
    if duration not in config.ALLOWED_DURATIONS:
        raise ScenarioError(f"La clase {cid} dura {duration} h; solo se permiten {config.ALLOWED_DURATIONS} h")

    try:
        starts = grid.hours_to_slots(d.get("allowed_starts"))
    except ValueError as exc:
        raise ScenarioError(f"Horas de inicio inválidas en la clase {cid}: {exc}") from exc
    if "allowed_starts" in d:
        bad = [grid.format_slot(s) for s in starts if not grid.is_valid_start(s, duration)]
        if bad:
            raise ScenarioError(
                f"La clase {cid} ({duration} h) tiene horas de inicio que terminan fuera de la jornada: {bad}"
            )
    else:
        starts = grid.candidate_starts(duration)

    return CourseClass(
        id=cid,
        professor_id=_required(d, "professor_id", f"clase {cid}"),
        capacity=_positive_int(d, "capacity", f"clase {cid}"),
        duration_hours=duration,
        allowed_starts=starts,
        course_id=str(d.get("course_id", cid)),
        course_name=str(d.get("course_name", d.get("course_id", cid))),
        required_room_type=str(d.get("required_room_type", "")),
    )


def _parse_student(d: dict[str, Any], grid: TimeGrid) -> Student:
    sid = _required(d, "id", "estudiante")
    requests: list[Request] = []
    for r in d.get("requests", []):
        class_id = _required(r, "class_id", f"solicitud del estudiante {sid}")
        priority = int(r.get("priority", config.MIN_PRIORITY))
        if priority not in config.PRIORITY_LEVELS:
            raise ScenarioError(
                f"Prioridad {priority} inválida en la solicitud {sid}->{class_id}; "
                f"la escala es {config.MIN_PRIORITY}..{config.MAX_PRIORITY} ({config.MAX_PRIORITY} = más alta)"
            )
        requests.append(Request(class_id=class_id, priority=priority))
    return Student(
        id=sid,
        name=str(d.get("name", sid)),
        requests=requests,
        availability_mask=_hours_mask(d.get("availability"), grid, f"estudiante {sid}"),
    )


# ----------------------------------------------------------------------
# Utilidades de validación
# ----------------------------------------------------------------------
def _required(d: dict[str, Any], key: str, owner: str) -> str:
    if key not in d or d[key] in (None, ""):
        raise ScenarioError(f"Falta el campo '{key}' en {owner}")
    return str(d[key])


def _positive_int(d: dict[str, Any], key: str, owner: str) -> int:
    value = int(d.get(key, 0))
    if value <= 0:
        raise ScenarioError(f"El campo '{key}' de {owner} debe ser positivo (vale {value})")
    return value


def _hours_mask(spec: Any, grid: TimeGrid, owner: str) -> int:
    try:
        return grid.hours_to_mask(spec)
    except ValueError as exc:
        raise ScenarioError(f"Disponibilidad inválida en {owner}: {exc}") from exc


def _check_unique_ids(kind: str, items: list[Any]) -> None:
    seen: set[str] = set()
    for item in items:
        if item.id in seen:
            raise ScenarioError(f"Identificador de {kind} repetido: {item.id}")
        seen.add(item.id)
