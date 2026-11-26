import unittest

from src.models.time_mask import TimeGrid, mask_to_slots, masks_overlap, slots_to_mask


class TimeGridTest(unittest.TestCase):
    def setUp(self) -> None:
        self.grid = TimeGrid()  # un día, 8:00 a 18:00

    def test_default_day_has_ten_slots(self) -> None:
        self.assertEqual(self.grid.total_slots, 10)
        self.assertEqual(self.grid.full_mask, (1 << 10) - 1)

    def test_two_hour_class_cannot_start_at_17(self) -> None:
        self.assertTrue(self.grid.is_valid_start(self.grid.day_hour_to_slot(0, 16), 2))
        self.assertFalse(self.grid.is_valid_start(self.grid.day_hour_to_slot(0, 17), 2))
        self.assertEqual(len(self.grid.candidate_starts(1)), 10)
        self.assertEqual(len(self.grid.candidate_starts(2)), 9)

    def test_back_to_back_classes_do_not_overlap(self) -> None:
        # Una clase que termina a las 10:00 y otra que inicia a las 10:00 no se superponen.
        a = self.grid.create_slot_mask(self.grid.day_hour_to_slot(0, 8), 2)
        b = self.grid.create_slot_mask(self.grid.day_hour_to_slot(0, 10), 1)
        c = self.grid.create_slot_mask(self.grid.day_hour_to_slot(0, 9), 1)
        self.assertFalse(masks_overlap(a, b))
        self.assertTrue(masks_overlap(a, c))

    def test_hours_spec_round_trip(self) -> None:
        mask = self.grid.hours_to_mask([8, 9, 14])
        self.assertEqual(self.grid.mask_to_hours(mask), [8, 9, 14])
        self.assertEqual(self.grid.hours_to_mask(None), self.grid.full_mask)

    def test_several_days(self) -> None:
        grid = TimeGrid(num_days=2)
        self.assertEqual(grid.total_slots, 20)
        # Una lista de horas aplica a todos los días
        self.assertEqual(mask_to_slots(grid.hours_to_mask([8])), [0, 10])
        self.assertEqual(grid.hours_to_slots({"Martes": [9]}), [11])
        # Una clase de dos horas no cruza de un día al siguiente
        self.assertFalse(grid.is_valid_start(9, 2))
        self.assertEqual(grid.format_slot(11, 2), "Martes 09:00-11:00")

    def test_format_mask_groups_contiguous_blocks(self) -> None:
        mask = slots_to_mask([0, 1, 5])
        self.assertEqual(self.grid.format_mask(mask), "08:00-10:00, 13:00-14:00")


if __name__ == "__main__":
    unittest.main()
