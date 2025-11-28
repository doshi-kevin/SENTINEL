# src/pipeline/window_generator.py
import pandas as pd
from datetime import timedelta

class WindowGenerator:
    """
    Efficient 1-second window slicing:
    - Only generates windows for timestamps that actually exist
    - Avoids thousands of empty windows
    """

    def __init__(self, window_seconds=1):
        self.window = timedelta(seconds=window_seconds)
        self.attack_start = None
        self.attack_end = None

    def set_attack_period(self, start, end):
        self.attack_start = start
        self.attack_end = end

    def generate_windows(self, events):
        """
        FAST: Instead of looping thousands of seconds,
        generate windows only for unique time bins that have events.
        """
        events = events.copy()
        events["second_bin"] = events["timestamp"].dt.floor("1S")

        # Unique windows with actual events
        unique_bins = sorted(events["second_bin"].unique())

        windows = [(t, t + self.window) for t in unique_bins]
        return windows

    def label_window(self, ws, we):
        """Label based on attack overlap."""
        if self.attack_start is None:
            return 0
        return 1 if (ws <= self.attack_end and we >= self.attack_start) else 0
