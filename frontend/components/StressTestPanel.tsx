/**
 * Stress test status panel.
 *
 * Renders the six stress-test outcomes from STRESS_TEST_REPORT.md as a
 * compact, scannable status board. Hard-coded to the most recent reported
 * results; updates manually after each stress_test.py run.
 */
"use client";

const TESTS: Array<{
  name: string;
  result: string;
  verdict: "pass" | "warn" | "fail" | "info";
}> = [
  {
    name: "Shuffled-label control",
    result: "ROC-AUC = 0.5007 (expected 0.5)",
    verdict: "pass",
  },
  {
    name: "Rolling-context corruption",
    result: "PR-AUC stable after attack-window feature replacement",
    verdict: "pass",
  },
  {
    name: "Class imbalance 10:1 → 1000:1",
    result: "PR-AUC degrades monotonically 0.98 → 0.87",
    verdict: "pass",
  },
  {
    name: "Feature noise +10% std",
    result: "PR-AUC drops 0.86 → 0.41",
    verdict: "warn",
  },
  {
    name: "Window-size sensitivity",
    result: "PR-AUC monotonic 0.30 / 0.54 / 0.86 / 0.91 / 0.99 (5s/10s/30s/60s/120s)",
    verdict: "pass",
  },
  {
    name: "Cold start (10% training)",
    result: "ROC-AUC 0.998 with only 8 training attacks",
    verdict: "pass",
  },
];

const VERDICT_STYLES: Record<string, string> = {
  pass: "text-emerald-300 bg-emerald-500/10 ring-emerald-500/30",
  warn: "text-amber-300 bg-amber-500/10 ring-amber-500/30",
  fail: "text-red-300 bg-red-500/10 ring-red-500/30",
  info: "text-zinc-300 bg-zinc-700/30 ring-zinc-600",
};

const VERDICT_LABEL: Record<string, string> = {
  pass: "PASS",
  warn: "WARN",
  fail: "FAIL",
  info: "INFO",
};

export function StressTestPanel() {
  return (
    <div className="rounded-lg bg-zinc-900/50 ring-1 ring-zinc-800 overflow-hidden">
      <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
        <div>
          <h2 className="text-sm uppercase tracking-wider text-zinc-300">
            Stress test results
          </h2>
          <p className="text-xs text-zinc-500 font-mono mt-1">
            6 independent tests · industry-comparison in STRESS_TEST_REPORT.md
          </p>
        </div>
        <a
          href="https://github.com/kevin-doshi/sentinel-z/blob/main/STRESS_TEST_REPORT.md"
          target="_blank"
          rel="noreferrer"
          className="text-xs text-zinc-400 hover:text-zinc-100 underline-offset-4 hover:underline shrink-0"
        >
          full report →
        </a>
      </div>
      <ul className="divide-y divide-zinc-800/60">
        {TESTS.map((t) => (
          <li key={t.name} className="px-4 py-3 flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="text-sm text-zinc-100">{t.name}</div>
              <div className="text-xs text-zinc-500 font-mono mt-0.5 truncate">
                {t.result}
              </div>
            </div>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-mono ring-1 shrink-0 ${
                VERDICT_STYLES[t.verdict]
              }`}
            >
              {VERDICT_LABEL[t.verdict]}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
