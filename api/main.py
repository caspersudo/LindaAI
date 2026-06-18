"""
LindaAI API — Week 1 / Day 1 skeleton.

Just enough to prove the service is live and reachable from the Vercel frontend.
Real scanning endpoints arrive in Week 2 (see docs/06_Implementation_Plan.md).
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

APP_VERSION = "0.1.0"

app = FastAPI(
    title="LindaAI API",
    version=APP_VERSION,
    description="Passive, ownership-gated security auditing for Kenyan SMEs.",
)

# Allow the Vercel frontend (and local dev) to call us.
# Set ALLOWED_ORIGINS on Render to your Vercel URL, comma-separated.
# e.g. ALLOWED_ORIGINS="https://lindaai.vercel.app,http://localhost:3000"
_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [o.strip() for o in _origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "service": "lindaai-api",
        "status": "running",
        "version": APP_VERSION,
        "docs": "/docs",
    }


@app.get("/healthz")
def healthz():
    """Liveness probe. Also pinged by the frontend status pill and an
    optional keep-warm cron (see TRD §2.3) to soften Render cold starts."""
    return {"status": "ok", "service": "lindaai-api", "version": APP_VERSION}
