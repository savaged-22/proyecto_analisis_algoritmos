"""Métricas del informe, motivos de las pendientes y algoritmos usados, sobre el escenario inicial del documento."""

import unittest
from pathlib import Path

from src.solver.orchestrator import TimetableOrchestrator

INICIAL = Path(__file__).resolve().parent.parent / "data" / "scenarios" / "inicial.json"


class InitialScenarioReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.orch = TimetableOrchestrator()
        cls.orch.load_scenario_file(INICIAL)
        cls.result = cls.orch.run()
        cls.metrics = cls.result["metrics"]

    def test_has_the_document_size(self) -> None:
        sc = self.orch.scenario
        self.assertEqual((len(sc.students), len(sc.professors), len(sc.classes), len(sc.rooms)), (20, 5, 8, 10))

    def test_no_violations(self) -> None:
        self.assertEqual(self.metrics["violations_total"], 0)
        self.assertEqual(self.result["verification"]["total_violations"], 0)

    def test_counts_are_consistent(self) -> None:
        m = self.metrics
        self.assertEqual(m["total_requests"], 48)
        self.assertEqual(m["attended_requests"] + m["pending_requests"], m["total_requests"])
        self.assertEqual(sum(m["pending_by_reason"].values()), m["pending_requests"])
        self.assertEqual(sum(level["requests"] for level in m["by_priority"].values()), m["total_requests"])

    def test_expected_outcome(self) -> None:
        expected = self.orch.scenario.expected
        self.assertEqual(self.metrics["scheduled_classes"], expected["scheduled_classes"])
        self.assertEqual(self.metrics["unscheduled_class_ids"], expected["unscheduled_classes"])
        self.assertEqual(self.metrics["attended_requests"], 37)

    def test_pending_reasons(self) -> None:
        students = self.result["student_schedule"]
        reasons = {(sid, p["class_id"]): p["reason"] for sid, s in students.items() for p in s["pending_requests"]}
        self.assertEqual(reasons[("E03", "ALG")], "cruce con BD (prioridad 3)")
        self.assertEqual(reasons[("E04", "BD")], "cruce con ALG (prioridad 3)")
        self.assertEqual(reasons[("E16", "COM")], "clase no programada")
        self.assertEqual(self.metrics["pending_by_reason"]["cupo agotado"], 4)

    def test_lab_class_in_a_lab_and_theory_classes_in_classrooms(self) -> None:
        rooms = {c.id: c.assigned_room_id for c in self.orch.classes}
        self.assertTrue(rooms["RED"].startswith("LAB"))
        self.assertTrue(all(room.startswith("AULA") for cid, room in rooms.items() if room and cid != "RED"))

    def test_reports_algorithms_and_complexity(self) -> None:
        algorithms = self.result["algorithms"]
        names = [a["step"] for a in algorithms]
        self.assertEqual(names, ["Grafo de conflictos", "Ubicar clases", "Inscribir", "Verificador"])
        place = algorithms[1]
        self.assertEqual(place["algorithm"], "Ramificación y poda (exacto)")
        self.assertIn("O(", place["complexity"])
        self.assertIn("≤ 12", place["why"])


if __name__ == "__main__":
    unittest.main()
