from abc import ABC, abstractmethod
import pyautogui
import time

class BaseAction:
    @abstractmethod
    def execute(self, stop_event=None, pause_event=None):
        pass

    @abstractmethod
    def to_dict(self) -> dict:
        # used to save to json
        pass

'''
    Clicks at a specific pixel coordinate

    Args:
        x (int): Horizontal pixel coordinate
        y (int): Vertical pixel coordinate
        button (str): Mouse button to click ('left', 'right', 'middle'). Defaults to 'left'

    Usage:
        action = ClickAction(1000, 300, 'right')
        action.execute()

        action = ClickAction(x=1000, y=300, button='right')
        action.execute()
'''
class ClickAction(BaseAction):
    def __init__(self, x, y, button='left'):
        self.x = x
        self.y = y
        self.button = button

    def execute(self, stop_event=None, pause_event=None):
        print(f"Clicking at ({self.x}, {self.y}) [{self.button}]")
        pyautogui.click(self.x, self.y, button=self.button)
    
    def to_dict(self):
        return {
            "Type": "Click", 
            "x": self.x, 
            "y": self.y, 
            "button": self.button
        }




'''
    Clicks at a specific pixel coordinate <count> times with <interval> seconds between clicks

    Args:
        x (int): Horizontal pixel coordinate
        y (int): Vertical pixel coordinate
        count (int): Number of times to click
        interval (float): Seconds to wait between each click. Defaults to 0.1
        button (str): Mouse button to click ('left', 'right', 'middle'). Defaults to 'left'

    Usage:
        action = RepeatClickAction(1000, 300, 5, 1)
        action.execute()

        action = RepeatClickAction(x=1000, y=300, count=5, interval=1, button='right')
        action.execute()
'''
class RepeatClickAction(BaseAction):
    def __init__(self, x, y, count, interval=0.1, button='left'):
        self.x = x
        self.y = y
        self.count = count
        self.interval = interval
        self.button = button

    def execute(self, stop_event=None, pause_event=None):
        print(f"Clicking at ({self.x}, {self.y}) x{self.count} every {self.interval}s [{self.button}]")
        for _ in range(self.count):
            if stop_event and stop_event.is_set():
                break
            if pause_event:
                pause_event.wait()
                if stop_event and stop_event.is_set():
                    break
            pyautogui.click(self.x, self.y, clicks=1, button=self.button)
            time.sleep(self.interval)
    
    def to_dict(self):
        return {
            "Type": "RepeatClick",
            "x": self.x,
            "y": self.y,
            "count": self.count,
            "interval": self.interval,
            "button": self.button
        }
        



'''
    Moves cursor from (start_x, start_y) to (end_x, end_y), across duration seconds
    
    Args:
        end_x (int): Horizontal pixel coordinate where mouse is moved
        end_y (int): Vertical pixel coordinate where mouse is moved
        duration (int): Time in seconds to move from initial position to end position
        start_x (int): Horizontal pixel coordinate for starting mouse position
        start_y (int): Vertical pixel coordinate for starting mouse position

    Usage:
        action = MoveCursorAction(1000, 300, 1, 500, 300)
        action.execute()

        action = MoveCursorAction(end_x=1000, end_y=300, duration=1, start_x=500, start_y=300)
        action.execute()
'''
class MoveCursorAction(BaseAction):
    def __init__(self, end_x, end_y, duration=0.5, start_x=None, start_y=None):
        self.end_x = end_x
        self.end_y = end_y
        self.duration = duration
        self.start_x = start_x
        self.start_y = start_y

    def execute(self, stop_event=None, pause_event=None):
        '''
            If a start coord is designated, instantly jump to (start_x, start_y) first.
            Then move to (end_x, end_y) over duration seconds.
            Note: for duration >= pyautogui.MINIMUM_DURATION the moveTo call
            cannot be interrupted mid-motion.
        '''
        print(f"Moving cursor to ({self.end_x}, {self.end_y}) over {self.duration}s")
        if self.start_x is not None and self.start_y is not None:
            pyautogui.moveTo(self.start_x, self.start_y)
        if 0 < self.duration < pyautogui.MINIMUM_DURATION:
            # pyautogui silently treats any duration below MINIMUM_DURATION as
            # instantaneous, discarding the elapsed time entirely. That's fine
            # for a single hand-placed move, but a recorded mouse path is
            # replayed as many short MoveCursorActions back-to-back, so
            # dropping each one compounds into large timing drift. Time it
            # ourselves instead, then snap to the final position.
            deadline = time.time() + self.duration
            while time.time() < deadline:
                if stop_event and stop_event.is_set():
                    return
                if pause_event:
                    pause_event.wait()
                    if stop_event and stop_event.is_set():
                        return
                time.sleep(min(0.01, max(0, deadline - time.time())))
            pyautogui.moveTo(self.end_x, self.end_y)
        else:
            pyautogui.moveTo(self.end_x, self.end_y, duration=self.duration)

    def to_dict(self):
        return {
            "Type": "MoveCursor",
            "end_x": self.end_x,
            "end_y": self.end_y,
            "duration": self.duration,
            "start_x": self.start_x,
            "start_y": self.start_y,
        }


