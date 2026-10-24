import unittest
from unittest.mock import MagicMock, patch

try:
    from unshaky_linux import backend
except ImportError:
    backend = None


@unittest.skipIf(backend is None, 'python3-evdev is not installed')
class BackendTests(unittest.TestCase):
    def setUp(self):
        self.worker = backend.Worker({'enabled': True, 'delay_ms': 40, 'keys': {}, 'device_name': ''})
        self.device = MagicMock(spec=backend.InputDevice)
        self.device.fd = 99
        self.device.name = 'Physical Keyboard'
        self.device.path = '/dev/input/event99'
        self.device.capabilities.return_value = {backend.E.EV_KEY: [backend.E.KEY_A, backend.E.KEY_Z, backend.E.KEY_SPACE]}
        self.device.active_keys.return_value = []
        self.device.read.side_effect = BlockingIOError()
        self.selector = self.worker.selector
        self.worker.selector = MagicMock()
        self.ui = MagicMock()
        ioctl = patch.object(backend.fcntl, 'ioctl')
        self.ioctl = ioctl.start()
        self.addCleanup(ioctl.stop)

    def tearDown(self):
        for path in list(self.worker.devices):
            self.worker.close_device(path)
        self.selector.close()

    def scan(self):
        with patch.object(backend, 'glob', return_value=[self.device.path]), \
             patch.object(backend, 'InputDevice', return_value=self.device), \
             patch.object(backend.UInput, 'from_device', return_value=self.ui):
            self.worker.scan()

    def test_log_records_only_rejected_press_not_release_or_repeat(self):
        self.scan()
        debounce = self.worker.devices[self.device.path][2]
        for value, usec in ((1, 0), (0, 100000), (1, 115000), (2, 120000), (0, 125000)):
            from evdev import InputEvent
            event = InputEvent(1, usec, backend.E.EV_KEY, 30, value)
            self.worker.accept_key(self.device, debounce, event)
        _, rows = self.worker.log.snapshot()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1:], ('KEY_A', '30', 'Physical Keyboard', '15.00', '40'))
        self.worker.log.clear()
        self.assertEqual(self.worker.count(), 1)

    def test_disabled_filter_logs_nothing(self):
        from evdev import InputEvent
        self.scan()
        self.worker.config['enabled'] = False
        debounce = self.worker.devices[self.device.path][2]
        for value, usec in ((1, 0), (0, 100000), (1, 110000), (0, 120000)):
            event = InputEvent(1, usec, backend.E.EV_KEY, 30, value)
            self.assertTrue(self.worker.accept_key(self.device, debounce, event))
        self.assertEqual(self.worker.log.snapshot()[1], ())

    def test_permission_error_is_visible_instead_of_hidden(self):
        with patch.object(backend, 'glob', return_value=[self.device.path]), \
             patch.object(backend, 'InputDevice', side_effect=PermissionError('Permission denied')):
            self.worker.scan()
        self.assertIn('FILTER NOT OPERATIONAL', self.worker.status)
        self.assertIn('Permission denied', self.worker.status)

    def test_pregrab_input_is_drained_before_virtual_keyboard_creation(self):
        self.device.read.side_effect = [[object()], BlockingIOError()]
        with patch.object(backend, 'glob', return_value=[self.device.path]), \
             patch.object(backend, 'InputDevice', return_value=self.device), \
             patch.object(backend.UInput, 'from_device', return_value=self.ui) as create:
            self.worker.scan()
        self.assertEqual(self.device.read.call_count, 2)
        self.device.grab.assert_called_once()
        create.assert_called_once()
        self.ui.write_event.assert_not_called()

    def test_worker_forwards_only_accepted_cycles_and_releases_grab(self):
        from evdev import InputEvent
        from types import SimpleNamespace
        self.scan()
        self.device.read.side_effect = [[
            InputEvent(1, usec, backend.E.EV_KEY, 30, value)
            for value, usec in ((1, 0), (0, 20000), (1, 38000),
                               (0, 58000), (1, 200000), (0, 250000))]]
        def selected(_timeout):
            self.worker.stop_event.set()
            return [(SimpleNamespace(fileobj=self.device), None)]
        self.worker.selector.select.side_effect = selected
        with patch.object(self.worker, 'scan'):
            self.worker.run()
        forwarded = [call.args[0].value for call in self.ui.write_event.call_args_list]
        self.assertEqual(forwarded, [1, 0, 1, 0])
        self.assertEqual(self.worker.count(), 1)
        self.assertEqual(len(self.worker.log.snapshot()[1]), 1)
        self.assertFalse(self.worker.devices)
        self.device.close.assert_called_once()

    def test_clock_configuration_uses_linux_ioctl_not_missing_evdev_method(self):
        import struct
        backend.set_monotonic_clock(self.device)
        self.ioctl.assert_called_once_with(99, 0x400445A0,
                                           struct.pack('i', backend.time.CLOCK_MONOTONIC))

    def test_held_keyboard_is_not_grabbed(self):
        self.device.active_keys.return_value = [30]
        self.scan()
        self.device.grab.assert_not_called()
        self.device.close.assert_called_once()

    def test_virtual_device_is_never_recaptured(self):
        self.device.name = backend.PREFIX + 'Keyboard'
        self.scan()
        self.device.grab.assert_not_called()

    def test_cleanup_releases_virtual_held_keys(self):
        self.scan()
        debounce = self.worker.devices[self.device.path][2]
        debounce.accept(30, 1, 1, 40)
        self.worker.close_device(self.device.path)
        self.ui.write.assert_called_once_with(backend.E.EV_KEY, 30, 0)
        self.ui.syn.assert_called_once()
        self.ui.close.assert_called_once()
        self.device.close.assert_called_once()

    def test_grab_failure_closes_original_without_creating_virtual_device(self):
        self.device.grab.side_effect = OSError('busy')
        self.scan()
        self.assertFalse(self.worker.devices)
        self.ui.close.assert_not_called()
        self.device.close.assert_called_once()

    def test_selected_name_is_exact(self):
        self.worker.config['device_name'] = 'Different Keyboard'
        self.scan()
        self.device.grab.assert_not_called()

    def test_uinput_failure_releases_original_by_closing_fd(self):
        with patch.object(backend, 'glob', return_value=[self.device.path]), \
             patch.object(backend, 'InputDevice', return_value=self.device), \
             patch.object(backend.UInput, 'from_device', side_effect=PermissionError('denied')):
            self.worker.scan()
        self.device.grab.assert_called_once()
        self.device.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
