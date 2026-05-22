import { PageHeader } from "@/components/PageHeader";
import { MetricsHeader } from "@/components/MetricsHeader";
import { CampaignList } from "@/components/CampaignList";
import { StressTestPanel } from "@/components/StressTestPanel";

export default function Home() {
  return (
    <div className="min-h-screen">
      <PageHeader />
      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        <section>
          <div className="mb-4">
            <h2 className="text-sm uppercase tracking-wider text-zinc-400">
              Held-out performance
            </h2>
            <p className="text-xs text-zinc-500 mt-1">
              30-iteration paired-bootstrap on DARPA TC E5 (FiveDirections) · all numbers in{" "}
              <a
                href="https://github.com/kevin-doshi/sentinel-z/blob/main/MODEL_CARD.md"
                className="underline-offset-4 hover:underline hover:text-zinc-300"
                target="_blank"
                rel="noreferrer"
              >
                MODEL_CARD.md
              </a>
            </p>
          </div>
          <MetricsHeader />
        </section>

        <section>
          <div className="mb-4">
            <h2 className="text-sm uppercase tracking-wider text-zinc-400">
              Detected campaigns
            </h2>
            <p className="text-xs text-zinc-500 mt-1">
              Auto-grouped from anomalous 1-second windows. Click any to inspect.
            </p>
          </div>
          <CampaignList />
        </section>

        <section>
          <div className="mb-4">
            <h2 className="text-sm uppercase tracking-wider text-zinc-400">
              Validation methodology
            </h2>
            <p className="text-xs text-zinc-500 mt-1">
              Six independent stress tests including the shuffled-label leakage control
              that no published baseline runs.
            </p>
          </div>
          <StressTestPanel />
        </section>

        <footer className="pt-12 pb-8 border-t border-zinc-800/60 text-xs text-zinc-500">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span>
              Sentinel-Z · Apache 2.0 ·{" "}
              <a
                href="https://github.com/kevin-doshi/sentinel-z"
                className="hover:text-zinc-300 underline-offset-4 hover:underline"
                target="_blank"
                rel="noreferrer"
              >
                github
              </a>
            </span>
            <span className="font-mono">
              Built with disciplined methodology, not hype.
            </span>
          </div>
        </footer>
      </main>
    </div>
  );
}
