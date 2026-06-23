"""
LindaAI — Week 3 report generation.
  build_llm_input : compact pre-filter for GPT-4o-mini
  call_llm        : GPT-4o-mini executive summary + Pydantic validation
  generate_pdf    : on-demand bilingual PDF via fpdf2
"""
import collections
import io
import json
import os
from pathlib import Path

from fpdf import FPDF
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

# Load once at module import
_MAP_PATH = Path(__file__).parent / "mappings" / "findings.json"
FINDINGS: dict = json.loads(_MAP_PATH.read_text(encoding="utf-8"))

SEV_ORDER = ["critical", "high", "medium", "low"]

SEV_RGB = {
    "critical": (180, 35, 24),
    "high":     (194, 65, 12),
    "medium":   (161, 98,  7),
    "low":      ( 71, 85, 105),
}

NAVY  = (10, 37, 64)
SLATE = (71, 85, 105)
GREEN = (27, 127, 92)


# ─── LLM ─────────────────────────────────────────────────────────────────────

class LLMSummary(BaseModel):
    overall_risk: str
    summary: str
    top_priority_id: str


_FALLBACK = {
    "en": "Your website's passive security scan is complete. Please review the findings below and address each item, starting with the highest severity issues. None of these require rebuilding your site — most can be fixed with a single change.",
    "sw": "Ukaguzi wa usalama wa tovuti yako umekamilika. Tafadhali pitia matokeo hapa chini na shughulikia kila kipengele, ukianzia na masuala ya ukali zaidi. Hakuna haja ya kujenga upya tovuti yako.",
}


def build_llm_input(findings: list[dict]) -> str:
    """Compact pre-filter: one line per unique finding, sorted by severity."""
    if not findings:
        return "No issues detected."
    rolled = collections.Counter((f["severity"], f["id"]) for f in findings)
    order = {s: i for i, s in enumerate(SEV_ORDER)}
    lines = sorted(
        [f"{sev}: {fid} x{n}" for (sev, fid), n in rolled.items()],
        key=lambda l: order.get(l.split(":")[0], 9),
    )
    return "\n".join(lines)


async def call_llm(
    llm_input: str, lang: str, findings: list[dict]
) -> tuple[LLMSummary, int, int]:
    api_key = os.getenv("OPENAI_API_KEY")
    top_id = findings[0]["id"] if findings else ""
    top_risk = findings[0]["severity"] if findings else "low"

    if not api_key:
        return LLMSummary(
            overall_risk=top_risk,
            summary=_FALLBACK.get(lang, _FALLBACK["en"]),
            top_priority_id=top_id,
        ), 0, 0

    client = AsyncOpenAI(api_key=api_key)
    lang_label = "English" if lang == "en" else "Kiswahili"
    system = (
        "You write a 3-4 sentence security summary for a non-technical Kenyan "
        "small-business owner. Input is a compact list of detected issues "
        "(severity: finding-id xCount). Be calm, concrete, and prioritised. "
        'Output ONLY valid JSON: {"overall_risk":"critical|high|medium|low",'
        '"summary":"...","top_priority_id":"..."}. '
        f"Language: {lang_label}."
    )

    for attempt in range(2):
        try:
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": llm_input},
                ],
                temperature=0.3,
                max_tokens=400,
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)
            summary = LLMSummary(**data)
            return summary, resp.usage.prompt_tokens, resp.usage.completion_tokens
        except (ValidationError, json.JSONDecodeError, Exception):
            if attempt == 1:
                break

    return LLMSummary(
        overall_risk=top_risk,
        summary=_FALLBACK.get(lang, _FALLBACK["en"]),
        top_priority_id=top_id,
    ), 0, 0


# ─── PDF ──────────────────────────────────────────────────────────────────────

def _safe(text: str) -> str:
    """Encode to latin-1 safely (fpdf2 built-in fonts are latin-1)."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_pdf(
    hostname: str, findings: list[dict], summary: LLMSummary, lang: str
) -> bytes:
    tk = f"title_{lang}"
    ik = f"impact_{lang}"
    fk = f"fix_{lang}"
    lang_label = "English" if lang == "en" else "Kiswahili"

    pdf = FPDF()
    pdf.set_margins(20, 18, 20)
    pdf.add_page()

    # ── Header ──────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 10, "LindaAI Security Report", ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*SLATE)
    pdf.cell(0, 6, f"Domain: {hostname}   |   Language: {lang_label}   |   Overall risk: {summary.overall_risk.upper()}", ln=True)
    pdf.ln(3)

    pdf.set_draw_color(226, 232, 240)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(5)

    # ── Executive summary ────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 7, "Executive Summary", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*SLATE)
    pdf.multi_cell(0, 6, _safe(summary.summary))
    pdf.ln(4)

    # ── Severity count row ───────────────────────────────────────────────────
    counts = {s: 0 for s in SEV_ORDER}
    for f in findings:
        sev = f.get("severity", "low")
        if sev in counts:
            counts[sev] += 1

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 6, "Findings at a glance:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for sev in SEV_ORDER:
        pdf.set_text_color(*SEV_RGB[sev])
        pdf.cell(0, 5, f"  {sev.capitalize()}: {counts[sev]}", ln=True)
    pdf.ln(4)

    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(4)

    # ── Per-finding cards (Critical → Low) ───────────────────────────────────
    for sev in SEV_ORDER:
        sev_findings = [f for f in findings if f.get("severity") == sev]
        if not sev_findings:
            continue

        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*SEV_RGB[sev])
        pdf.cell(0, 7, sev.upper(), ln=True)
        pdf.ln(1)

        for finding in sev_findings:
            mapping = FINDINGS.get(finding["id"])
            title = _safe(mapping[tk]) if mapping else finding["id"]
            impact = _safe(mapping[ik]) if mapping else ""
            fix    = _safe(mapping[fk]) if mapping else ""

            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*NAVY)
            pdf.multi_cell(0, 6, title)

            if finding.get("detail"):
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(*SLATE)
                pdf.cell(0, 5, f"Detail: {finding['detail']}", ln=True)

            if impact:
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(*SLATE)
                pdf.cell(0, 5, "What this means for your business:", ln=True)
                pdf.set_font("Helvetica", "", 9)
                pdf.multi_cell(0, 5, impact)

            if fix:
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(*GREEN)
                pdf.cell(0, 5, "How to fix it:", ln=True)
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*SLATE)
                pdf.multi_cell(0, 5, fix)

            pdf.ln(4)

        pdf.ln(1)

    # ── Checklist page ───────────────────────────────────────────────────────
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 7, "Action Checklist", ln=True)
    pdf.set_font("Helvetica", "", 9)

    for sev in SEV_ORDER:
        for finding in findings:
            if finding.get("severity") != sev:
                continue
            mapping = FINDINGS.get(finding["id"])
            title = _safe(mapping[tk]) if mapping else finding["id"]
            pdf.set_text_color(*SEV_RGB[sev])
            pdf.cell(8, 5, "[ ]")
            pdf.set_text_color(*SLATE)
            pdf.multi_cell(0, 5, title)

    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*SLATE)
    pdf.multi_cell(
        0, 5,
        "This is a passive surface check, not a full penetration test. "
        "For businesses handling sensitive data (patient records, financial information), "
        "we recommend commissioning a professional security audit."
    )

    return bytes(pdf.output())
