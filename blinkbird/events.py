"""Thread-safe input boundary for a future BrainFlow blink detector."""
from queue import Queue, Empty, Full
from time import monotonic


class FlapInput:
    def __init__(self):
        self.events = Queue(maxsize=1)

    def submit_flap(self):
        """Call from a future acquisition worker for each accepted blink."""
        try:
            self.events.put_nowait(monotonic())
        except Full:
            pass

    def poll(self):
        try:
            return monotonic() - self.events.get_nowait() < 0.25
        except Empty:
            return False

    def clear(self):
        while True:
            try:
                self.events.get_nowait()
            except Empty:
                break
