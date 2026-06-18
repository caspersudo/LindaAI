# LindaAI — Lean 4-Week Implementation Plan

**Document:** 6 of 6
**Team:** one engineer + an AI pair (you + me). Laptop only. Free tiers only.
**Cadence:** each week ends with a *demoable, deployed* increment. Ship small, ship often.

---

## Operating rules for the whole build
- **Deploy on day 1, not week 4.** A "Hello LindaAI" page is live on Vercel before any feature exists.
- **Vertical slices over layers.** Each week produces something a user could touch end-to-end, not just a backend nobody can see.
- **The ownership gate is built before the scanner.** We never write scan code that can run without a `verified` domain.
- **Cost telemetry from the first LLM call.** Every report logs tokens → `scans` row → we watch the KES 0.20 target live.

---

## Week 1 — Skeleton, Auth, and the Database
**Theme:** "It's online, I can log in, my domain is saved."

| Day | Task | Output |
|---|---|---|
| 1 | Repo + Next.js app, deploy to Vercel; FastAPI hello-world to Render; `/healthz`. | Two live URLs. |
| 1 | Create Supabase project; run `05_schema.sql`; enable RLS; confirm `auth.users` link. | Schema live, RLS on. |
| 2 | Supabase Auth: email/password sign-up, email verification, session handling in Next.js. | Working login. |
| 2 | On first login, auto-create `organizations` + `users` profile row (DB trigger or app code). | Org per user. |
| 3 | Dashboard shell (navy/green per UI brief), empty state, nav, "Add domain" CTA. | Dashboard renders. |
| 3–4 | "Add domain" form → validates hostname → inserts `verified_domains(status=pending)` + token. | Pending domain row. |
| 4 | Wire frontend reads through RLS (user only sees own org's rows). Manual security test. | Isolation verified. |
| 5 | Buffer / polish / write README + env-var docs. **Demo:** sign up → add a domain. | Week-1 increment shipped. |

**Definition of done:** a stranger can sign up, log in, and see their pending domain. No scanning yet.
**Risks:** Supabase RLS misconfig (test with two accounts), Render cold start (acceptable, no scans yet).

---

## Week 2 — Ownership Verification + the Passive Scanner
**Theme:** "I proved I own it, and I can run a real scan."

| Day | Task | Output |
|---|---|---|
| 1 | TXT verification endpoint: resolve `verified_domains` token via dnspython; flip to `verified`. | Verification works. |
| 1 | 3-step wizard UI (copy TXT, registrar guides, "Verify now", forgiving retry). | Wizard live. |
| 2 | Scan job model: `POST /scans` (202 + scan_id), `BackgroundTasks`, `GET /scans/{id}` poll. | Async plumbing. |
| 2–3 | Implement `check_http_headers` (TRD §3.1) incl. cookie flags + redirect check. | Headers check. |
| 3 | Implement `check_tls` (native `ssl`, expiry/version/self-signed). | TLS check. |
| 3 | Implement `check_dns` (A/MX/SPF/DMARC/CAA). | DNS check. |
| 4 | `asyncio.gather` orchestration + `normalize_findings`; write `raw_findings` JSONB. | End-to-end scan. |
| 4 | **Hard gate test:** scanning an unverified domain returns 403. Unit-test it. | Gate enforced. |
| 5 | Frontend loading checklist + severity grid (counts only); cold-start copy. **Demo:** verify → scan → see grid. | Week-2 increment shipped. |

**Definition of done:** a verified domain produces real findings; an unverified one is refused.
**Risks:** Render free tier blocking outbound:443 (test early), DNS timeouts (5s cap + graceful per-check errors).

---

## Week 3 — The Token-Optimized AI Report (EN + SW)
**Theme:** "I get a clear, prioritized report in my language."

| Day | Task | Output |
|---|---|---|
| 1 | Author `mappings/findings.json`: every finding id → {title, impact, fix} in EN + SW (draft). | Static mapping. |
| 1 | `build_llm_input` pre-filter (TRD §4.2) — compact id+severity lines only. | Min-token input. |
| 2 | GPT-4o-mini call: terse system prompt, JSON-only output, Pydantic validation + 1 retry + template fallback. | Summary generated. |
| 2 | Log `prompt/completion tokens` + computed `cost_kes` to the `scans` row. | Live cost KPI. |
| 3 | `vulnerability_summaries` rollup (counts, top_priority_id, summary_en/sw). | Rollup persisted. |
| 3–4 | On-demand PDF builder: LLM summary + static per-finding cards, Critical→Low, +checklist. (e.g. WeasyPrint / ReportLab) | PDF renders. |
| 4 | Language toggle EN/SW; render both; native-speaker review pass on Swahili strings. | Bilingual report. |
| 5 | Verify measured cost ≤ KES 0.20 across 10 sample domains. **Demo:** download EN + SW PDF. | Week-3 increment shipped. |

**Definition of done:** a real scan yields a downloadable, prioritized, jargon-free PDF in both languages, under budget.
**Risks:** LLM returning non-JSON (validate+repair), Swahili quality (human gate), PDF font support for diacritics (use Noto).

---

## Week 4 — Payments, Hardening, Launch
**Theme:** "I can pay with M-Pesa and it just works."

| Day | Task | Output |
|---|---|---|
| 1 | Daraja sandbox: STK push initiation endpoint; create `payments(status=initiated)`. | STK push fires. |
| 1–2 | Daraja callback webhook: validate, set `paid` + `mpesa_receipt`, unlock report. Replay-guard via unique receipt. | Reconciliation works. |
| 2 | Paywall UX: first scan free, locked report blurred + "Get full report — KES 50", WhatsApp share. | Monetization live. |
| 3 | End-to-end tests: signup→verify→scan→pay→report. Edge paths from Journey §3. | E2E green. |
| 3 | Security pass: secrets only on Render, RLS re-audit, scan gate re-test, rate limits on scan + report. | Hardened. |
| 4 | Observability: structured logs, `scan_metrics` view, optional keep-warm pinger on `/healthz`. | Monitoring on. |
| 4 | Switch Daraja to production creds; final cost + latency check against KPIs. | Prod-ready. |
| 5 | Soft launch to 3–5 friendly Kenyan SMEs; collect feedback. **Launch.** | LindaAI live 🎉 |

**Definition of done:** a paying user completes the full journey on production infra, reconciled via M-Pesa, within KPI targets.
**Risks:** Daraja callback only reaches public HTTPS (Render URL is fine; localhost needs a tunnel in dev), STK timeouts (clear "payment not received" path), going-live credential mix-ups (checklist + dry run).

---

## Post-MVP backlog (not in 4 weeks, parked deliberately)
Scheduled re-scans & change alerts · team seats/roles · more checks (mixed-content, basic CMS fingerprint, subdomain inventory from CT logs) · branded/white-label reports for web agencies · annual prepaid bundles · email-delivered reports.

## What I (your AI pair) will drive each week
- **W1:** generate the Next.js + FastAPI scaffolds, the Supabase migration, and the org-creation trigger.
- **W2:** write and unit-test the three scanner functions and the job/poll endpoints.
- **W3:** draft the full `findings.json` (EN+SW), the prompt, the Pydantic models, and the PDF template.
- **W4:** write the Daraja STK + callback handlers, the E2E test script, and the launch checklist.
