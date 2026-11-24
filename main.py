"""CLI del sistema de asignación de horarios estudiantiles.

Uso:
    python main.py                                   # ejecuta el escenario de demostración
    python main.py -i data/scenarios/C_profesor.json -v
    python main.py --generate [--seed 2026]          # escribe el conjunto base (A) y los escenarios B-F
    python main.py --scale 20 50 100 200 --seeds 1 2 3
    python main.py --benchmark
    python main.py --verify data/scenarios/demo.json data/outputs/output_demo.json
    python main.py -i data/scenarios/F_imposible.json --modo exacto
    python main.py --comparar -i data/scenarios/demo.json   # heurística vs backtracking vs exacto vs fuerza bruta
"""

import argparse
import json
import sys
from pathlib import Path

from src import config
from src.data.generator import DEFAULT_SEED, write_scale_scenarios, write_standard_scenarios
from src.phase1.brute_force import InstanceTooLargeError
from src.data.scenario import load_scenario_file
from src.solver.orchestrator import TimetableOrchestrator
from src.verify.verifier import RULES, verify_solution

BASE_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = BASE_DIR / "data" / "scenarios"
SCALE_DIR = SCENARIOS_DIR / "escala"
OUTPUTS_DIR = BASE_DIR / "data" / "outputs"
DEFAULT_SCENARIO = SCENARIOS_DIR / "demo.json"
STANDARD_SCENARIOS = ["demo", "A_factible", "B_salones", "C_profesor", "D_estudiantes", "E_capacidad", "F_imposible"]


