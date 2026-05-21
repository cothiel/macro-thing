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


if __name__ == '__main__':
    unittest.main()
