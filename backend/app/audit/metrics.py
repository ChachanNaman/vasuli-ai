"""Reads the computed-on-read metrics views (PRD §6.3, supabase/migrations/0001_init.sql).
No aggregation logic lives here — it's all in the SQL views, this just fetches.
"""

from __future__ import annotations

from app.audit.supabase_client import get_supabase


def get_metrics_overview() -> dict:
    supabase = get_supabase()
    response = supabase.table("metrics_overview").select("*").execute()
    return response.data[0] if response.data else {}


def get_metrics_by_root_cause() -> list[dict]:
    supabase = get_supabase()
    response = supabase.table("metrics_by_root_cause").select("*").execute()
    return response.data or []


def get_exceptions() -> list[dict]:
    supabase = get_supabase()
    response = supabase.table("metrics_exceptions").select("*").execute()
    return response.data or []
