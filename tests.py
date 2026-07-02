import unittest
from unittest.mock import patch, MagicMock, call
import threading
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.actions import (
    ClickAction, RepeatClickAction, MoveCursorAction, ClickDragAction,
    WaitAction, PressKeyAction, HotkeyAction, TypeTextAction, HoldKeyAction
)
from engine.player import MacroPlayer
from engine.precision_translator import translate_precision, build_move_path


class _BlockingAction:
    """
    Test helper that blocks until release() is called or stop_event is set.
    Use started.wait() in tests to confirm the action has begun before asserting.
    """
    def __init__(self):
        self.started = threading.Event()
        self._released = threading.Event()

    def release(self):
        self._released.set()

    def execute(self, stop_event=None, pause_event=None):
        self.started.set()
        while not self._released.is_set():
            if stop_event and stop_event.is_set():
                return
            time.sleep(0.01)

    def to_dict(self):
        return {"Type": "Blocking"}


class _CountingAction:
    """
    Test helper that counts how many times it has executed, and sets a
    'ready' event once it reaches a target count -- lets a test wait for N
    executions (e.g. across repeat/continuous loops) without a fixed sleep.
    """
    def __init__(self, target_count, ready_event):
        self.count = 0
        self._target = target_count
        self._ready = ready_event

    def execute(self, stop_event=None, pause_event=None):
        self.count += 1
        if self.count >= self._target:
            self._ready.set()

    def to_dict(self):
        return {"Type": "Counting"}


# ---------------------------------------------------------------------------
# ClickAction
# ---------------------------------------------------------------------------

class TestClickAction(unittest.TestCase):

    @patch('pyautogui.click')
    def test_execute_default_button(self, mock_click):
        ClickAction(100, 200).execute()
        mock_click.assert_called_once_with(100, 200, button='left')

    @patch('pyautogui.click')
    def test_execute_right_button(self, mock_click):
        ClickAction(100, 200, 'right').execute()
        mock_click.assert_called_once_with(100, 200, button='right')

    def test_to_dict(self):
        self.assertEqual(
            ClickAction(100, 200, 'right').to_dict(),
            {"Type": "Click", "x": 100, "y": 200, "button": "right"}
        )


# ---------------------------------------------------------------------------
# RepeatClickAction
# ---------------------------------------------------------------------------

class TestRepeatClickAction(unittest.TestCase):

    @patch('time.sleep')
    @patch('pyautogui.click')
    def test_execute_correct_count(self, mock_click, mock_sleep):
        RepeatClickAction(100, 200, 4).execute()
        self.assertEqual(mock_click.call_count, 4)

    @patch('time.sleep')
    @patch('pyautogui.click')
    def test_stop_event_prevents_any_clicks(self, mock_click, mock_sleep):
        stop = threading.Event()
        stop.set()
        RepeatClickAction(100, 200, 5).execute(stop_event=stop)
        mock_click.assert_not_called()

    @patch('time.sleep')
    @patch('pyautogui.click')
    def test_stop_event_halts_mid_loop(self, mock_click, mock_sleep):
        stop = threading.Event()
        click_count = [0]

        def set_stop_on_second(*args, **kwargs):
            click_count[0] += 1
            if click_count[0] == 2:
                stop.set()

        mock_click.side_effect = set_stop_on_second
        RepeatClickAction(100, 200, 10).execute(stop_event=stop)
        self.assertLess(mock_click.call_count, 10)

    def test_to_dict(self):
        self.assertEqual(
            RepeatClickAction(100, 200, 3, 0.5, 'right').to_dict(),
            {"Type": "RepeatClick", "x": 100, "y": 200, "count": 3, "interval": 0.5, "button": "right"}
        )


# ---------------------------------------------------------------------------
# MoveCursorAction
# ---------------------------------------------------------------------------

