# LindaAI — Product Requirements Document (PRD)

**Document:** 1 of 6 · **Status:** MVP scope, locked
**Product:** LindaAI — Security-Audit-as-a-Service for Kenyan SMEs
**One-line:** "Linda" means *protect/guard* in Swahili. We protect small businesses that went online without a security budget.

---

## 1. Problem

Kenyan SMEs — law firms, private clinics, retailers, SACCOs — are moving online fast (M-Pesa storefronts, booking sites, patient portals) but operate with **zero cybersecurity infrastructure**. A proper penetration test from a Nairobi consultancy costs KES 80,000–500,000, which is out of reach. The result: avoidable ransomware, defacement, customer-data leaks, and M-Pesa/email impersonation fraud.

The gap is not a lack of tools — it is a lack of **translation**. The signals that reveal a weak security posture (missing HTTP headers, an expiring TLS certificate, no SPF/DMARC records) are already publicly observable, but they are written for engineers. A clinic owner cannot act on `Strict-Transport-Security: missing`.

## 2. Target User

| Attribute | Detail |
|---|---|
| Primary persona | **Wanjiku, 41**, owns a 3-lawyer firm in Nakuru. Has a website built by a freelancer who has since vanished. Non-technical. Worried after a peer firm got "hacked." |
| Secondary persona | **Brian, 29**, IT-curious clinic admin who manages the WordPress site part-time. Slightly technical, wants a checklist to hand his web guy. |
| Anti-persona (out of scope) | Security professionals, red-teamers. They have better tools. We will not build for them. |
| Device reality | Mobile-first. Most will open the report on a phone. Bandwidth is metered. |

## 3. Goals & Non-Goals

**Goals (MVP)**
- Let a non-technical owner discover, in plain English or Swahili, the top security risks on a domain **they own**, and what to do about each.
- Prove the unit economics: a full scan + AI report must cost **< KES 0.20 (≈ $0.0016)** in variable cost.
- Run end-to-end on **free-tier infrastructure** with **zero paid security APIs**.

**Non-Goals (explicitly out of scope for MVP)**
- ❌ Active or intrusive scanning (no port scans, fuzzing, login attempts, payload injection, or rate-heavy probing).
- ❌ Scanning domains the user has **not** verified ownership of. This is a hard product and ethical boundary, not a nice-to-have.
- ❌ Continuous monitoring, scheduled re-scans, alerting (post-MVP).
- ❌ Multi-user roles / team seats beyond a single owner per organization (post-MVP).
- ❌ Storing generated PDFs long-term. Reports are generated **on demand** from stored scan JSON.

## 4. The Ownership-Verification Principle (read this first)

LindaAI only ever inspects assets the user has **proven they control**. Every scan target must map to a row in `verified_domains` with `status = 'verified'`. Verification uses a **DNS TXT record** the user adds to their own zone:

```
linda-verify=<random_32_char_token>
```

If the TXT record is absent, the scan endpoint returns `403` and never touches the target. This single rule is what makes LindaAI a defensive auditing product rather than a scanning tool, and it must never be relaxed, bypassed, or made optional — including for "demo" domains, which use a pre-owned sandbox we control.

## 5. MVP Feature Set (zero-cost only)

### F1 — Sign-up / Login
- Email + password auth via **Supabase Auth** (free tier, no extra service).
- Email verification link required before first scan.
- On first login, auto-create one `organization` row for the user.
- No social login in MVP (avoids OAuth app-review overhead).

### F2 — Domain Ownership Verification (DNS TXT)
- User enters a root domain (e.g. `wanjikulaw.co.ke`). We normalize and validate format.
- System generates a one-time token, stores a `verified_domains` row with `status='pending'`.
- UI shows a **3-step wizard**: (1) copy this TXT record → (2) add it at your registrar → (3) "Verify now."
- Backend resolves TXT records and looks for the token. Match → `status='verified'`. No match → friendly retry with a 60-second cooldown (DNS propagation guidance).
- Token never expires while pending but can be rotated by the user.

