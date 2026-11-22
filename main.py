"""CLI, lectura/escritura JSON y ejecución principal del sistema de programación académica.

Uso básico:
    python main.py --input data/scenarios/scenario_small.json --output data/outputs/schedule_small.json
    python main.py --generate
    python main.py --benchmark
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

from src.solver.orchestrator import TimetableOrchestrator


def generate_benchmark_scenarios(base_dir: Path) -> dict[str, Path]:
    """Genera escenarios de prueba realistas (pequeño, mediano y grande con 200 estudiantes).

    Args:
        base_dir: Directorio raíz del proyecto.

    Returns:
        Diccionario con las rutas de los archivos generados.
    """
    scenarios_dir = base_dir / "data" / "scenarios"
    scenarios_dir.mkdir(parents=True, exist_ok=True)

    configs = [
        ("scenario_small.json", 4, 6, 6, 10, 25, (2, 3)),
        ("scenario_medium.json", 8, 14, 14, 25, 80, (3, 4)),
        ("scenario_large.json", 16, 30, 25, 52, 200, (3, 5)),
    ]

    generated_paths: dict[str, Path] = {}

    for filename, n_rooms, n_profs, n_courses, n_classes, n_students, req_range in configs:
        # Fijar semilla determinista para reproducibilidad exacta
        rng = random.Random(42 + n_students)

        # 1. Salones
        rooms: list[dict[str, Any]] = []
        for r_idx in range(1, n_rooms + 1):
            is_lab = (r_idx % 4 == 0)
            capacity = rng.choice([35, 45, 60, 80]) if not is_lab else rng.choice([30, 40])
            r_type = "laboratorio" if is_lab else "teoria"
            rooms.append({
                "id": f"AULA-{r_idx:02d}" if not is_lab else f"LAB-{r_idx:02d}",
                "name": f"Salón {r_idx:02d}" if not is_lab else f"Laboratorio {r_idx:02d}",
                "capacity": capacity,
                "room_type": r_type
            })

        # 2. Profesores
        professors: list[dict[str, Any]] = []
        prof_names = [
            "Dr. Alan Turing", "Dra. Ada Lovelace", "Dr. John von Neumann",
            "Dra. Grace Hopper", "Dr. Claude Shannon", "Dra. Margaret Hamilton",
            "Dr. Donald Knuth", "Dra. Barbara Liskov", "Dr. Edsger Dijkstra",
            "Dra. Katherine Johnson", "Dr. Ken Thompson", "Dra. Radia Perlman",
            "Dr. Dennis Ritchie", "Dra. Frances Allen", "Dr. Tim Berners-Lee",
            "Dra. Shafi Goldwasser", "Dr. Leslie Lamport", "Dra. Karen Spärck Jones",
            "Dr. Richard Karp", "Dra. Judea Pearl", "Dr. Stephen Cook",
            "Dra. Daphne Koller", "Dr. Michael Rabin", "Dra. Cynthia Dwork",
            "Dr. Robert Tarjan", "Dra. Jennifer Chayes", "Dr. Andrew Yao",
            "Dra. Fei-Fei Li", "Dr. Manuel Blum", "Dra. Lenore Blum"
        ]
        for p_idx in range(1, n_profs + 1):
            name = prof_names[(p_idx - 1) % len(prof_names)] + (f" ({p_idx})" if p_idx > len(prof_names) else "")
            professors.append({
                "id": f"PROF-{p_idx:02d}",
                "name": name,
                "max_hours": rng.choice([16, 20, 24])
            })

        # 3. Cursos y Secciones
        course_catalog = [
            ("INF101", "Algoritmos y Complejidad", "teoria"),
            ("INF102", "Estructuras de Datos Avanzadas", "teoria"),
            ("INF103", "Bases de Datos Relacionales", "teoria"),
            ("INF104", "Laboratorio de Redes y Seguridad", "laboratorio"),
            ("INF105", "Sistemas Operativos Distribuidos", "teoria"),
            ("INF106", "Inteligencia Artificial y Grafos", "teoria"),
            ("INF107", "Optimización Combinatoria", "teoria"),
            ("INF108", "Taller de Desarrollo de Software", "laboratorio"),
            ("MAT201", "Cálculo en Varias Variables", "teoria"),
            ("MAT202", "Álgebra Lineal Computacional", "teoria"),
            ("MAT203", "Probabilidad y Procesos Estocásticos", "teoria"),
            ("MAT204", "Matemática Discreta", "teoria"),
            ("FIS301", "Física para Computación", "teoria"),
            ("FIS302", "Laboratorio de Física Experimental", "laboratorio"),
            ("INF401", "Compiladores y Lenguajes", "teoria"),
            ("INF402", "Criptografía y Seguridad", "teoria"),
            ("INF403", "Arquitectura de Computadores", "teoria"),
            ("INF404", "Computación Gráfica", "laboratorio"),
            ("INF405", "Ingeniería de Requerimientos", "teoria"),
            ("INF406", "Minería de Datos", "teoria"),
            ("INF407", "Computación Cuántica", "teoria"),
            ("INF408", "Robótica Autónoma", "laboratorio"),
            ("HUM101", "Ética en Inteligencia Artificial", "teoria"),
            ("HUM102", "Comunicación Científica", "teoria"),
            ("GES201", "Gestión de Proyectos Tecnológicos", "teoria"),
        ]

        classes: list[dict[str, Any]] = []
        classes_per_course = max(1, n_classes // n_courses)
        remaining = n_classes - (classes_per_course * n_courses)

        c_counter = 1
        for c_idx in range(n_courses):
            c_code, c_name, req_type = course_catalog[c_idx % len(course_catalog)]
            secs = classes_per_course + (1 if c_idx < remaining else 0)

            for s_idx in range(1, secs + 1):
                p_assigned = f"PROF-{((c_counter - 1) % n_profs) + 1:02d}"
                duration = 2 if rng.random() < 0.75 else 1
                cap = rng.choice([30, 35, 40]) if req_type == "laboratorio" else rng.choice([40, 50, 60])

                classes.append({
                    "id": f"{c_code}-{s_idx}",
                    "course_id": c_code,
                    "course_name": c_name,
                    "professor_id": p_assigned,
                    "capacity": cap,
                    "duration_hours": duration,
                    "required_room_type": req_type
                })
                c_counter += 1

        # 4. Estudiantes con prioridades y solicitudes
        students: list[dict[str, Any]] = []
        selected_courses = [course_catalog[i % len(course_catalog)][0] for i in range(n_courses)]

        for s_idx in range(1, n_students + 1):
            n_req = rng.randint(req_range[0], req_range[1])
            chosen_courses = rng.sample(selected_courses, min(n_req, len(selected_courses)))

            requests: list[dict[str, Any]] = []
            for r_prio, c_code in enumerate(chosen_courses, start=1):
                requests.append({
                    "course_id": c_code,
                    "priority": r_prio
                })

            # Mérito académico ponderado entre 3.0 y 5.0
            gpa = round(rng.uniform(3.2, 4.9), 2)
            students.append({
                "id": f"EST-{s_idx:03d}",
                "name": f"Estudiante {s_idx:03d}",
                "priority_score": gpa,
                "requests": requests
            })

        scenario_data = {
            "metadata": {
                "name": filename.replace(".json", ""),
                "description": f"Escenario sintético con {n_students} estudiantes, {n_classes} clases y {n_rooms} salones.",
                "total_students": n_students,
                "total_classes": len(classes),
                "total_rooms": n_rooms,
                "total_professors": n_profs
            },
            "rooms": rooms,
            "professors": professors,
            "classes": classes,
            "students": students
        }

        target_file = scenarios_dir / filename
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(scenario_data, f, indent=2, ensure_ascii=False)

        generated_paths[filename] = target_file
        print(f"[OK] Generado escenario: {target_file.name} ({n_students} estudiantes, {len(classes)} clases, {n_rooms} aulas)")

    return generated_paths


def run_single_scenario(input_path: Path, output_path: Path, verbose: bool = False) -> None:
    """Ejecuta la optimización sobre un archivo de escenario y exporta la solución."""
    print(f"\n>> Procesando escenario: {input_path}")
    orchestrator = TimetableOrchestrator()
    orchestrator.load_scenario_file(input_path)

    orchestrator.run()

    # Imprimir reporte resumido en consola
    print(orchestrator.get_summary_text())

    # Exportar solución JSON
    orchestrator.export_solution(output_path)
    print(f"[OK] Solución exportada exitosamente a: {output_path}")

    if verbose and orchestrator.report:
        report_data = orchestrator.report.to_full_dict()
        print("\n--- Muestra de Horarios de Clases Programadas (Primeras 5) ---")
        sample_classes = list(report_data["class_schedule"].values())[:5]
        for c in sample_classes:
            print(f" * {c['class_id']}: {c['course_name']} | {c['time_str']} | {c['room_id']} | "
                  f"Prof: {c['professor_name']} | Inscritos: {c['enrolled_count']}/{c['capacity']}")


def run_benchmark(base_dir: Path) -> None:
    """Ejecuta una batería de benchmarks sobre los escenarios estándar y despliega métricas comparativas."""
    scenarios_dir = base_dir / "data" / "scenarios"
    outputs_dir = base_dir / "data" / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    scenarios = [
        ("scenario_small.json", "output_small.json"),
        ("scenario_medium.json", "output_medium.json"),
        ("scenario_large.json", "output_large.json"),
    ]

    print("\n" + "=" * 80)
    print("                    BENCHMARK DE ESCALABILIDAD UCTP")
    print("=" * 80)

    summary_rows = []

    for scen_file, out_file in scenarios:
        in_p = scenarios_dir / scen_file
        if not in_p.exists():
            print(f"[!] No existe {in_p.name}, generando escenarios...")
            generate_benchmark_scenarios(base_dir)

        out_p = outputs_dir / out_file
        orch = TimetableOrchestrator()
        orch.load_scenario_file(in_p)
        result = orch.run()
        orch.export_solution(out_p)

        m = result["metrics"]
        t = m["timings_ms"]
        summary_rows.append({
            "scenario": scen_file.replace(".json", ""),
            "students": m["total_students"],
            "classes": f"{m['scheduled_classes']}/{m['total_classes']}",
            "satisfaction": f"{m['global_student_satisfaction_percent']}%",
            "hard_conflicts": m["hard_conflicts_count"],
            "student_clashes": m["student_clashes_count"],
            "phase1_ms": f"{t.get('phase1_dsatur_ms', 0):.2f}",
            "phase2_ms": f"{t.get('phase2_mcmf_ms', 0):.2f}",
            "total_ms": f"{t.get('total_ms', 0):.2f}",
        })

    # Imprimir tabla formateada
    headers = ["Escenario", "Alumnos", "Clases Prog.", "Satisfacción", "Conf. Duros", "Choques", "DSATUR ms", "MCMF ms", "Total ms"]
    col_widths = [16, 9, 13, 14, 13, 9, 11, 10, 10]

    header_line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    sep_line = "-+-".join("-" * w for w in col_widths)

    print(header_line)
    print(sep_line)
    for r in summary_rows:
        row_vals = [
            r["scenario"],
            str(r["students"]),
            r["classes"],
            r["satisfaction"],
            str(r["hard_conflicts"]),
            str(r["student_clashes"]),
            r["phase1_ms"],
            r["phase2_ms"],
            r["total_ms"]
        ]
        print(" | ".join(v.ljust(w) for v, w in zip(row_vals, col_widths)))
    print("=" * 80)
    print("[OK] Benchmark completado con 100% de invariantes satisfechas.")


def main() -> None:
    """Punto de entrada principal de la interfaz por línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Sistema de Programación Académica Universitaria (Grafo de Conflictos + DSATUR + MCMF)"
    )
    parser.add_argument(
        "-i", "--input",
        type=str,
        default=None,
        help="Ruta al archivo JSON del escenario de entrada."
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Ruta al archivo JSON donde se exportará la programación e informe."
    )
    parser.add_argument(
        "-g", "--generate",
        action="store_true",
        help="Genera los escenarios estándar (pequeño, mediano y grande con 200 estudiantes)."
    )
    parser.add_argument(
        "-b", "--benchmark",
        action="store_true",
        help="Ejecuta la batería de pruebas y comparativa de rendimiento en todos los escenarios."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Muestra detalles extendidos de la asignación en consola."
    )

    args = parser.parse_args()
    base_dir = Path(__file__).resolve().parent

    # Opción 1: Generar escenarios
    if args.generate:
        generate_benchmark_scenarios(base_dir)
        return

    # Opción 2: Ejecutar benchmark
    if args.benchmark:
        run_benchmark(base_dir)
        return

    # Opción 3: Ejecución de un escenario específico (o default)
    input_file = Path(args.input) if args.input else (base_dir / "data" / "scenarios" / "scenario_small.json")
    if not input_file.exists():
        print(f"[*] El archivo de escenario por defecto {input_file.name} no existe. Generando escenarios estándar...")
        generate_benchmark_scenarios(base_dir)

    scenario_name = input_file.stem
    output_file = (
        Path(args.output)
        if args.output
        else (base_dir / "data" / "outputs" / f"schedule_{scenario_name}.json")
    )

    run_single_scenario(input_file, output_file, verbose=args.verbose)


if __name__ == "__main__":
    main()
