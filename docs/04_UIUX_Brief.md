# LindaAI — UI/UX Design Brief

**Document:** 4 of 6
**Design north star:** A worried non-technical owner should feel *calmer and clearer* after using LindaAI — never more confused or more scared.

---

## 1. Design Principles
1. **Trust over flash.** This is security software for skeptical users. Calm, solid, unglamorous-but-credible beats trendy.
2. **One decision per screen.** Never present two primary actions at once.
3. **Plain language everywhere.** If a sentence needs a CS degree, it's wrong. Jargon lives only in a collapsed "technical detail."
4. **Mobile-first, low-bandwidth.** System fonts, no heavy hero images, works on a mid-range Android on metered data.
5. **Honest, not alarmist.** Severity is shown with restraint. Green for safe, never a screen drenched in red.

## 2. Visual Identity

### Palette (trust · accessibility · clarity)
| Token | Hex | Use |
|---|---|---|
| `--navy-900` | `#0A2540` | Primary text, headers, trust anchor |
| `--navy-700` | `#163B5C` | Secondary surfaces, nav |
| `--green-600` | `#1B7F5C` | Brand primary, "safe", CTAs |
| `--green-100` | `#E6F4EE` | Success backgrounds, subtle fills |
| `--white` | `#FFFFFF` | Base background |
| `--mist-50` | `#F6F8FA` | Card/section backgrounds |
| `--border` | `#E2E8F0` | Hairlines, dividers |

### Severity colors (used *only* in the grid + badges, sparingly)
| Severity | Hex | Note |
|---|---|---|
| Critical | `#B42318` | Deep red, not neon. Reserved. |
| High | `#D97706` | Amber |
| Medium | `#B7791F` | Muted gold |
| Low | `#475569` | Slate (a "good to fix," not a fire) |
| Safe / none | `--green-600` | Reassurance |

All pairings meet **WCAG AA** contrast on white. Color is **never** the only signal — every severity also carries a text label and an icon (accessibility + colour-blind safe).

### Typography
- System stack: `-apple-system, "Segoe UI", Roboto, "Noto Sans", sans-serif` — zero font download, renders crisp Swahili diacritics via Noto fallback.
- Scale: 28/22/18/16/14 px. Generous line-height (1.6) for readability on small screens.
- Numbers (severity counts) in a tabular, slightly larger weight.

### Voice & tone
- Warm, direct, second person: "Your site," "Here's the one thing to fix first."
- Swahili copy is a first-class peer, not a machine-translated afterthought.
- Never: "vulnerability exploited," "attack surface," "0-day." Yes: "weak spot," "risk," "fix."

## 3. Component Blueprints

### 3.1 Minimalist Dashboard
```
┌─────────────────────────────────────────────┐
│  LindaAI            Wanjiku ▾   [Help]        │  ← navy nav, green logo mark
├─────────────────────────────────────────────┤
│  Your domains                                 │
│  ┌─────────────────────────────────────────┐ │
│  │ wanjikulaw.co.ke      ✅ Verified        │ │
│  │ Last scan: 2 days ago · High risk        │ │
│  │                       [ Run scan ]  ▸     │ │
│  └─────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────┐ │
│  │ + Add a domain                            │ │  ← single secondary action
│  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```
- One card per domain. Verified badge prominent. Empty state = a friendly single CTA, never a blank void.

### 3.2 Domain Verification Wizard (3 steps)
- Stepper at top (●──○──○). One step visible at a time.
- **Step A** shows the TXT record in a monospace pill with a big **Copy** button and a "What is this?" inline expander.
- **Step B** = registrar picker (logos: Truehost, Safaricom, KenyaWebExperts, GoDaddy, "Other") → tailored 3-line instructions.
- **Step C** = a single **Verify now** button; on failure, a *calm* yellow note (not red) + 60s countdown + "DNS can take a few minutes."
- Progress is forgiving: the user can leave and come back; state persists.

### 3.3 Scan Progress Indicator (low-overhead)
- **Not** an indeterminate spinner. A 3-item checklist that ticks live:
```
  ◐ Checking your certificate
  ○ Checking security headers
  ○ Checking DNS & email protection
```
- Each flips to ✓ as `raw_findings` arrives. Cold-start swaps the subtitle to "Waking up the scanner…".
- Honest time hint: "Usually under 15 seconds."

### 3.4 Prioritized Vulnerability Summary Grid
```
┌──────────┬──────────┬──────────┬──────────┐
│ CRITICAL │   HIGH   │  MEDIUM  │   LOW    │
│    0     │    2     │    3     │    1     │
│  (grey   │  amber   │   gold   │  slate   │
│  if 0)   │  badge   │  badge   │  badge   │
└──────────┴──────────┴──────────┴──────────┘
   ▼ Below the grid: "Fix this first" — single highlighted card
   ┌───────────────────────────────────────────┐
   │ ⚠ High · Email impersonation is possible   │
   │ Anyone can send email that looks like it's │
   │ from you. Common in fake-invoice fraud.    │
   │ ▸ How to fix   ▸ Technical detail (collapsed)│
   └───────────────────────────────────────────┘
```
- Zero counts render muted/grey — absence of fire is shown as calm, not emphasized red.
- Findings list below the grid, ordered Critical→Low, each an expandable card: **What it is → Why it matters to your business → How to fix.** Technical jargon hidden in a collapsed footer.

### 3.5 Report / PDF screen
- Language toggle **English | Kiswahili** at the top.
- Preview of the cover (logo, domain, date, overall risk badge) → **Download PDF** / **Share** (WhatsApp share is huge in Kenya — include it).
- Locked state (pre-payment) shows the summary blurred with a clear **Get full report — KES 50** button and M-Pesa mark.

## 4. Accessibility Checklist
- AA contrast on all text; severity never color-only (icon + label always).
- Touch targets ≥ 44px; full keyboard nav; visible focus rings.
- Copy buttons announce "Copied" to screen readers.
- Respect `prefers-reduced-motion` (no animated spinners then).
- All imagery has alt text; Swahili strings reviewed by a native speaker.

## 5. Things to deliberately NOT do
- No dark "hacker terminal" aesthetic — it intimidates the exact user we serve.
- No red-flashing alarms or scare-tactics.
- No long forms; no dashboards with 12 metrics.
- No downloadable PDF stored on a server we pay for (generate on demand).
