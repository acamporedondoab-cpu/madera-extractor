#!/usr/bin/env python3
"""
Supabase REST client for extraction persistence.
Uses the Supabase PostgREST API directly — no SDK required.

Required env vars:
  SUPABASE_URL          e.g. https://xxxx.supabase.co
  SUPABASE_ANON_KEY     eyJ... (database read/write via PostgREST)

Optional env vars:
  SUPABASE_SERVICE_KEY  eyJ... (service role key — needed for Storage uploads
                                from Railway backend; bypasses bucket RLS)
"""

import os
from datetime import datetime, timezone
from typing import Optional

import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")
# Service role key used only for Storage uploads (never sent to the client).
# Falls back to anon key if not set; upload will then fail if bucket RLS blocks anon writes.
_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "") or SUPABASE_KEY
_TABLE = "extractions"
_BUCKET = "pdf-attachments"


def is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _url() -> str:
    return f"{SUPABASE_URL}/rest/v1/{_TABLE}"


def _headers(prefer: str = "") -> dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save(extraction_id: str, data: dict) -> bool:
    """Upsert a full extraction (insert or replace on conflict)."""
    payload = {
        "id": extraction_id,
        "data": data,
        "approved": False,
        "status": "pending",
        "updated_at": _now(),
    }
    r = requests.post(
        _url(),
        json=payload,
        headers=_headers("resolution=merge-duplicates,return=representation"),
        timeout=15,
    )
    r.raise_for_status()
    return True


def list_all() -> list:
    """Return all rows ordered newest first."""
    r = requests.get(
        _url(),
        params={"order": "updated_at.desc"},
        headers=_headers(),
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def get_one(extraction_id: str) -> Optional[dict]:
    """Return one row by id, or None if not found."""
    r = requests.get(
        _url(),
        params={"id": f"eq.{extraction_id}"},
        headers=_headers(),
        timeout=10,
    )
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None


def upload_pdf(project_id: str, filename: str, pdf_bytes: bytes) -> str:
    """Upload PDF to Supabase Storage bucket using service role key. Returns public URL.

    Uses SUPABASE_SERVICE_KEY so Railway backend can write to the bucket
    regardless of bucket RLS policies. Falls back to anon key if service key
    is not configured (upload will fail with 403 if bucket denies anon writes).
    """
    path = f"{project_id}/{filename}"
    url = f"{SUPABASE_URL}/storage/v1/object/{_BUCKET}/{path}"
    r = requests.post(
        url,
        data=pdf_bytes,
        headers={
            "apikey": _SERVICE_KEY,
            "Authorization": f"Bearer {_SERVICE_KEY}",
            "Content-Type": "application/pdf",
            "x-upsert": "true",
        },
        timeout=30,
    )
    if not r.ok:
        raise RuntimeError(
            f"Storage upload failed [{r.status_code}]: {r.text[:200]}"
        )
    return f"{SUPABASE_URL}/storage/v1/object/public/{_BUCKET}/{path}"


def update(extraction_id: str, fields: dict) -> bool:
    """Patch specific columns on a row."""
    fields["updated_at"] = _now()
    r = requests.patch(
        _url(),
        params={"id": f"eq.{extraction_id}"},
        json=fields,
        headers=_headers("return=representation"),
        timeout=10,
    )
    r.raise_for_status()
    return True
