import random
import unittest
from pathlib import Path

from src.data.scenario import load_scenario_dict
from src.graph.conflict_graph import build_conflict_graph
from src.phase1.backtracking import BacktrackingScheduler
from src.phase1.brute_force import BruteForceScheduler, InstanceTooLargeError
from src.phase1.cost import ScheduleCost
from src.phase1.dsatur import DSATURColoringSolver
from src.phase1.scheduler import read_assignment
from src.solver.orchestrator import TimetableOrchestrator

SCENARIOS = Path(__file__).resolve().parent.parent / "data" / "scenarios"


def random_tiny_scenario(rng: random.Random) -> dict:
    """Instancia diminuta (jornada de 4 horas) para poder compararla con fuerza bruta."""
    hours = [8, 9, 10, 11]
    rooms = [{"id": f"R{i}", "capacity": rng.choice([2, 4, 6]),
              "availability": sorted(rng.sample(hours, rng.randint(2, 4))),
              "room_type": "laboratorio" if i == 0 and rng.random() < 0.5 else ""}
             for i in range(rng.randint(1, 3))]
    profs = [{"id": f"P{i}", "availability": sorted(rng.sample(hours, rng.randint(1, 4)))} for i in range(2)]
    classes = []
    for i in range(rng.randint(2, 4)):
        duration = rng.choice([1, 2])
        starts = [h for h in hours if h + duration <= 12]
        classes.append({
            "id": f"C{i}", "professor_id": rng.choice(profs)["id"], "capacity": rng.choice([2, 3, 5]),
            "duration_hours": duration, "allowed_starts": sorted(rng.sample(starts, rng.randint(1, len(starts)))),
            "required_room_type": "laboratorio" if rng.random() < 0.15 else "",
        })
    students = []
    for i in range(rng.randint(2, 6)):
        picked = rng.sample(classes, rng.randint(1, len(classes)))
        students.append({"id": f"S{i}", "requests": [{"class_id": c["id"], "priority": rng.randint(1, 3)}
                                                      for c in picked]})
    return {"parameters": {"start_hour": 8, "end_hour": 12}, "rooms": rooms, "professors": profs,
            "classes": classes, "students": students}


def solvers_for(data: dict):
    sc = load_scenario_dict(data)
    graph = build_conflict_graph(sc.classes, sc.students)
    cost = ScheduleCost(graph, sc.students)
    return sc, graph, cost


class ExactSearchTest(unittest.TestCase):
    def test_branch_and_bound_matches_brute_force(self) -> None:
        """Ramificación y poda y backtracking sin cota encuentran el mismo óptimo que la fuerza bruta."""
        rng = random.Random(2026)
        for case in range(80):
            data = random_tiny_scenario(rng)
            sc, _, cost = solvers_for(data)
            with self.subTest(case=case):
                _, brute = BruteForceScheduler(sc.classes, sc.rooms, sc.professors, sc.grid, cost).solve()
                _, exact, proven = BacktrackingScheduler(sc.classes, sc.rooms, sc.professors, sc.grid, cost).solve()
                _, plain, _ = BacktrackingScheduler(sc.classes, sc.rooms, sc.professors, sc.grid, cost,
                                                    use_bound=False).solve()
                self.assertTrue(proven)
                self.assertEqual(exact.total, brute.total)
                self.assertEqual(plain.total, brute.total)

    def test_heuristic_is_never_better_than_exact(self) -> None:
        rng = random.Random(7)
        for case in range(40):
            sc, graph, cost = solvers_for(random_tiny_scenario(rng))
            DSATURColoringSolver(graph, sc.rooms, sc.professors, sc.grid).solve()
            heuristic = read_assignment(sc.classes)
            masks = {c.id: c.time_mask for c in sc.classes if c.is_scheduled}
            h_cost = cost.breakdown(heuristic, masks).total
            _, exact, _ = BacktrackingScheduler(sc.classes, sc.rooms, sc.professors, sc.grid, cost).solve(heuristic)
            with self.subTest(case=case):
                self.assertLessEqual(exact.total, h_cost)

    def test_pruning_explores_fewer_nodes(self) -> None:
        sc, _, cost = solvers_for(_load(SCENARIOS / "F_imposible.json"))
        plain = BacktrackingScheduler(sc.classes, sc.rooms, sc.professors, sc.grid, cost, use_bound=False)
        exact = BacktrackingScheduler(sc.classes, sc.rooms, sc.professors, sc.grid, cost)
        plain.solve()
        exact.solve()
        self.assertLess(exact.stats.nodes * 10, plain.stats.nodes)

    def test_rooms_are_reassigned_when_best_fit_blocks_another_class(self) -> None:
        # X (1 h a las 8) toma PEQ, el salón que mejor le sirve. Luego L (2 h desde las 8) solo cabe en
        # PEQ, porque GRANDE solo está habilitado a las 8: hay que mover X a GRANDE.
        data = {
            "rooms": [{"id": "PEQ", "capacity": 8}, {"id": "GRANDE", "capacity": 20, "availability": [8]}],
            "professors": [{"id": "P1", "availability": [8, 9]}, {"id": "P2", "availability": [8, 9]}],
            "classes": [
                {"id": "X", "professor_id": "P1", "capacity": 5, "duration_hours": 1, "allowed_starts": [8]},
                {"id": "L", "professor_id": "P2", "capacity": 8, "duration_hours": 2, "allowed_starts": [8]},
            ],
            "students": [{"id": f"S{i}", "requests": [{"class_id": "X", "priority": 3}] +
                          ([{"class_id": "L", "priority": 1}] if i < 8 else [])} for i in range(10)],
        }
        sc, _, cost = solvers_for(data)
        solver = BacktrackingScheduler(sc.classes, sc.rooms, sc.professors, sc.grid, cost)
        self.assertEqual(solver.order[0], "X")
        best, breakdown, _ = solver.solve()
        self.assertEqual(breakdown.unscheduled_classes, 0)
        self.assertEqual(best["L"][1], "PEQ")
        self.assertEqual(best["X"][1], "GRANDE")
        self.assertGreaterEqual(solver.stats.room_reassignments, 1)

    def test_lab_rooms_are_kept_for_classes_that_need_them(self) -> None:
        data = {
            "rooms": [{"id": "LAB", "capacity": 10, "room_type": "laboratorio"}, {"id": "AULA", "capacity": 30}],
            "professors": [{"id": "P1"}],
            "classes": [{"id": "X", "professor_id": "P1", "capacity": 5, "duration_hours": 1, "allowed_starts": [8]}],
            "students": [{"id": "S", "requests": [{"class_id": "X", "priority": 1}]}],
        }
        sc, graph, cost = solvers_for(data)
        best, _, _ = BacktrackingScheduler(sc.classes, sc.rooms, sc.professors, sc.grid, cost).solve()
        self.assertEqual(best["X"][1], "AULA")
        DSATURColoringSolver(graph, sc.rooms, sc.professors, sc.grid).solve()
        self.assertEqual(sc.classes[0].assigned_room_id, "AULA")

    def test_brute_force_refuses_large_instances(self) -> None:
        sc, _, cost = solvers_for(_load(SCENARIOS / "A_factible.json"))
        with self.assertRaises(InstanceTooLargeError):
            BruteForceScheduler(sc.classes, sc.rooms, sc.professors, sc.grid, cost)


