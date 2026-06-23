"""
LindaAI API — Week 2
Routes:
  GET  /healthz
  POST /domains/{domain_id}/verify  → DNS TXT check, flip to verified
  POST /scans                       → enqueue scan (202), run in background
  GET  /scans/{scan_id}             → poll status + findings
"""
import asyncio
import base64
import io
import os
import ssl
import socket
from datetime import datetime, timezone

import dns.asyncresolver
import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from report import build_llm_input, call_llm, generate_pdf

APP_VERSION = "0.2.0"
UA = "LindaAI-Scanner/1.0"

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [o.strip() for o in _origins.split(",") if o.strip()]

# ── Daraja / M-Pesa ───────────────────────────────────────────────────────────
DARAJA_KEY      = os.getenv("DARAJA_CONSUMER_KEY", "")
DARAJA_SECRET   = os.getenv("DARAJA_CONSUMER_SECRET", "")
DARAJA_CODE     = os.getenv("DARAJA_SHORTCODE", "174379")   # sandbox default
DARAJA_PASSKEY  = os.getenv("DARAJA_PASSKEY", "")
DARAJA_BASE     = os.getenv("DARAJA_BASE", "https://sandbox.safaricom.co.ke")
API_BASE_URL    = os.getenv("API_BASE_URL", "https://lindaai-api.onrender.com")
REPORT_PRICE_KES = int(os.getenv("REPORT_PRICE_KES", "500"))

app = FastAPI(
    title="LindaAI API",
    version=APP_VERSION,
    description="Passive, ownership-gated security auditing for Kenyan SMEs.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Supabase REST helpers ────────────────────────────────────────────────────

REST = f"{SUPABASE_URL}/rest/v1"


def _svc_headers(extra: dict | None = None) -> dict:
    h = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "apikey": SUPABASE_SERVICE_KEY,
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


async def db_get(table: str, params: dict) -> list[dict]:
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{REST}/{table}", params=params, headers=_svc_headers())
    r.raise_for_status()
    return r.json()


async def db_insert(table: str, data: dict) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{REST}/{table}", json=data,
            headers=_svc_headers({"Prefer": "return=representation"}),
        )
    r.raise_for_status()
    return r.json()[0]


async def db_patch(table: str, match: dict, data: dict) -> None:
    params = {k: f"eq.{v}" for k, v in match.items()}
    async with httpx.AsyncClient() as c:
        r = await c.patch(f"{REST}/{table}", params=params, json=data,
                          headers=_svc_headers())
    r.raise_for_status()


# ─── Auth ─────────────────────────────────────────────────────────────────────

async def current_user(authorization: str = Header(...)) -> dict:
    """Verify the Supabase JWT by calling auth/v1/user and return the user."""
    token = authorization.removeprefix("Bearer ").strip()
    async with httpx.AsyncClient() as c:
        r = await c.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": SUPABASE_ANON_KEY},
        )
    if r.status_code != 200:
        raise HTTPException(401, "Invalid or expired session")
    return r.json()


async def get_org_id(user: dict) -> str:
    rows = await db_get("users", {"id": f"eq.{user['id']}", "select": "org_id"})
    if not rows:
        raise HTTPException(403, "User profile not found")
    return rows[0]["org_id"]


# ─── Daraja helpers ───────────────────────────────────────────────────────────

def _norm_phone(raw: str) -> str:
    """Normalise a Kenya number to 2547XXXXXXXX (12 digits, no +)."""
    digits = "".join(c for c in raw if c.isdigit())
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    if not (digits.startswith("254") and len(digits) == 12):
        raise ValueError("Enter a valid Kenyan number e.g. 0712 345 678")
    return digits


async def _daraja_token() -> str:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{DARAJA_BASE}/oauth/v1/generate?grant_type=client_credentials",
            auth=(DARAJA_KEY, DARAJA_SECRET),
        )
    r.raise_for_status()
    return r.json()["access_token"]


async def _stk_push(phone: str, amount: int, scan_id: str) -> dict:
    token = await _daraja_token()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    pw = base64.b64encode(f"{DARAJA_CODE}{DARAJA_PASSKEY}{ts}".encode()).decode()
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            f"{DARAJA_BASE}/mpesa/stkpush/v1/processrequest",
            json={
                "BusinessShortCode": DARAJA_CODE,
                "Password": pw,
                "Timestamp": ts,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": amount,
                "PartyA": phone,
                "PartyB": DARAJA_CODE,
                "PhoneNumber": phone,
                "CallBackURL": f"{API_BASE_URL}/payments/callback",
                "AccountReference": f"LindaAI-{scan_id[:8]}",
                "TransactionDesc": "LindaAI Security Report",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    r.raise_for_status()
    return r.json()


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"service": "lindaai-api", "status": "running", "version": APP_VERSION}


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "lindaai-api", "version": APP_VERSION}


