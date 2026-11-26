"""Cada regla R1-R10 se prueba con una solución hecha a mano que la incumple a propósito."""

import copy
import unittest

from src.data.scenario import load_scenario_dict
from src.verify.verifier import verify_solution

SCENARIO = {
    "rooms": [
        {"id": "R1", "capacity": 2},
        {"id": "R2", "capacity": 10, "availability": [8, 9, 10, 11]},
        {"id": "LAB", "capacity": 10, "room_type": "laboratorio"},
    ],
    "professors": [
        {"id": "P1", "availability": [8, 9, 10, 11, 12]},
        {"id": "P2"},
    ],
    "classes": [
        {"id": "A", "professor_id": "P1", "capacity": 3, "duration_hours": 2, "allowed_starts": [8, 10]},
        {"id": "B", "professor_id": "P1", "capacity": 5, "duration_hours": 1, "allowed_starts": [10, 11, 12]},
        {"id": "C", "professor_id": "P2", "capacity": 5, "duration_hours": 1},
        {"id": "L", "professor_id": "P2", "capacity": 5, "duration_hours": 1, "required_room_type": "laboratorio"},
    ],
    "students": [
        {"id": "S1", "requests": [{"class_id": "A", "priority": 3}, {"class_id": "C", "priority": 1}]},
        {"id": "S2", "requests": [{"class_id": "A", "priority": 2}, {"class_id": "B", "priority": 2}]},
        {"id": "S3", "requests": [{"class_id": "C", "priority": 3}], "availability": [13, 14]},
    ],
}

VALID = {
    "classes": [
        {"class_id": "A", "day": "Lunes", "start_hour": 8, "end_hour": 10, "room_id": "R2", "students": ["S1", "S2"]},
        {"class_id": "B", "day": "Lunes", "start_hour": 10, "end_hour": 11, "room_id": "R2", "students": ["S2"]},
        {"class_id": "C", "day": "Lunes", "start_hour": 13, "end_hour": 14, "room_id": "R1", "students": ["S1", "S3"]},
    ],
    "unscheduled_classes": ["L"],
}


class VerifierTest(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = load_scenario_dict(SCENARIO)

    def check(self, mutate) -> dict[str, int]:
        solution = copy.deepcopy(VALID)
        mutate(solution)
        return verify_solution(self.scenario, solution).count_by_rule()

    def entry(self, solution, class_id):
        return next(e for e in solution["classes"] if e["class_id"] == class_id)

    def test_valid_solution_has_no_violations(self) -> None:
        result = verify_solution(self.scenario, VALID)
        self.assertTrue(result.is_valid, result.to_dict())

    def test_r1_room_shared_at_same_time(self) -> None:
        def m(s):
            self.entry(s, "C").update(start_hour=9, end_hour=10, room_id="R2", students=["S1"])
        counts = self.check(m)
        self.assertEqual(counts["R1"], 1)

    def test_r2_professor_twice_or_unavailable(self) -> None:
        def same_time(s):
            self.entry(s, "B").update(start_hour=9, end_hour=10, room_id="R1")
        self.assertGreaterEqual(self.check(same_time)["R2"], 1)

        def unavailable(s):
            self.entry(s, "B").update(start_hour=13, end_hour=14, room_id="R1", students=[])
        self.assertEqual(self.check(unavailable)["R2"], 1)

    def test_r3_student_cross_and_availability(self) -> None:
        def cross(s):
            self.entry(s, "C").update(start_hour=9, end_hour=10, room_id="R1", students=["S1"])
        self.assertEqual(self.check(cross)["R3"], 1)

        def outside(s):
            self.entry(s, "C").update(start_hour=15, end_hour=16)
        self.assertEqual(self.check(outside)["R3"], 1)

    def test_r4_room_capacity(self) -> None:
        def m(s):
            self.entry(s, "B").update(room_id="R1", students=["S2", "S1", "S3"])
        self.assertEqual(self.check(m)["R4"], 1)

    def test_r5_class_capacity(self) -> None:
        def m(s):
            self.entry(s, "A")["students"] = ["S1", "S2", "S3", "S4"]
        self.assertEqual(self.check(m)["R5"], 1)

    def test_r6_duration(self) -> None:
        def m(s):
            self.entry(s, "A").update(end_hour=9)
        self.assertEqual(self.check(m)["R6"], 1)

    def test_r7_outside_the_day(self) -> None:
        def m(s):
            self.entry(s, "C").update(start_hour=18, end_hour=19)
        self.assertEqual(self.check(m)["R7"], 1)

    def test_r8_start_not_allowed_or_room_unavailable(self) -> None:
        def start(s):
            self.entry(s, "A").update(start_hour=9, end_hour=11, students=[])
        self.assertEqual(self.check(start)["R8"], 1)

        def room(s):
            self.entry(s, "C").update(room_id="R2")
        self.assertEqual(self.check(room)["R8"], 1)

    def test_r9_student_did_not_request_class(self) -> None:
        def m(s):
            self.entry(s, "B")["students"] = ["S2", "S1"]
        self.assertEqual(self.check(m)["R9"], 1)

    def test_r10_integrity(self) -> None:
        def missing(s):
            s["unscheduled_classes"] = []
        self.assertEqual(self.check(missing)["R10"], 1)

        def wrong_room_type(s):
            s["unscheduled_classes"] = []
            s["classes"].append({"class_id": "L", "day": "Lunes", "start_hour": 15, "end_hour": 16,
                                 "room_id": "R1", "students": []})
        self.assertEqual(self.check(wrong_room_type)["R10"], 1)

        def unknown_room(s):
            self.entry(s, "B")["room_id"] = "X"
        self.assertEqual(self.check(unknown_room)["R10"], 1)

        def duplicated(s):
            s["classes"].append(copy.deepcopy(self.entry(s, "B")))
        self.assertEqual(self.check(duplicated)["R10"], 1)


if __name__ == "__main__":
    unittest.main()