class TestMoveCursorAction(unittest.TestCase):

    @patch('pyautogui.moveTo')
    def test_execute_no_start(self, mock_move):
        MoveCursorAction(500, 300, 1.0).execute()
        mock_move.assert_called_once_with(500, 300, duration=1.0)

    @patch('pyautogui.moveTo')
    def test_execute_with_start_jumps_first(self, mock_move):
        MoveCursorAction(500, 300, 1.0, start_x=100, start_y=200).execute()
        self.assertEqual(mock_move.call_args_list, [
            call(100, 200),
            call(500, 300, duration=1.0),
        ])

    def test_to_dict(self):
        self.assertEqual(
            MoveCursorAction(500, 300, 1.0, 100, 200).to_dict(),
            {"Type": "MoveCursor", "end_x": 500, "end_y": 300,
             "duration": 1.0, "start_x": 100, "start_y": 200}
        )

    def test_to_dict_start_defaults_to_none(self):
        d = MoveCursorAction(500, 300).to_dict()
        self.assertIsNone(d["start_x"])
        self.assertIsNone(d["start_y"])


# ---------------------------------------------------------------------------
# ClickDragAction
# ---------------------------------------------------------------------------

class TestClickDragAction(unittest.TestCase):

    @patch('pyautogui.mouseUp')
    @patch('pyautogui.moveTo')
    @patch('pyautogui.mouseDown')
    def test_execute_no_start(self, mock_down, mock_move, mock_up):
        ClickDragAction(500, 300).execute()
        mock_down.assert_called_once_with(button='left', _pause=False)
        mock_move.assert_called_once_with(500, 300, duration=0.5, _pause=False)
        mock_up.assert_called_once_with(button='left', _pause=False)

    @patch('pyautogui.mouseUp')
    @patch('pyautogui.moveTo')
    @patch('pyautogui.mouseDown')
    def test_execute_with_start_jumps_first(self, mock_down, mock_move, mock_up):
        ClickDragAction(500, 300, start_x=100, start_y=200).execute()
        self.assertEqual(mock_move.call_args_list, [
            call(100, 200),
            call(500, 300, duration=0.5, _pause=False),
        ])
        mock_down.assert_called_once_with(button='left', _pause=False)
        mock_up.assert_called_once_with(button='left', _pause=False)

    def test_to_dict(self):
        self.assertEqual(
            ClickDragAction(500, 300, 1.0, 'right', 100, 200).to_dict(),
            {"Type": "ClickDrag", "end_x": 500, "end_y": 300,
             "duration": 1.0, "button": "right", "start_x": 100, "start_y": 200}
        )

    def test_to_dict_start_defaults_to_none(self):
        d = ClickDragAction(500, 300).to_dict()
        self.assertIsNone(d["start_x"])
        self.assertIsNone(d["start_y"])


# ---------------------------------------------------------------------------
# WaitAction
# ---------------------------------------------------------------------------

class TestWaitAction(unittest.TestCase):

    def test_stop_event_exits_early(self):
        stop = threading.Event()
        stop.set()
        start = time.time()
        WaitAction(10).execute(stop_event=stop)
        self.assertLess(time.time() - start, 1.0)

    def test_pause_event_blocks_execution(self):
        pause = threading.Event()  # cleared = paused
        done = threading.Event()

        def run():
            WaitAction(0.5).execute(pause_event=pause)
            done.set()

        t = threading.Thread(target=run)
        t.start()
        t.join(timeout=0.15)
        self.assertFalse(done.is_set())  # still blocked by pause

        pause.set()
        done.wait(timeout=2)
        self.assertTrue(done.is_set())

    def test_stop_while_paused_exits(self):
        stop = threading.Event()
        pause = threading.Event()  # cleared = paused
        done = threading.Event()

        def run():
            WaitAction(10).execute(stop_event=stop, pause_event=pause)
            done.set()

        t = threading.Thread(target=run)
        t.start()
        t.join(timeout=0.1)
        stop.set()
        pause.set()  # unblock so the thread can check stop and exit
        done.wait(timeout=2)
        self.assertTrue(done.is_set())

    def test_to_dict(self):
        self.assertEqual(WaitAction(3.5).to_dict(), {"Type": "Wait", "seconds": 3.5})


# ---------------------------------------------------------------------------
# PressKeyAction
# ---------------------------------------------------------------------------

class TestPressKeyAction(unittest.TestCase):

    @patch('pyautogui.press')
    def test_execute(self, mock_press):
        PressKeyAction('enter').execute()
        mock_press.assert_called_once_with('enter')

    def test_to_dict(self):
        self.assertEqual(
            PressKeyAction('f5').to_dict(),
            {"Type": "PressKey", "key": "f5"}
        )


