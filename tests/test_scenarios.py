"""Escenario inicial y escenarios A-F: el resultado cumple lo esperado, con cualquier estrategia y con varias semillas."""

import unittest
from pathlib import Path

from src.data.generator import SCENARIO_BUILDERS, build_base_scenario
from src.solver.orchestrator import TimetableOrchestrator
from src.verify.expectations import check_expectations, failed_checks

SCENARIOS = Path(__file__).resolve().parent.parent / "data" / "scenarios"
STANDARD = ["inicial", "pequeno", "A_factible", "B_salones", "C_profesor", "D_estudiantes", "E_capacidad", "F_imposible"]


def run(source, mode: str):
    orch = TimetableOrchestrator()
    if isinstance(source, Path):
        orch.load_scenario_file(source)
    else:
        orch.load_scenario_dict(source)
    return orch, orch.run(phase1_mode=mode)


class StandardScenariosTest(unittest.TestCase):
    def test_every_scenario_meets_its_expectations(self) -> None:
        for name in STANDARD:
            for mode in ("exacto", "heuristica"):
                with self.subTest(scenario=name, mode=mode):
                    orch, result = run(SCENARIOS / f"{name}.json", mode)
                    self.assertEqual(failed_checks(orch.scenario, result), [])
                    self.assertTrue(check_expectations(orch.scenario, result))

    def test_exact_mode_reaches_every_optimal_expectation(self) -> None:
        for name in STANDARD:
            with self.subTest(scenario=name):
                orch, result = run(SCENARIOS / f"{name}.json", "exacto")
                self.assertTrue(result["phase1_details"]["optimal"])
                self.assertTrue(all(c.passed for c in check_expectations(orch.scenario, result)))


class GeneratedSeedsTest(unittest.TestCase):
    def test_expectations_hold_for_many_seeds(self) -> None:
        """Lo esperado de cada escenario es correcto para cualquier semilla, no solo para la publicada."""
        for seed in range(1, 16):
            base = build_base_scenario(seed)
            for data in [base] + [builder(base, seed) for builder in SCENARIO_BUILDERS]:
                with self.subTest(seed=seed, scenario=data["metadata"]["name"]):
                    orch, result = run(data, "exacto")
                    self.assertTrue(all(c.passed for c in check_expectations(orch.scenario, result)),
                                    [c.to_dict() for c in check_expectations(orch.scenario, result) if not c.passed])


if __name__ == "__main__":
    unittest.main()
