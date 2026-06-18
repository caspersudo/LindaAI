/**
 * Supabase browser client.
 *
 * Not used on Day 1 — it's here so Day 2 (auth) is a drop-in.
 * Guarded so a missing env var doesn't crash the build/landing page.
 */
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let _client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (_client) return _client;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !anon) {
    throw new Error(
      "Supabase env vars are not set. Add NEXT_PUBLIC_SUPABASE_URL and " +
        "NEXT_PUBLIC_SUPABASE_ANON_KEY to .env.local (see .env.local.example)."
    );
  }

  _client = createClient(url, anon);
  return _client;
}
