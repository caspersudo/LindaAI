# LindaAI — Technical Requirements Document (TRD)

**Document:** 2 of 6
**Stack:** Next.js (Vercel free) · FastAPI (Render free) · PostgreSQL (Supabase free) · GPT-4o-mini · Daraja
**Guiding constraint:** zero paid security APIs, all scanning is **passive** and **ownership-gated**.

---

## 1. System Overview

```
 ┌──────────────┐   HTTPS/JSON   ┌─────────────────────┐
 │  Next.js UI  │ ─────────────► │  FastAPI on Render  │
 │  (Vercel)    │ ◄───────────── │  (single web svc)   │
 └──────┬───────┘   poll status  └─────────┬───────────┘
        │                                  │
        │ Supabase JS (auth, reads)        │ asyncpg + httpx + dnspython + ssl
        ▼                                  ▼
 ┌─────────────────────────────────────────────────────┐
 │   Supabase Postgres  (auth · domains · scans · jsonb)│
 └─────────────────────────────────────────────────────┘
        ▲                                  │
        │ Daraja webhook (payments)        │ on-demand
        │                                  ▼
 ┌──────────────┐                  ┌────────────────┐
 │  Safaricom   │                  │  GPT-4o-mini   │  (summary only)
 │  Daraja API  │                  └────────────────┘
 └──────────────┘
```

Three trust boundaries: the browser (Supabase RLS-protected reads), the FastAPI service (holds the only secrets that can run scans + call the LLM + verify M-Pesa), and Postgres (row-level security on every table).

## 2. Asynchronous Architecture on a Free Tier (the hard part)

### 2.1 The constraints we must design around
- **Render free web service** spins down after ~15 min idle; **cold start ≈ 30–60 s**. There is **no separate background-worker dyno** on free tier — async work must live **inside the one web process**.
- Long-held HTTP connections risk Render's request timeout and frontend fetch timeouts.
- **Supabase free** pauses a project after 7 days of inactivity and caps at 500 MB.

### 2.2 The pattern: DB-backed job + short worker + polling
We deliberately **avoid** websockets, Celery, Redis, and external queues (all add cost/ops). A scan is short (three passive checks, typically < 8 s warm), so we use:

1. **Enqueue (fast, returns immediately).** `POST /scans` validates ownership, inserts a `scans` row with `status='queued'`, schedules the work with **FastAPI `BackgroundTasks`**, and returns `{ scan_id }` in < 300 ms.
2. **Run (in-process background task).** The task flips `status='running'`, executes the three checks concurrently with `asyncio.gather`, writes `raw_findings` (JSONB) and `status='complete'` (or `'failed'` + reason).
3. **Poll (frontend).** UI calls `GET /scans/{id}` every 2–3 s. Cheap, stateless, survives cold starts (a poll that hits a cold instance simply waits out the spin-up, then succeeds).

```python
# main.py — enqueue endpoint (abbreviated, FastAPI)
@app.post("/scans", status_code=202)
async def create_scan(body: ScanCreate, bg: BackgroundTasks, user=Depends(current_user)):
    domain = await get_verified_domain(body.domain_id, owner=user.id)
    if domain is None or domain.status != "verified":
        raise HTTPException(403, "Domain not verified or not owned by you")
    scan_id = await insert_scan(domain_id=domain.id, org_id=domain.org_id, status="queued")
    bg.add_task(run_scan, scan_id, domain.hostname)   # runs after response is sent
    return {"scan_id": scan_id, "status": "queued"}
```

```python
async def run_scan(scan_id: str, hostname: str):
    await set_scan_status(scan_id, "running")
    try:
        headers, tls, dns = await asyncio.gather(
            check_http_headers(hostname),
            check_tls(hostname),
            check_dns(hostname),
            return_exceptions=True,            # one failing check never aborts the rest
        )
        findings = normalize_findings(headers, tls, dns)   # -> list[dict]
        await save_findings(scan_id, findings, status="complete")
    except Exception as e:
        await set_scan_status(scan_id, "failed", reason=str(e)[:300])
```

### 2.3 Cold-start handling (UX contract)
- Frontend treats the first poll specially: if `GET /scans/{id}` takes > 3 s, switch the loading copy to **"Waking up the scanner… (this only happens after a quiet period)."**
- A lightweight **keep-warm** is optional: a free uptime pinger (e.g. a cron-job.org GET to `/healthz` every 10 min during business hours) keeps the dyno warm cheaply without violating free-tier terms. Document it as optional, not required.
- Idempotency: `run_scan` checks current status before writing, so a duplicated background task (rare, on restart) cannot double-charge or double-write.