### F3 — Single-Input Passive Scan Engine
- One input: a verified domain (dropdown of the org's verified domains, never free text at scan time).
- Runs three passive checks (full logic in TRD §3):
  1. **HTTP security headers** — single `GET`, inspect HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, cookie flags, server banner, HTTP→HTTPS redirect.
  2. **TLS/SSL** — certificate expiry, issuer, hostname match, negotiated TLS version, self-signed detection.
  3. **Passive DNS** — A/AAAA, MX, NS, SPF (TXT), DMARC, CAA presence.
- **Hard constraints:** one request per check type, sane timeouts (5s), a global rate limit, and a strict allow-rule that the target must be a verified domain. No retries that amount to probing.

### F4 — On-Demand Localized PDF Report
- Generated when the user clicks "Download report," not stored.
- Plain-language, prioritized (Critical → Low), bilingual (user picks EN or SW per report).
- Contains: executive summary, per-finding {what it is, why it matters to *your business*, how to fix}, and a one-page checklist.

## 6. Localization & Plain-Language Mapping

Every technical finding maps to a **business-impact statement**, not a definition. The mapping is a **static table shipped in code** (no LLM cost — see TRD §4). The LLM is used only to weave a personalized 3–4 sentence executive summary, which is where natural language genuinely adds value.

Representative mapping (full table lives in `mappings/findings.json`):

| Finding (technical) | Severity | Business impact — English | Business impact — Swahili |
|---|---|---|---|
| Missing `Strict-Transport-Security` | Medium | Visitors can be silently downgraded to an insecure connection, letting an attacker on the same Wi-Fi read what they type. | Wateja wanaweza kuunganishwa kwa njia isiyo salama, na mtu kwenye mtandao huo huo akasoma taarifa wanazoandika. |
| TLS certificate expires < 14 days | High | Soon browsers will show your customers a red "Not secure" warning and many will leave, costing you sales and trust. | Hivi karibuni vivinjari vitaonyesha onyo jekundu "Si salama," na wateja wengi wataondoka — utapoteza mauzo na imani. |
| No SPF / DMARC record | High | Anyone can send email that looks like it's from your domain — a common trick for fake invoices and M-Pesa fraud. | Mtu yeyote anaweza kutuma barua pepe inayoonekana kana kwamba ni yako — mbinu ya kawaida ya ankara za uongo na ulaghai wa M-Pesa. |
| Server version disclosed in banner | Low | Your website tells attackers exactly which software version you run, making it easier to find a matching exploit. | Tovuti yako inawaambia washambuliaji toleo halisi la programu unayotumia, kuwarahisishia kupata udhaifu unaolingana. |
| Missing `X-Frame-Options` / frame-ancestors | Medium | Your site can be hidden inside a fake page to trick users into clicking things they didn't mean to (clickjacking). | Tovuti yako inaweza kufichwa ndani ya ukurasa bandia ili kuwadanganya watumiaji wabofye vitu bila kukusudia. |
| Cookies without `Secure` / `HttpOnly` | High | A logged-in customer's session can be stolen, letting an attacker act as them. | Kipindi cha mteja aliyeingia kinaweza kuibiwa, na mshambuliaji akajifanya kuwa yeye. |
| No HTTP→HTTPS redirect | Medium | Some visitors stay on an unencrypted version of your site without realizing it. | Baadhi ya wageni hubaki kwenye toleo lisilo na usimbaji bila kujua. |

**Tone rules for all copy:** no jargon in the impact line; jargon allowed only in a collapsed "technical detail" footer. Swahili is reviewed by a native speaker before launch (the strings above are drafts, not final).

## 7. Success Metrics (KPIs)

| KPI | Target (MVP, first 90 days) | Why |
|---|---|---|
| **Variable cost per scan** | ≤ KES 0.20 (≤ $0.0016) | Core thesis. Tracked from token usage logs (TRD §4). |
| LLM tokens per report | ≤ 1,500 in / ≤ 700 out | Driven by pre-filtering; the lever for cost. |
| Scan-to-report success rate | ≥ 95% | Reliability of the free-tier pipeline. |
| Median scan completion | ≤ 12 s (warm), ≤ 70 s (cold start) | UX on Render free tier. |
| Visitor → verified-domain conversion | ≥ 15% | Verification is the funnel's hardest step. |
| Verified → first-paid-scan conversion | ≥ 25% | Validates willingness to pay. |
| Repeat scans / paying user / month | ≥ 1.5 | Early retention signal. |

## 8. Monetization (MVP)

Pay-as-you-go via **Safaricom Daraja (M-Pesa) STK Push**. No subscription, no upfront fee. Suggested price **KES 50–100 per detailed report**, with the first scan free to drive the funnel. Commission/markup sits comfortably above the ≤ KES 0.20 variable cost. Webhook reconciliation detailed in TRD and the 4-week plan (Week 4).

## 9. Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| User scans a domain they don't own | Hard-gated by `verified_domains`; scan endpoint returns 403 otherwise. Non-negotiable. |
| Render free tier cold starts frustrate users | Async job + polling, explicit "waking the scanner" state, scans kept short (TRD §2). |
| LLM cost creep | Static mapping does the heavy lifting; LLM only writes the summary; hard token cap + per-org rate limit. |
| Supabase free tier storage cap (500 MB) | Store compact scan JSON only; **never** store generated PDFs; prune raw logs after report generation. |
| False sense of security ("scan passed = I'm safe") | Report states clearly this is a passive surface check, not a full pen-test; recommends a professional audit for sensitive data. |
| Swahili quality | Native-speaker review gate before launch; strings versioned in `mappings/`. |

## 10. Acceptance Criteria (MVP "done")

1. A new user can sign up, verify email, and land on an empty dashboard.
2. The user can add a domain, follow the TXT wizard, and reach `verified` state.
3. The user can run a scan **only** on a verified domain; an unverified target is refused.
4. A scan produces stored JSON findings within the latency targets.
5. The user can download an EN **and** a SW PDF, each prioritized and jargon-free.
6. A completed M-Pesa STK push unlocks the detailed report and is reconciled via webhook.
7. Measured variable cost of one full scan+report is ≤ KES 0.20.
