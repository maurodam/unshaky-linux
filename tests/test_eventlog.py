import unittest
from unshaky_linux.eventlog import EventLog


class EventLogTests(unittest.TestCase):
    def test_history_is_bounded_and_keeps_latest_events(self):
        log = EventLog(limit=2)
        for code in (30, 31, 32):
            log.append('KEY_TEST', code, 'Keyboard', 12.345, 40)
        revision, rows = log.snapshot()
        self.assertEqual(revision, 3)
        self.assertEqual([row[2] for row in rows], ['31', '32'])
        self.assertEqual(rows[-1][4:], ('12.35', '40'))
        self.assertRegex(rows[-1][0], r'^\d{4}-\d{2}-\d{2}T.*[+-]\d{2}:\d{2}$')

    def test_clear_invalidates_view_and_preserves_old_snapshot(self):
        log = EventLog()
        log.append('KEY_A', 30, 'Keyboard', 10, 40)
        revision, rows = log.snapshot()
        log.clear()
        new_revision, empty = log.snapshot()
        self.assertGreater(new_revision, revision)
        self.assertEqual(empty, ())
        self.assertEqual(len(rows), 1)
