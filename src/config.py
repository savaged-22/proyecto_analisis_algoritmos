"""Reglas y parámetros del problema, reunidos en un solo lugar.

Si cambia una regla (la escala de prioridades, la jornada por defecto, el
objetivo), se cambia aquí y el resto del sistema la toma de este módulo.
"""

from typing import Final

# ----------------------------------------------------------------------
# Jornada por defecto (un escenario puede cambiarla en "parameters")
# ----------------------------------------------------------------------
DEFAULT_NUM_DAYS: Final[int] = 1
DEFAULT_START_HOUR: Final[int] = 8
DEFAULT_END_HOUR: Final[int] = 18
ALLOWED_DURATIONS: Final[tuple[int, ...]] = (1, 2)

# ----------------------------------------------------------------------
# Prioridad de las solicitudes: 1 a 3, donde 3 es la más alta
# ----------------------------------------------------------------------
MIN_PRIORITY: Final[int] = 1
MAX_PRIORITY: Final[int] = 3
PRIORITY_LEVELS: Final[tuple[int, ...]] = tuple(range(MIN_PRIORITY, MAX_PRIORITY + 1))


# ----------------------------------------------------------------------
# Fase 1: cómo ubicar las clases
# ----------------------------------------------------------------------
# auto:          exacto si hay pocas clases, heurística si no
# heuristica:    DSATUR (rápido, sin garantía de óptimo)
# backtracking:  búsqueda exhaustiva podando solo por restricciones
# exacto:        backtracking con ramificación y poda (óptimo)
# fuerza_bruta:  todas las combinaciones (solo instancias diminutas)
PHASE1_MODES: Final[tuple[str, ...]] = ("auto", "heuristica", "backtracking", "exacto", "fuerza_bruta")
DEFAULT_PHASE1_MODE: Final[str] = "auto"
EXACT_MAX_CLASSES: Final[int] = 12           # en modo auto, hasta cuántas clases se usa el exacto
EXACT_NODE_LIMIT: Final[int] = 1_000_000     # tope de nodos del backtracking (devuelve lo mejor hallado)
BRUTE_FORCE_MAX_LEAVES: Final[int] = 2_000_000


def request_weight(priority: int, total_requests: int) -> int:
    """Peso de una solicitud para el objetivo del problema.

    Regla: se prefiere la programación con mayor suma de prioridades atendidas;
    a igual suma, la que atiende más solicitudes.

    Con w = prioridad * (N + 1) + 1, donde N es el total de solicitudes, maximizar
    la suma de pesos aplica exactamente esa regla: el término "+1" cuenta
    solicitudes, pero N solicitudes extra nunca alcanzan a compensar una unidad
    de prioridad, porque cada unidad de prioridad vale N + 1.
    """
    return priority * (total_requests + 1) + 1
