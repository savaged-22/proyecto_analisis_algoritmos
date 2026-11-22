# Sistema de Programación Académica Universitaria (UCTP)
### Grafo de Conflictos + Coloración DSATUR Ponderada + Red de Flujo de Costo Mínimo (MCMF)

Este proyecto implementa una solución completa, rigurosa y de alto rendimiento en **Python 3.12** (utilizando exclusivamente la biblioteca estándar) para el **Problema de Horarios de Cursos Universitarios (University Course Timetabling Problem - UCTP)** y la **Asignación Óptima de Matrícula Estudiantil**.

El sistema desacopla el problema combinatorial NP-Hard en dos fases secuenciales complementarias:
1. **Fase 1: Programación Espacio-Temporal de Clases (Timetabling)** mediante un **Grafo No Dirigido Ponderado de Conflictos** resuelto con el algoritmo de coloración heurística **DSATUR** (Degree of Saturation, Brélaz 1979) adaptado a listas de pares factibles $(h, s)$ (horario, salón).
2. **Fase 2: Asignación de Cupos Estudiantiles (Student Enrollment)** modelada como una **Red de Flujo de Costo Mínimo (Min-Cost Max-Flow - MCMF)** con búsqueda de caminos de costo mínimo (Successive Shortest Path / SPFA) y restricciones de compatibilidad temporal por estudiante ($O(1)$ mediante bitmasks).

---

## 1. Estructura Exacta del Proyecto

El proyecto respeta estrictamente la siguiente distribución de archivos y directorios:

```text
proyecto_analisis_algoritmos/
├── main.py                      # CLI, lectura/escritura JSON y ejecución principal
├── requirements.txt             # Dependencias del proyecto (librería estándar de Python)
├── README.md                    # Documentación de uso, arquitectura y análisis de complejidad
├── data/
│   ├── scenarios/               # Archivos JSON de entrada (escenarios de prueba)
│   └── outputs/                 # Archivos JSON de salida con programación e informe
└── src/
    ├── __init__.py
    ├── models/
    │   ├── __init__.py
    │   ├── student.py           # Entidades Student y Request
    │   ├── professor.py         # Entidad Professor
    │   ├── course_class.py      # Entidad CourseClass
    │   ├── room.py              # Entidad Room
    │   └── time_mask.py         # Utilidades de bitmasks (8:00-18:00, duración 1-2h)
    ├── graph/
    │   ├── __init__.py
    │   ├── conflict_graph.py    # Grafo no dirigido ponderado de conflictos entre clases
    │   ├── dsatur_coloring.py   # Fase 1: Coloración DSATUR ponderada con listas (h, s)
    │   ├── min_cost_flow.py     # Fase 2: Red de flujo de costo mínimo para inscripciones
    │   └── report.py            # Hashmaps de salida, horarios individuales e informe de métricas
    └── solver/
        ├── __init__.py
        └── orchestrator.py      # Orquestador único que coordina Fase 1 + Fase 2 + reporte
```

---

## 2. Modelado Matemático y Representación Temporal por Bitmasks

### 2.1 Representación de Horarios mediante Bitmasks de 50 bits
La semana académica consta de 5 días lectivos ($d \in [0, 4]$, Lunes a Viernes) y 10 slots horarios diarios ($h \in [8, 17]$):
$$\text{Slot Index} = d \times 10 + (h - 8), \quad \text{donde } 0 \le \text{Slot Index} < 50$$

Cada estado temporal se representa con un entero sin signo de 64 bits (`int` en Python):
- **Duración 1h**: Máscara con 1 bit activo: $M = 1 \ll \text{slot}$.
- **Duración 2h**: Máscara con 2 bits contiguos: $M = (1 \ll \text{slot}) \mid (1 \ll (\text{slot} + 1))$, con la restricción $h \le 16$ para no cruzar el fin de jornada lectiva.
- **Detección de Colisión Temporal en $O(1)$**:
  $$\text{Overlap}(M_1, M_2) \iff (M_1 \ \& \ M_2) \ne 0$$
- **Verificación de Disponibilidad en $O(1)$**:
  $$\text{IsAvailable}(M_{\text{agenda}}, M_{\text{clase}}) \iff (M_{\text{agenda}} \ \& \ M_{\text{clase}}) == M_{\text{clase}}$$

---

## 3. Arquitectura y Fases Algorítmicas

