"""Fase 1, exacta: backtracking con ramificación y poda.

Se recorre el árbol de decisiones: en el nivel i se decide a qué hora va la
clase i (una de sus horas permitidas) o si queda sin programar. Cada hoja es
una programación completa. Sin podas, el árbol tiene hasta Π (H_i + 1) hojas
(H_i horas permitidas de la clase i): crece exponencialmente con las clases.

¿Y los salones? No cambian el costo (los cruces dependen solo de las horas),
solo deciden si algo cabe o no. Por eso no se ramifica por salón: cada clase
recibe el salón libre más pequeño que le sirve, y si ninguno está libre se
intenta reacomodar los salones de las clases ya ubicadas (un backtracking
pequeño, solo de salones) antes de descartar esa hora. Así la búsqueda sigue
siendo exacta sin multiplicar el árbol por el número de salones.

Podas:
1. Restricciones (backtracking): una hora en la que el profesor no está
   disponible o ya dicta otra clase (R2, R8), o en la que no hay salón posible
   (R1, R4, R8), no se explora. La rama se descarta en cuanto aparece el
   conflicto, no al llegar a la hoja.
2. Cota (ramificación y poda): el costo de una programación parcial solo crece
   (ver cost.py). A lo que ya cuesta la rama se le suma una cota inferior de lo
   que falta: cada clase pendiente cuesta al menos su hora más barata frente a lo
   ya programado, y si a un profesor no le alcanzan las horas libres para todas
   sus clases pendientes, algunas quedarán sin programar. Si esa suma alcanza a
   la mejor solución conocida, la rama se abandona. La búsqueda arranca con la
   solución de DSATUR como mejor conocida.

Orden: primero las clases con menos opciones (las más restringidas, la misma
idea de DSATUR) y, dentro de cada clase, primero las horas más baratas, para
encontrar pronto soluciones buenas que poden más.

Con use_bound=False se aplica solo la poda 1 (backtracking puro), para comparar.
El resultado es óptimo respecto al costo de la fase 1 si la búsqueda termina
sin alcanzar el límite de nodos.
"""

from dataclasses import dataclass

from .. import config
from ..models.course_class import CourseClass
from ..models.professor import Professor
from ..models.room import Room
from ..models.time_mask import TimeGrid
from .cost import Assignment, CostBreakdown, ScheduleCost


@dataclass
class SearchStats:
    nodes: int = 0                 # nodos visitados del árbol
    pruned_by_bound: int = 0       # ramas cortadas por la cota
    improvements: int = 0          # veces que se encontró una solución mejor
    room_reassignments: int = 0    # veces que hubo que reacomodar salones
    node_limit_hit: bool = False

    def to_dict(self) -> dict:
        return {"nodes": self.nodes, "pruned_by_bound": self.pruned_by_bound,
                "improvements": self.improvements, "room_reassignments": self.room_reassignments,
                "node_limit_hit": self.node_limit_hit}


