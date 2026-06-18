# LindaAI 🛡️

Passive, ownership-gated security auditing for Kenyan SMEs. Plain-language reports in English or Kiswahili, built to run on free-tier infrastructure.

This repo currently contains the **Week 1 / Day 1 skeleton**: a deployed landing page, a live API health endpoint, and the database schema. The full blueprint lives in [`docs/`](./docs).

```
lindaai/
├── web/    Next.js 15 frontend  → Vercel (free)
├── api/    FastAPI backend       → Render (free)
├── db/     PostgreSQL schema     → Supabase (free)
└── docs/   The 6-part blueprint (PRD, TRD, journey, UI, schema, plan)
```

## Run it locally

**1. Backend**
```bash
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000          # http://localhost:8000/healthz
```

**2. Frontend**
```bash
cd web
cp .env.local.example .env.local               # default API URL is fine for local
npm install
npm run dev                                     # http://localhost:3000
```

The landing page shows a status pill. When the API is up, it reads **"Systems online."**

## Deploy (do it in this order)

1. **Supabase** — create a project, run `db/01_schema.sql` (see `db/README.md`). Copy the project URL + anon key + service role key.
2. **Render** — New → Blueprint → this repo. It reads `api/render.yaml` and deploys the API on the free tier. Copy the service URL (e.g. `https://lindaai-api.onrender.com`).
3. **Vercel** — import the repo, set **Root Directory = `web`**, and add env vars:
   - `NEXT_PUBLIC_API_URL` = your Render URL
   - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` = from Supabase
4. Back in **Render**, set `ALLOWED_ORIGINS` to your Vercel URL so the browser can call the API.

When the Vercel page shows **"Systems online,"** Day 1 is done — all three services are live and talking.

## The one rule
LindaAI only ever scans domains a user has **proven they own** (DNS TXT verification), and every check is **passive**. See `docs/01_PRD.md` §4.

## Roadmap
Day 2: Supabase Auth + org auto-create · Day 3: dashboard shell · Day 4–5: add-domain flow + RLS isolation tests. Full plan in `docs/06_Implementation_Plan.md`.