# ---------------------------------------------------------------------------
# HotkeyAction
# ---------------------------------------------------------------------------

class TestHotkeyAction(unittest.TestCase):

    @patch('pyautogui.hotkey')
    def test_execute(self, mock_hotkey):
        HotkeyAction(['ctrl', 'c']).execute()
        mock_hotkey.assert_called_once_with('ctrl', 'c')

    @patch('pyautogui.hotkey')
    def test_execute_three_keys(self, mock_hotkey):
        HotkeyAction(['ctrl', 'shift', 'esc']).execute()
        mock_hotkey.assert_called_once_with('ctrl', 'shift', 'esc')

    def test_to_dict(self):
        self.assertEqual(
            HotkeyAction(['ctrl', 'shift', 'esc']).to_dict(),
            {"Type": "Hotkey", "keys": ['ctrl', 'shift', 'esc']}
        )


# ---------------------------------------------------------------------------
# TypeTextAction
# ---------------------------------------------------------------------------

class TestTypeTextAction(unittest.TestCase):

    @patch('pyautogui.typewrite')
    def test_execute_default_interval(self, mock_typewrite):
        TypeTextAction('hello').execute()
        mock_typewrite.assert_called_once_with('hello', interval=0.05)

    @patch('pyautogui.typewrite')
    def test_execute_custom_interval(self, mock_typewrite):
        TypeTextAction('hello', interval=0.1).execute()
        mock_typewrite.assert_called_once_with('hello', interval=0.1)

    def test_to_dict(self):
        self.assertEqual(
            TypeTextAction('hello world', 0.1).to_dict(),
            {"Type": "TypeText", "text": "hello world", "interval": 0.1}
        )


# ---------------------------------------------------------------------------
# HoldKeyAction
# ---------------------------------------------------------------------------

class TestHoldKeyAction(unittest.TestCase):

    @patch('pyautogui.keyUp')
    @patch('pyautogui.keyDown')
    def test_keydown_and_keyup_called(self, mock_down, mock_up):
        stop = threading.Event()
        stop.set()
        HoldKeyAction('shift', 5).execute(stop_event=stop)
        mock_down.assert_called_once_with('shift')
        mock_up.assert_called_once_with('shift')

    @patch('pyautogui.keyUp')
    @patch('pyautogui.keyDown')
    def test_keyup_called_on_stop_mid_hold(self, mock_down, mock_up):
        # Verifies the finally block fires even when stop interrupts mid-hold
        stop = threading.Event()
        threading.Timer(0.05, stop.set).start()
        HoldKeyAction('w', 10).execute(stop_event=stop)
        mock_down.assert_called_once_with('w')
        mock_up.assert_called_once_with('w')

    @patch('pyautogui.keyUp')
    @patch('pyautogui.keyDown')
    def test_pause_event_not_respected(self, mock_down, mock_up):
        # pause_event being cleared should NOT block HoldKeyAction mid-hold
        stop = threading.Event()
        pause = threading.Event()  # cleared = paused
        stop.set()
        start = time.time()
        HoldKeyAction('ctrl', 10).execute(stop_event=stop, pause_event=pause)
        self.assertLess(time.time() - start, 1.0)
        mock_up.assert_called_once()

    def test_to_dict(self):
        self.assertEqual(
            HoldKeyAction('shift', 2.5).to_dict(),
            {"Type": "HoldKey", "key": "shift", "duration": 2.5}
        )


# ---------------------------------------------------------------------------
# MacroPlayer
# ---------------------------------------------------------------------------

