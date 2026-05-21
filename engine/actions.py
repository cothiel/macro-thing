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
            Note: the moveTo call cannot be interrupted mid-motion.
        '''
        print(f"Moving cursor to ({self.end_x}, {self.end_y}) over {self.duration}s")
        if self.start_x is not None and self.start_y is not None:
            pyautogui.moveTo(self.start_x, self.start_y)
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