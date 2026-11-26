"""Grafo de conflictos entre clases."""

from .conflict_graph import ConflictGraph, HARD_CONFLICT_WEIGHT, build_conflict_graph

__all__ = ["ConflictGraph", "HARD_CONFLICT_WEIGHT", "build_conflict_graph"]
