/**
 * Campaign list / table.
 *
 * Renders the list of detected APT campaigns from the backend. Click selects
 * a campaign and shows its full narrative + chapter breakdown.
 */
"use client";

import { useEffect, useState } from "react";
import { api, CampaignStory } from "@/lib/api";
import { NarrativePanel } from "./NarrativePanel";

const SAMPLE: CampaignStory[] = [
  {
    progression_id: "campaign_000131_000137",
    start_time: "2019-05-07 11:11:00",
    end_time: "2019-05-07 11:11:06",
    duration_seconds: 7,
    title: "APT progression: lateral_movement -> execution (windows 131-137)",
    narrative:
      "Attack progression over 7s (5 windows): lateral_movement -> execution. Peak anomaly at window 131 (fused=68.9). Lateral-movement indicator: 100% novel subjects interacting in a dense graph (density 0.92). Affected: a2a93850.",
    chapters: [
      {
        window_id: 131,
        stage: "lateral_movement",
        summary:
          "[RF score 0.96] Lateral-movement indicator: 100% novel subjects interacting in a dense graph (density 0.92). Primary signals: num_nodes=75, num_subjects=21.",
        risk_factors: [],
        high_risk_entities: ["a2a93850d9954f05"],
        mitre_hints: ["TA0008"],
        raw_score: 0.961,
        confidence: "high",
        signals: { num_nodes: 75, unknown_ratio: 1.0, density: 0.92 },
      },
    ],
    mitre_tactics: ["TA0008"],
  },
];

export function CampaignList() {
  const [campaigns, setCampaigns] = useState<CampaignStory[]>([]);
  const [selected, setSelected] = useState<CampaignStory | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api
      .campaigns()
      .then((c) => {
        if (!cancelled) {
          setCampaigns(c);
          setSelected(c[0] ?? null);
          setLoading(false);
        }
      })
      .catch(() => {
        // Fall back to sample data so the page is still demoable offline
        if (!cancelled) {
          setCampaigns(SAMPLE);
          setSelected(SAMPLE[0]);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="lg:col-span-1 rounded-lg bg-zinc-900/50 ring-1 ring-zinc-800 overflow-hidden">
        <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
          <h2 className="text-sm uppercase tracking-wider text-zinc-300">
            Detected Campaigns
          </h2>
          <span className="text-xs text-zinc-500 font-mono">
            {loading ? "…" : `${campaigns.length} total`}
          </span>
        </div>
        <div className="max-h-[60vh] overflow-y-auto divide-y divide-zinc-800/60">
          {campaigns.length === 0 && !loading && (
            <div className="p-4 text-sm text-zinc-500">No campaigns detected.</div>
          )}
          {campaigns.map((c) => {
            const isActive = selected?.progression_id === c.progression_id;
            return (
              <button
                key={c.progression_id}
                onClick={() => setSelected(c)}
                className={`w-full text-left px-4 py-3 hover:bg-zinc-800/40 transition ${
                  isActive ? "bg-emerald-500/10 border-l-2 border-emerald-500" : ""
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-zinc-400">
                    {c.progression_id.replace("campaign_", "#")}
                  </span>
                  <span className="text-xs text-zinc-500">
                    {c.duration_seconds.toFixed(0)}s
                  </span>
                </div>
                <div className="text-sm text-zinc-100 mt-1 truncate">
                  {c.title}
                </div>
                <div className="flex gap-1.5 mt-2 flex-wrap">
                  {c.mitre_tactics.slice(0, 4).map((t) => (
                    <span
                      key={t}
                      className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-red-500/10 text-red-300 ring-1 ring-red-500/30"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </button>
            );
          })}
        </div>
      </div>
      <div className="lg:col-span-2">
        <NarrativePanel campaign={selected} />
      </div>
    </div>
  );
}
