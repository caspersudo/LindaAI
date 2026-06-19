"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/app/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type DomainStatus = "pending" | "verified" | "revoked";
type ScanStatus = "queued" | "running" | "complete" | "failed";
type Severity = "critical" | "high" | "medium" | "low";

type Domain = {
  id: string;
  hostname: string;
  status: DomainStatus;
  verify_token: string;
};

type Scan = {
  id: string;
  status: ScanStatus;
  raw_findings: { id: string; severity: Severity; detail?: string }[];
  fail_reason?: string;
};

const SEV_ORDER: Severity[] = ["critical", "high", "medium", "low"];

async function getToken(): Promise<string> {
  const { data } = await createClient().auth.getSession();
  return data.session?.access_token ?? "";
}

async function apiFetch(path: string, method = "GET", body?: object) {
  const token = await getToken();
  const r = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(text || `HTTP ${r.status}`);
  }
  return r.json();
}

export default function DomainCard({ domain }: { domain: Domain }) {
  const [domainStatus, setDomainStatus] = useState<DomainStatus>(domain.status);
  const [verifyMsg, setVerifyMsg] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [copied, setCopied] = useState(false);

  const [scan, setScan] = useState<Scan | null>(null);
  const [scanning, setScanning] = useState(false);
  const [activeScanId, setActiveScanId] = useState<string | null>(null);

  // Poll while a scan is queued or running
  useEffect(() => {
    if (!activeScanId) return;
    const interval = setInterval(async () => {
      try {
        const s: Scan = await apiFetch(`/scans/${activeScanId}`);
        setScan(s);
        if (s.status !== "queued" && s.status !== "running") {
          clearInterval(interval);
          setScanning(false);
          setActiveScanId(null);
        }
      } catch {
        clearInterval(interval);
        setScanning(false);
        setActiveScanId(null);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [activeScanId]);

  async function handleVerify() {
    setVerifying(true);
    setVerifyMsg(null);
    try {
      const result = await apiFetch(`/domains/${domain.id}/verify`, "POST");
      if (result.verified) {
        setDomainStatus("verified");
        setVerifyMsg(null);
      } else {
        setVerifyMsg(result.message);
      }
    } catch {
      setVerifyMsg("Could not reach the server. Try again.");
    }
    setVerifying(false);
  }

  async function handleScan() {
    setScanning(true);
    setScan(null);
    try {
      const { scan_id } = await apiFetch("/scans", "POST", { domain_id: domain.id });
      setActiveScanId(scan_id);
      // Kick off first poll immediately
      const s: Scan = await apiFetch(`/scans/${scan_id}`);
      setScan(s);
      if (s.status !== "queued" && s.status !== "running") {
        setScanning(false);
        setActiveScanId(null);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setScan({ id: "", status: "failed", raw_findings: [], fail_reason: msg });
      setScanning(false);
    }
  }

  function copyToken() {
    navigator.clipboard.writeText(domain.verify_token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const counts = scan?.raw_findings?.reduce(
    (acc, f) => { acc[f.severity] = (acc[f.severity] ?? 0) + 1; return acc; },
    {} as Record<Severity, number>
  );

  return (
    <div className="domain-card">
      <div className="domain-head">
        <span className="domain-host">{domain.hostname}</span>
        <span className={`badge badge--${domainStatus}`}>{domainStatus}</span>
      </div>

      {/* ── Pending: verification wizard ── */}
      {domainStatus === "pending" && (
        <div className="verify-section">
          <p className="domain-note">
            <strong>Step 1</strong> — Copy this TXT record and add it at your domain registrar
            (e.g. in your DNS settings on GoDaddy, Safaricom, or wherever you bought the domain):
          </p>
          <code className="token">{domain.verify_token}</code>
          <p className="domain-note">
            <strong>Step 2</strong> — DNS can take a few minutes (sometimes up to 48 hours) to spread.
            Once you&apos;ve added the record, click <em>Verify now</em>.
          </p>
          <div className="card-actions">
            <button className="btn btn--ghost btn--sm" onClick={copyToken}>
              {copied ? "Copied!" : "Copy record"}
            </button>
            <button className="btn btn--primary btn--sm" onClick={handleVerify} disabled={verifying}>
              {verifying ? "Checking DNS…" : "Verify now"}
            </button>
          </div>
          {verifyMsg && <p className="domain-note verify-msg">{verifyMsg}</p>}
        </div>
      )}

      {/* ── Verified: scan button ── */}
      {domainStatus === "verified" && !scan && (
        <div className="card-actions">
          <button className="btn btn--primary btn--sm" onClick={handleScan} disabled={scanning}>
            {scanning ? "Starting scan…" : "Run security scan"}
          </button>
        </div>
      )}

      {/* ── Scan in progress ── */}
      {scan && (scan.status === "queued" || scan.status === "running") && (
        <div className="scan-running">
          <span className="scan-spinner" aria-hidden="true" />
          <p className="domain-note">
            Running checks: HTTP headers · TLS certificate · DNS records…
          </p>
        </div>
      )}

      {/* ── Scan failed ── */}
      {scan?.status === "failed" && (
        <p className="domain-note msg--error">
          Scan failed: {scan.fail_reason ?? "unknown error"}
        </p>
      )}

      {/* ── Scan complete: severity grid ── */}
      {scan?.status === "complete" && counts !== undefined && (
        <>
          <div className="sev-grid">
            {SEV_ORDER.map((s) => (
              <div key={s} className={`sev-cell sev--${s}`}>
                <span className="sev-count">{counts[s] ?? 0}</span>
                <span className="sev-label">{s}</span>
              </div>
            ))}
          </div>
          <div className="card-actions">
            <button className="btn btn--ghost btn--sm" onClick={handleScan} disabled={scanning}>
              Run again
            </button>
          </div>
        </>
      )}
    </div>
  );
}
