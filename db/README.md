# Database setup (Supabase)

Day 1 goal: get the schema live with Row-Level Security on.

1. Create a project at https://supabase.com (Free tier).
2. Open **SQL Editor** → **New query**.
3. Paste the full contents of `01_schema.sql` and click **Run**.
4. Under **Table editor**, confirm these tables exist:
   `organizations, users, verified_domains, scans, vulnerability_summaries, payments`
5. Confirm **RLS is enabled** on each (a lock icon appears next to the table).

### Notes
- The schema references `auth.users`, which Supabase provides automatically — no extra setup.
- `users` is a thin profile table linked 1:1 to `auth.users(id)`.
- Backend writes use the **service role key** (bypasses RLS); browser reads use the **anon key** and go through RLS.
- The org auto-create trigger is added in **Day 2** (auth), not Day 1.
- Grab your keys from **Settings → API** for the frontend `.env.local` and the backend env.
