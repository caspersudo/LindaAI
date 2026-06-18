# LindaAI 🛡️
**Security-Audit-as-a-Service for Kenyan SMEs.** *Linda* = "protect" in Swahili.

A passive, ownership-gated vulnerability scanner that turns dense security signals into a clear, prioritized PDF report in **English or Kiswahili** — built to run entirely on **free-tier infrastructure** at **< KES 0.20 per scan**.

## Stack
Next.js (Vercel) · FastAPI (Render) · PostgreSQL (Supabase) · GPT-4o-mini (summary only) · Daraja / M-Pesa

## The one rule that defines this product
LindaAI **only scans domains the user has proven they own** (DNS TXT verification). Every check is passive — the same observations a browser or mail server makes. No active probing, ever. This is what makes it a defensive auditing tool, not scanning tooling.

## Blueprint documents
| # | Document | What it covers |
|---|---|---|
| 1 | `01_PRD.md` | Problem, personas, MVP scope, EN/SW impact mapping, KPIs, risks |
| 2 | `02_TRD.md` | Free-tier async architecture, passive scanner pseudo-code, token-optimized AI pipeline |
| 3 | `03_User_Journey.md` | Step-by-step flow, data map, failure paths |
| 4 | `04_UIUX_Brief.md` | Visual identity (navy/green/white), component blueprints, accessibility |
| 5 | `05_schema.sql` | Production PostgreSQL DDL with RLS, validated to parse |
| 6 | `06_Implementation_Plan.md` | Lean 4-week agile build, demoable each week |

## Cost thesis (verified)
Static `findings.json` mapping does the per-finding explanations for free; the LLM writes only a 3–4 sentence personalized summary → **≈ KES 0.015 / report**, ~13× under target.