### 2.4 Why not synchronous?
A warm scan would finish inside one request, but a **cold** request (60 s) plus the scan would routinely exceed browser/Vercel fetch timeouts and feel broken. The job+poll model degrades gracefully instead.

## 3. Zero-Cost Passive Scanning Engine

**Rules baked into every probe:** target must be a verified hostname; **one** request per check; 5 s timeout; no retries that constitute probing; a descriptive `User-Agent: LindaAI-Scanner/1.0 (+https://lindaai.…/scanner)`. These are passive observations any browser/email server makes — never active exploitation.

### 3.1 HTTP security headers
```python
SECURITY_HEADERS = {
    "strict-transport-security":  ("HSTS",          "medium"),
    "content-security-policy":    ("CSP",           "medium"),
    "x-frame-options":            ("X-Frame-Options","medium"),
    "x-content-type-options":     ("X-Content-Type","low"),
    "referrer-policy":            ("Referrer-Policy","low"),
    "permissions-policy":         ("Permissions-Policy","low"),
}

async def check_http_headers(hostname: str) -> dict:
    findings, url = [], f"https://{hostname}"
    async with httpx.AsyncClient(timeout=5, follow_redirects=False) as c:
        try:
            r = await c.get(url, headers={"User-Agent": UA})
        except httpx.RequestError as e:
            return {"category": "http", "error": str(e), "findings": []}

    present = {k.lower(): v for k, v in r.headers.items()}

    # (a) missing security headers
    for key, (label, sev) in SECURITY_HEADERS.items():
        if key not in present:
            findings.append(mk("missing-" + key, sev))

    # (b) server banner leaks a version  e.g. "nginx/1.18.0"
    if any(ch.isdigit() for ch in present.get("server", "")):
        findings.append(mk("server-version-disclosed", "low",
                           detail=present["server"]))

    # (c) cookie flags
    for cookie in r.headers.get_list("set-cookie"):
        low = cookie.lower()
        if "secure" not in low or "httponly" not in low:
            findings.append(mk("weak-cookie-flags", "high",
                               detail=cookie.split("=")[0]))

    # (d) HTTP -> HTTPS redirect (one extra plain request, still passive)
    async with httpx.AsyncClient(timeout=5, follow_redirects=False) as c:
        try:
            h = await c.get(f"http://{hostname}", headers={"User-Agent": UA})
            if h.status_code not in (301, 302, 307, 308):
                findings.append(mk("no-https-redirect", "medium"))
        except httpx.RequestError:
            pass
    return {"category": "http", "findings": findings}
```

### 3.2 TLS / SSL certificate (Python native `ssl`, no paid API)
```python
import ssl, socket
from datetime import datetime, timezone

async def check_tls(hostname: str) -> dict:
    findings = []
    ctx = ssl.create_default_context()
    loop = asyncio.get_running_loop()
    def _handshake():
        with socket.create_connection((hostname, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ss:
                return ss.getpeercert(), ss.version()
    try:
        cert, tls_version = await loop.run_in_executor(None, _handshake)
    except ssl.SSLCertVerificationError as e:
        if "self signed" in str(e).lower():
            return {"category": "tls", "findings": [mk("self-signed-cert", "high")]}
        return {"category": "tls", "findings": [mk("cert-validation-failed", "high",
                                                   detail=str(e)[:120])]}
    except (socket.timeout, OSError) as e:
        return {"category": "tls", "findings": [mk("no-tls", "critical",
                                                   detail=str(e)[:120])]}

    not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")\
                        .replace(tzinfo=timezone.utc)
    days_left = (not_after - datetime.now(timezone.utc)).days
    if days_left < 0:    findings.append(mk("cert-expired", "critical", detail=f"{days_left}d"))
    elif days_left < 14: findings.append(mk("cert-expiring-soon", "high", detail=f"{days_left}d"))
    elif days_left < 30: findings.append(mk("cert-expiring", "medium", detail=f"{days_left}d"))

    if tls_version in ("TLSv1", "TLSv1.1"):
        findings.append(mk("outdated-tls-version", "medium", detail=tls_version))
    return {"category": "tls", "findings": findings}
```

