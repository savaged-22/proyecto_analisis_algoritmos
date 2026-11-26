"""Fase 2: inscripción de estudiantes (DP por estudiante + reparto de cupos)."""

from .enrollment import EnrollmentSolver, Rejection
from .interval_dp import DPResult, Interval, last_compatible, weighted_interval_scheduling

__all__ = [
    "EnrollmentSolver",
    "Rejection",
    "DPResult",
    "Interval",
    "last_compatible",
    "weighted_interval_scheduling",
]