# ── Domain verification ────────────────────────────────────────────────────────

@app.post("/domains/{domain_id}/verify")
async def verify_domain(domain_id: str, user: dict = Depends(current_user)):
    org_id = await get_org_id(user)
    rows = await db_get(
        "verified_domains",
        {"id": f"eq.{domain_id}", "org_id": f"eq.{org_id}", "select": "*"},
    )
    if not rows:
        raise HTTPException(404, "Domain not found")

    domain = rows[0]
    if domain["status"] == "verified":
        return {"verified": True, "message": "Already verified"}

    token = domain["verify_token"]
    hostname = domain["hostname"]

    try:
        resolver = dns.asyncresolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5
        answers = await resolver.resolve(hostname, "TXT")
        txt_values = [b.decode() for rdata in answers for b in rdata.strings]
    except Exception:
        txt_values = []

    if not any(token in v for v in txt_values):
        return {
            "verified": False,
            "message": (
                "TXT record not found yet — DNS can take up to 48 hours to spread. "
                "Wait a few minutes and try again."
            ),
        }

    await db_patch(
        "verified_domains",
        {"id": domain_id},
        {"status": "verified", "verified_at": datetime.now(timezone.utc).isoformat()},
    )
    return {"verified": True, "message": "Domain verified successfully"}


# ── Scans ──────────────────────────────────────────────────────────────────────

class ScanCreate(BaseModel):
    domain_id: str


@app.post("/scans", status_code=202)
async def create_scan(
    body: ScanCreate,
    bg: BackgroundTasks,
    user: dict = Depends(current_user),
):
    org_id = await get_org_id(user)
    rows = await db_get(
        "verified_domains",
        {"id": f"eq.{body.domain_id}", "org_id": f"eq.{org_id}",
         "select": "id,hostname,status,org_id"},
    )
    if not rows:
        raise HTTPException(404, "Domain not found")

    domain = rows[0]
    if domain["status"] != "verified":
        # Hard gate: unverified domains are refused — non-negotiable per PRD §4
        raise HTTPException(403, "Domain must be verified before scanning")

    scan = await db_insert("scans", {
        "domain_id": domain["id"],
        "org_id": org_id,
        "status": "queued",
    })
    bg.add_task(run_scan, scan["id"], domain["hostname"])
    return {"scan_id": scan["id"], "status": "queued"}


@app.get("/scans/{scan_id}")
async def get_scan(scan_id: str, user: dict = Depends(current_user)):
    org_id = await get_org_id(user)
    rows = await db_get(
        "scans",
        {"id": f"eq.{scan_id}", "org_id": f"eq.{org_id}", "select": "*"},
    )
    if not rows:
        raise HTTPException(404, "Scan not found")
    return rows[0]


# ── Payments ───────────────────────────────────────────────────────────────────

class PaymentCreate(BaseModel):
    scan_id: str
    phone: str


@app.post("/payments", status_code=202)
async def initiate_payment(body: PaymentCreate, user: dict = Depends(current_user)):
    org_id = await get_org_id(user)

    rows = await db_get(
        "scans",
        {"id": f"eq.{body.scan_id}", "org_id": f"eq.{org_id}", "select": "id,status"},
    )
    if not rows:
        raise HTTPException(404, "Scan not found")
    if rows[0]["status"] != "complete":
        raise HTTPException(409, "Scan is not complete yet")

    try:
        phone = _norm_phone(body.phone)
    except ValueError as e:
        raise HTTPException(400, str(e))

    payment = await db_insert("payments", {
        "scan_id": body.scan_id,
        "org_id": org_id,
        "amount_kes": REPORT_PRICE_KES,
        "status": "initiated",
        "phone_e164": phone,
    })

    if not DARAJA_KEY:
        # Daraja not configured — return sandbox stub so UI can still be tested
        return {"payment_id": payment["id"], "status": "initiated", "sandbox": True}

    try:
        resp = await _stk_push(phone, REPORT_PRICE_KES, body.scan_id)
        await db_patch("payments", {"id": payment["id"]}, {
            "merchant_request_id": resp.get("MerchantRequestID"),
            "checkout_request_id": resp.get("CheckoutRequestID"),
        })
    except Exception as e:
        await db_patch("payments", {"id": payment["id"]}, {"status": "failed"})
        raise HTTPException(502, f"M-Pesa push failed: {e}")

    return {
        "payment_id": payment["id"],
        "status": "initiated",
        "message": "Check your phone for the M-Pesa prompt",
    }


