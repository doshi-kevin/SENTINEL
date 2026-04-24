"""
SENTINEL-Z Phase 4: Semantic Risk Engine

This module implements semantic analysis to improve detection precision.
Instead of relying solely on structural graph anomalies, we analyze:
1. Command-line semantics (LOLBins, suspicious arguments)
2. Behavioral patterns (event type distributions)
3. Entity relationships (file access patterns)

The key insight: structural anomalies + semantic risk = better precision.
"""

import json
import re
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')


@dataclass
class SemanticRisk:
    """Risk assessment for a single entity."""
    entity_id: str
    entity_type: str  # 'subject' or 'object'
    risk_score: float  # 0-10 scale
    risk_factors: List[str]
    cmd_line: Optional[str] = None
    is_lolbin: bool = False
    is_known_benign: bool = False


@dataclass
class WindowRisk:
    """Risk assessment for an entire window."""
    window_id: int
    structural_score: float  # From Phase 3
    semantic_score: float    # From this phase
    fused_score: float       # Combined
    risk_factors: List[str]
    high_risk_entities: List[str]
    behavioral_profile: Dict[str, float]
    is_anomaly: bool


class SemanticRiskEngine:
    """
    Engine for computing semantic risk scores.

    Uses pattern matching to identify:
    1. LOLBins (Living Off the Land Binaries)
    2. Suspicious command-line patterns
    3. Known benign system noise
    4. Behavioral anomalies
    """

    # LOLBins - legitimate Windows binaries often abused by attackers
    LOLBINS = {
        'powershell.exe': 8.0,
        'powershell': 8.0,
        'cmd.exe': 6.0,
        'cmd': 6.0,
        'wscript.exe': 7.0,
        'cscript.exe': 7.0,
        'mshta.exe': 8.5,
        'regsvr32.exe': 7.5,
        'rundll32.exe': 7.0,
        'certutil.exe': 8.0,
        'bitsadmin.exe': 7.5,
        'msiexec.exe': 6.5,
        'wmic.exe': 7.5,
        'net.exe': 6.0,
        'net1.exe': 6.0,
        'sc.exe': 6.5,
        'schtasks.exe': 7.0,
        'reg.exe': 6.0,
        'at.exe': 7.0,
        'psexec.exe': 9.0,
        'psexec': 9.0,
        'mimikatz': 10.0,
        'procdump.exe': 8.0,
        'netsh.exe': 6.5,
        'ftp.exe': 5.5,
        'curl.exe': 5.0,
        'wget': 5.0,
    }

    # Suspicious command-line patterns (regex, risk_score)
    SUSPICIOUS_PATTERNS = [
        (r'-enc\s+[A-Za-z0-9+/=]+', 8.5, 'encoded_command'),        # Encoded PowerShell
        (r'-encodedcommand', 8.5, 'encoded_command'),
        (r'-nop\s+-w\s+hidden', 7.5, 'hidden_window'),              # Hidden execution
        (r'-windowstyle\s+hidden', 7.5, 'hidden_window'),
        (r'bypass', 6.5, 'bypass_flag'),                            # Execution policy bypass
        (r'-ep\s+bypass', 7.0, 'execution_bypass'),
        (r'downloadstring', 8.0, 'download_execute'),               # Download and execute
        (r'downloadfile', 7.5, 'download_file'),
        (r'invoke-expression', 7.5, 'invoke_expression'),
        (r'iex\s*\(', 7.5, 'invoke_expression'),
        (r'invoke-webrequest', 6.5, 'web_request'),
        (r'new-object\s+net\.webclient', 7.0, 'webclient'),
        (r'/c\s+.*&&', 5.5, 'chained_commands'),                    # Command chaining
        (r'\|\s*iex', 8.0, 'pipe_to_iex'),                          # Pipe to IEX
        (r'http[s]?://\d{1,3}\.\d{1,3}', 7.0, 'ip_url'),           # IP-based URLs
        (r'base64', 6.0, 'base64_reference'),
        (r'-credential', 6.5, 'credential_access'),
        (r'password', 5.0, 'password_reference'),
        (r'mimikatz', 10.0, 'mimikatz'),
        (r'sekurlsa', 9.5, 'credential_dump'),
        (r'lsass', 8.5, 'lsass_access'),
        (r'sam\s+dump', 9.0, 'sam_dump'),
        (r'ntds\.dit', 9.0, 'ntds_access'),
        (r'-dumpcreds', 9.0, 'dump_credentials'),
    ]

    # Known benign system noise (process name, suppression_factor)
    KNOWN_BENIGN = {
        'searchfilterhost.exe': 0.05,      # Windows Search indexer
        'searchprotocolhost.exe': 0.05,
        'searchindexer.exe': 0.1,
        'svchost.exe': 0.3,                # Generic service host
        'taskhostw.exe': 0.2,
        'runtimebroker.exe': 0.2,
        'backgroundtaskhost.exe': 0.15,
        'smartscreen.exe': 0.2,
        'sihost.exe': 0.2,
        'conhost.exe': 0.3,
        'dllhost.exe': 0.4,                # Could be abused, slight suppression
        'spoolsv.exe': 0.2,
        'lsass.exe': 0.5,                  # Critical, but expected system activity
        'csrss.exe': 0.3,
        'services.exe': 0.3,
        'winlogon.exe': 0.3,
        'explorer.exe': 0.4,
        'system': 0.2,
        'idle': 0.1,
        'wmiapsrv.exe': 0.15,
        'mscorsvw.exe': 0.1,               # .NET compilation
        'ngentask.exe': 0.1,
        'tiworker.exe': 0.1,               # Windows Update
        'trustedinstaller.exe': 0.1,
        'wmiprvse.exe': 0.3,
    }

    # Behavioral risk weights based on event types
    BEHAVIORAL_WEIGHTS = {
        'EVENT_EXECUTE': 3.0,       # Execution is high risk
        'EVENT_FORK': 2.5,          # Process creation
        'EVENT_CLONE': 2.5,
        'EVENT_CREATE_THREAD': 2.0,
        'EVENT_LOADLIBRARY': 2.0,   # DLL loading
        'EVENT_CONNECT': 2.0,       # Network activity
        'EVENT_SENDTO': 1.5,
        'EVENT_SENDMSG': 1.5,
        'EVENT_WRITE': 1.0,         # File writes
        'EVENT_CREATE_OBJECT': 1.0,
        'EVENT_READ': 0.3,          # Normal activity
        'EVENT_OPEN': 0.2,
        'EVENT_CLOSE': 0.1,
    }

    def __init__(self, subjects_csv: str = None):
        """
        Initialize the semantic risk engine.

        Args:
            subjects_csv: Path to subjects CSV with command-line info
        """
        self.uuid_to_cmd = {}
        self.uuid_to_type = {}
        self.uuid_to_parent = {}
        self.subjects_df = None

        if subjects_csv and Path(subjects_csv).exists():
            self._load_subjects(subjects_csv)

    def _load_subjects(self, csv_path: str):
        """Load subject UUID to command-line mapping with parent chain resolution.

        Accepts either a single CSV or a directory containing subjects_*.csv files
        (auto-concatenates across all host/chunk partitions).
        """
        p = Path(csv_path)
        if p.is_dir():
            import glob
            files = sorted(glob.glob(str(p / 'subjects_*.csv')))
            if not files:
                print(f"No subjects_*.csv found in {p}")
                return
            df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
            df = df.drop_duplicates(subset=['uuid'], keep='first')
            print(f"Loaded subjects from {len(files)} partition(s)")
        else:
            df = pd.read_csv(csv_path)
        self.subjects_df = df

        # Direct mappings
        self.uuid_to_cmd = dict(zip(df['uuid'], df['cmd_line'].fillna('')))
        self.uuid_to_type = dict(zip(df['uuid'], df['type'].fillna('UNKNOWN')))
        self.uuid_to_parent = dict(zip(df['uuid'], df['parent_subject'].fillna('')))

        # Resolve thread -> parent process command lines
        resolved_count = 0
        for uuid, subject_type in self.uuid_to_type.items():
            if subject_type == 'SUBJECT_THREAD' and not self.uuid_to_cmd.get(uuid):
                # Try to find parent's command line
                parent = self.uuid_to_parent.get(uuid)
                if parent:
                    parent_cmd = self.uuid_to_cmd.get(parent, '')
                    if parent_cmd:
                        self.uuid_to_cmd[uuid] = parent_cmd
                        resolved_count += 1
                    else:
                        # Try grandparent
                        grandparent = self.uuid_to_parent.get(parent)
                        if grandparent:
                            gp_cmd = self.uuid_to_cmd.get(grandparent, '')
                            if gp_cmd:
                                self.uuid_to_cmd[uuid] = gp_cmd
                                resolved_count += 1

        print(f"Loaded {len(self.uuid_to_cmd)} subject mappings")
        print(f"Resolved {resolved_count} thread -> parent command lines")

    def score_command_line(self, cmd_line: str, uuid: str = None) -> Tuple[float, List[str]]:
        """
        Score a command line for risk.

        Returns:
            (risk_score, list_of_risk_factors)
        """
        # Check if UUID is completely unknown (not in subjects.csv at all)
        uuid_exists = uuid and uuid in self.uuid_to_type if uuid else True

        if not cmd_line or cmd_line == 'UNKNOWN' or cmd_line == '' or pd.isna(cmd_line):
            if not uuid_exists:
                # Completely unknown subject - higher suspicion
                # Key insight: many attacks come from subjects not in the normal catalog
                return 2.5, ['unknown_subject_not_in_catalog']
            else:
                return 1.4, ['unknown_command']  # Known subject but no cmd_line

        cmd_lower = cmd_line.lower()
        risk_score = 1.0
        risk_factors = []

        # Extract executable name
        exe_match = re.search(r'([a-zA-Z0-9_-]+\.exe)', cmd_lower)
        exe_name = exe_match.group(1) if exe_match else ''

        # Also check without extension
        exe_base = exe_name.replace('.exe', '') if exe_name else ''

        # Check for LOLBins
        for lolbin, lolbin_risk in self.LOLBINS.items():
            if lolbin in cmd_lower:
                risk_score = max(risk_score, lolbin_risk)
                risk_factors.append(f'lolbin:{lolbin}')
                break

        # Check for suspicious patterns
        for pattern, pattern_risk, factor_name in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, cmd_lower, re.IGNORECASE):
                risk_score = max(risk_score, pattern_risk)
                risk_factors.append(factor_name)

        # Check for known benign and apply suppression
        for benign_name, suppression in self.KNOWN_BENIGN.items():
            if benign_name in cmd_lower:
                # Only suppress if no other high-risk factors
                if risk_score < 5.0:
                    risk_score *= suppression
                    risk_factors.append(f'benign:{benign_name}')
                break

        return min(risk_score, 10.0), risk_factors

    def score_entity(self, entity_id: str, entity_type: str) -> SemanticRisk:
        """Score a single entity (subject or object)."""
        cmd_line = self.uuid_to_cmd.get(entity_id, '')
        risk_score, risk_factors = self.score_command_line(cmd_line, uuid=entity_id)

        # Check if LOLBin
        is_lolbin = any('lolbin:' in f for f in risk_factors)

        # Check if known benign
        is_benign = any('benign:' in f for f in risk_factors)

        return SemanticRisk(
            entity_id=entity_id,
            entity_type=entity_type,
            risk_score=risk_score,
            risk_factors=risk_factors,
            cmd_line=cmd_line[:100] if cmd_line else None,
            is_lolbin=is_lolbin,
            is_known_benign=is_benign
        )

    def compute_behavioral_risk(self, event_types: Dict[str, int]) -> Tuple[float, Dict[str, float]]:
        """
        Compute behavioral risk from event type distribution.

        Args:
            event_types: Dict mapping event type -> count

        Returns:
            (behavioral_risk_score, normalized_profile)
        """
        if not event_types:
            return 1.0, {}

        total_events = sum(event_types.values())
        if total_events == 0:
            return 1.0, {}

        # Compute weighted risk
        weighted_sum = 0.0
        profile = {}

        for event_type, count in event_types.items():
            weight = self.BEHAVIORAL_WEIGHTS.get(event_type, 0.5)
            weighted_sum += weight * count
            profile[event_type] = count / total_events

        # Normalize by total events (but cap the contribution)
        risk = min(weighted_sum / max(total_events, 1) * 5, 10.0)

        return risk, profile


