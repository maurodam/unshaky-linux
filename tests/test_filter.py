import unittest
from unshaky_linux.filter import Debouncer


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.f = Debouncer()

    def key(self, code, value, ms, delay=40):
        return self.f.accept(code, value, ms / 1000, delay)

    def test_bounce_cycle_is_removed(self):
        self.assertTrue(self.key(30, 1, 0))
        self.assertTrue(self.key(30, 0, 100))
        self.assertFalse(self.key(30, 1, 115))
        self.assertFalse(self.key(30, 2, 120))
        self.assertFalse(self.key(30, 0, 125))
        self.assertEqual(self.f.dismissed, 1)
        self.assertFalse(self.f.down)

    def test_intentional_double_press(self):
        for value, ms in [(1, 0), (0, 100), (1, 150), (0, 200)]:
            self.assertTrue(self.key(30, value, ms))

    def test_distinct_keys_are_independent(self):
        self.key(30, 1, 0)
        self.key(30, 0, 100)
        self.assertTrue(self.key(48, 1, 101))

    def test_hold_repeat_survives(self):
        self.key(30, 1, 0)
        self.assertTrue(self.key(30, 2, 500))
        self.assertTrue(self.key(30, 2, 600))
        self.assertTrue(self.key(30, 0, 700))

    def test_disabled_threshold(self):
        for value, ms in [(1, 0), (0, 10), (1, 11), (0, 12)]:
            self.assertTrue(self.key(30, value, ms, 0))

    def test_disable_during_rejected_cycle_preserves_pair(self):
        self.key(30, 1, 0)
        self.key(30, 0, 10)
        self.assertFalse(self.key(30, 1, 20))
        self.assertFalse(self.key(30, 0, 21, 0))
        self.assertTrue(self.key(30, 1, 22, 0))

    def test_bounce_does_not_extend_window(self):
        self.key(30, 1, 0)
        self.key(30, 0, 100)
        self.key(30, 1, 110)
        self.key(30, 0, 120)
        self.assertTrue(self.key(30, 1, 150))

    def test_duplicate_down_cannot_release_accepted_cycle(self):
        self.key(30, 1, 0)
        self.assertFalse(self.key(30, 1, 1))
        self.assertTrue(self.key(30, 0, 2))

    def test_orphan_release_and_repeat_are_ignored(self):
        self.assertFalse(self.key(30, 0, 0))
        self.assertFalse(self.key(30, 2, 1))

    def test_timestamps_use_release_not_down(self):
        self.key(30, 1, 0)
        self.key(30, 0, 1000)
        self.assertFalse(self.key(30, 1, 1020))

    def test_new_device_has_independent_state(self):
        self.key(30, 1, 0)
        self.key(30, 0, 100)
        self.assertTrue(Debouncer().accept(30, 1, .101, 40))

    def test_original_diagram_sequence_for_all_standard_key_codes(self):
        # Normal down, unintended up, unintended down, normal up (blocked),
        # followed by an intentional second press outside the threshold.
        for code in range(1, 256):
            with self.subTest(code=code):
                f = Debouncer()
                sequence = [(1, 1.000), (0, 1.020), (1, 1.038),
                            (0, 1.058), (1, 1.200), (0, 1.250)]
                actual = [f.accept(code, value, timestamp, 40)
                          for value, timestamp in sequence]
                self.assertEqual(actual, [True, True, False, False, True, True])
                self.assertFalse(f.down)
                self.assertFalse(f.blocked)

    def test_aggressive_mode_extends_window_from_rejected_release(self):
        f = Debouncer()
        sequence = [(1, 0), (0, 100), (1, 120), (0, 130),
                    (1, 150), (0, 160), (1, 210), (0, 220)]
        actual = [f.accept(30, value, ms / 1000, 40, aggressive=True)
                  for value, ms in sequence]
        self.assertEqual(actual, [True, True, False, False, False, False, True, True])
        self.assertEqual(f.dismissed, 2)

    def test_exact_threshold_is_accepted_at_large_monotonic_timestamp(self):
        self.f.accept(30, 1, 1234567.0, 40)
        self.f.accept(30, 0, 1234567.1, 40)
        self.assertTrue(self.f.accept(30, 1, 1234567.14, 40))

    def test_sub_five_millisecond_physical_bounce_is_blocked(self):
        self.key(30, 1, 0)
        self.key(30, 0, 100)
        self.assertFalse(self.key(30, 1, 102))
        self.assertFalse(self.key(30, 0, 104))


if __name__ == '__main__':
    unittest.main()