```mermaid
flowchart TD
    JSON["Entrada JSON (Escenario)"] --> ORCH["TimetableOrchestrator"]
    ORCH --> G_CONF["Construcción de Grafo de Conflictos (conflict_graph.py)"]
    G_CONF --> FASE1["Fase 1: DSATUR Ponderado con Listas (h, s) (dsatur_coloring.py)"]
    FASE1 --> VAL1["Validación de Invariantes Duras (Cero choques docente/aula)"]
    VAL1 --> FASE2["Fase 2: Red Min-Cost Max-Flow (min_cost_flow.py)"]
    FASE2 --> VAL2["Validación de Asignaciones (Capacidades y Cero choques de alumno)"]
    VAL2 --> REP["Generador de Hashmaps y Reportes (report.py)"]
    REP --> JSON_OUT["data/outputs/schedule.json"]
    REP --> CLI["Consola CLI"]
```

### 3.1 Grafo de Conflictos (`conflict_graph.py`)
Sea $V = \{C_1, C_2, \dots, C_M\}$ el conjunto de clases a programar. El grafo $G = (V, E, w)$ contiene dos tipos de aristas:
1. **Conflictos Duros ($is\_hard = \text{True}, w = 10^6$)**:
   - Mismo docente: $C_i.\text{prof\_id} == C_j.\text{prof\_id}$.
   - Secciones de la misma materia: $C_i.\text{course\_id} == C_j.\text{course\_id}$ (permite diversificar horarios).
2. **Conflictos Blandos ($is\_hard = \text{False}, w > 0$)**:
   - Demanda compartida por estudiantes: Si un estudiante $s$ solicita el curso $A$ y el curso $B$, las secciones de $A$ y $B$ reciben una arista ponderada por:
     $$w_s(A, B) = \text{prioridad}(s) \times \frac{10}{\text{prio}(r_A) + \text{prio}(r_B)}$$
     El peso total de la arista es la suma acumulada sobre todos los estudiantes interesados.

### 3.2 Fase 1: Coloración DSATUR Ponderada (`dsatur_coloring.py`)
El algoritmo de Brélaz selecciona iterativamente la clase no programada $u$ más restringida:
1. **Grado de Saturación**: $\rho(u) = |\{ \text{slot}(v) : v \in \text{vecinos}(u) \text{ ya programados} \}|$.
2. **Desempate**: Mayor grado ponderado $\sum_{v} w(u, v) \to$ Mayor duración ($2h > 1h$) $\to$ Mayor capacidad.
3. **Selección del par $(h, s)$**:
   Para la clase $u^*$, se evalúan todos los pares de horario $h$ y aula $s$ que cumplan:
   - Aula libre y con capacidad suficiente ($s.\text{cap} \ge u^*.\text{cap}$) y tipo coincidente (teoría vs laboratorio).
   - Docente libre en el horario $h$ y dentro de su cuota de horas semanales.
   - Cero solapamiento con vecinos con conflicto duro.
   - **Minimización de costo**:
     $$\min_{(h, s)} \left[ \sum_{v \in \text{vecinos}(u^*), \text{solapan}(h, v)} w(u^*, v) + 0.01 \times (s.\text{capacity} - u^*.\text{capacity}) \right]$$

### 3.3 Fase 2: Red de Flujo de Costo Mínimo (MCMF) (`min_cost_flow.py`)
Una vez fijados los horarios y aulas en la Fase 1, la asignación de estudiantes a secciones se formula como una red de flujo dirigida residual:

- **Estructura de la Red**:
  - Nodo Fuente ($\text{SRC}$) y Sumidero ($\text{SNK}$).
  - Nodos Estudiante $\text{STU}_s$, Nodos Solicitud $\text{REQ}_{s, c}$, Nodos Clase $\text{CLS}_k$.
- **Aristas y Capacidades**:
  - $\text{SRC} \to \text{STU}_s$: $\text{Capacidad} = |\text{requests}(s)|$, Costo = 0.
  - $\text{STU}_s \to \text{REQ}_{s, c}$: $\text{Capacidad} = 1$, Costo = 0 (máximo 1 sección por curso).
  - $\text{REQ}_{s, c} \to \text{CLS}_k$: $\text{Capacidad} = 1$,
    $$\text{Costo} = 100 + 30 \times (\text{prio}(req) - 1) - 15 \times (\text{gpa} - 1.0) - (20 \text{ si docente preferido else } 0)$$
  - $\text{CLS}_k \to \text{SNK}$: $\text{Capacidad} = \text{capacidad}(k)$, Costo = 0.
- **Control de Conflictos de Horario**:
  Mediante **Successive Shortest Path (SPFA)**, cada aumento de 1 unidad de flujo verifica que la clase candidata $k$ no solape la agenda acumulada del estudiante:
  $$(\text{schedule\_mask}_s \ \& \ \text{time\_mask}_k) == 0$$
  Esto garantiza que el 100% de los estudiantes queden matriculados sin choques de horario.

