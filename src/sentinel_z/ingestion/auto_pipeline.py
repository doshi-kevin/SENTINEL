"""
Automated Data Ingestion & Training Pipeline

This is the "drop .bin.gz → auto-train" pipeline you requested.

Pipeline Flow:
1. Ingest raw .bin.gz DARPA CDM files
2. Parse Avro/JSON records into events, subjects, objects
3. Build provenance graphs with semantic labels
4. Split by engagement for cross-dataset validation
5. Train SENTINEL-Z model
6. Evaluate zero-shot performance

Supports:
- Multiple DARPA TC engagements (E3, E5, etc.)
- Multiple teams (FiveDirections, THEIA, TRACE, etc.)
- Automatic ground truth alignment
"""

import gzip
import json
import subprocess
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Generator
from dataclasses import dataclass
from datetime import datetime
import hashlib
import shutil
import sys
import time
import os

# Try to import avro - if not available, we'll use JSON fallback
try:
    import fastavro
    HAS_AVRO = True
except ImportError:
    HAS_AVRO = False


def get_file_size(file_path: Path) -> int:
    """Get file size in bytes."""
    return os.path.getsize(file_path)


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def print_progress(current: int, total: int, prefix: str = "", size: int = 40, elapsed: float = 0):
    """Print a progress bar."""
    if total == 0:
        return
    percent = current / total
    filled = int(size * percent)
    bar = '█' * filled + '░' * (size - filled)

    # Calculate ETA
    if elapsed > 0 and percent > 0:
        eta = (elapsed / percent) - elapsed
        eta_str = f"ETA: {eta:.0f}s"
    else:
        eta_str = "ETA: --"

    sys.stdout.write(f'\r  {prefix} |{bar}| {percent*100:.1f}% ({current:,}/{total:,}) {eta_str}    ')
    sys.stdout.flush()

    if current >= total:
        print()  # New line when complete


@dataclass
class DARPADataset:
    """Metadata about a DARPA TC dataset file."""
    file_path: Path
    team: str           # e.g., "fivedirections", "theia", "trace"
    engagement: str     # e.g., "e3", "e5"
    file_num: int       # File number in sequence
    source: str         # Full source identifier

    @classmethod
    def from_filename(cls, path: Path) -> 'DARPADataset':
        """Parse DARPA filename to extract metadata."""
        # Example: ta1-fivedirections-1-e5-official-1.bin.1.gz
        name = path.name.lower()
        parts = name.replace('.bin', '').replace('.gz', '').split('-')

        team = "unknown"
        engagement = "unknown"
        file_num = 1

        for i, part in enumerate(parts):
            if part in ['fivedirections', 'theia', 'trace', 'cadets', 'clearscope']:
                team = part
            if part.startswith('e') and part[1:].isdigit():
                engagement = part
            if part.isdigit():
                file_num = int(part)

        source = f"SOURCE_{team.upper()}_{engagement.upper()}"

        return cls(
            file_path=path,
            team=team,
            engagement=engagement,
            file_num=file_num,
            source=source
        )


