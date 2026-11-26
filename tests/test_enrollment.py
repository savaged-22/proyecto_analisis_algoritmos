import unittest
from pathlib import Path

from src.data.scenario import load_scenario_dict
from src.phase2.enrollment import EnrollmentSolver
from src.solver.orchestrator import TimetableOrchestrator

SCENARIOS = Path(__file__).resolve().parent.parent / "data" / "scenarios"


def scheduled(data: dict, placements: dict[str, tuple[int, str]]):
    """Carga un escenario y fija a mano el horario de cada clase (sin pasar por la fase 1)."""
    sc = load_scenario_dict(data)
    for c in sc.classes:
        if c.id in placements:
            hour, room = placements[c.id]
            c.assigned_slot = sc.grid.day_hour_to_slot(0, hour)
            c.assigned_room_id = room
            c.time_mask = sc.grid.create_slot_mask(c.assigned_slot, c.duration_hours)
    return sc


def solve(sc) -> dict[str, list[str]]:
    EnrollmentSolver(sc.classes, sc.students, sc.rooms, sc.total_requests).solve()
    return {s.id: sorted(s.assigned_classes) for s in sc.students}


ROOMS = [{"id": "R", "capacity": 50}, {"id": "R2", "capacity": 50}]
PROFS = [{"id": "P"}, {"id": "Q"}]


class EnrollmentTest(unittest.TestCase):
    def test_full_class_goes_to_higher_priority(self) -> None:
        data = {
            "rooms": ROOMS, "professors": PROFS,
            "classes": [{"id": "X", "professor_id": "P", "capacity": 1, "duration_hours": 1}],
            "students": [
                {"id": "S1", "requests": [{"class_id": "X", "priority": 1}]},
                {"id": "S2", "requests": [{"class_id": "X", "priority": 3}]},
            ],
        }
        result = solve(scheduled(data, {"X": (8, "R")}))
        self.assertEqual(result, {"S1": [], "S2": ["X"]})

    def test_rejected_student_replans_with_another_combination(self) -> None:
        # S1 prefiere A (8-10) pero A tiene un solo cupo y S2 la pide con prioridad 3.
        # Sin A, S1 puede tomar B (8-9) y C (9-10), que se cruzaban con A.
        data = {
            "rooms": ROOMS, "professors": PROFS,
            "classes": [
                {"id": "A", "professor_id": "P", "capacity": 1, "duration_hours": 2},
                {"id": "B", "professor_id": "Q", "capacity": 5, "duration_hours": 1},
                {"id": "C", "professor_id": "Q", "capacity": 5, "duration_hours": 1},
            ],
            "students": [
                {"id": "S1", "requests": [{"class_id": "A", "priority": 3},
                                          {"class_id": "B", "priority": 1},
                                          {"class_id": "C", "priority": 1}]},
                {"id": "S2", "requests": [{"class_id": "A", "priority": 3}]},
            ],
        }
        sc = scheduled(data, {"A": (8, "R"), "B": (8, "R2"), "C": (9, "R2")})
        result = solve(sc)
        self.assertEqual(result, {"S1": ["A"], "S2": []})  # a igual prioridad gana el primero de la entrada

        # Si S2 aparece primero, gana el cupo de A; S1 vuelve a planear y toma B y C.
        data["students"].reverse()
        sc = scheduled(data, {"A": (8, "R"), "B": (8, "R2"), "C": (9, "R2")})
        solver = EnrollmentSolver(sc.classes, sc.students, sc.rooms, sc.total_requests)
        stats = solver.solve()
        result = {s.id: sorted(s.assigned_classes) for s in sc.students}
        self.assertEqual(result, {"S1": ["B", "C"], "S2": ["A"]})
        self.assertEqual(stats["rejections"], 1)
        self.assertEqual(stats["rounds"], 2)

    def test_room_capacity_limits_the_class(self) -> None:
        data = {
            "rooms": [{"id": "SMALL", "capacity": 1}], "professors": PROFS,
            "classes": [{"id": "X", "professor_id": "P", "capacity": 10, "duration_hours": 1}],
            "students": [{"id": f"S{i}", "requests": [{"class_id": "X", "priority": 2}]} for i in range(3)],
        }
        result = solve(scheduled(data, {"X": (8, "SMALL")}))
        self.assertEqual(sum(len(v) for v in result.values()), 1)

    def test_respects_student_availability(self) -> None:
        data = {
            "rooms": ROOMS, "professors": PROFS,
            "classes": [{"id": "X", "professor_id": "P", "capacity": 5, "duration_hours": 1}],
            "students": [{"id": "S1", "availability": [14], "requests": [{"class_id": "X", "priority": 3}]}],
        }
        self.assertEqual(solve(scheduled(data, {"X": (8, "R")})), {"S1": []})


class GeneratedScenariosTest(unittest.TestCase):
    def run_scenario(self, name: str):
        orch = TimetableOrchestrator()
        orch.load_scenario_file(SCENARIOS / f"{name}.json")
        return orch, orch.run()

    def test_d_students_keep_higher_priority(self) -> None:
        orch, result = self.run_scenario("D_estudiantes")
        students = {s.id: s for s in orch.students}
        for sid, keep in orch.scenario.expected["students_keep"].items():
            self.assertEqual(students[sid].assigned_classes, [keep])
        self.assertEqual(result["metrics"]["violations_total"], 0)

    def test_e_capacity_pending_are_the_excess(self) -> None:
        orch, result = self.run_scenario("E_capacidad")
        exp = orch.scenario.expected
        cls = next(c for c in orch.classes if c.id == exp["class_id"])
        self.assertEqual(len(cls.enrolled_students), exp["capacity"])
        pending_full = [p for s in result["student_schedule"].values() for p in s["pending_requests"]
                        if p["class_id"] == exp["class_id"] and p["reason"] == "cupo agotado"]
        self.assertEqual(len(pending_full), exp["best_pending_for_capacity"])


if __name__ == "__main__":
    unittest.main()