def run_single_scenario(input_path: Path, output_path: Path, verbose: bool = False,
                        mode: str = config.DEFAULT_PHASE1_MODE) -> None:
    """Ejecuta el algoritmo sobre un escenario y exporta la solución."""
    print(f"\n>> Procesando escenario: {input_path}")
    orchestrator = TimetableOrchestrator()
    orchestrator.load_scenario_file(input_path)
    orchestrator.run(phase1_mode=mode)

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
            f"{m['scheduled_classes']}/{m['total_classes']}",
            f"{m['attended_requests']}/{m['total_requests']}",
            f"{m['coverage_percent']}%",
            f"{m['priority_satisfaction_percent']}%",
            str(m["violations_total"]),
            f"{t.get('phase1_ms', 0):.2f}",
            f"{t.get('phase2_ms', 0):.2f}",
            f"{t.get('total_ms', 0):.2f}",
        ])

    headers = ["Escenario", "Clases", "Solicitudes", "Cobertura", "Prioridad", "Incumpl.", "Fase 1 ms", "Fase 2 ms", "Total ms"]
    widths = [14, 7, 12, 10, 10, 9, 10, 10, 9]
    print("\n" + " | ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(" | ".join(v.ljust(w) for v, w in zip(row, widths)))


def run_comparison(input_path: Path) -> None:
    """Corre la fase 1 con cada estrategia sobre el mismo escenario y compara trabajo y resultado."""
    print(f"\nComparación de estrategias de la fase 1 sobre {input_path.name}\n")
    headers = ["Estrategia", "Nodos/hojas", "Podas", "Costo F1", "Clases", "Solicitudes", "Prioridad", "Óptimo", "ms F1"]
    widths = [13, 12, 8, 9, 7, 12, 10, 11, 9]
    print(" | ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("-+-".join("-" * w for w in widths))
    for mode in ["heuristica", "backtracking", "exacto", "fuerza_bruta"]:
        orch = TimetableOrchestrator()
        orch.load_scenario_file(input_path)
        try:
            result = orch.run(phase1_mode=mode)
        except InstanceTooLargeError as exc:
            print(f"{mode.ljust(widths[0])} | {exc}")
            continue
        m, p1 = result["metrics"], result["phase1_details"]
        search = p1["search"] or {}
        work = search.get("nodes", search.get("leaves", "-"))
        optimal = {True: "sí", False: "no (límite)", None: "-"}[p1["optimal"]]
        row = [mode, str(work), str(search.get("pruned_by_bound", "-")), str(p1["cost"]["total"]),
               f"{m['scheduled_classes']}/{m['total_classes']}", f"{m['attended_requests']}/{m['total_requests']}",
               f"{m['priority_satisfaction_percent']}%", optimal, f"{m['timings_ms']['phase1_ms']:.1f}"]
        print(" | ".join(v.ljust(w) for v, w in zip(row, widths)))


def print_table(title: str, headers: list[str], rows: list[list[str]]) -> None:
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    print(f"\n{title}\n")
    print(" | ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(" | ".join(v.ljust(w) for v, w in zip(row, widths)))


def run_experiments(which: list[str], sizes: list[int], seeds: list[int]) -> None:
    """Experimentos de escalabilidad, podas y aproximación; guarda CSV y JSON en data/outputs/experimentos."""
    from src.analysis import experiments

    results = {}
    if "escalabilidad" in which:
        res = experiments.scalability(sizes, seeds)
        results["escalabilidad"] = res
        print_table(
            f"ESCALABILIDAD (escenario A en proporción, promedio de {len(seeds)} semillas)",
            ["Modo", "Estudiantes", "Clases", "Cobertura", "Prioridad", "Incumpl.", "Fase 1 ms", "Fase 2 ms", "Total ms"],
            [[r["mode"], str(r["students"]), str(r["classes"]), f"{r['coverage']}%", f"{r['priority']}%",
              str(r["violations"]), f"{r['phase1_ms']:.1f}", f"{r['phase2_ms']:.1f}", f"{r['total_ms']:.1f}"]
             for r in res["summary"]],
        )
        print("\nExponente empírico (pendiente log-log del tiempo contra el número de estudiantes):")
        for mode, slopes in res["loglog_slopes"].items():
            print(f"  {mode:<11} fase 1: {slopes['phase1_ms']}  fase 2: {slopes['phase2_ms']}  total: {slopes['total_ms']}")

    if "podas" in which:
        res = experiments.pruning([SCENARIOS_DIR / f"{n}.json" for n in STANDARD_SCENARIOS])
        results["podas"] = res
        limit = res["node_limit"]
        print_table(
            "PODAS: trabajo de cada estrategia de la fase 1",
            ["Escenario", "Clases", "Fuerza bruta (hojas)", "Backtracking (nodos)", "Ramif. y poda (nodos)", "Reducción"],
            [[r["scenario"], str(r["classes"]), f"{r['brute_force_leaves']:.2e}",
              f"{r['backtracking_nodes']:,}" + ("" if r["backtracking_complete"] else f" (tope {limit:,})"),
              f"{r['exacto_nodes']:,}", f"x{r['reduction']}"] for r in res["rows"]],
        )

    if "aproximacion" in which:
        res = experiments.approximation()
        results["aproximacion"] = res
        print_table(
            "APROXIMACIÓN: heurística (DSATUR) frente al óptimo (ramificación y poda)",
            ["Estudiantes", "Semilla", "Clases", "Costo heur.", "Costo óptimo", "Prioridad heur.", "Prioridad ópt.",
             "Razón", "ms heur.", "ms ópt."],
            [[str(r["students"]), str(r["seed"]), str(r["classes"]), str(r["heuristic_cost"]), str(r["exact_cost"]),
              str(r["heuristic_priority"]), str(r["exact_priority"]), f"{r['ratio']:.3f}",
              f"{r['heuristic_ms']:.1f}", f"{r['exact_ms']:.1f}"] for r in res["rows"]],
        )
        print(f"\nRazón promedio: {res['mean_ratio']} · peor caso: {res['min_ratio']} · "
              f"la heurística llegó al óptimo en {res['heuristic_optimal_share'] * 100:.0f}% de los casos")

    for path in experiments.write_results(OUTPUTS_DIR / "experimentos", results):
        print(f"[OK] {path.relative_to(BASE_DIR)}")


def run_verifier(scenario_path: Path, output_path: Path) -> None:
    """Verifica con R1-R10 una solución exportada, sin ejecutar el algoritmo."""
    scenario = load_scenario_file(scenario_path)
    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    result = verify_solution(scenario, data.get("solution", data))

    print(f"Verificación de {output_path.name} contra {scenario_path.name}")
    for rule, count in result.count_by_rule().items():
        print(f"  {rule:<4} {RULES[rule]:<34} {count}")
    print(f"  Total de incumplimientos: {result.total}")
    for v in result.violations:
        print(f"   - [{v.rule}] {v.message}")


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
    parser.add_argument("--modo", choices=config.PHASE1_MODES, default=config.DEFAULT_PHASE1_MODE,
                        help="Estrategia de la fase 1 (por defecto: auto).")
    parser.add_argument("--comparar", action="store_true",
                        help="Compara las estrategias de la fase 1 sobre el escenario de entrada.")
    parser.add_argument("--experimentos", nargs="*", choices=["escalabilidad", "podas", "aproximacion"],
                        help="Experimentos de análisis (sin argumentos: todos). Usa --sizes y --seeds.")
    parser.add_argument("--sizes", type=int, nargs="+", default=[20, 50, 100, 200],
                        help="Tamaños (estudiantes) para el experimento de escalabilidad.")
    parser.add_argument("--verify", nargs=2, metavar=("ESCENARIO", "SALIDA"),
                        help="Verifica una solución exportada contra su escenario (R1-R10).")
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

    if args.experimentos is not None:
        run_experiments(args.experimentos or ["escalabilidad", "podas", "aproximacion"], args.sizes, args.seeds)
        return

    if args.verify:
        run_verifier(Path(args.verify[0]), Path(args.verify[1]))
        return

    input_file = Path(args.input) if args.input else DEFAULT_SCENARIO
    if args.comparar:
        run_comparison(input_file)
        return
    output_file = Path(args.output) if args.output else OUTPUTS_DIR / f"output_{input_file.stem}.json"
    run_single_scenario(input_file, output_file, verbose=args.verbose, mode=args.modo)


if __name__ == "__main__":
    main()
