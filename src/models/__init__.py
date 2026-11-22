"""Paquete de modelos para el sistema de programación académica."""

from .time_mask import (
    DAYS,
    NUM_DAYS,
    SLOTS_PER_DAY,
    START_HOUR,
    END_HOUR,
    TOTAL_SLOTS,
    FULL_WEEK_MASK,
    EMPTY_MASK,
    slot_to_day_hour,
    day_hour_to_slot,
    create_slot_mask,
    create_time_mask,
    masks_overlap,
    mask_to_slots,
    slots_to_mask,
    format_slot,
    format_mask,
    get_all_candidate_slots,
)
from .room import Room
from .professor import Professor
from .course_class import CourseClass
from .student import Student, Request

__all__ = [
    "DAYS",
    "NUM_DAYS",
    "SLOTS_PER_DAY",
    "START_HOUR",
    "END_HOUR",
    "TOTAL_SLOTS",
    "FULL_WEEK_MASK",
    "EMPTY_MASK",
    "slot_to_day_hour",
    "day_hour_to_slot",
    "create_slot_mask",
    "create_time_mask",
    "masks_overlap",
    "mask_to_slots",
    "slots_to_mask",
    "format_slot",
    "format_mask",
    "get_all_candidate_slots",
    "Room",
    "Professor",
    "CourseClass",
    "Student",
    "Request",
]
