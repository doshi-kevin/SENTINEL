/**
 * Narrative detail panel.
 *
 * Renders the full campaign story plus per-window chapters. Each chapter shows:
 *   - The deterministic summary (text)
 *   - The signals dictionary (auditable evidence)
 *   - The MITRE ATT&CK tactic tag
 *   - The confidence level
 *
 * Why no LLM: every claim in the narrative cites a signal value the user can
 * trace back to the underlying graph. See src/sentinel_z/narrative/story_builder.py.
 */
"use client";

import { CampaignStory } from "@/lib/api";

const STAGE_COLORS: Record<string, string> = {
  reconnaissance: "text-blue-300 bg-blue-500/10 ring-blue-500/30",
  discovery: "text-blue-300 bg-blue-500/10 ring-blue-500/30",
  execution: "text-amber-300 bg-amber-500/10 ring-amber-500/30",
  persistence: "text-orange-300 bg-orange-500/10 ring-orange-500/30",
  lateral_movement: "text-red-300 bg-red-500/10 ring-red-500/30",
  command_and_control: "text-purple-300 bg-purple-500/10 ring-purple-500/30",
  exfiltration: "text-red-300 bg-red-500/10 ring-red-500/30",
  collection: "text-cyan-300 bg-cyan-500/10 ring-cyan-500/30",
};

const CONFIDENCE_DOT: Record<string, string> = {
  high: "bg-emerald-500",
  medium: "bg-amber-500",
  low: "bg-zinc-500",
};

export function NarrativePanel({ campaign }: { campaign: CampaignStory | null }) {
  if (!campaign) {
    return (
      <div className="h-full min-h-[60vh] rounded-lg bg-zinc-900/30 ring-1 ring-zinc-800 flex items-center justify-center text-zinc-500">
        Select a campaign to see its narrative.
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-zinc-900/50 ring-1 ring-zinc-800 overflow-hidden">
      <div className="px-5 py-4 border-b border-zinc-800">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-base font-medium text-zinc-100">{campaign.title}</h2>
          <span className="font-mono text-xs text-zinc-500 shrink-0">
            {campaign.duration_seconds.toFixed(0)}s
          </span>
        </div>
        <div className="flex gap-1.5 mt-2 flex-wrap">
          {campaign.mitre_tactics.map((t) => (
            <span
              key={t}
              className="px-2 py-0.5 rounded text-[10px] font-mono bg-red-500/10 text-red-300 ring-1 ring-red-500/30"
            >
              MITRE {t}
            </span>
          ))}
        </div>
      </div>

      <div className="px-5 py-4 border-b border-zinc-800">
        <h3 className="text-xs uppercase tracking-wider text-zinc-400 mb-2">
          Campaign narrative
        </h3>
        <p className="text-sm text-zinc-200 leading-relaxed">{campaign.narrative}</p>
      </div>

      <div className="px-5 py-4">
        <h3 className="text-xs uppercase tracking-wider text-zinc-400 mb-3">
          Chapter breakdown — {campaign.chapters.length} window{campaign.chapters.length === 1 ? "" : "s"}
        </h3>
        <div className="space-y-3">
          {campaign.chapters.map((ch) => (
            <div
              key={ch.window_id}
              className="rounded-md bg-zinc-950/70 ring-1 ring-zinc-800/80 p-4"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-zinc-500">
                    window #{ch.window_id}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-mono ring-1 ${
                      STAGE_COLORS[ch.stage] || "text-zinc-300 bg-zinc-700/30 ring-zinc-600"
                    }`}
                  >
                    {ch.stage}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-zinc-400">
                  <span
                    className={`size-1.5 rounded-full ${CONFIDENCE_DOT[ch.confidence] || CONFIDENCE_DOT.low}`}
                  />
                  <span className="uppercase">{ch.confidence}</span>
                  <span className="font-mono">{ch.raw_score.toFixed(3)}</span>
                </div>
              </div>
              <p className="text-sm text-zinc-200 leading-relaxed">{ch.summary}</p>

              {ch.signals && Object.keys(ch.signals).length > 0 && (
                <details className="mt-3 group">
                  <summary className="cursor-pointer text-xs text-zinc-400 hover:text-zinc-200 select-none">
                    Evidence (raw signals)
                  </summary>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1.5 mt-2 font-mono text-xs">
                    {Object.entries(ch.signals).map(([k, v]) => (
                      <div key={k} className="flex justify-between gap-2 text-zinc-400">
                        <span className="truncate">{k}</span>
                        <span className="text-zinc-200">
                          {typeof v === "number" ? v.toFixed(3) : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                </details>
              )}

              {ch.high_risk_entities.length > 0 && (
                <div className="mt-3 text-xs text-zinc-400">
                  Affected entities:{" "}
                  {ch.high_risk_entities.slice(0, 3).map((e) => (
                    <span key={e} className="font-mono text-zinc-200 mr-2">
                      {e}
                    </span>
                  ))}
                  {ch.high_risk_entities.length > 3 && (
                    <span className="text-zinc-500">+{ch.high_risk_entities.length - 3} more</span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
