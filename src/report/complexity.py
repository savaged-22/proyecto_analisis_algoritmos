"""Qué algoritmo se usó en cada paso de una ejecución y cuál es su complejidad.

Se arma con lo que el orquestador ya registró (estrategia de la fase 1, nodos de
la búsqueda, rondas de la fase 2, tiempos) y el tamaño de la instancia, para que
el informe diga, en cada escenario, qué se ejecutó y cuánto cuesta.

Notación: M clases, S estudiantes, R solicitudes por estudiante, A salones,
H horas de inicio permitidas por clase, d vecinos de una clase en el grafo y
K clases inscritas por estudiante.
"""

from typing import Any

from .. import config

PHASE1 = {
    "heuristica": {
        "algorithm": "Heurística DSATUR",
        "technique": "Heurística voraz (coloración de grafos por grado de saturación)",
        "complexity": "O(M²·H + M·H·(d + A))",
    },
    "exacto": {
        "algorithm": "Ramificación y poda (exacto)",
        "technique": "Backtracking con poda por restricciones y por cota, arrancando desde DSATUR",
        "complexity": "O(Π (H_i + 1)) en el peor caso: exponencial en M",
    },
    "backtracking": {
        "algorithm": "Backtracking sin cota",
        "technique": "Backtracking con poda solo por restricciones",
        "complexity": "O(Π (H_i + 1)) en el peor caso: exponencial en M",
    },
    "fuerza_bruta": {
        "algorithm": "Fuerza bruta",
        "technique": "Enumeración de todas las combinaciones (hora, salón)",
        "complexity": "Θ(Π (H_i · A + 1) · M²)",
    },
}


def algorithms_used(scenario, phase1: dict[str, Any], phase2: dict[str, Any], timings: dict[str, float],
                    graph_stats: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Una fila por paso: algoritmo, técnica del curso, complejidad, tamaño de la instancia y lo medido."""
    m = len(scenario.classes)
    s = len(scenario.students)
    a = len(scenario.rooms)
    r = max((len(st.requests) for st in scenario.students), default=0)
    h = max((len(c.allowed_starts) for c in scenario.classes), default=0)
    d = (graph_stats or {}).get("max_degree", "-")

    mode = phase1["mode"]
    info = PHASE1[mode]
    search = phase1.get("search") or {}
    if phase1.get("requested_mode") == "auto":
        if mode == "exacto":
            why = f"Automático: M = {m} ≤ {config.EXACT_MAX_CLASSES} clases, se usa la búsqueda exacta."
        else:
            why = f"Automático: M = {m} > {config.EXACT_MAX_CLASSES} clases, se usa la heurística."
    else:
        why = "Elegida en la ejecución."
    if "nodes" in search:
        detail = f"{_miles(search['nodes'])} nodos visitados, {_miles(search['pruned_by_bound'])} podados por cota"
        detail += "; óptimo probado" if phase1.get("optimal") else "; mejor hallado (límite de nodos)"
    elif "leaves" in search:
        detail = f"{_miles(search['leaves'])} combinaciones revisadas, {_miles(search['valid_leaves'])} válidas; óptimo"
    else:
        detail = "Sin búsqueda: una sola pasada"

    return [
        {
            "step": "Grafo de conflictos",
            "algorithm": "Construcción del grafo de conflictos",
            "technique": "Grafos: clases como vértices, conflictos como aristas",
            "complexity": "O(M² + S·R²)",
            "instance": f"M = {m}, S = {s}, R ≤ {r}",
            "measured": f"{timings.get('conflict_graph_ms', 0):.2f} ms",
            "why": "Siempre.",
        },
        {
            "step": "Ubicar clases",
            "algorithm": info["algorithm"],
            "technique": info["technique"],
            "complexity": info["complexity"],
            "problem": "NP-difícil: ubicar las clases sin cruces equivale a colorear el grafo (k-coloración)",
            "instance": f"M = {m}, H ≤ {h}, A = {a}, d ≤ {d}",
            "measured": f"{detail} · {timings.get('phase1_ms', 0):.2f} ms",
            "why": why,
        },
        {
            "step": "Inscribir",
            "algorithm": "Programación dinámica por estudiante + reparto de cupos por prioridad",
            "technique": "Programación dinámica (intervalos ponderados); dividir y conquistar en el "
                         "ordenamiento Θ(n log n) y la búsqueda binaria Θ(log n), por el teorema maestro",
            "complexity": "Θ(R log R) por estudiante; O(S·R log R) por ronda",
            "instance": f"S = {s}, R ≤ {r}",
            "measured": f"{phase2.get('rounds', 0)} ronda(s), {phase2.get('rejections', 0)} cupo(s) negado(s) · "
                        f"{timings.get('phase2_ms', 0):.2f} ms",
            "why": "Siempre.",
        },
        {
            "step": "Verificador",
            "algorithm": "Revisión independiente de las 10 restricciones obligatorias",
            "technique": "Verificación polinomial de una solución (el problema de decisión está en NP)",
            "complexity": "O(M² + S·K²)",
            "instance": f"M = {m}, S = {s}, K ≤ {r}",
            "measured": "Sobre la solución final",
            "why": "Siempre.",
        },
    ]


def _miles(n: int) -> str:
    """12345 -> '12.345'."""
    return f"{n:,}".replace(",", ".")
