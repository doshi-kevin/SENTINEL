"""
Story Builder: Narrative Generation for Attack Campaigns

Transforms Phase 4 semantic risk results into human-readable attack narratives.
Uses template-based generation (NO LLMs) to describe:
1. Attack stages (reconnaissance, execution, persistence, etc.)
2. Risk factor summaries
3. Affected entities and infrastructure
4. Campaign progression across time

Key insight: Attack narratives help security teams understand the "why" and "how"
of a detection, not just the "what score."
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta


@dataclass
class AttackNarrative:
    """Narrative for a single attack window."""
    window_id: int
    stage: str  # e.g., "reconnaissance", "execution", "persistence"
    summary: str  # One-sentence description
    risk_factors: List[str]  # ["LOLBin usage", "Hidden execution", ...]
    high_risk_entities: List[str]  # Process names, file paths, etc.
    mitre_hints: List[str]  # MITRE tactic IDs
    raw_score: float  # 0-10 semantic risk score
    confidence: str  # "low", "medium", "high"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CampaignStory:
    """Narrative for a full attack campaign."""
    progression_id: str
    start_time: str
    end_time: str
    duration_seconds: float
    title: str
    narrative: str  # Multi-sentence summary of campaign
    chapters: List[AttackNarrative]  # One narrative per window
    mitre_tactics: List[str]  # Aggregated MITRE tactic IDs

    def to_dict(self) -> dict:
        return {
            'progression_id': self.progression_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_seconds': self.duration_seconds,
            'title': self.title,
            'narrative': self.narrative,
            'chapters': [ch.to_dict() for ch in self.chapters],
            'mitre_tactics': self.mitre_tactics
        }


class StoryBuilder:
    """
    Builds attack narratives from Phase 4 results.

    Uses template-based generation:
    - Each stage has predefined sentence templates
    - Risk factors and entities are inserted into templates
    - No external LLM calls (reproducible, offline)
    """

    # Stage-to-MITRE tactic mapping
    STAGE_TO_MITRE = {
        'reconnaissance': 'TA0043',
        'execution': 'TA0002',
        'persistence': 'TA0003',
        'collection': 'TA0009',
        'exfiltration': 'TA0010',
        'lateral_movement': 'TA0008',
    }

    # Templates for one-sentence summaries per stage
    STAGE_TEMPLATES = {
        'reconnaissance': (
            "Attacker gathered information about target systems and infrastructure.",
            "Attacker probed for vulnerabilities and enumerated network topology."
        ),
        'execution': (
            "Attacker executed malicious code on target system.",
            "Attacker launched payload for command execution and exploitation."
        ),
        'persistence': (
            "Attacker established mechanisms to maintain long-term access.",
            "Attacker installed backdoors and scheduled tasks for persistence."
        ),
        'collection': (
            "Attacker gathered sensitive data from target systems.",
            "Attacker exfiltrated files and credentials for further exploitation."
        ),
        'exfiltration': (
            "Attacker transferred stolen data outside the network.",
            "Attacker used C2 channels to exfiltrate sensitive information."
        ),
        'lateral_movement': (
            "Attacker moved horizontally to compromise additional systems.",
            "Attacker pivoted through the network to expand attack surface."
        ),
        'benign': (
            "Normal system activity detected.",
            "No suspicious activity detected in this window."
        ),
    }

    # Confidence levels based on risk score
    SCORE_TO_CONFIDENCE = {
        (0.0, 3.0): 'low',
        (3.0, 6.5): 'medium',
        (6.5, 10.0): 'high',
    }

    def __init__(self):
        """Initialize story builder."""
        pass

    def _get_confidence(self, score: float) -> str:
        """Map risk score to confidence level."""
        for (low, high), confidence in self.SCORE_TO_CONFIDENCE.items():
            if low <= score < high:
                return confidence
        return 'high'

    def _pick_template(self, stage: str, risk_factor_count: int) -> str:
        """
        Pick a template based on stage and complexity.
        More risk factors → use more descriptive template.
        """
        templates = self.STAGE_TEMPLATES.get(stage, self.STAGE_TEMPLATES['benign'])
        if risk_factor_count >= 3:
            idx = 1 if len(templates) > 1 else 0
        else:
            idx = 0
        return templates[idx]

    def build_window_narrative(
        self,
        window_risk: dict,
        attack_stage: str
    ) -> AttackNarrative:
        """
        Build a narrative for a single attack window.

        Args:
            window_risk: Dict from Phase 4 WindowRisk with keys:
                - window_id: int
                - semantic_score: float (0-10)
                - risk_factors: List[str]
                - high_risk_entities: List[str]
            attack_stage: str, one of the STAGE_TO_MITRE keys

        Returns:
            AttackNarrative for this window.
        """
        window_id = window_risk.get('window_id', 0)
        score = window_risk.get('semantic_score', 0.0)
        risk_factors = window_risk.get('risk_factors', [])
        entities = window_risk.get('high_risk_entities', [])

        # Pick template and generate summary
        template = self._pick_template(attack_stage, len(risk_factors))
        summary = template

        # Map stage to MITRE tactic
        mitre_tactic = self.STAGE_TO_MITRE.get(attack_stage, 'TA0000')
        mitre_hints = [mitre_tactic] if mitre_tactic != 'TA0000' else []

        # Determine confidence from score
        confidence = self._get_confidence(score)

        return AttackNarrative(
            window_id=window_id,
            stage=attack_stage,
            summary=summary,
            risk_factors=risk_factors[:5],  # Top 5 risk factors
            high_risk_entities=entities[:5],  # Top 5 entities
            mitre_hints=mitre_hints,
            raw_score=score,
            confidence=confidence
        )

    def build_campaign_story(
        self,
        progression: dict,
        window_risks: List[dict],
        window_stages: List[str]
    ) -> CampaignStory:
        """
        Build a narrative for a full attack campaign.

        Args:
            progression: Dict from timeline_builder.AttackProgression with keys:
                - start_window: int
                - end_window: int
                - duration_seconds: float
            window_risks: List of window_risk dicts (from Phase 4)
            window_stages: List of attack stage strings (aligned with window_risks)

        Returns:
            CampaignStory for this campaign.
        """
        start_wid = progression.get('start_window', 0)
        end_wid = progression.get('end_window', 0)
        duration = progression.get('duration_seconds', 0.0)

        # Generate ID
        progression_id = f"campaign_{start_wid:06d}_{end_wid:06d}"

        # Build chapters (one narrative per window)
        chapters = []
        all_mitre_tactics = set()

        for i, window_risk in enumerate(window_risks):
            stage = window_stages[i] if i < len(window_stages) else 'reconnaissance'
            narrative = self.build_window_narrative(window_risk, stage)
            chapters.append(narrative)

            # Aggregate MITRE tactics
            for tactic in narrative.mitre_hints:
                all_mitre_tactics.add(tactic)

        # Generate overall campaign narrative
        if chapters:
            avg_score = sum(ch.raw_score for ch in chapters) / len(chapters)
            high_confidence_count = sum(1 for ch in chapters if ch.confidence == 'high')

            if high_confidence_count >= len(chapters) * 0.5:
                campaign_narrative = (
                    f"Multi-stage attack campaign detected spanning {len(chapters)} windows. "
                    f"Progression suggests: "
                )
            else:
                campaign_narrative = (
                    f"Potential attack activity detected across {len(chapters)} windows. "
                    f"Activity pattern indicates: "
                )

            # Summarize stage progression
            stages_used = set(ch.stage for ch in chapters)
            if 'reconnaissance' in stages_used:
                campaign_narrative += "initial reconnaissance; "
            if 'execution' in stages_used:
                campaign_narrative += "command execution; "
            if 'lateral_movement' in stages_used:
                campaign_narrative += "lateral movement; "
            if 'persistence' in stages_used:
                campaign_narrative += "persistence mechanisms; "
            if 'collection' in stages_used:
                campaign_narrative += "data collection; "
            if 'exfiltration' in stages_used:
                campaign_narrative += "data exfiltration. "

            campaign_narrative = campaign_narrative.rstrip('; ') + "."
        else:
            campaign_narrative = "No attack activity detected."

        # Time strings (placeholders if not in progression)
        start_time = progression.get('start_time', 'unknown')
        end_time = progression.get('end_time', 'unknown')

        # Title based on severity
        if avg_score >= 7.0 if chapters else False:
            title = f"High-Severity Attack Campaign (Windows {start_wid}-{end_wid})"
        elif avg_score >= 5.0 if chapters else False:
            title = f"Suspicious Activity Campaign (Windows {start_wid}-{end_wid})"
        else:
            title = f"Anomalous Activity Campaign (Windows {start_wid}-{end_wid})"

        return CampaignStory(
            progression_id=progression_id,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            title=title,
            narrative=campaign_narrative,
            chapters=chapters,
            mitre_tactics=sorted(list(all_mitre_tactics))
        )

    def build_full_report(
        self,
        phase4_results_path: str,
        timeline_data: dict
    ) -> List[CampaignStory]:
        """
        Build a full report of all detected campaigns.

        Args:
            phase4_results_path: Path to phase4_results.json from detection module
            timeline_data: Dict from timeline_builder with keys:
                - windows: List of TimelineWindow dicts
                - attack_progressions: List of AttackProgression dicts

        Returns:
            List of CampaignStory objects, one per detected attack campaign.
        """
        # Load Phase 4 results
        phase4_path = Path(phase4_results_path)
        if not phase4_path.exists():
            return []

        with open(phase4_path, 'r') as f:
            phase4_results = json.load(f)

        # Build a mapping: window_id -> window_risk
        window_risks_by_id = {}
        for wr in phase4_results.get('window_risks', []):
            window_risks_by_id[wr['window_id']] = wr

        # Extract attack progressions and build campaigns
        campaigns = []
        attack_progressions = timeline_data.get('attack_progressions', [])

        for prog in attack_progressions:
            start_wid = prog.get('start_window', 0)
            end_wid = prog.get('end_window', 0)

            # Gather window risks and stages for this progression
            window_risks_in_prog = []
            stages_in_prog = []

            for wid in range(start_wid, end_wid + 1):
                if wid in window_risks_by_id:
                    window_risks_in_prog.append(window_risks_by_id[wid])
                    # Infer stage from progression data if available
                    stage_info = next(
                        (s for s in prog.get('stages', []) if s.get('window_id') == wid),
                        None
                    )
                    stage = stage_info.get('stage', 'reconnaissance') if stage_info else 'reconnaissance'
                    stages_in_prog.append(stage)

            # Build campaign story
            if window_risks_in_prog:
                story = self.build_campaign_story(prog, window_risks_in_prog, stages_in_prog)
                campaigns.append(story)

        return campaigns
