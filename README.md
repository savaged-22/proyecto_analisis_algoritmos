# Algoritmo de asignación de horarios estudiantiles

Proyecto de Análisis de Algoritmos (Pontificia Universidad Javeriana, 2026-30).

El sistema recibe estudiantes con sus solicitudes de clases (con prioridad de 1 a 3), clases con su
profesor, duración, cupo y horas de inicio permitidas, profesores y salones con su disponibilidad, y
produce:

- la programación de cada clase (hora y salón) y las clases que no se pudieron programar,
- el horario de cada estudiante y sus solicitudes pendientes,
- un informe que permite verificar que no se incumple ninguna restricción obligatoria.

Python 3.12, solo biblioteca estándar.

## Estructura

```text
main.py                     CLI: ejecutar, generar escenarios, benchmark
src/
├── config.py               reglas del problema (jornada, escala de prioridades, peso del objetivo)
├── models/                 entidades y representación del tiempo con bitmasks (TimeGrid)
├── data/
│   ├── scenario.py         lectura y validación de escenarios JSON
│   └── generator.py        generador con semilla: conjunto base, escenarios B-F, escalabilidad
├── graph/
│   ├── conflict_graph.py   grafo de conflictos entre clases
│   ├── dsatur_coloring.py  fase 1: ubicar clases en (hora, salón) con DSATUR
│   └── min_cost_flow.py    fase 2: inscripción de estudiantes
├── report/report.py        solución, horarios por clase/salón/profesor/estudiante, motivos y métricas
├── verify/verifier.py      verificador independiente de R1-R10
└── solver/orchestrator.py  coordina carga, fase 1, fase 2, reporte y verificación
tests/                      pruebas unitarias (python -m unittest discover -s tests -t .)
data/scenarios/             demo y escenarios A-F
```

## Representación del tiempo

La jornada (por defecto un día de 8:00 a 18:00) se divide en bloques de una hora, y cada bloque es un
bit de un entero. Una clase de dos horas que inicia a las 10:00 ocupa los bits de 10:00 y 11:00:

```text
se_cruzan(a, b)  <=>  (a & b) != 0          O(1)
cabe_en(disp, a) <=>  (disp & a) == a       O(1)
```

Una clase que termina a las 10:00 y otra que inicia a las 10:00 no comparten bits, así que no se cruzan.
El número de días es un parámetro del escenario (`parameters.num_days`).

## Formato de un escenario

```json
{
  "parameters": {"num_days": 1, "start_hour": 8, "end_hour": 18},
  "rooms":      [{"id": "AULA-01", "capacity": 30, "availability": [8, 9, 10], "room_type": "laboratorio"}],
  "professors": [{"id": "PROF-01", "name": "...", "availability": [8, 9, 10, 11]}],
  "classes":    [{"id": "ALG", "professor_id": "PROF-01", "capacity": 25,
                  "duration_hours": 2, "allowed_starts": [8, 10]}],
  "students":   [{"id": "E1", "requests": [{"class_id": "ALG", "priority": 3}]}]
}
```

- `availability` y `allowed_starts` son horas de inicio de bloques. Una lista aplica a todos los días;
  con varios días también se acepta `{"Lunes": [8, 9], "Martes": [14]}`. Si se omiten, se asume toda la jornada.
- La prioridad va de 1 a 3, y **3 es la más alta**.
- Los estudiantes de cada clase no se escriben en la entrada: se deducen de las solicitudes.
- `room_type`, `required_room_type` y `max_hours` son opcionales.
- Al cargar, el escenario se valida (identificadores repetidos, clases o profesores inexistentes,
  prioridades fuera de escala, horas que terminan fuera de la jornada) con mensajes claros.

## Datos de prueba

`python main.py --generate` escribe, con una semilla fija:

| Escenario | Qué prueba |
|---|---|
| `A_factible` | Conjunto base (20 estudiantes, 5 profesores, 8 clases, 10 salones). Se construye ubicando primero las clases sin conflictos y generando después las solicitudes desde esa programación, así que todas se pueden atender. Trae la solución de referencia. |
| `B_salones` | Tres clases solo pueden iniciar a la misma hora y solo quedan dos salones libres. |
| `C_profesor` | Un profesor tiene una sola hora disponible para dos de sus clases. |
| `D_estudiantes` | Estudiantes que piden dos clases que forzosamente se cruzan, con prioridades distintas. |
| `E_capacidad` | Una clase con dos cupos menos que solicitudes. |
| `F_imposible` | Un profesor con seis clases de dos horas en una jornada de diez horas. |

Cada archivo trae en `expected` la descripción del caso y lo que debe cumplir la salida.
`data/scenarios/demo.json` es un ejemplo pequeño escrito a mano para la demostración.

`python main.py --scale 20 50 100 200 --seeds 1 2 3` genera escenarios de escalabilidad (el conjunto
base con estudiantes, clases, profesores y salones en proporción) en `data/scenarios/escala/`.

## Salida e informe

El JSON de salida tiene:

- `solution`: la programación en un formato simple (clase, día, hora de inicio y fin, salón, estudiantes)
  y la lista de clases sin programar. Es lo único que lee el verificador.
- `student_schedule`: por estudiante, las clases que logró cursar y cada solicitud pendiente con su
  motivo: `clase no programada`, `fuera de la disponibilidad del estudiante`, `cruce con X (prioridad p)`
  o `cupo agotado`.
- `metrics`: solicitudes recibidas, atendidas y pendientes, cobertura, satisfacción de prioridades
  (suma atendida / suma recibida) global y por nivel, pendientes por motivo, incumplimientos de R1-R10,
  uso de salones y profesores, y tiempos.
- `verification`: el detalle de cada incumplimiento encontrado.

## Verificador independiente

[`src/verify/verifier.py`](src/verify/verifier.py) revisa R1-R10 leyendo solo el escenario y la sección
`solution`: recalcula cada horario desde la hora de inicio y fin, sin usar nada del algoritmo. Sirve
para revisar cualquier solución, incluso una escrita a mano:

```bash
python main.py --verify data/scenarios/demo.json data/outputs/output_demo.json
```

Revisar una solución cuesta O(M² + S·K²) (pares de clases y pares de clases de cada estudiante), es
decir, tiempo polinomial.

## Uso

```bash
python main.py                                       # escenario de demostración
python main.py -i data/scenarios/C_profesor.json -v  # un escenario, con la programación de cada clase
python main.py --generate                            # escenarios A-F
python main.py --benchmark                           # demo + A-F en una tabla
python main.py --verify ESCENARIO SALIDA             # verifica una solución exportada
python -m unittest discover -s tests -t .            # pruebas
```
