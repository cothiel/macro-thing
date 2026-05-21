import sys
import os
import threading

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.actions import * # Apparently importing everything is "bad" but im doing it anyway (for now)


class MacroPlayer:
    def __init__(self, actions, on_complete=None):
        self.actions = actions
        self.on_complete = on_complete
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # set = running, clear = paused
        self._thread = None

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_paused(self):
        return self.is_running and not self._pause_event.is_set()

    def start(self):
        if self.is_running:
            return
        self._stop_event.clear()
        self._pause_event.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._pause_event.set()  # unblock any pause wait so the thread can exit

    def pause(self):
        self._pause_event.clear()

    def resume(self):
        self._pause_event.set()

    def toggle_pause(self):
        if self._pause_event.is_set():
            self.pause()
        else:
            self.resume()

    def _run(self):
        for action in self.actions:
            if self._stop_event.is_set():
                break
            self._pause_event.wait()  # blocks here while paused
            if self._stop_event.is_set():
                break
            action.execute(self._stop_event, self._pause_event)

        if self.on_complete and not self._stop_event.is_set():
            self.on_complete()