@app.post("/payments/callback")
async def payment_callback(request: Request):
    """Daraja STK-push callback — called by Safaricom, no user auth."""
    try:
        data = await request.json()
    except Exception:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    stk = data.get("Body", {}).get("stkCallback", {})
    checkout_id = stk.get("CheckoutRequestID")
    result_code = stk.get("ResultCode")

    if not checkout_id:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    rows = await db_get(
        "payments",
        {"checkout_request_id": f"eq.{checkout_id}", "select": "id"},
    )
    if not rows:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    payment_id = rows[0]["id"]

    if result_code == 0:
        items = stk.get("CallbackMetadata", {}).get("Item", [])
        meta = {item["Name"]: item.get("Value") for item in items}
        await db_patch("payments", {"id": payment_id}, {
            "status": "paid",
            "mpesa_receipt": str(meta.get("MpesaReceiptNumber", "")),
            "paid_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        await db_patch("payments", {"id": payment_id}, {"status": "failed"})

    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@app.get("/payments/{payment_id}")
async def get_payment(payment_id: str, user: dict = Depends(current_user)):
    org_id = await get_org_id(user)
    rows = await db_get(
        "payments",
        {"id": f"eq.{payment_id}", "org_id": f"eq.{org_id}",
         "select": "id,status,amount_kes,mpesa_receipt"},
    )
    if not rows:
        raise HTTPException(404, "Payment not found")
    return rows[0]


@app.get("/scans/{scan_id}/report")
async def download_report(
    scan_id: str,
    lang: str = "en",
    user: dict = Depends(current_user),
):
    if lang not in ("en", "sw"):
        raise HTTPException(400, "lang must be 'en' or 'sw'")

    org_id = await get_org_id(user)
    rows = await db_get(
        "scans",
        {"id": f"eq.{scan_id}", "org_id": f"eq.{org_id}", "select": "*"},
    )
    if not rows:
        raise HTTPException(404, "Scan not found")
    scan = rows[0]

    if scan["status"] != "complete":
        raise HTTPException(409, "Scan is not complete yet")

    # ── Paywall: first completed scan per domain is free; rest need payment ──
    if DARAJA_KEY:
        domain_scans = await db_get(
            "scans",
            {"domain_id": f"eq.{scan['domain_id']}", "status": "eq.complete",
             "select": "id", "order": "created_at.asc"},
        )
        is_first = bool(domain_scans) and domain_scans[0]["id"] == scan_id
        if not is_first:
            paid = await db_get(
                "payments",
                {"scan_id": f"eq.{scan_id}", "status": "eq.paid", "select": "id"},
            )
            if not paid:
                raise HTTPException(402, "Report requires payment")

    findings = scan.get("raw_findings") or []

    domain_rows = await db_get(
        "verified_domains",
        {"id": f"eq.{scan['domain_id']}", "select": "hostname"},
    )
    hostname = domain_rows[0]["hostname"] if domain_rows else "unknown"

    llm_input = build_llm_input(findings)
    summary, prompt_tokens, completion_tokens = await call_llm(llm_input, lang, findings)

    # Cost tracking: GPT-4o-mini @ $0.15/M in, $0.60/M out → KES at ~130/$
    cost_kes = ((prompt_tokens * 0.00000015) + (completion_tokens * 0.0000006)) * 130

    try:
        await db_patch("scans", {"id": scan_id}, {
            "llm_prompt_tokens": prompt_tokens,
            "llm_completion_tokens": completion_tokens,
            "cost_kes": round(cost_kes, 4),
            "overall_risk": summary.overall_risk,
        })
    except Exception:
        pass  # cost telemetry is non-critical; don't block PDF delivery

    pdf_bytes = generate_pdf(hostname, findings, summary, lang)
    filename = f"lindaai-{hostname}-{lang}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Scanner ──────────────────────────────────────────────────────────────────

def mk(id: str, severity: str, detail: str | None = None) -> dict:
    return {"id": id, "severity": severity, "detail": detail}


SECURITY_HEADERS = {
    "strict-transport-security": "medium",
    "content-security-policy": "medium",
    "x-frame-options": "medium",
    "x-content-type-options": "low",
    "referrer-policy": "low",
    "permissions-policy": "low",
}


async def check_http_headers(hostname: str) -> dict:
    findings = []
    async with httpx.AsyncClient(timeout=5, follow_redirects=False) as c:
        try:
            r = await c.get(f"https://{hostname}", headers={"User-Agent": UA})
        except httpx.RequestError as e:
            return {"category": "http", "error": str(e)[:120], "findings": []}

    present = {k.lower() for k in r.headers}
    for header, sev in SECURITY_HEADERS.items():
        if header not in present:
            findings.append(mk(f"missing-{header}", sev))

    server = r.headers.get("server", "")
    if any(ch.isdigit() for ch in server):
        findings.append(mk("server-version-disclosed", "low", detail=server))

    for cookie in r.headers.get_list("set-cookie"):
        low = cookie.lower()
        if "secure" not in low or "httponly" not in low:
            findings.append(mk("weak-cookie-flags", "high",
                               detail=cookie.split("=")[0]))

    async with httpx.AsyncClient(timeout=5, follow_redirects=False) as c:
        try:
            h = await c.get(f"http://{hostname}", headers={"User-Agent": UA})
            if h.status_code not in (301, 302, 307, 308):
                findings.append(mk("no-https-redirect", "medium"))
        except httpx.RequestError:
            pass

    return {"category": "http", "findings": findings}


async def check_tls(hostname: str) -> dict:
    ctx = ssl.create_default_context()
    loop = asyncio.get_running_loop()

    def _handshake():
        with socket.create_connection((hostname, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ss:
                return ss.getpeercert(), ss.version()

    try:
        cert, tls_version = await loop.run_in_executor(None, _handshake)
    except ssl.SSLCertVerificationError as e:
        msg = str(e).lower()
        if "self signed" in msg or "self-signed" in msg:
            return {"category": "tls", "findings": [mk("self-signed-cert", "high")]}
        return {"category": "tls",
                "findings": [mk("cert-validation-failed", "high", detail=str(e)[:120])]}
    except (socket.timeout, OSError, ssl.SSLError) as e:
        return {"category": "tls",
                "findings": [mk("no-tls", "critical", detail=str(e)[:120])]}

    not_after = datetime.strptime(
        cert["notAfter"], "%b %d %H:%M:%S %Y %Z"
    ).replace(tzinfo=timezone.utc)
    days_left = (not_after - datetime.now(timezone.utc)).days

    findings = []
    if days_left < 0:
        findings.append(mk("cert-expired", "critical", detail=f"{days_left}d"))
    elif days_left < 14:
        findings.append(mk("cert-expiring-soon", "high", detail=f"{days_left}d"))
    elif days_left < 30:
        findings.append(mk("cert-expiring", "medium", detail=f"{days_left}d"))

    if tls_version in ("TLSv1", "TLSv1.1"):
        findings.append(mk("outdated-tls-version", "medium", detail=tls_version))

    return {"category": "tls", "findings": findings}


async def check_dns(hostname: str) -> dict:
    resolver = dns.asyncresolver.Resolver()
    resolver.timeout = 5
    resolver.lifetime = 5

    async def q(name: str, rtype: str) -> list[str]:
        try:
            ans = await resolver.resolve(name, rtype)
            return [str(x) for x in ans]
        except Exception:
            return []

    a, mx, txt, dmarc, caa = await asyncio.gather(
        q(hostname, "A"),
        q(hostname, "MX"),
        q(hostname, "TXT"),
        q(f"_dmarc.{hostname}", "TXT"),
        q(hostname, "CAA"),
    )
    spf = [t for t in txt if "v=spf1" in t.lower()]

    findings = []
    if not a:
        findings.append(mk("no-a-record", "medium"))
    if mx and not spf:
        findings.append(mk("missing-spf", "high"))
    if mx and not dmarc:
        findings.append(mk("missing-dmarc", "high"))
    if not caa:
        findings.append(mk("no-caa", "low"))

    return {"category": "dns", "findings": findings}


def normalize_findings(results: list) -> list[dict]:
    out = []
    for r in results:
        if isinstance(r, Exception):
            continue
        if isinstance(r, dict):
            out.extend(r.get("findings", []))
    return out


async def run_scan(scan_id: str, hostname: str) -> None:
    await db_patch("scans", {"id": scan_id}, {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        results = await asyncio.gather(
            check_http_headers(hostname),
            check_tls(hostname),
            check_dns(hostname),
            return_exceptions=True,
        )
        findings = normalize_findings(list(results))
        await db_patch("scans", {"id": scan_id}, {
            "status": "complete",
            "raw_findings": findings,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        await db_patch("scans", {"id": scan_id}, {
            "status": "failed",
            "fail_reason": str(e)[:300],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