class ScenarioExpectationsTest(unittest.TestCase):
    def run_scenario(self, name: str, mode: str = "exacto"):
        orch = TimetableOrchestrator()
        orch.load_scenario_file(SCENARIOS / f"{name}.json")
        result = orch.run(phase1_mode=mode)
        self.assertEqual(result["metrics"]["violations_total"], 0)
        return orch, result

    def test_a_exact_attends_every_request(self) -> None:
        _, result = self.run_scenario("A_factible")
        self.assertEqual(result["metrics"]["coverage_percent"], 100.0)
        self.assertTrue(result["phase1_details"]["optimal"])

    def test_b_at_most_two_classes_in_the_window(self) -> None:
        orch, result = self.run_scenario("B_salones")
        exp = orch.scenario.expected
        grid = orch.grid
        window = grid.hours_to_mask(exp["window_hours"])
        scheduled = [c for c in orch.classes if c.is_scheduled]
        for hour in exp["window_hours"]:
            bit = grid.hours_to_mask([hour])
            self.assertLessEqual(sum(1 for c in scheduled if c.time_mask & bit), exp["max_classes_in_window"])
        competing = [c for c in scheduled if c.id in exp["competing_classes"]]
        self.assertLessEqual(len(competing), exp["max_competing_scheduled"])
        self.assertTrue(all(c.assigned_room_id in exp["rooms_in_window"] for c in scheduled if c.time_mask & window))

    def test_c_keeps_the_class_with_more_priority(self) -> None:
        orch, result = self.run_scenario("C_profesor")
        exp = orch.scenario.expected
        kept = [cid for cid in exp["exactly_one_scheduled_of"]
                if cid not in result["metrics"]["unscheduled_class_ids"]]
        self.assertEqual(len(kept), 1)
        if exp["best_kept_class"]:
            self.assertEqual(kept[0], exp["best_kept_class"])

    def test_f_schedules_at_most_five_of_six(self) -> None:
        orch, result = self.run_scenario("F_imposible")
        exp = orch.scenario.expected
        scheduled = [c for c in orch.classes if c.is_scheduled and c.id in exp["overloaded_classes"]]
        self.assertEqual(len(scheduled), exp["max_scheduled_of_overloaded"])
        self.assertEqual(result["metrics"]["scheduled_classes"], exp["best_scheduled_classes"])

    def test_auto_mode_uses_exact_search_for_small_instances(self) -> None:
        _, result = self.run_scenario("inicial", mode="auto")
        self.assertEqual(result["phase1_details"]["mode"], "exacto")


def _load(path: Path) -> dict:
    import json
    with open(path, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    unittest.main()
