"""Métricas del informe y motivos de las solicitudes pendientes sobre el escenario de demostración."""

import unittest
from pathlib import Path

from src.solver.orchestrator import TimetableOrchestrator

DEMO = Path(__file__).resolve().parent.parent / "data" / "scenarios" / "demo.json"


class DemoReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.orch = TimetableOrchestrator()
        cls.orch.load_scenario_file(DEMO)
        cls.result = cls.orch.run()
        cls.metrics = cls.result["metrics"]

    def test_no_violations(self) -> None:
        self.assertEqual(self.metrics["violations_total"], 0)
        self.assertEqual(self.result["verification"]["total_violations"], 0)

    def test_counts_are_consistent(self) -> None:
        m = self.metrics
        self.assertEqual(m["total_requests"], 21)
        self.assertEqual(m["attended_requests"] + m["pending_requests"], m["total_requests"])
        self.assertEqual(sum(m["pending_by_reason"].values()), m["pending_requests"])
        self.assertEqual(sum(level["requests"] for level in m["by_priority"].values()), m["total_requests"])
        self.assertEqual(m["received_priority_sum"], 43)

    def test_expected_outcome_of_demo(self) -> None:
        expected = self.orch.scenario.expected
        self.assertEqual(self.metrics["scheduled_classes"], expected["scheduled_classes"])
        self.assertEqual(self.metrics["unscheduled_class_ids"], expected["unscheduled_classes"])
        self.assertEqual(self.metrics["attended_requests"], 14)

    def test_pending_reasons(self) -> None:
        students = self.result["student_schedule"]
        reasons = {(sid, p["class_id"]): p["reason"] for sid, s in students.items() for p in s["pending_requests"]}
        self.assertEqual(reasons[("E1", "BD")], "cruce con ALG (prioridad 3)")
        self.assertEqual(reasons[("E2", "ALG")], "cruce con BD (prioridad 3)")
        self.assertEqual(reasons[("E8", "COM")], "clase no programada")
        self.assertEqual(self.metrics["pending_by_reason"]["cupo agotado"], 2)


if __name__ == "__main__":
    unittest.main()