class TestMacroPlayer(unittest.TestCase):

    def test_actions_execute_in_order(self):
        order = []
        actions = []
        for i in range(3):
            m = MagicMock()
            m.execute.side_effect = lambda *a, i=i, **kw: order.append(i)
            actions.append(m)

        player = MacroPlayer(actions)
        player.start()
        player._thread.join(timeout=2)
        self.assertEqual(order, [0, 1, 2])

    def test_is_running_true_while_thread_alive(self):
        action = _BlockingAction()
        player = MacroPlayer([action])
        player.start()
        action.started.wait(timeout=1)
        self.assertTrue(player.is_running)
        action.release()
        player._thread.join(timeout=1)
        self.assertFalse(player.is_running)

    def test_stop_prevents_remaining_actions(self):
        action1 = _BlockingAction()
        action2 = MagicMock()

        player = MacroPlayer([action1, action2])
        player.start()
        action1.started.wait(timeout=1)
        player.stop()
        player._thread.join(timeout=2)
        action2.execute.assert_not_called()

    def test_pause_sets_is_paused(self):
        action = _BlockingAction()
        player = MacroPlayer([action])
        player.start()
        action.started.wait(timeout=1)

        player.pause()
        self.assertTrue(player.is_paused)

        player.resume()
        self.assertFalse(player.is_paused)

        action.release()
        player._thread.join(timeout=1)

    def test_toggle_pause_flips_state(self):
        action = _BlockingAction()
        player = MacroPlayer([action])
        player.start()
        action.started.wait(timeout=1)

        self.assertFalse(player.is_paused)
        player.toggle_pause()
        self.assertTrue(player.is_paused)
        player.toggle_pause()
        self.assertFalse(player.is_paused)

        action.release()
        player._thread.join(timeout=1)

    def test_on_complete_fires_when_finished_naturally(self):
        callback = MagicMock()
        player = MacroPlayer([], on_complete=callback)
        player.start()
        player._thread.join(timeout=2)
        callback.assert_called_once()

    def test_on_complete_not_fired_when_stopped(self):
        action = _BlockingAction()
        callback = MagicMock()
        player = MacroPlayer([action], on_complete=callback)
        player.start()
        action.started.wait(timeout=1)
        player.stop()
        player._thread.join(timeout=2)
        callback.assert_not_called()

    def test_start_while_already_running_is_ignored(self):
        action = _BlockingAction()
        player = MacroPlayer([action])
        player.start()
        action.started.wait(timeout=1)
        thread1 = player._thread
        player.start()
        self.assertIs(player._thread, thread1)
        action.release()
        player._thread.join(timeout=1)

    def test_repeat_count_executes_action_n_times(self):
        action = MagicMock()
        player = MacroPlayer([action], repeat_count=4)
        player.start()
        player._thread.join(timeout=2)
        self.assertEqual(action.execute.call_count, 4)

    def test_repeat_count_default_is_single_pass(self):
        action = MagicMock()
        player = MacroPlayer([action])
        player.start()
        player._thread.join(timeout=2)
        self.assertEqual(action.execute.call_count, 1)

    def test_continuous_playback_loops_until_stopped(self):
        ready = threading.Event()
        action = _CountingAction(target_count=3, ready_event=ready)
        player = MacroPlayer([action], continuous=True)
        player.start()
        self.assertTrue(ready.wait(timeout=2))
        player.stop()
        player._thread.join(timeout=2)
        self.assertGreaterEqual(action.count, 3)

    def test_continuous_ignores_repeat_count(self):
        ready = threading.Event()
        action = _CountingAction(target_count=5, ready_event=ready)
        player = MacroPlayer([action], repeat_count=1, continuous=True)
        player.start()
        self.assertTrue(ready.wait(timeout=2))
        player.stop()
        player._thread.join(timeout=2)
        self.assertGreaterEqual(action.count, 5)

    def test_continuous_with_no_actions_completes_immediately(self):
        callback = MagicMock()
        player = MacroPlayer([], on_complete=callback, continuous=True)
        player.start()
        player._thread.join(timeout=1)
        self.assertFalse(player.is_running)
        callback.assert_called_once()


# ---------------------------------------------------------------------------
# precision_translator
# ---------------------------------------------------------------------------