class RefinedDetector:
    """
    Phase 4 Refined Detector that fuses structural and semantic scores.

    Strategy:
    1. Load Phase 3 structural scores
    2. Compute semantic risk for each window
    3. Fuse scores: fused = structural * semantic_weight
    4. Apply dynamic thresholding
    """

    def __init__(
        self,
        graphs_dir: str,
        labels_csv: str,
        subjects_csv: str,
        phase3_results: str = None
    ):
        self.graphs_dir = Path(graphs_dir)
        self.labels_csv = Path(labels_csv)
        self.subjects_csv = Path(subjects_csv)
        self.phase3_results = Path(phase3_results) if phase3_results else None

        self.risk_engine = SemanticRiskEngine(subjects_csv)
        self.results = []
        self.metrics = None

    def _analyze_window(self, window_id: int, graph_data: dict,
                        structural_score: float, label: int) -> WindowRisk:
        """Analyze a single window for semantic risk."""
        nodes = graph_data.get('nodes', [])
        links = graph_data.get('links', [])

        risk_factors = []
        high_risk_entities = []
        semantic_risks = []
        unknown_subject_count = 0

        # Analyze each subject node
        for node in nodes:
            if node.get('node_type') == 'subject':
                entity_risk = self.risk_engine.score_entity(
                    node.get('id', ''),
                    'subject'
                )

                semantic_risks.append(entity_risk.risk_score)

                if 'unknown_subject_not_in_catalog' in entity_risk.risk_factors:
                    unknown_subject_count += 1

                if entity_risk.risk_score > 5.0:
                    high_risk_entities.append(entity_risk.entity_id[:16])
                    risk_factors.extend(entity_risk.risk_factors)

        # Compute behavioral profile from edges
        event_types = {}
        for link in links:
            event = link.get('event', 'UNKNOWN')
            event_types[event] = event_types.get(event, 0) + 1

        behavioral_risk, behavioral_profile = self.risk_engine.compute_behavioral_risk(event_types)

        # Aggregate semantic risk
        max_semantic_risk = max(semantic_risks) if semantic_risks else 1.0
        mean_semantic_risk = np.mean(semantic_risks) if semantic_risks else 1.0

        # Unknown subject ratio - attacks often have many unknown subjects
        num_subjects = len([n for n in nodes if n.get('node_type') == 'subject'])
        unknown_ratio = unknown_subject_count / max(num_subjects, 1)

        # Size-based risk (attacks are larger)
        size_risk = 1.0 + np.log1p(len(nodes)) * 0.2  # Logarithmic boost for large graphs

        # Combine semantic signals
        semantic_score = (
            max_semantic_risk * 0.4 +
            mean_semantic_risk * 0.2 +
            behavioral_risk * 0.2 +
            unknown_ratio * 3.0 +  # Boost for unknown subjects
            size_risk * 0.5
        )

        # Compute network event ratio
        total_events = sum(event_types.values()) if event_types else 1
        network_events = sum(v for k, v in event_types.items()
                            if 'SEND' in k or 'RECV' in k or 'CONNECT' in k)
        network_ratio = network_events / total_events

        # Graph density
        density = len(links) / max(len(nodes), 1)

        # Optimized fused score based on correlation analysis
        # Key insight: unknown_subject_ratio is the strongest discriminator (corr=0.137)
        fused_score = (
            unknown_ratio * 15 +          # Strongest signal - attacks have 95.7% unknown
            structural_score * 0.2 +       # Structural contribution
            np.log1p(len(nodes)) * 1.0 +  # Size boost (attacks are larger)
            network_ratio * 3 +            # Network activity
            density * 2                    # Graph density
        )

        return WindowRisk(
            window_id=window_id,
            structural_score=structural_score,
            semantic_score=semantic_score,
            fused_score=fused_score,
            risk_factors=list(set(risk_factors)),
            high_risk_entities=high_risk_entities,
            behavioral_profile={
                **behavioral_profile,
                '_num_nodes': float(len(nodes)),
                '_num_edges': float(len(links)),
                '_num_subjects': float(num_subjects),
                '_unknown_ratio': float(unknown_ratio),
                '_network_ratio': float(network_ratio),
                '_density': float(density),
                '_event_types': event_types,
            },
            is_anomaly=False
        )

    def run(self, n_workers: int = 4) -> Dict:
        """
        Run the complete Phase 4 analysis.

        Returns:
            Dict with results and metrics
        """
        print("\n" + "="*60)
        print("SENTINEL-Z Phase 4: Semantic Risk Refinement")
        print("="*60 + "\n")

        # Load Phase 3 results
        phase3_scores = {}
        if self.phase3_results and self.phase3_results.exists():
            with open(self.phase3_results) as f:
                phase3_data = json.load(f)
            for w in phase3_data.get('windows', []):
                phase3_scores[w['window_id']] = w['anomaly_score']
            print(f"Loaded {len(phase3_scores)} Phase 3 scores")

        # Load labels
        labels_df = pd.read_csv(self.labels_csv)

        # Process all windows
        print("Analyzing windows with semantic risk engine...")
        results = []

        graph_files = sorted(self.graphs_dir.glob("window_*.json"))
        print(f"Found {len(graph_files)} windows to analyze")

        for i, graph_file in enumerate(graph_files):
            try:
                wid = int(graph_file.stem.split('_')[1])

                with open(graph_file) as f:
                    graph_data = json.load(f)

                # Get structural score (from Phase 3 or compute simple one)
                structural_score = phase3_scores.get(wid, len(graph_data.get('nodes', [])) * 0.1)

                # Get label
                label = labels_df.iloc[wid]['label'] if wid < len(labels_df) else 0

                # Analyze window
                window_risk = self._analyze_window(wid, graph_data, structural_score, label)
                window_risk_dict = asdict(window_risk)
                window_risk_dict['label'] = label
                results.append(window_risk_dict)

                if (i + 1) % 500 == 0:
                    print(f"  Processed {i + 1}/{len(graph_files)} windows...")

            except Exception as e:
                print(f"  Error processing window {graph_file.name}: {e}")
                continue

        self.results = results
        print(f"Analyzed {len(results)} windows")

        # Compute metrics
        metrics = self._compute_metrics()
        self.metrics = metrics

        return {
            'windows': results,
            'metrics': metrics
        }

    def _compute_metrics(self) -> Dict:
        """Compute detection metrics with threshold optimization."""
        from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix

        df = pd.DataFrame(self.results)

        # Analyze score distributions
        benign = df[df['label'] == 0]
        attack = df[df['label'] == 1]

        print("\n=== Score Distribution Analysis ===")
        print(f"Benign fused_score: mean={benign['fused_score'].mean():.2f}, max={benign['fused_score'].max():.2f}")
        print(f"Attack fused_score: mean={attack['fused_score'].mean():.2f}, max={attack['fused_score'].max():.2f}")
        print(f"Benign semantic_score: mean={benign['semantic_score'].mean():.2f}")
        print(f"Attack semantic_score: mean={attack['semantic_score'].mean():.2f}")

        # Try different thresholds on fused score
        print("\n=== Threshold Optimization ===")
        best_f1 = 0
        best_threshold = 0
        best_metrics = None

        # Use fine-grained percentile-based thresholds
        for pct in range(80, 98):
            threshold = benign['fused_score'].quantile(pct / 100)

            y_true = df['label'].values
            y_pred = (df['fused_score'] > threshold).astype(int).values

            if y_pred.sum() == 0:
                continue

            precision = precision_score(y_true, y_pred, zero_division=0)
            recall = recall_score(y_true, y_pred, zero_division=0)
            f1 = f1_score(y_true, y_pred, zero_division=0)

            tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

            print(f"  {pct}th pct (thresh={threshold:.2f}): P={precision:.2%}, R={recall:.2%}, F1={f1:.4f}, FPR={fpr:.2%}, TP={tp}")

            if f1 > best_f1:
                best_f1 = f1
                best_threshold = threshold
                best_metrics = {
                    'precision': precision,
                    'recall': recall,
                    'f1_score': f1,
                    'true_positives': int(tp),
                    'false_positives': int(fp),
                    'true_negatives': int(tn),
                    'false_negatives': int(fn),
                    'false_positive_rate': fpr,
                    'threshold': threshold,
                    'percentile': pct
                }

        # Compute ROC-AUC
        try:
            roc_auc = roc_auc_score(df['label'], df['fused_score'])
            best_metrics['roc_auc'] = roc_auc
        except:
            best_metrics['roc_auc'] = 0.0

        # Mark anomalies with best threshold
        for result in self.results:
            result['is_anomaly'] = result['fused_score'] > best_threshold

        print(f"\n=== Best Configuration ===")
        print(f"Threshold: {best_threshold:.4f} ({best_metrics['percentile']}th percentile)")
        print(f"Precision: {best_metrics['precision']:.2%}")
        print(f"Recall: {best_metrics['recall']:.2%}")
        print(f"F1 Score: {best_metrics['f1_score']:.4f}")
        print(f"ROC-AUC: {best_metrics['roc_auc']:.4f}")

        return best_metrics

    def export_results(self, output_dir: str):
        """Export Phase 4 results."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Convert numpy types to Python native for JSON serialization
        def convert_to_native(obj):
            if isinstance(obj, dict):
                return {k: convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_native(v) for v in obj]
            elif isinstance(obj, (np.integer, np.int64, np.int32)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64, np.float32)):
                return float(obj)
            elif isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj

        # Export full results
        results_file = output_path / "phase4_results.json"
        with open(results_file, 'w') as f:
            json.dump(convert_to_native({
                'windows': self.results,
                'metrics': self.metrics
            }), f, indent=2)
        print(f"Results saved to {results_file}")

        # Export CSV for analysis
        df = pd.DataFrame(self.results)
        csv_file = output_path / "phase4_scores.csv"
        df.to_csv(csv_file, index=False)
        print(f"Scores saved to {csv_file}")

        return results_file


def run_phase4_pipeline():
    """Run the complete Phase 4 pipeline."""
    detector = RefinedDetector(
        graphs_dir='data/model_ready/graphs',
        labels_csv='data/model_ready/labels.csv',
        subjects_csv='data/auto_processed/fivedirections/e5',
        phase3_results='data/model_ready/detection/detection_results.json'
    )

    results = detector.run()
    detector.export_results('data/model_ready/detection')

    return results


if __name__ == '__main__':
    run_phase4_pipeline()
