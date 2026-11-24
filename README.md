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
├── graph/conflict_graph.py  grafo de conflictos entre clases
├── phase1/                 fase 1: ubicar clases en (hora, salón)
│   ├── cost.py             costo de una programación (lo que se minimiza)
│   ├── dsatur.py           heurística DSATUR
│   ├── backtracking.py     búsqueda exacta: backtracking con ramificación y poda
│   ├── brute_force.py      fuerza bruta (solo instancias diminutas)
│   └── scheduler.py        elige la estrategia y aplica el resultado
├── phase2/
│   ├── interval_dp.py      programación dinámica por estudiante (intervalos ponderados)
│   └── enrollment.py       fase 2: reparto de cupos entre estudiantes
├── report/report.py        solución, horarios por clase/salón/profesor/estudiante, motivos y métricas
├── verify/
│   ├── verifier.py         verificador independiente de R1-R10
│   └── expectations.py     compara el resultado con lo esperado de cada escenario
├── analysis/experiments.py escalabilidad, podas y aproximación
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

## El algoritmo

El problema se resuelve en dos fases. El grafo de conflictos se usa en las dos, de forma distinta:

```text
Escenario ─► Grafo de conflictos ─► Fase 1: ubicar clases ─► Fase 2: inscribir estudiantes ─► Verificador ─► Informe
             (clases = vértices)     (colorear el grafo:      (en el subgrafo de cada estudiante,
                                      horas = colores)         DP sobre intervalos)
```

**Fase 1** decide la hora y el salón de cada clase. Ubicar las clases sin cruces equivale a colorear el
grafo de conflictos usando las horas como colores; por eso esta fase es la parte difícil del problema.
Se minimiza un costo que estima la prioridad que se perdería:

```text
costo = BASE · (clases sin programar) + prioridad de las no programadas + Σ cruces entre clases pedidas por un mismo estudiante
```

Hay cuatro estrategias (`--modo`):

| Estrategia | Qué hace | Costo |
|---|---|---|
| `heuristica` | DSATUR: programa primero la clase con menos horas disponibles y le da la hora y el salón más baratos. No retrocede. | O(M²·H + M·H·(d + A)) |
| `backtracking` | Recorre el árbol de decisiones (hora de cada clase, o sin programar) y descarta una rama apenas incumple una restricción. | O(Π (H_i + 1)) en el peor caso |
| `exacto` | Lo anterior más ramificación y poda: cota inferior de lo que falta y la solución de DSATUR como mejor conocida. Da el óptimo. | igual en el peor caso, mucho menos en la práctica |
| `fuerza_bruta` | Prueba todas las combinaciones (hora, salón) de todas las clases. Solo para instancias diminutas. | Π (H_i · A + 1) hojas |

`auto` (por defecto) usa `exacto` hasta 12 clases y `heuristica` con más. Los salones no cambian el costo,
solo si algo cabe: el árbol ramifica por horas y a cada clase se le da el salón más pequeño que le sirve;
si ninguno queda libre, se reacomodan los salones de las clases ya ubicadas antes de descartar esa hora.

```bash
python main.py --comparar -i data/scenarios/demo.json
```

```text
Estrategia    | Nodos/hojas  | Podas | Costo F1 | Clases | Solicitudes | Óptimo
heuristica    | -            | -     | 75.0     | 5/6    | 14/21       | -
backtracking  | 189          | 0     | 75.0     | 5/6    | 14/21       | sí
exacto        | 3            | 2     | 75.0     | 5/6    | 14/21       | sí
fuerza_bruta  | 17920        | -     | 75.0     | 5/6    | 14/21       | sí
```

**Fase 2** inscribe a los estudiantes cuando las horas ya están fijas. Para un estudiante, sus clases
pedidas son intervalos en la línea del tiempo; dos se cruzan si se solapan. Ese subgrafo del grafo de
conflictos es un *grafo de intervalos*, y en él escoger el conjunto de clases sin cruces de mayor peso
(conjunto independiente de peso máximo, NP-difícil en un grafo cualquiera) se resuelve exacto con
programación dinámica:

```text
ordenar por hora de fin                      Θ(n log n)    T(n) = 2T(n/2) + Θ(n)
p(j) = clases que terminan antes de que j empiece, por búsqueda binaria
                                             Θ(log n) c/u  T(n) = T(n/2) + Θ(1)
OPT[j] = max(OPT[j-1], w_j + OPT[p(j)])      Θ(n)
```