### 3.3 Passive DNS (dnspython — pure lookups, no zone transfer, no brute force)
```python
import dns.asyncresolver as r

async def check_dns(hostname: str) -> dict:
    findings = []
    async def q(name, rtype):
        try:    return [str(x) for x in await r.resolve(name, rtype)]
        except Exception: return []

    a    = await q(hostname, "A")
    mx   = await q(hostname, "MX")
    spf  = [t for t in await q(hostname, "TXT") if "v=spf1" in t.lower()]
    dmarc= await q(f"_dmarc.{hostname}", "TXT")
    caa  = await q(hostname, "CAA")

    if not a:                       findings.append(mk("no-a-record", "medium"))
    if mx and not spf:              findings.append(mk("missing-spf", "high"))
    if mx and not dmarc:            findings.append(mk("missing-dmarc", "high"))
    if not caa:                     findings.append(mk("no-caa", "low"))
    return {"category": "dns", "findings": findings}
```

`mk(id, severity, detail=None)` returns `{"id": id, "severity": severity, "detail": detail}`. **No** free-text security content is generated here — that lives in the static mapping (see §4.2), which is the entire cost trick.

## 4. Token-Optimized AI Pipeline

### 4.1 Principle: the LLM is the smallest possible component
Most "report generation" is **deterministic** and should never touch the LLM. The `findings.json` mapping turns each finding `id` into pre-written, human-reviewed `{title, business_impact, fix}` strings in EN and SW — **zero tokens, zero cost, perfect consistency**. The LLM is used for exactly one thing it's good at and a table can't do: a short, personalized **executive summary** that reflects *this* domain's specific mix and severity of findings.

### 4.2 Pre-filtering → minimum tokens
Before any API call we (1) drop every passing/`OK` check (the engine already only emits problems), (2) deduplicate, (3) sort by severity, (4) send the LLM only a compact list of finding `id`s + severities + counts — **never raw logs or header dumps.**

```python
def build_llm_input(findings: list[dict]) -> str:
    # one tiny line per finding, e.g. "high: missing-dmarc x1"
    rolled = collections.Counter((f["severity"], f["id"]) for f in findings)
    lines  = [f'{sev}: {fid} x{n}' for (sev, fid), n in rolled.items()]
    return "\n".join(sorted(lines))      # ~10–25 tokens for a typical scan
```

### 4.3 Exact prompt + required JSON contract
System prompt (terse, costs input tokens once):
> You write a 3–4 sentence security summary for a non-technical Kenyan small-business owner. Input is a list of detected issues. Be calm, concrete, prioritized. Output **only** valid JSON matching the schema. Language: {EN|SW}.

The model returns **strictly** this shape (validated with Pydantic; on failure, retry once then fall back to a templated summary):
```json
{
  "overall_risk": "high",
  "summary": "Your website's biggest issue is an expiring security certificate; within two weeks visitors may see a scary warning. Email impersonation is also possible because anti-spoofing records are missing. None of this requires rebuilding your site — three small fixes resolve most of it.",
  "top_priority_id": "cert-expiring-soon"
}
```

The full report PDF is then assembled **locally**: LLM `summary` + static `findings.json` entries (looked up by id) for every finding, ordered Critical→Low. **The per-finding explanations never come from the LLM**, capping and stabilizing cost.

### 4.4 Cost accounting (verified against the KES 0.20 target)
| Component | Tokens | Cost (4o-mini @ $0.15/M in, $0.60/M out) |
|---|---|---|
| System + filtered input | ~280 in | $0.000042 |
| Summary output | ~120 out | $0.000072 |
| **Total LLM / report** | — | **≈ $0.00011 ≈ KES 0.015** |

That is **~13× under** the KES 0.20 ceiling, leaving headroom for one retry and for occasionally letting the LLM phrase an unmapped edge-case finding. We log `prompt_tokens`/`completion_tokens` per report into the `scans` row for live KPI tracking.

### 4.5 Guardrails
- Hard cap `max_tokens=400`; reject/repair non-JSON; never send PII or raw headers to the LLM.
- Per-org rate limit on report generation to prevent token-cost abuse.
- Temperature low (0.3) for stable, non-alarmist phrasing.

## 5. Security & Secrets
- All scan-capable secrets (LLM key, Daraja consumer secret, Supabase service key) live **only** on Render env vars, never in the browser.
- Supabase **Row-Level Security** on every table: a user reads only rows where `org_id` ∈ their orgs.
- Daraja callbacks verified by source + amount + reference before unlocking a report.
- The scanner's allow-rule (verified-domain-only) is enforced server-side and unit-tested.

## 6. Observability (free)
- Structured JSON logs to Render's log stream.
- A `scan_metrics` view aggregating cost/latency for the KPI dashboard.
- `/healthz` for the optional keep-warm pinger.
