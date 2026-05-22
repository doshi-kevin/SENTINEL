/**
 * Top page header with project identity + status indicator.
 */
"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function PageHeader() {
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .status()
      .then(() => {
        if (!cancelled) setOnline(true);
      })
      .catch(() => {
        if (!cancelled) setOnline(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <header className="border-b border-zinc-800 bg-zinc-950/60 backdrop-blur-sm sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="size-8 rounded bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center font-bold text-zinc-950">
            Z
          </div>
          <div>
            <h1 className="text-lg font-medium tracking-tight">Sentinel-Z</h1>
            <p className="text-xs text-zinc-500 font-mono">
              Explainable APT detection · DARPA TC E5
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs">
            <span
              className={`size-2 rounded-full ${
                online === null
                  ? "bg-zinc-500 animate-pulse"
                  : online
                  ? "bg-emerald-500"
                  : "bg-amber-500"
              }`}
            />
            <span className="font-mono text-zinc-400">
              {online === null
                ? "connecting…"
                : online
                ? "backend online"
                : "backend offline (demo mode)"}
            </span>
          </div>
          <a
            href="https://github.com/kevin-doshi/sentinel-z"
            target="_blank"
            rel="noreferrer"
            className="text-xs text-zinc-400 hover:text-zinc-100 underline-offset-4 hover:underline"
          >
            github →
          </a>
        </div>
      </div>
    </header>
  );
}
