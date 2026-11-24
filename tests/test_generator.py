import unittest

from src.data.generator import (
    SCENARIO_BUILDERS,
    build_base_scenario,
    build_scale_scenario,
)
from src.data.scenario import load_scenario_dict
from src.models.time_mask import masks_overlap


class GeneratorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.base = build_base_scenario(seed=7)

    def test_same_seed_same_scenario(self) -> None:
        self.assertEqual(build_base_scenario(seed=7), self.base)
        self.assertNotEqual(build_base_scenario(seed=8), self.base)

    def test_base_has_design_size(self) -> None:
        self.assertEqual(len(self.base["students"]), 20)
        self.assertEqual(len(self.base["professors"]), 5)
        self.assertEqual(len(self.base["classes"]), 8)
        self.assertEqual(len(self.base["rooms"]), 10)

    def test_reference_solution_is_valid(self) -> None:
        """La solución de referencia del conjunto base cumple las restricciones obligatorias."""
        sc = load_scenario_dict(self.base)
        grid = sc.grid
        ref = self.base["expected"]["reference_solution"]
        classes = {c.id: c for c in sc.classes}
        rooms = {r.id: r for r in sc.rooms}
        profs = {p.id: p for p in sc.professors}

        masks = {}
        for cid, placement in ref["classes"].items():
            c = classes[cid]
            slot = grid.day_hour_to_slot(0, placement["start_hour"])
            mask = grid.create_slot_mask(slot, c.duration_hours)
            masks[cid] = mask
            self.assertIn(slot, c.allowed_starts)                                   # R8 clase
            self.assertEqual(profs[c.professor_id].availability_mask & mask, mask)  # R2/R8 profesor
            self.assertEqual(rooms[placement["room_id"]].availability_mask & mask, mask)
            self.assertGreaterEqual(rooms[placement["room_id"]].capacity, c.min_room_capacity)

        ids = sorted(masks)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if masks_overlap(masks[a], masks[b]):
                    self.assertNotEqual(ref["classes"][a]["room_id"], ref["classes"][b]["room_id"])  # R1
                    self.assertNotEqual(classes[a].professor_id, classes[b].professor_id)            # R2

        for student in sc.students:
            taken = ref["enrollments"][student.id]
            self.assertEqual(taken, [r.class_id for r in student.requests])
            for i, a in enumerate(taken):
                for b in taken[i + 1:]:
                    self.assertFalse(masks_overlap(masks[a], masks[b]))  # R3
        for cid, c in classes.items():
            self.assertLessEqual(c.demand, c.capacity)  # R5

    def test_derived_scenarios_load_and_describe_expectations(self) -> None:
        for builder in SCENARIO_BUILDERS:
            with self.subTest(builder=builder.__name__):
                data = builder(self.base, seed=7)
                load_scenario_dict(data)
                self.assertIn("description", data["expected"])
                self.assertEqual(data["expected"]["violations"], 0)

    def test_scenario_c_professor_has_one_hour(self) -> None:
        data = SCENARIO_BUILDERS[1](self.base, seed=7)
        sc = load_scenario_dict(data)
        c1, c2 = data["expected"]["exactly_one_scheduled_of"]
        prof_id = next(c.professor_id for c in sc.classes if c.id == c1)
        prof = next(p for p in sc.professors if p.id == prof_id)
        self.assertEqual(bin(prof.availability_mask).count("1"), 1)

    def test_scale_scenarios_keep_proportions(self) -> None:
        data = build_scale_scenario(100, seed=1)
        self.assertEqual(len(data["students"]), 100)
        self.assertEqual(len(data["classes"]), 40)
        self.assertEqual(len(data["rooms"]), 50)
        load_scenario_dict(data)


if __name__ == "__main__":
    unittest.main()
