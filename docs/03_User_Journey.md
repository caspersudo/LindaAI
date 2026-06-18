# LindaAI — User Journey Flow

**Document:** 3 of 6
**Persona for this walkthrough:** Wanjiku, non-technical law-firm owner, on her phone.

---

## 1. End-to-End Sequential Flow

```
[1] LANDING
     │  Sees: "Is your business website safe? Find out in 2 minutes."
     │  One field (domain) + "Check my site." Trust signals: passive-only,
     │  you-must-own-it, sample report, price (first scan free).
     ▼
[2] SIGN-UP  ───────────────────────────────────────────────►  Supabase Auth
     │  Email + password. "Why an account? So only YOU can scan
     │  your domain." → verification email sent.
     ▼
[3] VERIFY EMAIL
     │  Clicks link → returns to app → org auto-created → empty dashboard.
     ▼
[4] ADD DOMAIN
     │  Enters wanjikulaw.co.ke. We validate format, create
     │  verified_domains row (status=pending) + linda-verify token.
     ▼
[5] OWNERSHIP WIZARD  (3 steps, can't be skipped)
     │  Step A: "Copy this TXT record."  [ linda-verify=ab12…  📋 ]
     │  Step B: "Add it at your registrar." (links: Truehost, Safaricom,
     │           Kenya Web Experts, GoDaddy guides)
     │  Step C: [ Verify now ]
     │     └─► backend resolves TXT → found? ─ yes ─► status=verified ✅
     │                                        └ no ──► friendly retry,
     │                                                 60s cooldown,
     │                                                 "DNS can take a few minutes."
     ▼
[6] RUN SCAN
     │  Dashboard now shows the verified domain with a [ Run scan ] button.
     │  (No free-text target — you can only pick a verified domain.)
     │  POST /scans → 202 { scan_id, status:queued }
     ▼
[7] LOADING STATE  (low-overhead, honest)
     │  Poll GET /scans/{id} every 2–3s. Progress copy:
     │    queued  → "Queued…"
     │    running → "Checking certificate · headers · DNS"
     │    cold    → "Waking up the scanner (only after a quiet spell)…"
     │  No spinner-of-doom: a 3-step checklist ticks off as checks finish.
     ▼
[8] RESULTS SUMMARY
     │  status=complete → severity grid: Critical / High / Medium / Low
     │  counts + the top-priority finding highlighted.
     │  Free tier shows counts + top finding; full per-finding detail
     │  is behind the report.
     ▼
[9] PAYMENT  (only for the detailed report; first one free)
     │  [ Get full report — KES 50 ] → enter M-Pesa number →
     │  STK push to phone → user enters PIN → Daraja callback →
     │  payment row reconciled → report unlocked.
     ▼
[10] LOCALIZED PDF
     │  Picks language (English / Kiswahili). Server builds PDF on demand:
     │  LLM summary + static per-finding explanations, Critical→Low,
     │  + 1-page checklist. [ Download ] / [ Share ].
     ▼
[11] AFTER
        Dashboard lists scan history. CTA: "Re-scan after you apply fixes."
```

## 2. Logical Data Map (what each step writes/reads)

| Step | Reads | Writes | External call |
|---|---|---|---|
| 2 Sign-up | — | `auth.users` | Supabase Auth |
| 3 Verify email | `auth.users` | `organizations`, `users` profile | — |
| 4 Add domain | `verified_domains` | `verified_domains(status=pending, token)` | — |
| 5 Verify (C) | `verified_domains` | `verified_domains(status=verified, verified_at)` | DNS TXT lookup |
| 6 Run scan | `verified_domains` | `scans(status=queued)` | — |
| 7→ run | `scans` | `scans(status=running→complete, raw_findings)` | HTTP/TLS/DNS probes |
| 8 Summary | `scans`, `vulnerability_summaries` | `vulnerability_summaries` (rollup) | — |
| 9 Payment | `scans` | `payments(status=…)` | Daraja STK + callback |
| 10 PDF | `scans`, `findings.json` | `scans(llm_tokens…)` | GPT-4o-mini (summary only) |

## 3. Failure & Edge Paths (designed, not afterthoughts)

| Situation | What the user sees | System behavior |
|---|---|---|
| TXT not found yet | "Not visible yet — DNS can take 5–30 min. Try again shortly." | status stays `pending`; 60s cooldown; no error tone. |
| Tries to scan unverified domain | Button disabled + tooltip "Verify this domain first." | Endpoint also returns 403 (defense in depth). |
| Target site is down during scan | "We couldn't reach your site. Is it online?" + retry | individual check returns error; other checks still run. |
| Cold start | "Waking up the scanner…" | poll waits out spin-up, then succeeds. |
| STK push not completed | "Payment not received — try again." report stays locked | callback never arrives / fails validation. |
| Scan finds nothing alarming | "Good news — no major issues found on the surface. Note: this is a passive check, not a full audit." | honest framing, avoids false security. |

## 4. The Two Moments That Decide Success
1. **The TXT wizard (Step 5)** — the highest-friction, highest-drop step. Registrar-specific guides, copy buttons, and a forgiving retry tone are make-or-break.
2. **The summary reveal (Step 8)** — the "aha." Must feel like relief and clarity, never a wall of red. Lead with the single most important fix, not the longest list.