'''
    Holds a mouse button down at the start position, moves to the end position, then releases.
    If start_x and start_y are omitted, the drag begins from the cursor's current position.
    If specified, the cursor instantly jumps to (start_x, start_y) before the drag begins.

    Note:
        pyautogui.dragTo() cannot be interrupted mid-motion. Stop and pause signals
        take effect only after the drag completes.

    Args:
        end_x (int): Horizontal pixel coordinate where the drag ends
        end_y (int): Vertical pixel coordinate where the drag ends
        duration (float): Time in seconds to move from start to end position. Defaults to 0.5
        button (str): Mouse button to hold during the drag ('left', 'right', 'middle'). Defaults to 'left'
        start_x (int): Horizontal pixel coordinate for the start of the drag. Defaults to current cursor position
        start_y (int): Vertical pixel coordinate for the start of the drag. Defaults to current cursor position

    Usage:
        action = ClickDragAction(1000, 300)
        action.execute()

        action = ClickDragAction(end_x=1000, end_y=300, duration=1, button='left', start_x=500, start_y=300)
        action.execute()
'''
class ClickDragAction(BaseAction):
    def __init__(self, end_x, end_y, duration=0.5, button='left', start_x=None, start_y=None):
        self.end_x = end_x
        self.end_y = end_y
        self.duration = duration
        self.button = button
        self.start_x = start_x
        self.start_y = start_y

    def execute(self, stop_event=None, pause_event=None):
        '''
            If a start coord is designated, instantly jump to (start_x, start_y) first.
            Then drag to (end_x, end_y) over duration seconds.
            Note: the drag cannot be interrupted mid-motion.
        '''
        print(f"Dragging to ({self.end_x}, {self.end_y}) over {self.duration}s [{self.button}]")
        if self.start_x is not None and self.start_y is not None:
            pyautogui.moveTo(self.start_x, self.start_y)
        pyautogui.mouseDown(button=self.button, _pause=False)
        pyautogui.moveTo(self.end_x, self.end_y, duration=self.duration, _pause=False)
        time.sleep(0.05)
        pyautogui.mouseUp(button=self.button, _pause=False)

    def to_dict(self):
        return {
            "Type": "ClickDrag",
            "end_x": self.end_x,
            "end_y": self.end_y,
            "duration": self.duration,
            "button": self.button,
            "start_x": self.start_x,
            "start_y": self.start_y,
        }


