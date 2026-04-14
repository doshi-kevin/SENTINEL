# src/pipeline/graph_constructor.py
import networkx as nx

class GraphConstructor:
    """
    Builds raw directed provenance graphs for each window.
    Ensures timestamps are JSON-serializable (converted to ISO strings).
    """

    def build_graph(self, events_window):
        G = nx.DiGraph()

        for _, row in events_window.iterrows():
            subj = row["subject"]
            obj = row["predicate_object"] if row.get("predicate_object") else None

            # --- add subject node ---
            G.add_node(subj, node_type="subject")

            if obj:
                # --- add object node ---
                G.add_node(obj, node_type="object")

                # FIX: convert Timestamp → string
                ts_str = str(row["timestamp"])

                # --- add edge with event + timestamp ---
                G.add_edge(
                    subj,
                    obj,
                    event=row["type"],
                    ts=ts_str  # 🔥 ISO STRING, NOT Timestamp
                )

        return G
