"""Grafo de conflictos y fase 1 (ubicar clases en hora y salón)."""

from .conflict_graph import ConflictGraph, HARD_CONFLICT_WEIGHT, build_conflict_graph
from .dsatur_coloring import DSATURColoringSolver

__all__ = [
    "ConflictGraph",
    "HARD_CONFLICT_WEIGHT",
    "build_conflict_graph",
    "DSATURColoringSolver",
]
