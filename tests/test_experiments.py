import tempfile
import unittest
from pathlib import Path

from src.analysis.experiments import approximation, loglog_slope, pruning, scalability, write_results
from src.data.generator import build_conflict_scenario
from src.data.scenario import load_scenario_dict

DEMO = Path(__file__).resolve().parent.parent / "data" / "scenarios" / "inicial.json"


class ExperimentsTest(unittest.TestCase):
    def test_loglog_slope_recovers_exponent(self) -> None:
        self.assertEqual(loglog_slope([(n, 3 * n ** 2) for n in (10, 20, 40, 80)]), 2.0)
        self.assertEqual(loglog_slope([(n, 5 * n) for n in (10, 100)]), 1.0)
        self.assertIsNone(loglog_slope([(10, 1)]))

    def test_conflict_scenario_is_valid_and_reproducible(self) -> None:
        a, b = build_conflict_scenario(20, seed=4), build_conflict_scenario(20, seed=4)
        self.assertEqual(a, b)
        sc = load_scenario_dict(a)
        self.assertTrue(all(len(c.allowed_starts) <= 2 for c in sc.classes))

    def test_small_runs_and_export(self) -> None:
        scal = scalability(sizes=[20, 40], seeds=[1])
        self.assertEqual(len(scal["summary"]), 4)
        self.assertTrue(all(r["violations"] == 0 for r in scal["rows"]))

        prun = pruning([DEMO], conflict_sizes=[20], seeds=[1])
        demo = prun["rows"][0]
        self.assertEqual(demo["backtracking_cost"], demo["exacto_cost"])
        self.assertLessEqual(demo["exacto_nodes"], demo["backtracking_nodes"])

        approx = approximation(sizes=[20], seeds=[1, 3])
        self.assertTrue(all(0 < r["ratio"] <= 1 for r in approx["rows"]))
        self.assertTrue(all(r["exact_cost"] <= r["heuristic_cost"] for r in approx["rows"]))

        with tempfile.TemporaryDirectory() as tmp:
            paths = write_results(Path(tmp), {"escalabilidad": scal, "podas": prun, "aproximacion": approx})
            self.assertEqual(sorted(p.name for p in paths),
                             ["aproximacion.csv", "escalabilidad.csv", "experimentos.json", "podas.csv"])


if __name__ == "__main__":
    unittest.main()