class BacktrackingScheduler:
    """Búsqueda exhaustiva de la programación de menor costo."""

    def __init__(
        self,
        classes: list[CourseClass],
        rooms: list[Room],
        professors: list[Professor],
        grid: TimeGrid,
        cost: ScheduleCost,
        use_bound: bool = True,
        node_limit: int = config.EXACT_NODE_LIMIT,
    ) -> None:
        self.classes = {c.id: c for c in classes}
        self.rooms = {r.id: r for r in rooms}
        self.professors = {p.id: p for p in professors}
        self.grid = grid
        self.cost = cost
        self.use_bound = use_bound
        self.node_limit = node_limit

        # Horas permitidas de cada clase (con su máscara) y salones que le sirven, del más pequeño al más grande
        self.slot_masks = {
            c.id: [(s, grid.create_slot_mask(s, c.duration_hours)) for s in c.allowed_starts] for c in classes
        }
        self.fitting_rooms = {
            c.id: sorted((r for r in rooms if r.can_accommodate(c.min_room_capacity, c.required_room_type)),
                         key=lambda r: (r.capacity, r.id))
            for c in classes
        }
        self.order = sorted(
            self.classes,
            key=lambda cid: (len(self.slot_masks[cid]), len(self.fitting_rooms[cid]),
                             -cost.class_value[cid], cid),
        )

        self.stats = SearchStats()
        self.best_cost = float("inf")
        self.best: Assignment = {}

    # ==================================================================
    def solve(self, initial: Assignment | None = None) -> tuple[Assignment, CostBreakdown, bool]:
        """Devuelve (mejor programación, su costo, ¿se probó que es óptima?)."""
        self.stats = SearchStats()
        if initial is not None:
            self.best = dict(initial)
            self.best_cost = self.cost.breakdown(initial, self._masks_of(initial)).total

        self._slot_of: dict[str, int | None] = {}    # hora decidida de cada clase (None = sin programar)
        self._placed: dict[str, int] = {}            # máscara de cada clase ubicada
        self._room_of: dict[str, str] = {}           # salón actual de cada clase ubicada
        self._room_busy = {rid: 0 for rid in self.rooms}
        self._prof_busy = {pid: 0 for pid in self.professors}
        self._undo: list[tuple] = []
        self._search(0, 0.0)

        return self.best, self.cost.breakdown(self.best, self._masks_of(self.best)), not self.stats.node_limit_hit

    # ==================================================================
    # Búsqueda
    # ==================================================================
    def _search(self, level: int, cost_so_far: float) -> None:
        if self.stats.node_limit_hit:
            return
        self.stats.nodes += 1
        if self.stats.nodes >= self.node_limit:
            self.stats.node_limit_hit = True
            return

        # Poda por cota
        if self.use_bound and cost_so_far + self._lower_bound(level) >= self.best_cost:
            self.stats.pruned_by_bound += 1
            return

        # Hoja: programación completa
        if level == len(self.order):
            if cost_so_far < self.best_cost:
                self.best_cost = cost_so_far
                self.best = {cid: (slot, self._room_of[cid]) if slot is not None else None
                             for cid, slot in self._slot_of.items()}
                self.stats.improvements += 1
            return

        cid = self.order[level]
        for increment, slot, mask in self._options(cid):
            if not self._place(cid, slot, mask):
                continue                       # ningún acomodo de salones permite esta hora
            self._search(level + 1, cost_so_far + increment)
            self._remove(cid)
            if self.stats.node_limit_hit:
                return

        # Última opción: dejar la clase sin programar
        self._slot_of[cid] = None
        self._search(level + 1, cost_so_far + self.cost.unscheduled_cost(cid))
        del self._slot_of[cid]

    def _options(self, cid: str) -> list[tuple[float, int, int]]:
        """Horas válidas para la clase dado lo ya programado, con su costo incremental."""
        cls = self.classes[cid]
        prof = self.professors[cls.professor_id]
        options = []
        for slot, mask in self.slot_masks[cid]:
            # Poda por restricciones: profesor disponible y libre (R2, R8)
            if (prof.availability_mask & mask) != mask or self._prof_busy[prof.id] & mask:
                continue
            # ... y algún salón que sirva esté habilitado a esa hora (R8)
            if not any((r.availability_mask & mask) == mask for r in self.fitting_rooms[cid]):
                continue
            options.append((self.cost.overlap_cost(cid, mask, self._placed), slot, mask))
        if self.use_bound:
            options.sort(key=lambda o: o[0])
        return options

    def _lower_bound(self, level: int) -> float:
        """Cota inferior de lo que falta por costar (nunca mayor que el costo real).

        - Cada clase pendiente cuesta al menos su hora más barata frente a lo ya ubicado, o
          quedar sin programar si ya no tiene horas posibles. Es válido porque ubicar más
          clases solo agrega cruces y quita opciones.
        - Si las clases pendientes de un profesor piden más horas de las que le quedan libres,
          al menos k de ellas quedarán sin programar: se suman las k diferencias más pequeñas
          entre dejarlas sin programar y ubicarlas en su hora más barata.
        """
        bound = 0.0
        pending_by_prof: dict[str, list[tuple[float, int]]] = {}
        for cid in self.order[level:]:
            unscheduled = self.cost.unscheduled_cost(cid)
            cheapest = unscheduled
            for overlap, _, _ in self._options(cid):
                cheapest = min(cheapest, overlap)
                if cheapest == 0:
                    break
            bound += cheapest
            if cheapest < unscheduled:
                prof_id = self.classes[cid].professor_id
                pending_by_prof.setdefault(prof_id, []).append((unscheduled - cheapest,
                                                                self.classes[cid].duration_hours))

        for prof_id, items in pending_by_prof.items():
            prof = self.professors[prof_id]
            free_hours = (prof.availability_mask & ~self._prof_busy[prof_id]).bit_count()
            missing = sum(d for _, d in items) - free_hours
            if missing > 0:
                forced = -(-missing // max(d for _, d in items))   # ceil(missing / duración máxima)
                bound += sum(sorted(diff for diff, _ in items)[:forced])
        return bound

    # ==================================================================
    # Ubicar y retirar clases (con su salón)
    # ==================================================================
    def _place(self, cid: str, slot: int, mask: int) -> bool:
        """Ubica la clase a esa hora. Devuelve False si no hay forma de darle salón."""
        room = self._free_fitting_room(cid, mask, self._room_busy)
        if room is not None:
            self._room_of[cid] = room
            self._room_busy[room] |= mask
            self._undo.append(("simple", cid, room))
        else:
            # Ningún salón libre: intentar reacomodar los salones de todas las clases ubicadas
            wanted = dict(self._placed)
            wanted[cid] = mask
            rooms = self._assign_rooms(wanted)
            if rooms is None:
                return False
            self.stats.room_reassignments += 1
            self._undo.append(("full", cid, dict(self._room_of), dict(self._room_busy)))
            self._room_of = rooms
            self._room_busy = {rid: 0 for rid in self.rooms}
            for c, r in rooms.items():
                self._room_busy[r] |= wanted[c]

        self._slot_of[cid] = slot
        self._placed[cid] = mask
        self._prof_busy[self.classes[cid].professor_id] |= mask
        return True

    def _remove(self, cid: str) -> None:
        mask = self._placed.pop(cid)
        del self._slot_of[cid]
        self._prof_busy[self.classes[cid].professor_id] &= ~mask
        record = self._undo.pop()
        if record[0] == "simple":
            room = self._room_of.pop(cid)
            self._room_busy[room] &= ~mask
        else:
            _, _, room_of, room_busy = record
            self._room_of, self._room_busy = room_of, room_busy

    def _free_fitting_room(self, cid: str, mask: int, room_busy: dict[str, int]) -> str | None:
        """El salón más pequeño que le sirve a la clase y está libre a esa hora."""
        for room in self.fitting_rooms[cid]:
            if (room.availability_mask & mask) == mask and not room_busy[room.id] & mask:
                return room.id
        return None

    def _assign_rooms(self, wanted: dict[str, int]) -> dict[str, str] | None:
        """Backtracking de salones: da un salón a cada clase (con su hora ya fija) sin choques, o None."""
        order = sorted(wanted, key=lambda c: (len(self.fitting_rooms[c]), wanted[c]))
        room_busy = {rid: 0 for rid in self.rooms}
        result: dict[str, str] = {}

        def assign(i: int) -> bool:
            if i == len(order):
                return True
            cid, mask = order[i], wanted[order[i]]
            for room in self.fitting_rooms[cid]:
                if (room.availability_mask & mask) == mask and not room_busy[room.id] & mask:
                    room_busy[room.id] |= mask
                    result[cid] = room.id
                    if assign(i + 1):
                        return True
                    room_busy[room.id] &= ~mask
                    del result[cid]
            return False

        return dict(result) if assign(0) else None

    def _masks_of(self, assignment: Assignment) -> dict[str, int]:
        return {cid: self.grid.create_slot_mask(a[0], self.classes[cid].duration_hours)
                for cid, a in assignment.items() if a is not None}