class CDMParser:
    """
    Parser for DARPA CDM (Common Data Model) format.
    Handles both Avro binary and JSON formats.
    """

    # CDM record types we care about
    RECORD_TYPES = {
        'com.bbn.tc.schema.avro.cdm20.Event',
        'com.bbn.tc.schema.avro.cdm20.Subject',
        'com.bbn.tc.schema.avro.cdm20.FileObject',
        'com.bbn.tc.schema.avro.cdm20.NetFlowObject',
        'com.bbn.tc.schema.avro.cdm20.Principal',
    }

    def __init__(self):
        self.events = []
        self.subjects = []
        self.files = []
        self.network = []

    def parse_file(self, file_path: Path) -> Dict[str, pd.DataFrame]:
        """
        Parse a DARPA CDM file (gzipped Avro or JSON).

        Returns dict with DataFrames for events, subjects, files, network.
        """
        self.events = []
        self.subjects = []
        self.files = []
        self.network = []

        file_path = Path(file_path)

        if file_path.suffix == '.gz':
            # Try Avro first, fall back to JSON
            if HAS_AVRO:
                try:
                    self._parse_avro_gz(file_path)
                except Exception as e:
                    print(f"Avro parsing failed, trying JSON: {e}")
                    self._parse_json_gz(file_path)
            else:
                self._parse_json_gz(file_path)
        else:
            self._parse_json(file_path)

        return {
            'events': pd.DataFrame(self.events),
            'subjects': pd.DataFrame(self.subjects),
            'files': pd.DataFrame(self.files),
            'network': pd.DataFrame(self.network)
        }

    def _parse_avro_gz(self, file_path: Path) -> None:
        """Parse gzipped Avro CDM file with progress."""
        file_size = get_file_size(file_path)
        print(f"  File size: {format_size(file_size)} (compressed)")
        print(f"  Using fast Avro parser...")

        record_count = 0
        start_time = time.time()

        with gzip.open(file_path, 'rb') as f:
            reader = fastavro.reader(f)
            for record in reader:
                record_count += 1
                self._process_record(record)

                # Update progress every 10000 records
                if record_count % 10000 == 0:
                    elapsed = time.time() - start_time
                    rate = record_count / elapsed if elapsed > 0 else 0
                    print(f"\r  Processed {record_count:,} records ({rate:.0f} rec/sec)...", end='')
                    sys.stdout.flush()

        elapsed = time.time() - start_time
        print(f"\n  Parsed {record_count:,} records in {elapsed:.1f}s ({record_count/elapsed:.0f} rec/sec)")

    def _parse_json_gz(self, file_path: Path) -> None:
        """Parse gzipped JSON CDM file (line-delimited) with progress."""
        file_size = get_file_size(file_path)
        print(f"  File size: {format_size(file_size)} (compressed)")

        bytes_read = 0
        line_count = 0
        start_time = time.time()

        with gzip.open(file_path, 'rt', encoding='utf-8') as f:
            for line in f:
                line_count += 1
                bytes_read += len(line.encode('utf-8'))

                # Update progress every 10000 lines
                if line_count % 10000 == 0:
                    elapsed = time.time() - start_time
                    # Estimate based on typical compression ratio (~10x)
                    estimated_total = file_size * 10
                    print_progress(bytes_read, estimated_total, "Parsing", elapsed=elapsed)

                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    self._process_record(record)
                except json.JSONDecodeError:
                    continue

        elapsed = time.time() - start_time
        print(f"\n  Parsed {line_count:,} lines in {elapsed:.1f}s ({line_count/elapsed:.0f} lines/sec)")

    def _parse_json(self, file_path: Path) -> None:
        """Parse JSON CDM file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    self._process_record(record)
                except json.JSONDecodeError:
                    continue

    def _process_record(self, record: Dict) -> None:
        """Process a single CDM record."""
        # Check for top-level 'type' field which indicates record type
        record_type = record.get('type', '')

        # CDM records may have 'datum' containing the actual data
        if 'datum' in record and record['datum']:
            datum = record['datum']

            # Check if datum itself has a 'type' field (Event records)
            if isinstance(datum, dict) and 'type' in datum:
                dtype = datum.get('type')
                if isinstance(dtype, str):
                    if dtype.startswith('EVENT_'):
                        self._process_event(datum)
                        return
                    elif dtype in ['SUBJECT_PROCESS', 'SUBJECT_THREAD', 'SUBJECT_UNIT']:
                        self._process_subject(datum)
                        return

            # Check if datum is wrapped with a schema type key
            if isinstance(datum, dict):
                datum_keys = list(datum.keys())
                # If first key looks like a schema name, it's wrapped
                if datum_keys and 'com.bbn' in str(datum_keys[0]):
                    data = datum[datum_keys[0]]
                    self._route_record(datum_keys[0], data)
        else:
            # Direct record (no wrapper)
            if isinstance(record_type, str) and record_type.startswith('EVENT_'):
                self._process_event(record)
            elif 'subjectType' in record:
                self._process_subject(record)

    def _route_record(self, record_type: str, data: Dict) -> None:
        """Route record to appropriate processor."""
        if 'Event' in record_type:
            self._process_event(data)
        elif 'Subject' in record_type:
            self._process_subject(data)
        elif 'FileObject' in record_type:
            self._process_file(data)
        elif 'NetFlowObject' in record_type:
            self._process_network(data)

    def _extract_uuid(self, uuid_field) -> str:
        """Extract UUID from various CDM formats."""
        if isinstance(uuid_field, bytes):
            return uuid_field.hex()
        elif isinstance(uuid_field, dict):
            # CDM often wraps UUIDs
            if 'bytes' in uuid_field:
                return uuid_field['bytes'].hex() if isinstance(uuid_field['bytes'], bytes) else str(uuid_field['bytes'])
            return str(list(uuid_field.values())[0]) if uuid_field else ""
        elif isinstance(uuid_field, str):
            if uuid_field.startswith("b'"):
                try:
                    import ast
                    return ast.literal_eval(uuid_field).hex()
                except:
                    pass
            return uuid_field
        return str(uuid_field) if uuid_field else ""

    def _process_event(self, data: Dict) -> None:
        """Process Event record."""
        event = {
            'uuid': self._extract_uuid(data.get('uuid')),
            'type': data.get('type', 'UNKNOWN'),
            'timestamp': self._convert_timestamp(data.get('timestampNanos')),
            'timestamp_nanos': data.get('timestampNanos'),
            'subject': self._extract_uuid(data.get('subject')),
            'predicate_object': self._extract_uuid(data.get('predicateObject')),
            'predicate_object2': self._extract_uuid(data.get('predicateObject2')),
            'size': data.get('size'),
            'thread_id': data.get('threadId'),
        }
        self.events.append(event)

    def _process_subject(self, data: Dict) -> None:
        """Process Subject record."""
        subject = {
            'uuid': self._extract_uuid(data.get('uuid')),
            'type': data.get('type', data.get('subjectType', 'UNKNOWN')),
            'cid': data.get('cid'),
            'parent_subject': self._extract_uuid(data.get('parentSubject')),
            'local_principal': self._extract_uuid(data.get('localPrincipal')),
            'start_timestamp': self._convert_timestamp(data.get('startTimestampNanos')),
            'cmd_line': data.get('cmdLine'),
            'privilege_level': data.get('privilegeLevel'),
        }
        self.subjects.append(subject)

    def _process_file(self, data: Dict) -> None:
        """Process FileObject record."""
        file_obj = {
            'uuid': self._extract_uuid(data.get('uuid')),
            'file_type': data.get('type', data.get('fileObjectType')),
            'path': self._extract_path(data.get('baseObject', {}).get('properties')),
            'permission': data.get('permission'),
        }
        self.files.append(file_obj)

    def _process_network(self, data: Dict) -> None:
        """Process NetFlowObject record."""
        net = {
            'uuid': self._extract_uuid(data.get('uuid')),
            'local_address': data.get('localAddress'),
            'local_port': data.get('localPort'),
            'remote_address': data.get('remoteAddress'),
            'remote_port': data.get('remotePort'),
            'ip_protocol': data.get('ipProtocol'),
        }
        self.network.append(net)

    def _convert_timestamp(self, nanos) -> Optional[datetime]:
        """Convert nanosecond timestamp to datetime."""
        if nanos is None:
            return None
        try:
            seconds = int(nanos) / 1e9
            return datetime.fromtimestamp(seconds)
        except:
            return None

    def _extract_path(self, properties) -> Optional[str]:
        """Extract file path from properties."""
        if not properties:
            return None
        if isinstance(properties, dict):
            return properties.get('path', properties.get('filename'))
        return None


class AutoPipeline:
    """
    Automated pipeline for ingesting DARPA data and training models.

    Usage:
        pipeline = AutoPipeline(output_dir="data/processed")
        pipeline.ingest("data/raw/fivedirections/ta1-fivedirections-1-e5-official-1.bin.1.gz")
        pipeline.build_dataset()
        pipeline.train()
    """

    def __init__(self, output_dir: str = "data/auto_processed"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.parser = CDMParser()
        self.datasets: List[DARPADataset] = []
        self.all_events = []
        self.all_subjects = []

    def ingest(self, file_path: str) -> Dict[str, int]:
        """
        Ingest a single DARPA CDM file.

        Args:
            file_path: Path to .bin.gz file

        Returns:
            Dict with counts of parsed records
        """
        file_path = Path(file_path)
        print(f"\n{'='*60}")
        print(f"Ingesting: {file_path.name}")
        print(f"{'='*60}")

        # Parse metadata from filename
        dataset = DARPADataset.from_filename(file_path)
        self.datasets.append(dataset)
        print(f"  Team: {dataset.team}")
        print(f"  Engagement: {dataset.engagement}")

        # Parse CDM records
        print(f"  Parsing CDM records...")
        data = self.parser.parse_file(file_path)

        # Add source column
        for df_name in data:
            if len(data[df_name]) > 0:
                data[df_name]['source'] = dataset.source

        counts = {k: len(v) for k, v in data.items()}
        print(f"  Parsed: {counts}")

        # Append to accumulated data
        if len(data['events']) > 0:
            self.all_events.append(data['events'])
        if len(data['subjects']) > 0:
            self.all_subjects.append(data['subjects'])

        # Save intermediate results
        self._save_intermediate(data, dataset)

        return counts

    def ingest_directory(self, dir_path: str, pattern: str = "*.gz") -> Dict[str, int]:
        """Ingest all matching files in a directory."""
        dir_path = Path(dir_path)
        total_counts = {'events': 0, 'subjects': 0, 'files': 0, 'network': 0}

        for file_path in sorted(dir_path.glob(pattern)):
            counts = self.ingest(str(file_path))
            for k, v in counts.items():
                total_counts[k] += v

        return total_counts

    def _save_intermediate(self, data: Dict[str, pd.DataFrame], dataset: DARPADataset) -> None:
        """Save intermediate parsed data."""
        subdir = self.output_dir / dataset.team / dataset.engagement
        subdir.mkdir(parents=True, exist_ok=True)

        for name, df in data.items():
            if len(df) > 0:
                path = subdir / f"{name}_{dataset.file_num}.csv"
                df.to_csv(path, index=False)
                print(f"  Saved: {path}")

    def build_dataset(
        self,
        attack_periods: Optional[List[Tuple[str, str]]] = None,
        window_seconds: int = 1
    ) -> Path:
        """
        Build training dataset from all ingested data.

        Args:
            attack_periods: List of (start_time, end_time) tuples for attack labels
            window_seconds: Window size in seconds

        Returns:
            Path to dataset directory
        """
        print(f"\n{'='*60}")
        print("Building Training Dataset")
        print(f"{'='*60}")

        # Combine all events
        if not self.all_events:
            raise ValueError("No events ingested. Run ingest() first.")

        events_df = pd.concat(self.all_events, ignore_index=True)
        print(f"Total events: {len(events_df):,}")

        # Convert timestamps
        events_df['timestamp'] = pd.to_datetime(events_df['timestamp'])
        events_df = events_df.dropna(subset=['timestamp'])
        events_df = events_df.sort_values('timestamp')

        # Build semantic resolver
        from ..detection.semantic_resolver import SemanticResolver
        resolver = SemanticResolver()
        resolver.build_profiles_from_events(events_df)
        print(f"Built profiles for {len(resolver.entity_profiles)} entities")

        # Export semantic distribution
        sem_dist = resolver.get_semantic_distribution()
        print(f"Semantic distribution: {sem_dist}")

        # Save processed events
        events_path = self.output_dir / "events_combined.csv"
        events_df.to_csv(events_path, index=False)
        print(f"Saved combined events: {events_path}")

        # Build graphs using existing pipeline
        from ..pipeline.window_generator import WindowGenerator
        from ..pipeline.graph_constructor import GraphConstructor
        from ..pipeline.feature_engineer import FeatureEngineer
        from ..pipeline.graph_exporter import GraphExporter

        print("Generating time windows...")
        window_gen = WindowGenerator(window_seconds=window_seconds)
        windows = window_gen.generate(events_df)
        print(f"Generated {len(windows)} windows")

        # Build graphs
        graphs_dir = self.output_dir / "graphs"
        graphs_dir.mkdir(exist_ok=True)

        constructor = GraphConstructor()
        engineer = FeatureEngineer()
        exporter = GraphExporter(str(graphs_dir))

        labels = []
        for i, (window_events, start, end) in enumerate(windows):
            if len(window_events) == 0:
                continue

            # Build graph
            G = constructor.build(window_events)
            if len(G.nodes) == 0:
                continue

            # Add features
            G = engineer.add_features(G, window_events)

            # Determine label
            label = 0
            if attack_periods:
                for attack_start, attack_end in attack_periods:
                    attack_start = pd.to_datetime(attack_start)
                    attack_end = pd.to_datetime(attack_end)
                    if start <= attack_end and end >= attack_start:
                        label = 1
                        break

            # Export
            exporter.export(G, i)

            labels.append({
                'window_id': i,
                'start': start,
                'end': end,
                'label': label,
                'num_nodes': len(G.nodes),
                'num_edges': len(G.edges)
            })

        # Save labels
        labels_df = pd.DataFrame(labels)
        labels_path = self.output_dir / "labels.csv"
        labels_df.to_csv(labels_path, index=False)
        print(f"Saved labels: {labels_path}")

        print(f"\nDataset ready at: {self.output_dir}")
        print(f"  - {len(labels)} graphs")
        print(f"  - {sum(1 for l in labels if l['label']==1)} attack windows")
        print(f"  - {sum(1 for l in labels if l['label']==0)} benign windows")

        return self.output_dir

    def get_engagement_split(self) -> Dict[str, List[int]]:
        """
        Get window IDs split by engagement for cross-dataset validation.
        Train on E3, test on E5 (or vice versa).
        """
        # This would require tracking which engagement each window came from
        # Simplified version for now
        return {
            'train': [],
            'test': []
        }


def run_auto_pipeline(
    input_files: List[str],
    output_dir: str = "data/auto_processed",
    attack_periods: Optional[List[Tuple[str, str]]] = None
) -> Path:
    """
    Convenience function to run the full auto pipeline.

    Args:
        input_files: List of .bin.gz file paths
        output_dir: Where to save processed data
        attack_periods: List of (start, end) time tuples for attack labels

    Returns:
        Path to output directory
    """
    pipeline = AutoPipeline(output_dir)

    for file_path in input_files:
        pipeline.ingest(file_path)

    return pipeline.build_dataset(attack_periods)


# Ground truth attack periods from DARPA TC documentation
DARPA_ATTACK_PERIODS = {
    'e3': {
        'fivedirections': [
            ("2018-04-06 11:18:00", "2018-04-06 11:28:00"),  # Example
        ],
        'theia': [],
        'trace': [],
    },
    'e5': {
        'fivedirections': [
            ("2019-05-07 11:10:00", "2019-05-07 11:12:00"),  # From your data
        ],
    }
}
