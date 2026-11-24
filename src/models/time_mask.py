"""Representación de la jornada con bitmasks.

La jornada se divide en bloques de una hora. Cada bloque es un bit de un entero:

    slot = día * horas_por_día + (hora - hora_inicial)

Con la jornada por defecto (un día, 8:00 a 18:00) hay 10 slots:

    slot 0 -> 08:00-09:00, slot 1 -> 09:00-10:00, ..., slot 9 -> 17:00-18:00

Una clase de dos horas que inicia en el slot s ocupa los bits s y s+1.
Con esta representación, saber si dos horarios se cruzan es una sola operación:

    se_cruzan(a, b)  <=>  (a & b) != 0                      O(1)
    cabe_en(disp, a) <=>  (disp & a) == a                   O(1)

El número de días es un parámetro: con varios días, los slots de cada día van
seguidos y una clase nunca cruza de un día al siguiente.
"""

from dataclasses import dataclass
from typing import Final

DAY_NAMES: Final[list[str]] = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]

EMPTY_MASK: Final[int] = 0


@dataclass(frozen=True)
class TimeGrid:
    """Jornada académica: días x bloques de una hora.

    Atributos:
        num_days: Número de días de la programación (1 en la versión inicial).
        start_hour: Hora inicial de la jornada (8 = 8:00 a. m.).
        end_hour: Hora final de la jornada (18 = 6:00 p. m.).
    """
    num_days: int = 1
    start_hour: int = 8
    end_hour: int = 18

    def __post_init__(self) -> None:
        if not 1 <= self.num_days <= len(DAY_NAMES):
            raise ValueError(f"num_days debe estar entre 1 y {len(DAY_NAMES)}")
        if not 0 <= self.start_hour < self.end_hour <= 24:
            raise ValueError("La jornada debe cumplir 0 <= start_hour < end_hour <= 24")

    # ------------------------------------------------------------------
    # Tamaño de la jornada
    # ------------------------------------------------------------------
    @property
    def hours_per_day(self) -> int:
        return self.end_hour - self.start_hour

    @property
    def total_slots(self) -> int:
        return self.num_days * self.hours_per_day

    @property
    def full_mask(self) -> int:
        """Máscara con todos los bloques de la jornada disponibles."""
        return (1 << self.total_slots) - 1

    @property
    def day_names(self) -> list[str]:
        return DAY_NAMES[: self.num_days]

    # ------------------------------------------------------------------
    # Conversión slot <-> (día, hora)
    # ------------------------------------------------------------------
    def slot_to_day_hour(self, slot: int) -> tuple[int, int]:
        """Convierte un slot en (índice de día, hora de inicio)."""
        if not 0 <= slot < self.total_slots:
            raise ValueError(f"Slot {slot} fuera de rango [0, {self.total_slots - 1}]")
        return slot // self.hours_per_day, self.start_hour + slot % self.hours_per_day

    def day_hour_to_slot(self, day: int, hour: int) -> int:
        """Convierte (índice de día, hora) en slot."""
        if not 0 <= day < self.num_days:
            raise ValueError(f"Día {day} inválido. Debe estar en [0, {self.num_days - 1}]")
        if not self.start_hour <= hour < self.end_hour:
            raise ValueError(f"Hora {hour} fuera de la jornada [{self.start_hour}, {self.end_hour - 1}]")
        return day * self.hours_per_day + (hour - self.start_hour)

    # ------------------------------------------------------------------
    # Máscaras de clases
    # ------------------------------------------------------------------
    def is_valid_start(self, slot: int, duration_hours: int) -> bool:
        """Indica si una clase de esa duración puede iniciar en el slot sin salir de la jornada (R7)."""
        if not 0 <= slot < self.total_slots:
            return False
        _, hour = self.slot_to_day_hour(slot)
        return hour + duration_hours <= self.end_hour

    def create_slot_mask(self, slot: int, duration_hours: int) -> int:
        """Máscara de una clase que inicia en 'slot' y dura 'duration_hours' horas consecutivas."""
        if duration_hours not in (1, 2):
            raise ValueError(f"Duración {duration_hours}h no soportada. Debe ser 1 o 2 horas.")
        if not self.is_valid_start(slot, duration_hours):
            raise ValueError(f"Una clase de {duration_hours}h no puede iniciar en el slot {slot}.")
        return ((1 << duration_hours) - 1) << slot

    def candidate_starts(self, duration_hours: int) -> list[int]:
        """Todos los slots donde puede iniciar una clase de esa duración."""
        return [s for s in range(self.total_slots) if self.is_valid_start(s, duration_hours)]

    # ------------------------------------------------------------------
    # Lectura de horarios escritos en el escenario
    # ------------------------------------------------------------------
    def hours_to_slots(self, spec: list[int] | dict[str, list[int]] | None) -> list[int]:
        """Convierte una especificación de horas del escenario en slots.

        Formatos aceptados:
            None                       -> todos los slots de la jornada
            [8, 9, 14]                 -> esas horas, en todos los días
            {"Lunes": [8, 9], ...}     -> horas por día (con varios días)
        """
        if spec is None:
            return list(range(self.total_slots))
        if isinstance(spec, list):
            return sorted(
                self.day_hour_to_slot(day, int(h)) for day in range(self.num_days) for h in spec
            )
        if isinstance(spec, dict):
            slots: list[int] = []
            for day_name, hours in spec.items():
                if day_name not in self.day_names:
                    raise ValueError(f"Día '{day_name}' no existe en la jornada {self.day_names}")
                day = self.day_names.index(day_name)
                slots.extend(self.day_hour_to_slot(day, int(h)) for h in hours)
            return sorted(slots)
        raise ValueError(f"Formato de horario no reconocido: {spec!r}")

    def hours_to_mask(self, spec: list[int] | dict[str, list[int]] | None) -> int:
        """Igual que hours_to_slots, pero devuelve la máscara de disponibilidad."""
        return slots_to_mask(self.hours_to_slots(spec))

    def mask_to_hours(self, mask: int) -> list[int] | dict[str, list[int]]:
        """Operación inversa de hours_to_mask (lista con un día, diccionario con varios)."""
        by_day: dict[str, list[int]] = {}
        for slot in mask_to_slots(mask):
            day, hour = self.slot_to_day_hour(slot)
            by_day.setdefault(self.day_names[day], []).append(hour)
        if self.num_days == 1:
            return by_day.get(self.day_names[0], [])
        return by_day

    # ------------------------------------------------------------------
    # Formato legible
    # ------------------------------------------------------------------
    def format_slot(self, slot: int, duration_hours: int = 1) -> str:
        """Ej.: '08:00-10:00' con un día, 'Martes 14:00-15:00' con varios."""
        day, hour = self.slot_to_day_hour(slot)
        text = f"{hour:02d}:00-{hour + duration_hours:02d}:00"
        return text if self.num_days == 1 else f"{self.day_names[day]} {text}"

    def format_mask(self, mask: int) -> str:
        """Describe una máscara arbitraria como intervalos contiguos."""
        slots = mask_to_slots(mask)
        if not slots:
            return "Sin asignación"
        intervals: list[str] = []
        i = 0
        while i < len(slots):
            start = slots[i]
            day = start // self.hours_per_day
            length = 1
            while (i + 1 < len(slots) and slots[i + 1] == start + length
                   and slots[i + 1] // self.hours_per_day == day):
                length += 1
                i += 1
            intervals.append(self.format_slot(start, length))
            i += 1
        return ", ".join(intervals)

    def to_dict(self) -> dict[str, int]:
        return {"num_days": self.num_days, "start_hour": self.start_hour, "end_hour": self.end_hour}


def masks_overlap(mask1: int, mask2: int) -> bool:
    """Dos horarios se cruzan si comparten al menos un bloque. O(1)."""
    return (mask1 & mask2) != 0


def mask_to_slots(mask: int) -> list[int]:
    """Índices de los bits activos de la máscara, de menor a mayor."""
    slots: list[int] = []
    slot = 0
    while mask:
        if mask & 1:
            slots.append(slot)
        mask >>= 1
        slot += 1
    return slots


def slots_to_mask(slots: list[int]) -> int:
    """Máscara con los slots indicados activos."""
    mask = 0
    for s in slots:
        mask |= 1 << s
    return mask
