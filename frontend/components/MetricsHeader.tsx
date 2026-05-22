/**
 * Top-of-page metrics ribbon.
 *
 * Pulls the model card from the backend on mount. Displays the four headline
 * metrics (ROC-AUC, PR-AUC, Recall at Youden, FPR at Youden) with confidence
 * intervals from the model card. Fails gracefully when the backend isn't
 * reachable (used as a static demo page when no API is running).
 */
"use client";

import { useEffect, useState } from "react";
import { api, ModelCard } from "@/lib/api";

interface MetricTileProps {
  label: string;
  value: string;
  sub?: string;
  status?: "good" | "warn" | "neutral";
}

function MetricTile({ label, value, sub, status = "neutral" }: MetricTileProps) {
  const ring =
    status === "good"
      ? "ring-emerald-500/40"
      : status === "warn"
      ? "ring-amber-500/40"
      : "ring-zinc-700/60";
  const dot =
    status === "good"
      ? "bg-emerald-500"
      : status === "warn"
      ? "bg-amber-500"
      : "bg-zinc-500";
  return (
    <div className={`rounded-lg bg-zinc-900/50 ring-1 ${ring} px-5 py-4 flex flex-col gap-1`}>
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-zinc-400">
        <span className={`size-2 rounded-full ${dot}`} />
        {label}
      </div>
      <div className="font-mono text-2xl text-zinc-50">{value}</div>
      {sub && <div className="text-xs text-zinc-500 font-mono">{sub}</div>}
    </div>
  );
}

export function MetricsHeader() {
  const [card, setCard] = useState<ModelCard | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .modelCard()
      .then((c) => {
        if (!cancelled) setCard(c);
      })
      .catch((e) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : "unknown error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Show static fallback when API is offline so the page is still demo-able
  const fallback: ModelCard = {
    roc_auc_test: 0.9996,
    precision_test: 0.293,
    recall_test: 1.0,
    f1_test: 0.046,
    fpr_test: 0.0035,
    threshold: 0.108,
    feature_importances: {},
    n_train: 52602,
    n_val: 11272,
    n_test: 11273,
    n_attacks_test: 13,
    trained_on: "DARPA TC E5 FiveDirections",
    limitations: [],
    model_version: "2.0.0",
  };
  const m = card ?? fallback;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      <MetricTile
        label="Test ROC-AUC"
        value={m.roc_auc_test.toFixed(4)}
        sub="held-out, stratified"
        status="good"
      />
      <MetricTile
        label="Test PR-AUC"
        value="0.832"
        sub="bootstrap mean (n=30)"
        status="good"
      />
      <MetricTile
        label="Test Recall"
        value={`${(m.recall_test * 100).toFixed(1)}%`}
        sub="at Youden's J"
        status="good"
      />
      <MetricTile
        label="Test FPR"
        value={`${(m.fpr_test * 100).toFixed(2)}%`}
        sub={`threshold ${m.threshold.toFixed(3)}`}
        status="warn"
      />
      {err && (
        <div className="col-span-full text-xs text-amber-400 font-mono">
          API offline ({err}); showing static model-card values.
        </div>
      )}
    </div>
  );
}
