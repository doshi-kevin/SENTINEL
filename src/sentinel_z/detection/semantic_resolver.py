"""
Semantic Entity Resolver

The CORE innovation of SENTINEL-Z: Transform opaque UUIDs into semantic entities
based on their BEHAVIORAL patterns, not just metadata.

Key Insight: We don't need file paths or process names to understand semantics.
The BEHAVIOR of an entity reveals its semantic role:
- A node that spawns many children = orchestrator process
- A node that reads many files = scanner/indexer
- A node with external network connections = network service
- A node that only gets written to = log/data sink

This enables ZERO-SHOT transfer: the semantic roles are universal across systems.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


class SemanticEntityType(Enum):
    """
    Semantic entity types based on behavioral patterns.
    These are UNIVERSAL across systems - the key to zero-shot transfer.
    """
    # Process semantic types (subjects)
    ORCHESTRATOR = "orchestrator"       # Spawns many child processes
    WORKER = "worker"                   # Spawned by orchestrator, does actual work
    SERVICE = "service"                 # Long-running, handles requests
    SCANNER = "scanner"                 # Reads many files, discovery behavior
    WRITER = "writer"                   # Primarily writes/modifies files
    NETWORK_CLIENT = "network_client"   # Initiates outbound connections
    NETWORK_SERVER = "network_server"   # Accepts inbound connections
    EXECUTOR = "executor"               # Executes other processes
    UNKNOWN_PROCESS = "unknown_process"

    # Object semantic types (files, network, etc.)
    CONFIG_FILE = "config_file"         # Read at startup, rarely written
    LOG_FILE = "log_file"               # Append-only writes
    DATA_FILE = "data_file"             # Read/write mix
    EXECUTABLE = "executable"           # Gets executed
    TEMP_FILE = "temp_file"             # Short-lived, created and deleted
    SENSITIVE_FILE = "sensitive_file"   # Accessed by privileged processes
    EXTERNAL_HOST = "external_host"     # External network destination
    INTERNAL_HOST = "internal_host"     # Internal network destination
    UNKNOWN_OBJECT = "unknown_object"


@dataclass
class EntityBehaviorProfile:
    """Behavioral profile computed from graph structure."""
    uuid: str
    node_type: str  # "subject" or "object"

    # Degree metrics
    in_degree: int = 0
    out_degree: int = 0

    # Event type distributions
    event_types_initiated: Dict[str, int] = None  # For subjects
    event_types_received: Dict[str, int] = None   # For objects

    # Temporal patterns
    first_seen: Optional[float] = None
    last_seen: Optional[float] = None
    activity_duration: float = 0.0
    burst_count: int = 0

    # Relationship patterns
    unique_targets: int = 0      # How many different objects this subject touches
    unique_sources: int = 0      # How many different subjects touch this object

    # Network indicators
    has_network_activity: bool = False
    is_external: bool = False

    def __post_init__(self):
        if self.event_types_initiated is None:
            self.event_types_initiated = {}
        if self.event_types_received is None:
            self.event_types_received = {}


class SemanticResolver:
    """
    Resolves UUIDs to semantic entity types based on behavioral analysis.

    This is what enables zero-shot detection:
    - Train on semantic types, not specific entities
    - The same semantic patterns appear in any system
    - Attacks manifest as unusual semantic relationships
    """

    # Event type categories for semantic inference
    EXEC_EVENTS = {"EVENT_EXECUTE", "EVENT_FORK", "EVENT_CLONE"}
    READ_EVENTS = {"EVENT_READ", "EVENT_OPEN", "EVENT_RECVMSG", "EVENT_RECVFROM"}
    WRITE_EVENTS = {"EVENT_WRITE", "EVENT_CREATE", "EVENT_MODIFY_PROCESS"}
    NETWORK_EVENTS = {"EVENT_SENDMSG", "EVENT_SENDTO", "EVENT_RECVMSG", "EVENT_RECVFROM"}

    def __init__(self):
        self.entity_profiles: Dict[str, EntityBehaviorProfile] = {}
        self.semantic_cache: Dict[str, SemanticEntityType] = {}

    def build_profiles_from_events(self, events_df: pd.DataFrame) -> None:
        """
        Build behavioral profiles from raw event data.

        Args:
            events_df: DataFrame with columns [subject, predicate_object, type, timestamp]
        """
        profiles = defaultdict(lambda: EntityBehaviorProfile(uuid="", node_type=""))

        for _, row in events_df.iterrows():
            subject = str(row['subject'])
            obj = str(row.get('predicate_object', ''))
            event_type = row['type']
            timestamp = pd.to_datetime(row['timestamp']).timestamp() if pd.notna(row['timestamp']) else None

            # Update subject profile
            if subject not in self.entity_profiles:
                profiles[subject] = EntityBehaviorProfile(uuid=subject, node_type="subject")

            prof = profiles[subject]
            prof.out_degree += 1
            prof.event_types_initiated[event_type] = prof.event_types_initiated.get(event_type, 0) + 1

            if obj and obj != 'None' and obj != 'nan':
                prof.unique_targets += 1

            if event_type in self.NETWORK_EVENTS:
                prof.has_network_activity = True

            if timestamp:
                if prof.first_seen is None or timestamp < prof.first_seen:
                    prof.first_seen = timestamp
                if prof.last_seen is None or timestamp > prof.last_seen:
                    prof.last_seen = timestamp

            # Update object profile
            if obj and obj != 'None' and obj != 'nan':
                if obj not in profiles:
                    profiles[obj] = EntityBehaviorProfile(uuid=obj, node_type="object")

                obj_prof = profiles[obj]
                obj_prof.in_degree += 1
                obj_prof.event_types_received[event_type] = obj_prof.event_types_received.get(event_type, 0) + 1
                obj_prof.unique_sources += 1

                if timestamp:
                    if obj_prof.first_seen is None or timestamp < obj_prof.first_seen:
                        obj_prof.first_seen = timestamp
                    if obj_prof.last_seen is None or timestamp > obj_prof.last_seen:
                        obj_prof.last_seen = timestamp

        # Compute activity duration
        for uuid, prof in profiles.items():
            if prof.first_seen and prof.last_seen:
                prof.activity_duration = prof.last_seen - prof.first_seen

        self.entity_profiles = dict(profiles)

    def resolve_semantic_type(self, uuid: str) -> SemanticEntityType:
        """
        Resolve a UUID to its semantic type based on behavioral profile.

        This is the CORE of zero-shot capability: semantic types are
        determined by behavior, not by knowing what the entity "is".
        """
        if uuid in self.semantic_cache:
            return self.semantic_cache[uuid]

        if uuid not in self.entity_profiles:
            return SemanticEntityType.UNKNOWN_PROCESS

        profile = self.entity_profiles[uuid]

        if profile.node_type == "subject":
            sem_type = self._resolve_subject_type(profile)
        else:
            sem_type = self._resolve_object_type(profile)

        self.semantic_cache[uuid] = sem_type
        return sem_type

    def _resolve_subject_type(self, profile: EntityBehaviorProfile) -> SemanticEntityType:
        """Resolve semantic type for a subject (process)."""
        events = profile.event_types_initiated

        # Count event categories
        exec_count = sum(events.get(e, 0) for e in self.EXEC_EVENTS)
        read_count = sum(events.get(e, 0) for e in self.READ_EVENTS)
        write_count = sum(events.get(e, 0) for e in self.WRITE_EVENTS)
        network_count = sum(events.get(e, 0) for e in self.NETWORK_EVENTS)

        total = exec_count + read_count + write_count + network_count + 1  # +1 to avoid div by zero

        # Decision logic based on behavioral patterns
        if exec_count > 5 and exec_count / total > 0.3:
            return SemanticEntityType.ORCHESTRATOR

        if profile.has_network_activity and network_count / total > 0.3:
            if profile.activity_duration > 60:  # Long-running
                return SemanticEntityType.NETWORK_SERVER
            return SemanticEntityType.NETWORK_CLIENT

        if read_count > 10 and read_count / total > 0.5:
            return SemanticEntityType.SCANNER

        if write_count > read_count and write_count / total > 0.4:
            return SemanticEntityType.WRITER

        if exec_count > 0:
            return SemanticEntityType.EXECUTOR

        if profile.activity_duration > 30:
            return SemanticEntityType.SERVICE

        return SemanticEntityType.WORKER

    def _resolve_object_type(self, profile: EntityBehaviorProfile) -> SemanticEntityType:
        """Resolve semantic type for an object (file, network endpoint, etc.)."""
        events = profile.event_types_received

        read_count = sum(events.get(e, 0) for e in self.READ_EVENTS)
        write_count = sum(events.get(e, 0) for e in self.WRITE_EVENTS)
        exec_count = sum(events.get(e, 0) for e in self.EXEC_EVENTS)
        network_count = sum(events.get(e, 0) for e in self.NETWORK_EVENTS)

        # Check if it's a network endpoint
        if network_count > 0:
            if profile.is_external:
                return SemanticEntityType.EXTERNAL_HOST
            return SemanticEntityType.INTERNAL_HOST

        # Check if it's an executable
        if exec_count > 0:
            return SemanticEntityType.EXECUTABLE

        # Analyze read/write patterns
        total = read_count + write_count + 1

        if write_count == 0 and read_count > 0:
            # Read-only: likely config or data
            if profile.unique_sources == 1:
                return SemanticEntityType.CONFIG_FILE
            return SemanticEntityType.DATA_FILE

        if write_count > 0 and read_count == 0:
            # Write-only: likely log
            return SemanticEntityType.LOG_FILE

        if profile.activity_duration < 5 and profile.unique_sources <= 2:
            # Short-lived
            return SemanticEntityType.TEMP_FILE

        if profile.unique_sources > 3:
            # Accessed by many processes - could be sensitive
            return SemanticEntityType.SENSITIVE_FILE

        return SemanticEntityType.DATA_FILE

    def get_semantic_distribution(self) -> Dict[SemanticEntityType, int]:
        """Get distribution of semantic types in the current dataset."""
        distribution = defaultdict(int)
        for uuid in self.entity_profiles:
            sem_type = self.resolve_semantic_type(uuid)
            distribution[sem_type] += 1
        return dict(distribution)

    def export_semantic_mapping(self) -> pd.DataFrame:
        """Export UUID to semantic type mapping as DataFrame."""
        rows = []
        for uuid, profile in self.entity_profiles.items():
            sem_type = self.resolve_semantic_type(uuid)
            rows.append({
                'uuid': uuid,
                'node_type': profile.node_type,
                'semantic_type': sem_type.value,
                'in_degree': profile.in_degree,
                'out_degree': profile.out_degree,
                'activity_duration': profile.activity_duration,
                'unique_connections': profile.unique_targets + profile.unique_sources
            })
        return pd.DataFrame(rows)


class SemanticEdgeType(Enum):
    """
    Semantic edge types - what the relationship MEANS, not what event caused it.
    """
    # Information flow edges
    READS_FROM = "reads_from"           # Subject reads object
    WRITES_TO = "writes_to"             # Subject writes to object
    EXECUTES = "executes"               # Subject executes object
    SPAWNS = "spawns"                   # Subject creates child subject

    # Network edges
    CONNECTS_TO = "connects_to"         # Outbound connection
    RECEIVES_FROM = "receives_from"     # Inbound connection

    # Control flow edges
    SIGNALS = "signals"                 # Inter-process signaling
    MODIFIES = "modifies"               # Process modification

    # Derived semantic edges (inferred from patterns)
    EXFILTRATES_TO = "exfiltrates_to"   # Data flow to external
    INFILTRATES_FROM = "infiltrates_from"  # Data flow from external
    PRIVILEGE_ESCALATES = "privilege_escalates"  # Privilege flow anomaly


def map_event_to_semantic_edge(event_type: str) -> SemanticEdgeType:
    """Map raw CDM event types to semantic edge types."""
    mapping = {
        "EVENT_READ": SemanticEdgeType.READS_FROM,
        "EVENT_OPEN": SemanticEdgeType.READS_FROM,
        "EVENT_WRITE": SemanticEdgeType.WRITES_TO,
        "EVENT_CREATE": SemanticEdgeType.WRITES_TO,
        "EVENT_EXECUTE": SemanticEdgeType.EXECUTES,
        "EVENT_FORK": SemanticEdgeType.SPAWNS,
        "EVENT_CLONE": SemanticEdgeType.SPAWNS,
        "EVENT_SENDMSG": SemanticEdgeType.CONNECTS_TO,
        "EVENT_SENDTO": SemanticEdgeType.CONNECTS_TO,
        "EVENT_RECVMSG": SemanticEdgeType.RECEIVES_FROM,
        "EVENT_RECVFROM": SemanticEdgeType.RECEIVES_FROM,
        "EVENT_SIGNAL": SemanticEdgeType.SIGNALS,
        "EVENT_MODIFY_PROCESS": SemanticEdgeType.MODIFIES,
    }
    return mapping.get(event_type, SemanticEdgeType.READS_FROM)
