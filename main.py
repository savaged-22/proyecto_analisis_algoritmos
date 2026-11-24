"""CLI del sistema de asignación de horarios estudiantiles.

Uso:
    python main.py                                   # ejecuta el escenario de demostración
    python main.py -i data/scenarios/C_profesor.json -v
    python main.py --generate [--seed 2026]          # escribe el conjunto base (A) y los escenarios B-F
    python main.py --scale 20 50 100 200 --seeds 1 2 3
    python main.py --benchmark
"""

import argparse
import sys
from pathlib import Path

from src.data.generator import DEFAULT_SEED, write_scale_scenarios, write_standard_scenarios
from src.solver.orchestrator import TimetableOrchestrator

BASE_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = BASE_DIR / "data" / "scenarios"
SCALE_DIR = SCENARIOS_DIR / "escala"
OUTPUTS_DIR = BASE_DIR / "data" / "outputs"
DEFAULT_SCENARIO = SCENARIOS_DIR / "demo.json"
STANDARD_SCENARIOS = ["demo", "A_factible", "B_salones", "C_profesor", "D_estudiantes", "E_capacidad", "F_imposible"]


def run_single_scenario(input_path: Path, output_path: Path, verbose: bool = False) -> None:
    """Ejecuta el algoritmo sobre un escenario y exporta la solución."""
    print(f"\n>> Procesando escenario: {input_path}")
    orchestrator = TimetableOrchestrator()
    orchestrator.load_scenario_file(input_path)
    orchestrator.run()

    print(orchestrator.get_summary_text())
    orchestrator.export_solution(output_path)
    print(f"[OK] Solución exportada a: {output_path}")

    if verbose and orchestrator.report:
        report_data = orchestrator.report.to_full_dict()
        print("\n--- Programación de clases ---")
        for c in report_data["class_schedule"].values():
            print(f" * {c['class_id']}: {c['course_name']} | {c['time_str']} | {c['room_id']} | "
                  f"Prof: {c['professor_name']} | Inscritos: {c['enrolled_count']}/{c['capacity']}")


def run_benchmark() -> None:
    """Ejecuta los escenarios estándar y muestra una tabla comparativa."""
    if not all((SCENARIOS_DIR / f"{name}.json").exists() for name in STANDARD_SCENARIOS[1:]):
        print("[!] Faltan escenarios estándar, generándolos...")
        write_standard_scenarios(SCENARIOS_DIR)

    rows = []
    for name in STANDARD_SCENARIOS:
        orch = TimetableOrchestrator()
        orch.load_scenario_file(SCENARIOS_DIR / f"{name}.json")
        result = orch.run()
        orch.export_solution(OUTPUTS_DIR / f"output_{name}.json")

        m = result["metrics"]
        t = m["timings_ms"]
        rows.append([
            name,
            str(m["total_students"]),
            f"{m['scheduled_classes']}/{m['total_classes']}",
            f"{m['satisfied_requests']}/{m['total_requests']}",
            str(m["hard_conflicts_count"]),
            str(m["student_clashes_count"]),
            f"{t.get('phase1_dsatur_ms', 0):.2f}",
            f"{t.get('phase2_mcmf_ms', 0):.2f}",
            f"{t.get('total_ms', 0):.2f}",
        ])

    headers = ["Escenario", "Alumnos", "Clases", "Solicitudes", "Conf. duros", "Choques", "Fase 1 ms", "Fase 2 ms", "Total ms"]
    widths = [14, 8, 8, 12, 11, 8, 10, 10, 9]
    print("\n" + " | ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(" | ".join(v.ljust(w) for v, w in zip(row, widths)))


def main() -> None:
    # Consolas de Windows: forzar UTF-8 para que las tildes se vean bien
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser =argparse.ArgumentParser(description="Asignación de horarios estudiantiles")
    parser.add_argument("-i", "--input", type=str, help="Escenario JSON de entrada (por defecto, demo.json).")
    parser.add_argument("-o", "--output", type=str, help="Archivo JSON de salida.")
    parser.add_argument("-g", "--generate", action="store_true", help="Genera el conjunto base (A) y los escenarios B-F.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Semilla para --generate.")
    parser.add_argument("--scale", type=int, nargs="+", metavar="N", help="Genera escenarios de escalabilidad con N estudiantes.")
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3], help="Semillas para --scale.")
    parser.add_argument("-b", "--benchmark", action="store_true", help="Ejecuta los escenarios estándar.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Muestra la programación de cada clase.")
    args = parser.parse_args()

    if args.generate:
        for path in write_standard_scenarios(SCENARIOS_DIR, args.seed):
            print(f"[OK] {path.relative_to(BASE_DIR)}")
        return

    if args.scale:
        for path in write_scale_scenarios(SCALE_DIR, args.scale, args.seeds):
            print(f"[OK] {path.relative_to(BASE_DIR)}")
        return

    if args.benchmark:
        run_benchmark()
        return

    input_file = Path(args.input) if args.input else DEFAULT_SCENARIO
    output_file = Path(args.output) if args.output else OUTPUTS_DIR / f"output_{input_file.stem}.json"
    run_single_scenario(input_file, output_file, verbose=args.verbose)


if __name__ == "__main__":
    main()
