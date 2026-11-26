"""Experimentos para el análisis del algoritmo.

1. Escalabilidad: tiempo y calidad al crecer el escenario A (20, 50, 100, 200
   estudiantes, con clases, profesores y salones en proporción), con varias
   semillas. Se estima el exponente empírico del tiempo con una regresión en
   escala log-log: si t ≈ c · n^k, entonces log t = log c + k · log n.

2. Podas: cuánto trabajo hace cada estrategia de la fase 1 sobre los mismos
   escenarios (hojas de la fuerza bruta, nodos del backtracking sin cota y de
   ramificación y poda).

3. Aproximación: en escenarios con conflictos inevitables, qué tan cerca queda
   la heurística (DSATUR) del óptimo (ramificación y poda), medido como
   prioridad atendida por la heurística / prioridad atendida con el óptimo.
"""

import csv
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

from .. import config
from ..data.generator import build_conflict_scenario, build_scale_scenario
from ..data.scenario import load_scenario_dict, load_scenario_file
from ..solver.orchestrator import TimetableOrchestrator

DEFAULT_SIZES = [20, 50, 100, 200]
DEFAULT_SEEDS = [1, 2, 3]


def _run(data_or_path, mode: str) -> dict[str, Any]:
    orch = TimetableOrchestrator()
    if isinstance(data_or_path, Path):
        orch.load_scenario_file(data_or_path)
    else:
        orch.load_scenario_dict(data_or_path)
    return orch.run(phase1_mode=mode)


def loglog_slope(points: list[tuple[float, float]]) -> float | None:
    """Pendiente de la recta de mínimos cuadrados de log(y) contra log(x)."""
    pts = [(math.log(x), math.log(y)) for x, y in points if x > 0 and y > 0]
    if len(pts) < 2:
        return None
    mx, my = mean(p[0] for p in pts), mean(p[1] for p in pts)
    den = sum((x - mx) ** 2 for x, _ in pts)
    return round(sum((x - mx) * (y - my) for x, y in pts) / den, 2) if den else None


# ======================================================================
# 1. Escalabilidad
# ======================================================================
def scalability(sizes: list[int] = DEFAULT_SIZES, seeds: list[int] = DEFAULT_SEEDS,
                modes: tuple[str, ...] = ("heuristica", "exacto")) -> dict[str, Any]:
    rows = []
    _run(build_scale_scenario(min(sizes), seeds[0]), modes[0])   # calentamiento: no se mide
    for mode in modes:
        for n in sizes:
            for seed in seeds:
                data = build_scale_scenario(n, seed)
                result = _run(data, mode)
                m, p1 = result["metrics"], result["phase1_details"]
                rows.append({
                    "mode": mode, "students": n, "seed": seed,
                    "classes": m["total_classes"], "rooms": m["total_rooms"], "requests": m["total_requests"],
                    "scheduled": m["scheduled_classes"], "coverage": m["coverage_percent"],
                    "priority": m["priority_satisfaction_percent"], "violations": m["violations_total"],
                    "nodes": (p1["search"] or {}).get("nodes"), "optimal": p1["optimal"],
                    "phase1_ms": m["timings_ms"]["phase1_ms"], "phase2_ms": m["timings_ms"]["phase2_ms"],
                    "total_ms": m["timings_ms"]["total_ms"],
                })

    summary = []
    for mode in modes:
        by_size = [[r for r in rows if r["mode"] == mode and r["students"] == n] for n in sizes]
        averages = [{
            "mode": mode, "students": group[0]["students"], "classes": group[0]["classes"],
            "coverage": round(mean(r["coverage"] for r in group), 2),
            "priority": round(mean(r["priority"] for r in group), 2),
            "violations": sum(r["violations"] for r in group),
            "phase1_ms": round(mean(r["phase1_ms"] for r in group), 2),
            "phase2_ms": round(mean(r["phase2_ms"] for r in group), 2),
            "total_ms": round(mean(r["total_ms"] for r in group), 2),
        } for group in by_size]
        summary.extend(averages)
    slopes = {
        mode: {key: loglog_slope([(a["students"], a[key]) for a in summary if a["mode"] == mode])
               for key in ("phase1_ms", "phase2_ms", "total_ms")}
        for mode in modes
    }
    return {"rows": rows, "summary": summary, "loglog_slopes": slopes}


