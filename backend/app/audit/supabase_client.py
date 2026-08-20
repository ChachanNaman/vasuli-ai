"""Shared Supabase client. One client, service-role key, backend-only writes."""

from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def get_supabase():
    from supabase import Client, create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(url, key)
