"use client";

import { useEffect, useState } from "react";

type Health = "checking" | "waking" | "online" | "down";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function ShieldMark() {
  // The signature: a calm shield with a check. "Linda" = protect.
  return (
    <svg width="26" height="30" viewBox="0 0 26 30" aria-hidden="true">
      <path
        d="M13 1.5 23.5 5v9c0 7.2-4.6 12-10.5 14.5C7.1 26 2.5 21.2 2.5 14V5L13 1.5Z"
        fill="var(--green-100)"
        stroke="var(--green-600)"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M8 14.5l3.4 3.4L18 11"
        fill="none"
        stroke="var(--green-600)"
        strokeWidth="2.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const STATUS_COPY: Record<Health, { dot: string; label: string }> = {
  checking: { dot: "dot", label: "Checking systems…" },
  waking: { dot: "dot dot--wake", label: "Waking the scanner…" },
  online: { dot: "dot dot--ok", label: "Systems online" },
  down: { dot: "dot dot--down", label: "Backend not reachable" },
};

export default function Home() {
  const [health, setHealth] = useState<Health>("checking");

  useEffect(() => {
    let cancelled = false;
    // Render free tier can cold-start (~30–60s). If the probe is slow,
    // show the honest "waking" copy from the TRD instead of a frozen state.
    const slowTimer = setTimeout(() => {
      if (!cancelled) setHealth((h) => (h === "checking" ? "waking" : h));
    }, 3000);

    fetch(`${API_URL}/healthz`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => {
        if (!cancelled) setHealth(d?.status === "ok" ? "online" : "down");
      })
      .catch(() => {
        if (!cancelled) setHealth("down");
      })
      .finally(() => clearTimeout(slowTimer));

    return () => {
      cancelled = true;
      clearTimeout(slowTimer);
    };
  }, []);

  const s = STATUS_COPY[health];

  return (
    <main className="page">
      <div className="shell">
        <span className="brand">
          <ShieldMark />
          LindaAI
        </span>

        <p className="eyebrow">Security audit for Kenyan businesses</p>
        <h1>Know if your website is safe — in plain language.</h1>
        <p className="subhead">
          Verify a domain you own, run a passive check, and get a clear
          report on what to fix.
        </p>
        <p className="subhead subhead--sw" lang="sw">
          Jua kama tovuti yako ni salama — kwa lugha rahisi.
        </p>

        <div
          className="status"
          role="status"
          aria-live="polite"
          title="Live connection to the LindaAI API"
        >
          <span className={s.dot} />
          {s.label}
        </div>

        <p className="foot">
          Week 1 · Day 1 — skeleton deploy. The scan engine arrives in Week 2.
          <br />
          Backend: <code>{API_URL}</code>
        </p>
      </div>
    </main>
  );
}