class TestPrecisionTranslatorKeyChords(unittest.TestCase):

    def test_overlapping_plain_keys_are_not_a_hotkey(self):
        # Fast-typing rollover: 'e' pressed before 'h' is released.
        events = [
            {'type': 'key_press', 'key': 'h', 'timestamp': 0.000},
            {'type': 'key_press', 'key': 'e', 'timestamp': 0.050},
            {'type': 'key_release', 'key': 'h', 'timestamp': 0.060},
            {'type': 'key_release', 'key': 'e', 'timestamp': 0.110},
        ]
        actions = translate_precision(events)
        self.assertTrue(all(isinstance(a, PressKeyAction) for a in actions))
        self.assertEqual([a.key for a in actions], ['h', 'e'])

    def test_overlapping_keys_with_modifier_is_a_hotkey(self):
        events = [
            {'type': 'key_press', 'key': 'ctrl_l', 'timestamp': 0.000},
            {'type': 'key_press', 'key': 'c', 'timestamp': 0.030},
            {'type': 'key_release', 'key': 'c', 'timestamp': 0.060},
            {'type': 'key_release', 'key': 'ctrl_l', 'timestamp': 0.090},
        ]
        actions = translate_precision(events)
        self.assertEqual(len(actions), 1)
        self.assertIsInstance(actions[0], HotkeyAction)
        self.assertEqual(actions[0].keys, ['ctrlleft', 'c'])

    def test_no_key_dropped_when_overlap_rejected_as_chord(self):
        events = [
            {'type': 'key_press', 'key': 'a', 'timestamp': 0.000},
            {'type': 'key_press', 'key': 'b', 'timestamp': 0.010},
            {'type': 'key_press', 'key': 'c', 'timestamp': 0.020},
            {'type': 'key_release', 'key': 'a', 'timestamp': 0.030},
            {'type': 'key_release', 'key': 'b', 'timestamp': 0.040},
            {'type': 'key_release', 'key': 'c', 'timestamp': 0.050},
        ]
        actions = translate_precision(events)
        self.assertEqual([a.key for a in actions], ['a', 'b', 'c'])


class TestPrecisionTranslatorTiming(unittest.TestCase):

    def test_sub_threshold_gap_between_clicks_is_preserved(self):
        events = [
            {'type': 'mouse_button', 'x': 10, 'y': 10, 'button': 'left', 'pressed': True, 'timestamp': 0.000},
            {'type': 'mouse_button', 'x': 10, 'y': 10, 'button': 'left', 'pressed': False, 'timestamp': 0.020},
            {'type': 'mouse_button', 'x': 10, 'y': 10, 'button': 'left', 'pressed': True, 'timestamp': 0.045},
            {'type': 'mouse_button', 'x': 10, 'y': 10, 'button': 'left', 'pressed': False, 'timestamp': 0.060},
        ]
        actions = translate_precision(events)
        waits = [a.seconds for a in actions if isinstance(a, WaitAction)]
        self.assertEqual(waits, [0.025])

    def test_idle_gap_before_move_becomes_wait_then_instant_jump(self):
        events = [
            {'type': 'mouse_move', 'x': 10, 'y': 10, 'timestamp': 2.5},
        ]
        actions = translate_precision(events)
        self.assertIsInstance(actions[0], WaitAction)
        self.assertEqual(actions[0].seconds, 2.5)
        self.assertIsInstance(actions[1], MoveCursorAction)
        self.assertEqual(actions[1].duration, 0.0)


class TestBuildMovePath(unittest.TestCase):
    """build_move_path() powers the 'draw new path' redraw feature: it
    converts (x, y, elapsed_seconds) samples captured from a mouse drag into
    the same kind of MoveCursorAction/WaitAction sequence a real recording
    would produce."""

    def test_empty_samples_produce_no_actions(self):
        self.assertEqual(build_move_path([]), [])

    def test_first_sample_has_zero_duration(self):
        actions = build_move_path([(10, 20, 0.0)])
        self.assertEqual(len(actions), 1)
        self.assertIsInstance(actions[0], MoveCursorAction)
        self.assertEqual((actions[0].end_x, actions[0].end_y, actions[0].duration), (10, 20, 0.0))

    def test_closely_spaced_samples_stay_embedded_moves(self):
        samples = [(0, 0, 0.0), (5, 5, 0.01), (10, 10, 0.02)]
        actions = build_move_path(samples)
        self.assertTrue(all(isinstance(a, MoveCursorAction) for a in actions))
        self.assertEqual([a.duration for a in actions], [0.0, 0.01, 0.01])

    def test_pause_mid_drag_becomes_wait_then_jump(self):
        # User held the button but paused (no movement) for a while mid-drag.
        samples = [(0, 0, 0.0), (5, 5, 0.02), (5, 5, 0.02), (50, 50, 0.30)]
        actions = build_move_path(samples)
        types = [type(a).__name__ for a in actions]
        self.assertIn('WaitAction', types)
        wait = next(a for a in actions if isinstance(a, WaitAction))
        self.assertAlmostEqual(wait.seconds, 0.28, places=3)


if __name__ == '__main__':
    unittest.main()
