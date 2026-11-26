import itertools
import random
import unittest

from src.phase2.interval_dp import Interval, last_compatible, weighted_interval_scheduling


def brute_force_best(intervals: list[Interval]) -> int:
    """Fuerza bruta: prueba los 2^n subconjuntos y se queda con el mejor sin cruces."""
    best = 0
    for size in range(len(intervals) + 1):
        for subset in itertools.combinations(intervals, size):
            ordered = sorted(subset, key=lambda it: it.start)
            if all(a.end <= b.start for a, b in zip(ordered, ordered[1:])):
                best = max(best, sum(it.weight for it in subset))
    return best


class LastCompatibleTest(unittest.TestCase):
    def test_binary_search(self) -> None:
        ends = [2, 3, 3, 5, 8]
        self.assertEqual(last_compatible(ends, 0, 5), 0)
        self.assertEqual(last_compatible(ends, 3, 5), 3)
        self.assertEqual(last_compatible(ends, 9, 5), 5)
        self.assertEqual(last_compatible(ends, 9, 2), 2)  # solo mira ends[0:hi]


class WeightedIntervalSchedulingTest(unittest.TestCase):
    def test_empty(self) -> None:
        result = weighted_interval_scheduling([])
        self.assertEqual(result.best_weight, 0)
        self.assertEqual(result.chosen, [])

    def test_prefers_higher_priority_when_classes_cross(self) -> None:
        a = Interval("A", 0, 2, 67)   # 8:00-10:00, prioridad 3
        b = Interval("B", 1, 2, 23)   # 9:00-10:00, prioridad 1
        c = Interval("C", 2, 3, 45)   # 10:00-11:00, prioridad 2 (no cruza con A)
        result = weighted_interval_scheduling([b, c, a])
        self.assertEqual(result.chosen_keys, ["A", "C"])
        self.assertEqual(result.best_weight, 112)

    def test_two_small_beat_one_big(self) -> None:
        big = Interval("BIG", 0, 4, 10)
        small1 = Interval("S1", 0, 2, 6)
        small2 = Interval("S2", 2, 4, 6)
        self.assertEqual(weighted_interval_scheduling([big, small1, small2]).chosen_keys, ["S1", "S2"])

    def test_table_matches_recurrence(self) -> None:
        items = [Interval("A", 0, 2, 5), Interval("B", 1, 3, 4), Interval("C", 2, 4, 3)]
        r = weighted_interval_scheduling(items)
        self.assertEqual(r.p, [0, 0, 0, 1])          # C empieza cuando A termina
        self.assertEqual(r.opt, [0, 5, 5, 8])        # OPT[3] = max(5, 3 + OPT[1])

    def test_matches_brute_force_on_random_instances(self) -> None:
        rng = random.Random(123)
        for _ in range(300):
            n = rng.randint(0, 8)
            intervals = []
            for i in range(n):
                start = rng.randint(0, 9)
                end = min(10, start + rng.randint(1, 2))
                intervals.append(Interval(f"C{i}", start, end, rng.randint(1, 50)))
            result = weighted_interval_scheduling(intervals)
            self.assertEqual(result.best_weight, brute_force_best(intervals))
            chosen = sorted(result.chosen, key=lambda it: it.start)
            self.assertTrue(all(a.end <= b.start for a, b in zip(chosen, chosen[1:])))
            self.assertEqual(sum(it.weight for it in chosen), result.best_weight)


if __name__ == "__main__":
    unittest.main()