El peso de cada solicitud es `w = prioridad · (N + 1) + 1` (N = total de solicitudes), así que la DP
maximiza la suma de prioridades y, a igual suma, el número de clases.

Cuando una clase recibe más estudiantes que su cupo real `min(cupo, capacidad del salón)`, se queda con
los de mayor prioridad (a igual prioridad, el primero de la entrada); los demás vuelven a correr su DP
sin esa clase, hasta que nadie exceda cupos. Al final, los cupos que quedaron libres se ofrecen de nuevo
a quien mejore con ellos. El horario de cada estudiante es óptimo para las clases que tuvo disponibles;
el reparto de cupos entre estudiantes es una heurística.

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

Cada archivo trae en `expected` la descripción del caso y lo que debe cumplir la salida;
[`src/verify/expectations.py`](src/verify/expectations.py) lo comprueba sobre el resultado, y las pruebas
lo exigen para la semilla publicada y para otras 15 semillas.
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

## Resultados

`python main.py --experimentos` corre los tres experimentos y guarda CSV y JSON en
`data/outputs/experimentos/`. Valores medidos en un portátil con Python 3.12.

**Escalabilidad** (escenario A en proporción, promedio de 3 semillas, 0 incumplimientos en todos):

| Modo | Estudiantes | Clases | Cobertura | Fase 1 | Fase 2 | Total |
|---|---|---|---|---|---|---|
| heurística | 20 | 8 | 99.3 % | 0.9 ms | 1.1 ms | 2.1 ms |
| heurística | 50 | 20 | 97.7 % | 3.8 ms | 2.6 ms | 6.8 ms |
| heurística | 100 | 40 | 99.9 % | 14.3 ms | 6.0 ms | 21.4 ms |
| heurística | 200 | 80 | 99.3 % | 59.4 ms | 15.3 ms | 76.6 ms |
| exacto | 20 | 8 | 100 % | 3.2 ms | 1.6 ms | 5.0 ms |
| exacto | 50 | 20 | 100 % | 22.0 ms | 3.5 ms | 26.1 ms |
| exacto | 100 | 40 | 100 % | 41.3 ms | 7.3 ms | 49.7 ms |
| exacto | 200 | 80 | 100 % | 2630 ms | 20.1 ms | 2653 ms |

Exponente empírico del tiempo (pendiente en escala log-log, t ≈ c·n^k): heurística, fase 1 k ≈ 1.8
(DSATUR es O(M²·H)) y fase 2 k ≈ 1.2 (O(S·R log R)); con el exacto la fase 1 sube a k ≈ 2.7 y se dispara
en el tamaño más grande, como se espera de una búsqueda exponencial.

**Podas** (trabajo de cada estrategia de la fase 1 para el mismo óptimo):

| Escenario | Fuerza bruta (hojas) | Backtracking (nodos) | Ramificación y poda (nodos) |
|---|---|---|---|
| demo | 1.8·10⁴ | 189 | 3 |
| A_factible | 6.1·10¹¹ | 2 437 | 1 |
| C_profesor | 8.1·10¹¹ | 1 267 | 25 |
| F_imposible | 7.2·10¹⁴ | 107 439 | 437 |

**Aproximación** (escenarios con conflictos inevitables, 20 y 50 estudiantes, 5 semillas cada uno):
la heurística atiende en promedio el 98.9 % de la prioridad que atiende el óptimo, 94.8 % en el peor caso,
y llega al óptimo en el 60 % de las instancias. La coloración de grafos no admite una garantía de
aproximación de factor constante, por eso la calidad de la heurística se mide empíricamente.

## Uso

```bash
python main.py                                       # escenario de demostración
python main.py -i data/scenarios/C_profesor.json -v  # un escenario, con la programación de cada clase
python main.py --generate                            # escenarios A-F
python main.py --benchmark                           # demo + A-F en una tabla
python main.py --verify ESCENARIO SALIDA             # verifica una solución exportada
python main.py -i ESCENARIO --modo exacto            # elige la estrategia de la fase 1
python main.py --comparar -i ESCENARIO               # compara las estrategias de la fase 1
python main.py --experimentos [escalabilidad podas aproximacion]
python -m unittest discover -s tests -t .            # pruebas
```
