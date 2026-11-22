"""Módulo de utilidades de bitmasks para representación temporal (8:00 - 18:00, duración 1-2h).

Cada semana lectiva se modela en 5 días (Lunes a Viernes), con 10 slots horarios por día:
    Slot 0: 08:00 - 09:00
    Slot 1: 09:00 - 10:00
    Slot 2: 10:00 - 11:00
    Slot 3: 11:00 - 12:00
    Slot 4: 12:00 - 13:00
    Slot 5: 13:00 - 14:00
    Slot 6: 14:00 - 15:00
    Slot 7: 15:00 - 16:00
    Slot 8: 16:00 - 17:00
    Slot 9: 17:00 - 18:00

Total de slots semanales: 5 días * 10 horas = 50 slots.
Un entero de 64 bits almacena el horario completo de cualquier entidad, permitiendo
operaciones bitwise O(1) para detección de traslapes y verificaciones de disponibilidad.
"""

from typing import Final

DAYS: Final[list[str]] = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
NUM_DAYS: Final[int] = 5
SLOTS_PER_DAY: Final[int] = 10
START_HOUR: Final[int] = 8
END_HOUR: Final[int] = 18
TOTAL_SLOTS: Final[int] = NUM_DAYS * SLOTS_PER_DAY  # 50 slots

FULL_WEEK_MASK: Final[int] = (1 << TOTAL_SLOTS) - 1
EMPTY_MASK: Final[int] = 0


def slot_to_day_hour(slot: int) -> tuple[int, int]:
    """Convierte un índice de slot (0 a 49) a una tupla (índice_día, hora_inicio).

    Args:
        slot: Índice del slot entre 0 y 49.

    Returns:
        Tupla (día, hora) donde día está en [0, 4] y hora en [8, 17].

    Raises:
        ValueError: Si el slot está fuera de rango.
    """
    if not (0 <= slot < TOTAL_SLOTS):
        raise ValueError(f"Slot {slot} fuera de rango [0, {TOTAL_SLOTS - 1}]")
    day_idx = slot // SLOTS_PER_DAY
    start_hour = START_HOUR + (slot % SLOTS_PER_DAY)
    return day_idx, start_hour


def day_hour_to_slot(day: int, hour: int) -> int:
    """Convierte (día, hora) al índice de slot lineal (0 a 49).

    Args:
        day: Índice de día (0=Lunes, ..., 4=Viernes).
        hour: Hora de inicio (8 a 17).

    Returns:
        Índice lineal de slot.

    Raises:
        ValueError: Si el día o la hora están fuera de rango.
    """
    if not (0 <= day < NUM_DAYS):
        raise ValueError(f"Día {day} inválido. Debe estar en [0, {NUM_DAYS - 1}]")
    if not (START_HOUR <= hour < END_HOUR):
        raise ValueError(f"Hora {hour} inválida. Debe estar en [{START_HOUR}, {END_HOUR - 1}]")
    return day * SLOTS_PER_DAY + (hour - START_HOUR)


def create_slot_mask(slot: int, duration_hours: int = 1) -> int:
    """Genera la máscara de bits para un bloque que inicia en 'slot' con duración de 1 o 2 horas.

    Una clase de 2 horas no puede cruzar el límite entre días (no puede iniciar a las 17:00).

    Args:
        slot: Índice inicial de slot (0 a 49).
        duration_hours: Duración en horas (1 o 2).

    Returns:
        Máscara de bits entera con los bits correspondientes activados.

    Raises:
        ValueError: Si la duración no es 1 o 2, o si la clase sobrepasa el límite del día.
    """
    if duration_hours not in (1, 2):
        raise ValueError(f"Duración {duration_hours}h no soportada. Debe ser 1 o 2 horas.")

    day, hour = slot_to_day_hour(slot)
    if hour + duration_hours > END_HOUR:
        raise ValueError(
            f"La clase que inicia a las {hour}:00 con duración {duration_hours}h "
            f"excede el límite diario de las {END_HOUR}:00."
        )

    mask = 1 << slot
    if duration_hours == 2:
        mask |= (1 << (slot + 1))
    return mask


def create_time_mask(day: int, start_hour: int, duration_hours: int = 1) -> int:
    """Crea una máscara de bits a partir de día, hora de inicio y duración.

    Args:
        day: Índice del día (0=Lunes, 4=Viernes).
        start_hour: Hora de inicio (8 a 17).
        duration_hours: Duración (1 o 2 horas).

    Returns:
        Máscara de bits entera.
    """
    slot = day_hour_to_slot(day, start_hour)
    return create_slot_mask(slot, duration_hours)


def masks_overlap(mask1: int, mask2: int) -> bool:
    """Determina en O(1) si dos máscaras temporales comparten al menos un slot activo."""
    return (mask1 & mask2) != 0


def mask_to_slots(mask: int) -> list[int]:
    """Extrae la lista de índices de slots activos a partir de una máscara de bits."""
    slots: list[int] = []
    temp = mask
    slot_idx = 0
    while temp > 0:
        if temp & 1:
            slots.append(slot_idx)
        temp >>= 1
        slot_idx += 1
    return slots


def slots_to_mask(slots: list[int]) -> int:
    """Construye una máscara de bits a partir de una lista de slots."""
    mask = 0
    for s in slots:
        if 0 <= s < TOTAL_SLOTS:
            mask |= (1 << s)
    return mask


def format_slot(slot: int, duration_hours: int = 1) -> str:
    """Genera una representación textual legible de un slot o bloque horario.

    Ejemplo: 'Lunes 08:00-10:00' o 'Martes 14:00-15:00'.
    """
    day_idx, start_h = slot_to_day_hour(slot)
    end_h = start_h + duration_hours
    day_name = DAYS[day_idx]
    return f"{day_name} {start_h:02d}:00-{end_h:02d}:00"


def format_mask(mask: int) -> str:
    """Convierte una máscara arbitraria en una cadena descriptiva de intervalos horarios."""
    if mask == 0:
        return "Sin asignación"
    slots = mask_to_slots(mask)
    if not slots:
        return "Sin asignación"

    # Agrupar slots contiguos por día
    intervals: list[str] = []
    i = 0
    while i < len(slots):
        start_slot = slots[i]
        curr_day, start_h = slot_to_day_hour(start_slot)
        count = 1
        while (i + 1 < len(slots) and
               slots[i + 1] == start_slot + count and
               slot_to_day_hour(slots[i + 1])[0] == curr_day):
            count += 1
            i += 1
        end_h = start_h + count
        day_name = DAYS[curr_day]
        intervals.append(f"{day_name} {start_h:02d}:00-{end_h:02d}:00")
        i += 1

    return ", ".join(intervals)


def get_all_candidate_slots(duration_hours: int = 1) -> list[tuple[int, int]]:
    """Retorna todas las tuplas válidas (índice_slot, máscara) para una duración dada.

    Para duración 1h: 50 slots (todos los slots de la semana).
    Para duración 2h: 45 slots (se excluye el slot de las 17:00 de cada día).

    Returns:
        Lista de tuplas (slot_index, slot_mask).
    """
    candidates: list[tuple[int, int]] = []
    for day in range(NUM_DAYS):
        max_hour = END_HOUR - duration_hours
        for hour in range(START_HOUR, max_hour + 1):
            slot = day_hour_to_slot(day, hour)
            mask = create_slot_mask(slot, duration_hours)
            candidates.append((slot, mask))
    return candidates
