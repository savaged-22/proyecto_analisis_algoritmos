"""Módulo de grafos, algoritmos de coloración, flujo en redes y reportes."""

from .conflict_graph import ConflictGraph, HARD_CONFLICT_WEIGHT, build_conflict_graph
from .dsatur_coloring import DSATURColoringSolver
from .min_cost_flow import FlowEdge, MinCostFlowNetwork, StudentEnrollmentMCMF
from .report import TimetableReport

__all__ = [
    "ConflictGraph",
    "HARD_CONFLICT_WEIGHT",
    "build_conflict_graph",
    "DSATURColoringSolver",
    "FlowEdge",
    "MinCostFlowNetwork",
    "StudentEnrollmentMCMF",
    "TimetableReport",
]
