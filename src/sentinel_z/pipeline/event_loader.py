# src/pipeline/event_loader.py
import pandas as pd
import ast

class EventLoader:
    """
    Loads raw CDM events, cleans UUIDs, filters usable event types.
    Clean, modular, reusable across offline + real-time pipelines.
    """

    EXPANDED_EVENTS = {
        "EVENT_EXECUTE", "EVENT_FORK", "EVENT_SIGNAL", "EVENT_READ", "EVENT_WRITE",
        "EVENT_OPEN", "EVENT_CREATE", "EVENT_RECVMSG", "EVENT_RECVFROM",
        "EVENT_RENAME", "EVENT_CLONE", "EVENT_UNIT", "EVENT_MODIFY_PROCESS",
        "EVENT_SENDMSG", "EVENT_SENDTO", "EVENT_SHM", "EVENT_TEE", "EVENT_SPLICE",
        "EVENT_VMSPLICE", "EVENT_INIT_MODULE", "EVENT_FINIT_MODULE",
        "EVENT_SERVICEINSTALL"
    }

    def __init__(self, path):
        self.path = path
        self.data = None

    def _clean_uuid(self, x):
        """Convert b'..' to hex; ensure string form for graph nodes."""
        if isinstance(x, str) and x.startswith("b'"):
            try:
                b = ast.literal_eval(x)
                return b.hex()
            except:
                return x
        return str(x)

    def load(self):
        df = pd.read_csv(self.path)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Filter event types
        df = df[df["type"].isin(self.EXPANDED_EVENTS)]

        # Clean UUIDs
        df["subject"] = df["subject"].apply(self._clean_uuid)

        # Some events may not have predicate_object
        if "predicate_object" in df.columns:
            df["predicate_object"] = df["predicate_object"].apply(
                lambda x: self._clean_uuid(x) if isinstance(x, str) else None
            )

        self.data = df
        return df
