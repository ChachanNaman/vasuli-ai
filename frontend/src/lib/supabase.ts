import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  throw new Error(
    "NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY must be set"
  );
}

// Single-merchant demo, no auth (PRD §3.2) — anon key only, reads gated by
// the RLS "public read" policies in supabase/migrations/0001_init.sql.
export const supabase = createClient(url, anonKey);
