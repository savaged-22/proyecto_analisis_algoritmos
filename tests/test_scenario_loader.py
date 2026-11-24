import copy
import unittest

from src.data.scenario import ScenarioError, load_scenario_dict

MINIMAL = {
    "rooms": [{"id": "R1", "capacity": 20}],
    "professors": [{"id": "P1", "availability": [8, 9, 10]}],
    "classes": [
        {"id": "C1", "professor_id": "P1", "capacity": 10, "duration_hours": 2, "allowed_starts": [8, 9]},
        {"id": "C2", "professor_id": "P1", "capacity": 5, "duration_hours": 1},
    ],
    "students": [
        {"id": "S1", "requests": [{"class_id": "C1", "priority": 3}, {"class_id": "C2", "priority": 1}]},
        {"id": "S2", "requests": [{"class_id": "C1", "priority": 2}]},
    ],
}


class ScenarioLoaderTest(unittest.TestCase):
    def load(self, mutate=None):
        data = copy.deepcopy(MINIMAL)
        if mutate:
            mutate(data)
        return load_scenario_dict(data)

    def test_loads_minimal_scenario(self) -> None:
        sc = self.load()
        c1, c2 = sc.classes
        self.assertEqual(sc.grid.total_slots, 10)
        self.assertEqual(c1.allowed_starts, [0, 1])
        self.assertEqual(len(c2.allowed_starts), 10)  # sin restricción: toda la jornada
        self.assertEqual(sc.professors[0].availability_mask, 0b111)
        self.assertEqual(sc.rooms[0].availability_mask, sc.grid.full_mask)
        self.assertEqual(sc.total_requests, 3)

    def test_demand_is_derived_from_requests(self) -> None:
        sc = self.load()
        self.assertEqual([c.demand for c in sc.classes], [2, 1])
        # El salón solo necesita capacidad para min(cupo, demanda)
        self.assertEqual(sc.classes[0].min_room_capacity, 2)

    def test_rejects_priority_outside_scale(self) -> None:
        def bad(d):
            d["students"][0]["requests"][0]["priority"] = 5
        with self.assertRaises(ScenarioError):
            self.load(bad)

    def test_rejects_unknown_class(self) -> None:
        def bad(d):
            d["students"][0]["requests"].append({"class_id": "NOPE", "priority": 1})
        with self.assertRaises(ScenarioError):
            self.load(bad)

    def test_rejects_duplicated_request(self) -> None:
        def bad(d):
            d["students"][1]["requests"].append({"class_id": "C1", "priority": 1})
        with self.assertRaises(ScenarioError):
            self.load(bad)

    def test_rejects_start_that_ends_after_the_day(self) -> None:
        def bad(d):
            d["classes"][0]["allowed_starts"] = [17]
        with self.assertRaises(ScenarioError):
            self.load(bad)

    def test_rejects_unknown_professor_and_bad_duration(self) -> None:
        def bad_prof(d):
            d["classes"][0]["professor_id"] = "P9"

        def bad_duration(d):
            d["classes"][0]["duration_hours"] = 3
        for mutate in (bad_prof, bad_duration):
            with self.assertRaises(ScenarioError):
                self.load(mutate)


if __name__ == "__main__":
    unittest.main()
