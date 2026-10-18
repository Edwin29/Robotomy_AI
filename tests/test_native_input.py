import unittest
from unittest.mock import Mock
from robotomy.native_input import run_gesture, InputStopped
import test_live_control


class NativeValidationTests(unittest.TestCase):
    setUp = test_live_control.LiveControlTests.setUp
    publish = test_live_control.LiveControlTests.publish
    def test_native_coordinates_duration_and_drag_bounds(self):
        self.view['backend'] = 'native_win32'
        self.publish()
        self.control.prepare('view1', 'move', 'observed target', 'hover', 0, 0)
        self.control.prepare('view1', 'key', 'movement lesson', 'advance', key='d', duration_ms=2000)
        for value in (0, 3001, True, 1.5):
            with self.assertRaises(ValueError):
                self.control.prepare('view1', 'key', 'why', 'expected', key='d', duration_ms=value)
        for x, y in ((734, 100), (1, float('nan')), (-1, 10)):
            with self.assertRaises(ValueError):
                self.control.prepare('view1', 'drag', 'why', 'expected', 100, 100, to_x=x, to_y=y)


class GestureTests(unittest.TestCase):
    def api(self):
        api = Mock(); api.key_pressed.return_value = False; api.button_pressed.return_value = False
        return api

    def test_key_released_on_focus_loss_or_pause(self):
        for reason in ('focus lost', 'operator pause'):
            api = self.api()
            guard = Mock(side_effect=[None, InputStopped(reason)])
            with self.assertRaises(InputStopped):
                run_gesture(api, {'kind':'key', 'key':'d', 'duration_ms':2000}, guard)
            self.assertEqual(api.key.call_args_list[0].args, ('d', False))
            self.assertEqual(api.key.call_args_list[-1].args, ('d', True))

    def test_release_attempted_even_when_down_fails(self):
        api = self.api(); api.key.side_effect = [OSError('partial send'), None]
        with self.assertRaises(OSError):
            run_gesture(api, {'kind':'key', 'key':'w'}, lambda: None)
        self.assertEqual(api.key.call_args_list[-1].args, ('w', True))

    def test_existing_human_key_is_not_released(self):
        api = self.api(); api.key_pressed.return_value = True
        with self.assertRaises(InputStopped):
            run_gesture(api, {'kind':'key', 'key':'w'}, lambda: None)
        api.key.assert_not_called()

    def test_drag_releases_on_interruption(self):
        api = self.api(); guard = Mock(side_effect=[None, None, InputStopped('pause')])
        with self.assertRaises(InputStopped):
            run_gesture(api, {'kind':'drag','x':1,'y':2,'to_x':100,'to_y':200,'duration_ms':1000}, guard)
        self.assertEqual(api.button.call_args_list[-1].args, (False, True))

    def test_completed_drag_reaches_endpoint_and_releases(self):
        api = self.api()
        run_gesture(api, {'kind':'drag','x':1,'y':2,'to_x':10,'to_y':20,'duration_ms':20}, lambda: None)
        self.assertEqual(api.move.call_args_list[-1].args, (10, 20))
        self.assertEqual(api.button.call_args_list[-1].args, (False, True))

    def test_right_drag_uses_right_button(self):
        api = self.api()
        run_gesture(api, {'kind':'right_drag','x':1,'y':2,'to_x':10,'to_y':20,'duration_ms':20}, lambda: None)
        self.assertEqual(api.button.call_args_list[0].args, (True, False))
        self.assertEqual(api.button.call_args_list[-1].args, (True, True))


if __name__ == '__main__': unittest.main()
