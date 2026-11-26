"""Programación dinámica: selección de intervalos ponderados (weighted interval scheduling).

Problema que resuelve: un estudiante pidió varias clases que ya tienen horario.
Cada clase es un intervalo [inicio, fin) con un peso (el de su prioridad). Hay que
escoger un subconjunto de clases que no se crucen y cuya suma de pesos sea máxima.

En términos de grafos: las clases del estudiante forman un grafo de intervalos
(arista = se cruzan) y se busca un conjunto independiente de peso máximo. En un
grafo cualquiera ese problema es NP-difícil, pero en un grafo de intervalos se
resuelve exacto con esta programación dinámica.

Pasos:
1. Ordenar las clases por hora de fin.                       Θ(n log n)
2. Para cada clase j, calcular p(j): cuántas de las clases anteriores (en ese
   orden) terminan antes de que j empiece. Se hace con búsqueda binaria.
                                                              Θ(log n) cada una
3. Llenar la tabla:
       OPT[0] = 0
       OPT[j] = max( OPT[j-1],              <- no tomar la clase j
                     w_j + OPT[p(j)] )      <- tomar j y lo mejor compatible con ella
                                                              Θ(n)
4. Reconstruir la solución recorriendo la tabla hacia atrás.  Θ(n)

Total: Θ(n log n). Subestructura óptima: la mejor solución con las primeras j
clases o no usa j (y entonces es la mejor con j-1) o la usa (y entonces el resto
es la mejor con las clases que terminan antes de que j empiece, las primeras p(j)).

Dividir y conquistar aparece en los pasos 1 y 2, con su recurrencia resuelta por
el teorema maestro (caso 2 en ambos):
    ordenamiento (merge sort):  T(n) = 2T(n/2) + Θ(n)  ->  Θ(n log n)
    búsqueda binaria:           T(n) = T(n/2) + Θ(1)   ->  Θ(log n)
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Interval:
    """Clase candidata del estudiante: ocupa los slots [start, end) y vale 'weight'."""
    key: str
    start: int
    end: int
    weight: int


@dataclass
class DPResult:
    """Resultado de la DP, con la tabla completa para poder mostrarla paso a paso."""
    items: list[Interval]                          # ordenados por hora de fin
    p: list[int]                                   # p[j] para j = 1..n (p[0] no se usa)
    opt: list[int]                                 # OPT[0..n]
    chosen: list[Interval] = field(default_factory=list)

    @property
    def best_weight(self) -> int:
        return self.opt[-1]

    @property
    def chosen_keys(self) -> list[str]:
        return [it.key for it in self.chosen]


def last_compatible(ends: list[int], start: int, hi: int) -> int:
    """Búsqueda binaria: cuántos de ends[0:hi] son <= start (ends está ordenado).

    Dividir y conquistar: se mira el elemento del medio y se descarta la mitad
    que no puede contener la respuesta. T(n) = T(n/2) + O(1) = O(log n).
    """
    lo = 0
    while lo < hi:
        mid = (lo + hi) // 2
        if ends[mid] <= start:
            lo = mid + 1
        else:
            hi = mid
    return lo


def weighted_interval_scheduling(intervals: list[Interval]) -> DPResult:
    """Escoge intervalos que no se cruzan con suma de pesos máxima."""
    # 1. Ordenar por hora de fin (a igual fin, por inicio y clave para que sea determinista)
    items = sorted(intervals, key=lambda it: (it.end, it.start, it.key))
    n = len(items)
    ends = [it.end for it in items]

    # 2. p(j): número de intervalos anteriores que terminan antes de que j empiece
    p = [0] * (n + 1)
    for j in range(1, n + 1):
        p[j] = last_compatible(ends, items[j - 1].start, j - 1)

    # 3. Tabla OPT
    opt = [0] * (n + 1)
    for j in range(1, n + 1):
        opt[j] = max(opt[j - 1], items[j - 1].weight + opt[p[j]])

    # 4. Reconstrucción
    chosen: list[Interval] = []
    j = n
    while j > 0:
        if items[j - 1].weight + opt[p[j]] >= opt[j - 1]:
            chosen.append(items[j - 1])
            j = p[j]
        else:
            j -= 1
    chosen.reverse()

    return DPResult(items=items, p=p, opt=opt, chosen=chosen)
