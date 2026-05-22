import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Sentinel-Z — Explainable APT Detection",
  description:
    "Provenance-based APT detection with deterministic, signal-driven narratives. PR-AUC 0.83 on DARPA TC E5.",
  metadataBase: new URL("https://sentinel-z.local"),
  openGraph: {
    title: "Sentinel-Z",
    description: "Explainable provenance-based APT detection with honest validation.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-zinc-950 text-zinc-100 min-h-screen`}
        suppressHydrationWarning
      >
        {children}
      </body>
    </html>
  );
}