'''
    Pauses macro execution for a specified number of seconds.
    Responds to stop and pause signals within ~50ms.

    Args:
        seconds (float): Time in seconds to wait

    Usage:
        action = WaitAction(2)
        action.execute()

        action = WaitAction(seconds=0.5)
        action.execute()
'''
class WaitAction(BaseAction):
    def __init__(self, seconds):
        self.seconds = seconds

    def execute(self, stop_event=None, pause_event=None):
        print(f"Waiting {self.seconds}s")
        deadline = time.time() + self.seconds
        while time.time() < deadline:
            if stop_event and stop_event.is_set():
                return
            if pause_event:
                pause_event.wait()
                if stop_event and stop_event.is_set():
                    return
            time.sleep(min(0.05, max(0, deadline - time.time())))

    def to_dict(self):
        return {
            "Type": "Wait",
            "seconds": self.seconds
        }




'''
    Presses a single key once (keydown + keyup)

    Args:
        key (str): Key name as a pyautogui key string (e.g. 'enter', 'a', 'f5')

    Usage:
        action = PressKeyAction('enter')
        action.execute()

        action = PressKeyAction(key='f5')
        action.execute()
'''
class PressKeyAction(BaseAction):
    def __init__(self, key):
        self.key = key

    def execute(self, stop_event=None, pause_event=None):
        print(f"Pressing key '{self.key}'")
        pyautogui.press(self.key)

    def to_dict(self):
        return {
            "Type": "PressKey",
            "key": self.key,
        }




'''
    Presses multiple keys simultaneously (e.g. hotkeys, keyboard shortcuts)

    Args:
        keys (list[str]): Ordered list of key names to press together

    Usage:
        action = HotkeyAction(['ctrl', 'c'])
        action.execute()

        action = HotkeyAction(['ctrl', 'shift', 'esc'])
        action.execute()
'''
class HotkeyAction(BaseAction):
    def __init__(self, keys):
        self.keys = keys

    def execute(self, stop_event=None, pause_event=None):
        print(f"Hotkey {' + '.join(self.keys)}")
        pyautogui.hotkey(*self.keys)

    def to_dict(self):
        return {
            "Type": "Hotkey",
            "keys": self.keys,
        }




'''
    Types a string of text character by character

    Args:
        text (str): The text to type. Limited to printable ASCII characters.
        interval (float): Seconds between each keypress

    Usage:
        action = TypeTextAction('hello world')
        action.execute()

        action = TypeTextAction(text='hello world', interval=0.1)
        action.execute()
'''
class TypeTextAction(BaseAction):
    def __init__(self, text, interval=0.05):
        self.text = text
        self.interval = interval

    def execute(self, stop_event=None, pause_event=None):
        print(f"Typing '{self.text}' at {self.interval}s/char")
        pyautogui.typewrite(self.text, interval=self.interval)

    def to_dict(self):
        return {
            "Type": "TypeText",
            "text": self.text,
            "interval": self.interval,
        }




'''
    Holds a key down for a specified duration, then releases it.

    Pause behavior: This action does NOT respect pause signals mid-hold. A pause will
    only take effect after the hold completes and the key has been released. This is
    intentional — pausing mid-hold would leave the key physically pressed, causing the
    OS to fire repeated keypress events in the focused application. Stop signals are
    respected and will release the key immediately via a finally block.

    Args:
        key (str): Key name as a pyautogui key string (e.g. 'shift', 'w', 'space')
        duration (float): Time in seconds to hold the key down

    Usage:
        action = HoldKeyAction('w', 2.5)
        action.execute()

        action = HoldKeyAction(key='shift', duration=1)
        action.execute()
'''
class HoldKeyAction(BaseAction):
    def __init__(self, key, duration):
        self.key = key
        self.duration = duration

    def execute(self, stop_event=None, pause_event=None):
        print(f"Holding key '{self.key}' for {self.duration}s")
        pyautogui.keyDown(self.key)
        try:
            deadline = time.time() + self.duration
            while time.time() < deadline:
                if stop_event and stop_event.is_set():
                    return
                time.sleep(min(0.05, max(0, deadline - time.time())))
        finally:
            pyautogui.keyUp(self.key)

    def to_dict(self):
        return {
            "Type": "HoldKey",
            "key": self.key,
            "duration": self.duration,
        }


