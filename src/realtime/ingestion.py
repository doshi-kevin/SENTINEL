# src/realtime/ingestion.py

import time

def simulate_event_stream(events):
    for e in events:
        yield e
        time.sleep(0.01)