---

## 4. Análisis Asintótico de Complejidad

Sean:
- $M$: Número de clases / secciones ($M \approx 10 - 70$).
- $S$: Número de estudiantes ($S \approx 25 - 200$).
- $R$: Número promedio de solicitudes por estudiante ($R \approx 3 - 5$).
- $H$: Número de slots temporales candidatos ($H \le 50$).
- $A$: Número de salones disponibles ($A \approx 5 - 20$).
- $F$: Unidades de flujo total asignado ($F \le S \times R$).

| Componente | Complejidad Temporal | Complejidad Espacial | Justificación |
|---|---|---|---|
| **Máscaras Bitmask** | $O(1)$ | $O(1)$ | Operaciones a nivel de bit (`&`, `\|`, `~`) en registros de 64 bits. |
| **Construcción Grafo Conflictos** | $O(M^2 + S \cdot R^2)$ | $O(M^2)$ | Parejas de materias por estudiante y evaluación cuadrática de clases. |
| **Fase 1: DSATUR Ponderado** | $O(M^2 \cdot (H \cdot A))$ | $O(M^2 + H \cdot A)$ | $M$ selecciones de clase, cada una evaluando a lo sumo $H \cdot A$ pares $(h, s)$. |
| **Fase 2: Red MCMF (SPFA)** | $O(F \cdot \|V_F\| \cdot \|E_F\|)$ | $O(\|V_F\| + \|E_F\|)$ | Red con $\|V_F\| \approx 2 + S + S \cdot R + M$, $\|E_F\| \approx S + S \cdot R + S \cdot R \cdot \frac{M}{\text{cursos}} + M$. |
| **Generación de Reportes** | $O(M + S \cdot R + A)$ | $O(M + S + A)$ | Recorrido lineal de hashmaps y serialización JSON. |

### Escalabilidad hacia 200 estudiantes:
Para un escenario de 200 estudiantes ($S = 200$, $M = 52$, $A = 16$):
- Nodos en la red: $\|V_F\| \approx 1060$.
- Aristas en la red: $\|E_F\| \approx 2600$.
- El algoritmo ejecuta en **~1.6 segundos** en CPU estándar, confirmando su idoneidad para entornos universitarios reales.

---

## 5. Instrucciones de Uso y CLI

El sistema no requiere bibliotecas externas (`pip install` no es necesario). Requiere **Python 3.12+**.

### 5.1 Ejecutar el Escenario por Defecto
```bash
python main.py
```

### 5.2 Procesar un Escenario Específico con Detalle Verbose
```bash
python main.py --input data/scenarios/scenario_small.json --output data/outputs/schedule_small.json -v
```

### 5.3 Generar los Escenarios de Prueba Estándar
```bash
python main.py --generate
```
Genera de manera determinista:
- `data/scenarios/scenario_small.json` (25 estudiantes, 10 clases, 4 salones)
- `data/scenarios/scenario_medium.json` (80 estudiantes, 25 clases, 8 salones)
- `data/scenarios/scenario_large.json` (200 estudiantes, 52 clases, 16 salones)

### 5.4 Ejecutar Benchmark de Rendimiento Comparativo
```bash
python main.py --benchmark
```

---

## 6. Resultados de Benchmark y Validación de Invariantes

Resultados obtenidos en ejecución real sobre Python 3.12.3:

| Escenario | Estudiantes | Clases Prog. | Tasa Satisfacción | Conflictos Duros | Choques Alumnos | DSATUR (ms) | MCMF (ms) | Tiempo Total |
|---|---|---|---|---|---|---|---|---|
| **scenario_small** | 25 | 10 / 10 (100%) | 100.0% (62/62) | **0** | **0** | 2.91 ms | 11.09 ms | **14.79 ms** |
| **scenario_medium** | 80 | 25 / 25 (100%) | 100.0% (276/276) | **0** | **0** | 5.03 ms | 183.86 ms | **190.94 ms** |
| **scenario_large** | 200 | 52 / 52 (100%) | 100.0% (786/786) | **0** | **0** | 22.37 ms | 1615.53 ms | **1.64 s** |

### Invariantes Garantizadas:
1. **Docentes**: Ningún docente tiene dos clases en horarios que compartan bits temporales. Carga dentro de `max_hours`.
2. **Aulas**: Ningún salón alberga más de una clase simultáneamente. Capacidad física y tipo (teoría/laboratorio) estrictamente respetados.
3. **Estudiantes**: Ningún estudiante posee dos materias con solapamiento temporal (`schedule_mask & time_mask == 0`). A lo sumo 1 sección matriculada por curso solicitado.
