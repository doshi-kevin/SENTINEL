"""
Story Builder: Signal-driven Narrative Generation for Attack Campaigns

Transforms Phase 4 WindowRisk results into human-readable attack narratives.
Uses deterministic templates (NO LLMs) driven by ACTUAL detection signals:

    - unknown_subject_ratio: novel processes not in system catalog (strongest signal, ×15)
    - behavioral_profile: event-type distribution (EXEC, READ, WRITE, NETWORK)
    - graph_density, num_nodes: structural anomaly indicators
    - network_ratio: external-connection activity
    - risk_factors: LOLBin/suspicious-pattern flags (when they fire)
    - high_risk_entities: UUIDs of anomalous subjects

Narratives describe WHAT drove the detection, not a generic template.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict


@dataclass
class AttackNarrative:
    """Signal-driven narrative for one 1-second window."""
    window_id: int
    stage: str
    summary: str
    risk_factors: List[str]
    high_risk_entities: List[str]
    mitre_hints: List[str]
    raw_score: float
    confidence: str
    signals: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CampaignStory:
    """Narrative for a multi-window attack campaign."""
    progression_id: str
    start_time: str
    end_time: str
    duration_seconds: float
    title: str
    narrative: str
    chapters: List[AttackNarrative]
    mitre_tactics: List[str]

    def to_dict(self) -> dict:
        return {
            'progression_id': self.progression_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_seconds': self.duration_seconds,
            'title': self.title,
            'narrative': self.narrative,
            'chapters': [ch.to_dict() for ch in self.chapters],
            'mitre_tactics': self.mitre_tactics,
        }


class StoryBuilder:
    """Builds attack narratives from real Phase 4 signals."""

    STAGE_TO_MITRE = {
        'reconnaissance':    'TA0043',
        'execution':         'TA0002',
        'persistence':       'TA0003',
        'privilege_escalation': 'TA0004',
        'defense_evasion':   'TA0005',
        'credential_access': 'TA0006',
        'discovery':         'TA0007',
        'lateral_movement':  'TA0008',
        'collection':        'TA0009',
        'exfiltration':      'TA0010',
        'command_and_control': 'TA0011',
        'impact':            'TA0040',
    }

    NETWORK_EVENTS = {'SENDMSG', 'SENDTO', 'RECVMSG', 'RECVFROM', 'CONNECT', 'ACCEPT'}
    EXEC_EVENTS    = {'EXECUTE', 'FORK', 'CLONE', 'EXIT', 'MODIFY_PROCESS'}
    READ_EVENTS    = {'READ', 'OPEN', 'MMAP', 'LOADLIBRARY'}
    WRITE_EVENTS   = {'WRITE', 'CREATE', 'MODIFY_FILE', 'RENAME', 'UNLINK'}

    def _classify_stage(self, window_risk: dict) -> str:
        """Infer attack stage from actual event-type distribution.

        Priority order follows kill-chain logic: network activity -> exfiltration;
        exec-heavy -> execution; read-heavy without writes -> discovery; etc.
        """
        profile = window_risk.get('behavioral_profile', {}) or {}
        event_types = profile.get('_event_types', {}) or {}

        if not event_types:
            return 'reconnaissance'

        total = sum(event_types.values()) or 1
        buckets = {'exec': 0, 'read': 0, 'write': 0, 'network': 0}
        for evt, count in event_types.items():
            evt_short = evt.replace('EVENT_', '').upper()
            if evt_short in self.NETWORK_EVENTS:
                buckets['network'] += count
            elif evt_short in self.EXEC_EVENTS:
                buckets['exec'] += count
            elif evt_short in self.READ_EVENTS:
                buckets['read'] += count
            elif evt_short in self.WRITE_EVENTS:
                buckets['write'] += count

        ratios = {k: v / total for k, v in buckets.items()}
        network_ratio = profile.get('_network_ratio', ratios['network'])
        unknown_ratio = profile.get('_unknown_ratio', 0.0)

        if network_ratio > 0.3:
            return 'exfiltration' if ratios['read'] > 0.15 else 'command_and_control'
        if ratios['exec'] > 0.25 and unknown_ratio > 0.5:
            return 'execution'
        if ratios['write'] > 0.3:
            return 'persistence'
        if ratios['read'] > 0.4 and ratios['write'] < 0.1:
            return 'discovery'
        if unknown_ratio > 0.7:
            return 'lateral_movement'
        return 'reconnaissance'

    def _confidence(self, fused_score: float, threshold: float = 40.0) -> str:
        """Confidence from fused_score (typical attack range: 25-80)."""
        if fused_score < threshold * 0.7:
            return 'low'
        if fused_score < threshold * 1.2:
            return 'medium'
        return 'high'

    def _rf_confidence(self, rf_score: float, threshold: float) -> str:
        """Confidence from RF probability score (0-1 range)."""
        margin = rf_score - threshold
        if margin < 0:
            return 'low'
        if margin < 0.15:
            return 'medium'
        return 'high'

    def _format_entities(self, entities: List[str], limit: int = 3) -> str:
        """Short-form entity IDs (they're UUIDs; we only show first 8 chars)."""
        if not entities:
            return "no specific entity"
        shown = [e[:8] if len(e) > 8 else e for e in entities[:limit]]
        if len(entities) > limit:
            return f"{', '.join(shown)} +{len(entities) - limit} more"
        return ', '.join(shown)

    def _build_summary(self, wr: dict, stage: str) -> Tuple[str, Dict[str, float]]:
        """Construct a one-sentence summary from actual signals.

        Returns (summary_text, signals_dict).
        """
        profile = wr.get('behavioral_profile', {}) or {}
        unknown_ratio = profile.get('_unknown_ratio', 0.0)
        network_ratio = profile.get('_network_ratio', 0.0)
        density       = profile.get('_density', 0.0)
        num_nodes     = int(profile.get('_num_nodes', 0))
        num_subjects  = int(profile.get('_num_subjects', 0))
        fused         = wr.get('fused_score', 0.0)
        structural    = wr.get('structural_score', 0.0)
        entities      = wr.get('high_risk_entities', []) or []
        risk_factors  = wr.get('risk_factors', []) or []

        signals = {
            'unknown_ratio': round(unknown_ratio, 3),
            'network_ratio': round(network_ratio, 3),
            'density':       round(density, 3),
            'num_nodes':     num_nodes,
            'num_subjects':  num_subjects,
            'fused_score':   round(fused, 2),
            'structural':    round(structural, 2),
        }

        unknown_pct = int(unknown_ratio * 100)
        net_pct     = int(network_ratio * 100)
        entity_str  = self._format_entities(entities)
        lolbin_hits = [f.split(':', 1)[1] for f in risk_factors if f.startswith('lolbin:')]

        if stage == 'execution':
            if lolbin_hits:
                summary = (f"Suspicious process execution: {', '.join(lolbin_hits[:2])} invoked "
                           f"in a {num_nodes}-node graph ({unknown_pct}% unknown subjects). "
                           f"High-risk entity: {entity_str}.")
            else:
                summary = (f"Novel process execution: {unknown_pct}% of subjects are unknown to "
                           f"the system catalog. Graph density {density:.2f} with {num_nodes} nodes. "
                           f"Affected: {entity_str}.")
        elif stage == 'exfiltration':
            summary = (f"Data exfiltration signals: {net_pct}% of events are network-bound, "
                       f"involving {entity_str}. Unknown-subject ratio {unknown_pct}%.")
        elif stage == 'command_and_control':
            summary = (f"Potential C2 activity: {net_pct}% network events concentrated around "
                       f"{entity_str}. Graph density {density:.2f}.")
        elif stage == 'persistence':
            summary = (f"Persistence-like write activity detected on {num_nodes}-node graph. "
                       f"{unknown_pct}% of subjects are unknown; affected: {entity_str}.")
        elif stage == 'discovery':
            summary = (f"Reconnaissance pattern: heavy read activity across {num_nodes} nodes "
                       f"with minimal writes. {unknown_pct}% unknown subjects.")
        elif stage == 'lateral_movement':
            summary = (f"Lateral-movement indicator: {unknown_pct}% novel subjects interacting in "
                       f"a dense graph (density {density:.2f}). Affected: {entity_str}.")
        else:  # reconnaissance / fallback
            summary = (f"Anomalous activity: fused score {fused:.1f}, {unknown_pct}% unknown "
                       f"subjects across {num_nodes} nodes. Entities: {entity_str}.")

        if lolbin_hits and stage != 'execution':
            summary += f" LOLBin hit: {', '.join(lolbin_hits[:2])}."

        return summary, signals

    def build_window_narrative(
        self,
        window_risk: dict,
        attack_stage: Optional[str] = None,
        threshold: float = 40.0,
        rf_result: Optional[dict] = None,
    ) -> AttackNarrative:
        """Build a narrative for one window using Phase 4 signals + optional RF output.

        If rf_result is provided (from RFDetector.predict), the narrative uses
        RF anomaly_score and top_features as the primary trust signal, with
        semantic data as supporting context. This is the production path.

        If attack_stage is None, we classify from behavioral_profile._event_types.
        """
        stage = attack_stage or self._classify_stage(window_risk)
        summary, signals = self._build_summary(window_risk, stage)

        if rf_result is not None:
            rf_score = float(rf_result.get('anomaly_score', 0.0))
            rf_threshold = float(rf_result.get('threshold', 0.5))
            top_feats = rf_result.get('top_features', {})
            top_named = ', '.join(f"{k}={v:.2f}" for k, v in list(top_feats.items())[:3])
            summary = (f"[RF score {rf_score:.3f} >= {rf_threshold:.3f}] {summary} "
                       f"Primary signals: {top_named}.")
            signals['rf_score'] = rf_score
            signals['rf_threshold'] = rf_threshold
            confidence = self._rf_confidence(rf_score, rf_threshold)
            score_for_narrative = rf_score
        else:
            confidence = self._confidence(window_risk.get('fused_score', 0.0), threshold)
            score_for_narrative = window_risk.get('fused_score', 0.0)

        mitre = self.STAGE_TO_MITRE.get(stage)
        mitre_hints = [mitre] if mitre else []

        fused = score_for_narrative

        return AttackNarrative(
            window_id=window_risk.get('window_id', 0),
            stage=stage,
            summary=summary,
            risk_factors=(window_risk.get('risk_factors') or [])[:5],
            high_risk_entities=(window_risk.get('high_risk_entities') or [])[:5],
            mitre_hints=mitre_hints,
            raw_score=fused,
            confidence=confidence,
            signals=signals,
        )

    def build_campaign_story(
        self,
        progression: dict,
        window_risks: List[dict],
        window_stages: Optional[List[str]] = None,
        threshold: float = 40.0,
    ) -> CampaignStory:
        """Build a multi-window campaign story."""
        start_wid = progression.get('start_window', 0)
        end_wid   = progression.get('end_window', 0)
        duration  = progression.get('duration_seconds', 0.0)

        chapters: List[AttackNarrative] = []
        for i, wr in enumerate(window_risks):
            stage = None
            if window_stages and i < len(window_stages):
                stage = window_stages[i]
            chapters.append(self.build_window_narrative(wr, stage, threshold))

        mitre_tactics = sorted({t for ch in chapters for t in ch.mitre_hints})
        stages_seen   = [ch.stage for ch in chapters]
        unique_stages = list(dict.fromkeys(stages_seen))

        if chapters:
            peak_score = max(ch.raw_score for ch in chapters)
            peak_ch    = max(chapters, key=lambda c: c.raw_score)
            stage_chain = " -> ".join(unique_stages[:4])
            narrative = (
                f"Attack progression over {duration:.0f}s ({len(chapters)} windows): "
                f"{stage_chain}. Peak anomaly at window {peak_ch.window_id} "
                f"(fused={peak_score:.1f}). {peak_ch.summary}"
            )
            title = f"APT progression: {stage_chain[:50]} (windows {start_wid}-{end_wid})"
        else:
            narrative = "No windows in progression."
            title = f"Empty progression (windows {start_wid}-{end_wid})"

        return CampaignStory(
            progression_id=f"campaign_{start_wid:06d}_{end_wid:06d}",
            start_time=progression.get('start_time', 'unknown'),
            end_time=progression.get('end_time', 'unknown'),
            duration_seconds=duration,
            title=title,
            narrative=narrative,
            chapters=chapters,
            mitre_tactics=mitre_tactics,
        )

    def build_full_report(
        self,
        phase4_results_path: str,
        timeline_data: Optional[dict] = None,
        min_score: float = 40.0,
    ) -> List[CampaignStory]:
        """Build campaign stories from Phase 4 results.

        If timeline_data with attack_progressions is provided, uses those groupings.
        Otherwise, auto-groups consecutive anomalous windows into campaigns.
        """
        path = Path(phase4_results_path)
        if not path.exists():
            return []

        with open(path, 'r') as f:
            results = json.load(f)

        windows = results.get('windows', [])
        if not windows:
            return []

        threshold = float(results.get('metrics', {}).get('threshold', min_score))
        by_id = {w['window_id']: w for w in windows if 'window_id' in w}

        if timeline_data and timeline_data.get('attack_progressions'):
            campaigns = []
            for prog in timeline_data['attack_progressions']:
                ids = [s['window_id'] for s in prog.get('stages', [])
                       if s.get('window_id') in by_id]
                wrs = [by_id[i] for i in ids]
                stages = [s['stage'] for s in prog.get('stages', []) if s.get('window_id') in by_id]
                if wrs:
                    campaigns.append(self.build_campaign_story(prog, wrs, stages, threshold))
            return campaigns

        # Auto-group consecutive anomalous windows
        sorted_ws = sorted((w for w in windows if w.get('fused_score', 0) >= threshold),
                           key=lambda w: w['window_id'])
        campaigns = []
        current: List[dict] = []
        for w in sorted_ws:
            if not current:
                current = [w]
                continue
            if w['window_id'] - current[-1]['window_id'] <= 5:
                current.append(w)
            else:
                campaigns.append(self._auto_campaign(current, threshold))
                current = [w]
        if current:
            campaigns.append(self._auto_campaign(current, threshold))
        return campaigns

    def _auto_campaign(self, window_risks: List[dict], threshold: float) -> CampaignStory:
        """Build a campaign story from a contiguous run of anomalous windows."""
        start_wid = window_risks[0]['window_id']
        end_wid   = window_risks[-1]['window_id']
        prog = {
            'start_window': start_wid,
            'end_window': end_wid,
            'duration_seconds': float(end_wid - start_wid + 1),
            'start_time': 'unknown',
            'end_time': 'unknown',
        }
        return self.build_campaign_story(prog, window_risks, None, threshold)
