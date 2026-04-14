# src/realtime/event_buffer.py

from collections import deque
import time

class EventBuffer:
    def __init__(self, window_size=1.0):
        self.window_size = window_size
        self.buffer = deque()

    def add_event(self, event):
        self.buffer.append(event)
        self.cleanup()

    def cleanup(self):
        cutoff = time.time() - self.window_size
        while self.buffer and self.buffer[0]["timestamp"] < cutoff:
            self.buffer.popleft()

    def get_window(self):
        return list(self.buffer)