'''
    Scrolls the mouse wheel at a specific pixel coordinate.

    Amounts are measured in wheel "notches" -- the same unit pynput reports
    when recording (it normalizes Windows' raw WM_MOUSEWHEEL delta by
    dividing by WHEEL_DELTA=120 before it ever reaches the recorder), so a
    recorded scroll's dy/dx already means "notches" here. pyautogui.scroll()
    does not do that conversion itself -- it passes whatever value it's
    given straight through to the OS as a raw wheel delta -- so this class
    multiplies back up by WHEEL_DELTA before calling it.

    Args:
        x (int): Horizontal pixel coordinate
        y (int): Vertical pixel coordinate
        dy (int): Vertical notches. Positive scrolls up, negative down.
        dx (int): Horizontal notches. Positive scrolls right, negative left. Defaults to 0
        duration (float): Seconds to spread the scroll over. 0 scrolls
            instantly in a single motion (the default -- matches a single
            recorded wheel notch, which is already an instantaneous event).
        speed (int): Notches sent per step while animating a duration > 0
            scroll. Smaller feels smoother, larger feels choppier. Ignored
            when duration is 0.

    Usage:
        action = ScrollAction(1000, 300, dy=-5)
        action.execute()

        action = ScrollAction(x=1000, y=300, dy=10, duration=1.0, speed=2)
        action.execute()
'''
class ScrollAction(BaseAction):
    _WHEEL_DELTA = 120  # notch -> raw OS wheel delta, per the Windows API / pynput's own convention

    def __init__(self, x, y, dy, dx=0, duration=0.0, speed=1):
        self.x = x
        self.y = y
        self.dy = dy
        self.dx = dx
        self.duration = duration
        self.speed = max(1, speed)

    def execute(self, stop_event=None, pause_event=None):
        print(f"Scrolling ({self.dy}, {self.dx}) notches at ({self.x}, {self.y}) over {self.duration}s")
        steps = self._steps()
        delay = self.duration / len(steps) if self.duration > 0 and steps else 0.0
        for step_dy, step_dx in steps:
            if stop_event and stop_event.is_set():
                return
            if pause_event:
                pause_event.wait()
                if stop_event and stop_event.is_set():
                    return
            if step_dy:
                pyautogui.scroll(step_dy * self._WHEEL_DELTA, x=self.x, y=self.y)
            if step_dx:
                pyautogui.hscroll(step_dx * self._WHEEL_DELTA, x=self.x, y=self.y)
            if delay:
                time.sleep(delay)

    def _steps(self):
        """Split (dy, dx) into a list of (step_dy, step_dx) chunks of at
        most ~speed notches each, so a scroll with duration > 0 plays back
        as a smooth series of pulses instead of one instantaneous jump.
        Steps are computed via running rounding (not naive division) so
        they always sum to exactly (dy, dx) with no drift. `speed` only
        matters when duration > 0 -- an instant (duration == 0) scroll is
        always a single motion regardless of speed."""
        magnitude = max(abs(self.dy), abs(self.dx))
        if magnitude == 0:
            return []
        if self.duration <= 0:
            return [(self.dy, self.dx)]
        count = max(1, -(-magnitude // self.speed))  # ceil(magnitude / speed)
        steps = []
        dy_done = dx_done = 0
        for i in range(1, count + 1):
            dy_target = round(self.dy * i / count)
            dx_target = round(self.dx * i / count)
            steps.append((dy_target - dy_done, dx_target - dx_done))
            dy_done, dx_done = dy_target, dx_target
        return steps

    def to_dict(self):
        return {
            "Type": "Scroll",
            "x": self.x,
            "y": self.y,
            "dy": self.dy,
            "dx": self.dx,
            "duration": self.duration,
            "speed": self.speed,
        }