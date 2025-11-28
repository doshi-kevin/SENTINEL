# src/pipeline/build_dataset.py

import pandas as pd
from pathlib import Path

from src.pipeline.event_loader import EventLoader
from src.pipeline.window_generator import WindowGenerator
from src.pipeline.graph_constructor import GraphConstructor
from src.pipeline.feature_engineer import FeatureEngineer
from src.pipeline.graph_exporter import GraphExporter


class DatasetBuilder:
    def __init__(self):

        # FIXED: Correct events.csv path for your system
        self.events_path = Path("data/processed/events.csv")

        # FIXED: Correct output folder
        self.output_dir = Path("data/model_ready")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # FIXED: Graphs folder
        self.graph_dir = self.output_dir / "graphs"
        self.graph_dir.mkdir(parents=True, exist_ok=True)

        # Loader
        self.loader = EventLoader(self.events_path)

        # Windows
        self.windows = WindowGenerator(window_seconds=1)
        self.windows.set_attack_period(
            pd.to_datetime("2019-05-07 11:10:00"),
            pd.to_datetime("2019-05-07 11:11:59")
        )

        # Graph builders
        self.graph_builder = GraphConstructor()
        self.fe = FeatureEngineer()
        self.exporter = GraphExporter(self.graph_dir)


    def run(self):
        print("📥 Loading events from:", self.events_path)
        events = self.loader.load()
        print("✔ Loaded events:", len(events))

        windows = self.windows.generate_windows(events)
        print("✔ Generated windows:", len(windows))

        label_rows = []
        count = 0

        for i, (ws, we) in enumerate(windows):

            # FIXED: Correct timestamp filter
            w = events[(events["timestamp"] >= ws) & (events["timestamp"] < we)]

            if w.empty:
                # Debug print
                print(f"⚠️  Empty window {i}, skipping")
                continue

            # Build raw graph
            G = self.graph_builder.build_graph(w)

            if len(G.nodes) == 0:
                print(f"⚠️  Empty graph for window {i}, skipping")
                continue

            # Add features
            G = self.fe.compute_node_features(G)

            # Save
            self.exporter.save(G, count)

            label_rows.append({
                "window_id": count,
                "start": ws,
                "end": we,
                "label": self.windows.label_window(ws, we),
                "num_nodes": len(G.nodes),
                "num_edges": len(G.edges)
            })

            print(f"✔ Graph {count} saved ({len(G.nodes)} nodes, {len(G.edges)} edges)")

            count += 1

        # Save labels
        pd.DataFrame(label_rows).to_csv(self.output_dir / "labels.csv", index=False)

        print(f"\n🎉 Dataset ready!")
        print(f"Total graphs created: {count}")


# -----------------------------------------------------------
# MAIN BLOCK (THIS WAS MISSING)
# -----------------------------------------------------------

if __name__ == "__main__":
    builder = DatasetBuilder()
    builder.run()