# ======================================================================
# 2. Podas
# ======================================================================
def pruning(scenario_paths: list[Path], conflict_sizes: list[int] = (20,), seeds: list[int] = DEFAULT_SEEDS,
            ) -> dict[str, Any]:
    sources: list[tuple[str, Any]] = [(p.stem, p) for p in scenario_paths]
    sources += [(f"conflictos_{n}_s{s}", build_conflict_scenario(n, s)) for n in conflict_sizes for s in seeds]

    rows = []
    for name, source in sources:
        scenario = load_scenario_file(source) if isinstance(source, Path) else load_scenario_dict(source)
        leaves = math.prod(len(c.allowed_starts) * len(scenario.rooms) + 1 for c in scenario.classes)
        row: dict[str, Any] = {"scenario": name, "classes": len(scenario.classes),
                               "brute_force_leaves": leaves}
        for mode in ("backtracking", "exacto"):
            p1 = _run(source, mode)["phase1_details"]
            row[f"{mode}_nodes"] = p1["search"]["nodes"]
            row[f"{mode}_complete"] = not p1["search"]["node_limit_hit"]
            row[f"{mode}_ms"] = p1["search_ms"]
            row[f"{mode}_cost"] = p1["cost"]["total"]
        row["reduction"] = round(row["backtracking_nodes"] / max(1, row["exacto_nodes"]), 1)
        rows.append(row)
    return {"rows": rows, "node_limit": config.EXACT_NODE_LIMIT}


# ======================================================================
# 3. Aproximación
# ======================================================================
def approximation(sizes: list[int] = (20, 50), seeds: list[int] = (1, 2, 3, 4, 5)) -> dict[str, Any]:
    rows = []
    for n in sizes:
        for seed in seeds:
            data = build_conflict_scenario(n, seed)
            h, e = _run(data, "heuristica"), _run(data, "exacto")
            hm, em = h["metrics"], e["metrics"]
            rows.append({
                "students": n, "seed": seed, "classes": hm["total_classes"],
                "heuristic_cost": h["phase1_details"]["cost"]["total"],
                "exact_cost": e["phase1_details"]["cost"]["total"],
                "exact_proven_optimal": e["phase1_details"]["optimal"],
                "exact_nodes": e["phase1_details"]["search"]["nodes"],
                "heuristic_priority": hm["attended_priority_sum"], "exact_priority": em["attended_priority_sum"],
                "heuristic_coverage": hm["coverage_percent"], "exact_coverage": em["coverage_percent"],
                "ratio": round(hm["attended_priority_sum"] / em["attended_priority_sum"], 4)
                if em["attended_priority_sum"] else 1.0,
                "heuristic_ms": h["metrics"]["timings_ms"]["phase1_ms"],
                "exact_ms": e["metrics"]["timings_ms"]["phase1_ms"],
            })
    ratios = [r["ratio"] for r in rows]
    return {
        "rows": rows,
        "mean_ratio": round(mean(ratios), 4),
        "min_ratio": min(ratios),
        "heuristic_optimal_share": round(sum(1 for r in rows if r["heuristic_cost"] == r["exact_cost"]) / len(rows), 2),
    }


# ======================================================================
# Exportación
# ======================================================================
def write_results(out_dir: Path, results: dict[str, dict[str, Any]]) -> list[Path]:
    """Escribe un CSV por experimento y un JSON con todo (lo usa la interfaz)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, data in results.items():
        rows = data.get("rows", [])
        if rows:
            path = out_dir / f"{name}.csv"
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            paths.append(path)
    path = out_dir / "experimentos.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    paths.append(path)
    return paths
