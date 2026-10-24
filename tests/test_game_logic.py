import unittest
from decimal import Decimal
from fractions import Fraction
from itertools import combinations

import game_logic as g
from game_logic import GameError, Mode

H = g.HOUSE_FACTOR


class FakeRng:
    """Подставной генератор: возвращает заранее заданные числа."""
    def __init__(self, values):
        self.values = list(values)

    def randrange(self, n):
        return self.values.pop(0)


class TestMultipliers(unittest.TestCase):
    def test_mode1_table(self):
        table = {
            1: [Fraction(6, 5), Fraction(3, 2), 2, 3, 6],
            2: [Fraction(3, 2), Fraction(5, 2), 5, 15],
            3: [2, 5, 20],
            4: [3, 15],
            5: [6],
        }
        for bullets, values in table.items():
            for step, v in enumerate(values, start=1):
                self.assertEqual(g.multiplier(Mode.NO_SPIN, bullets, step),
                                 Fraction(v) * H, (bullets, step))

    def test_mode2_linear(self):
        cases = {(1, 1): Fraction(6, 5), (1, 2): Fraction(7, 5),
                 (2, 1): Fraction(3, 2), (2, 3): Fraction(5, 2),
                 (3, 2): 3, (4, 2): 5, (5, 2): 11}
        for (bullets, step), v in cases.items():
            self.assertEqual(g.multiplier(Mode.SPIN, bullets, step),
                             Fraction(v) * H, (bullets, step))

    def test_step_zero_is_bet_back(self):
        self.assertEqual(g.multiplier(Mode.NO_SPIN, 3, 0), 1)
        self.assertEqual(g.multiplier(Mode.SPIN, 3, 0), 1)

    def test_expected_value(self):
        """Режим 1: на любом шаге ожидаемый возврат ровно 97%.
        Режим 2: ровно 97% на первом шаге, дальше строго меньше."""
        for bullets in range(1, 6):
            for step in range(1, 6 - bullets + 1):
                ev = g.survival_probability(Mode.NO_SPIN, bullets, step) * \
                    g.multiplier(Mode.NO_SPIN, bullets, step)
                self.assertEqual(ev, H, (bullets, step))
            ev1 = g.survival_probability(Mode.SPIN, bullets, 1) * \
                g.multiplier(Mode.SPIN, bullets, 1)
            self.assertEqual(ev1, H, bullets)
            for step in range(2, 15):
                ev = g.survival_probability(Mode.SPIN, bullets, step) * \
                    g.multiplier(Mode.SPIN, bullets, step)
                self.assertLess(ev, H, (bullets, step))

    def test_mode2_continuing_is_unfavorable(self):
        for bullets in range(1, 6):
            p = g.survival_probability(Mode.SPIN, bullets, 1)
            for step in range(1, 15):
                keep = p * g.multiplier(Mode.SPIN, bullets, step + 1)
                self.assertLess(keep, g.multiplier(Mode.SPIN, bullets, step))

    def test_survival_matches_all_layouts(self):
        """Перебираем все расстановки патронов и сверяем с формулой."""
        for bullets in range(1, 6):
            layouts = list(combinations(range(6), bullets))
            for step in range(0, 6 - bullets + 1):
                alive = sum(1 for lay in layouts
                            if all(slot not in lay for slot in range(step)))
                self.assertEqual(Fraction(alive, len(layouts)),
                                 g.survival_probability(Mode.NO_SPIN, bullets, step))


class TestPayout(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(g.payout(Decimal("10.00"), Mode.NO_SPIN, 1, 1), Decimal("11.64"))
        self.assertEqual(g.payout(Decimal("100.00"), Mode.NO_SPIN, 5, 1), Decimal("582.00"))

    def test_rounds_down(self):
        # 1.01 * 1.164 = 1.17564 -> 1.17
        self.assertEqual(g.payout(Decimal("1.01"), Mode.NO_SPIN, 1, 1), Decimal("1.17"))

    def test_cash_out_needs_a_step(self):
        with self.assertRaises(GameError):
            g.cash_out(Decimal("10.00"), Mode.SPIN, 1, 0)


class TestSteps(unittest.TestCase):
    def test_place_bullets(self):
        for bullets in range(1, 6):
            pos = g.place_bullets(bullets)
            self.assertEqual(len(pos), bullets)
            self.assertEqual(len(set(pos)), bullets)
            self.assertTrue(all(0 <= p < 6 for p in pos))

    def test_mode1_sequence(self):
        r = g.make_step(Mode.NO_SPIN, 1, 0, [2])
        self.assertEqual((r.fired, r.step, r.status), (False, 1, "active"))
        r = g.make_step(Mode.NO_SPIN, 1, 1, [2])
        self.assertEqual((r.fired, r.step, r.status), (False, 2, "active"))
        r = g.make_step(Mode.NO_SPIN, 1, 2, [2])
        self.assertEqual((r.fired, r.status), (True, "lost"))

    def test_mode1_auto_win_at_end(self):
        r = g.make_step(Mode.NO_SPIN, 5, 0, [1, 2, 3, 4, 5])
        self.assertEqual((r.fired, r.step, r.status), (False, 1, "won"))
        r = g.make_step(Mode.NO_SPIN, 1, 4, [5])
        self.assertEqual((r.fired, r.step, r.status), (False, 5, "won"))

    def test_mode1_cannot_step_after_end(self):
        with self.assertRaises(GameError):
            g.make_step(Mode.NO_SPIN, 5, 1, [1, 2, 3, 4, 5])

    def test_mode1_needs_positions(self):
        with self.assertRaises(GameError):
            g.make_step(Mode.NO_SPIN, 2, 0)

    def test_mode2_with_fake_rng(self):
        r = g.make_step(Mode.SPIN, 1, 0, rng=FakeRng([0]))   # 0 < 1: выстрел
        self.assertEqual((r.fired, r.status), (True, "lost"))
        r = g.make_step(Mode.SPIN, 1, 0, rng=FakeRng([1]))   # 1 >= 1: выжил
        self.assertEqual((r.fired, r.step, r.status), (False, 1, "active"))

    def test_mode2_never_auto_wins(self):
        step = 0
        for _ in range(50):
            r = g.make_step(Mode.SPIN, 1, step, rng=FakeRng([5]))
            self.assertEqual(r.status, "active")
            step = r.step


class TestValidation(unittest.TestCase):
    def test_bet(self):
        bal = Decimal("100.00")
        self.assertEqual(g.validate_bet(Decimal("1.00"), bal), Decimal("1.00"))
        self.assertEqual(g.validate_bet(Decimal("100.00"), bal), Decimal("100.00"))
        for bad in (Decimal("0.99"), Decimal("100.01"), Decimal("5.555"),
                    Decimal("-3"), Decimal("NaN"), 5, 5.0):
            with self.assertRaises(GameError, msg=str(bad)):
                g.validate_bet(bad, bal)

    def test_bullets_and_mode(self):
        for bad in (0, 6, -1, 2.5, True, "3"):
            with self.assertRaises(GameError, msg=str(bad)):
                g.validate_bullets(bad)
        with self.assertRaises(GameError):
            g.validate_mode(3)


if __name__ == "__main__":
    unittest.main()
