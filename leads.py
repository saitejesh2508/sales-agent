"""Built-in leads and a durable local registry for newly added leads."""

import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

DATABASE = Path(__file__).with_name("leads.sqlite3")
LANGUAGES = {"English", "Spanish", "Mandarin", "French", "German", "Hindi", "Japanese"}
STAGES = ("New", "Contacted", "Responded", "Meeting", "Won")
INITIAL_STAGES = {"lead-alex-rivera": "Meeting", "lead-mei-chen": "Responded", "lead-hana-okonkwo": "Contacted"}

LEADS = [
    {"id": "lead-alex-rivera", "name": "Alex Rivera", "company": "Clínica Norte"},
    {"id": "lead-mei-chen", "name": "Mei Chen", "company": "Northwind Clinic"},
    {"id": "lead-luis-ortega", "name": "Luis Ortega", "company": "Taller Sol"},
    {"id": "lead-hana-okonkwo", "name": "Hana Okonkwo", "company": "BrightPath"},
]


class DuplicateLeadError(ValueError):
    pass


@contextmanager
def connect():
    connection = sqlite3.connect(DATABASE, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("""CREATE TABLE IF NOT EXISTS leads (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, company TEXT NOT NULL,
        language TEXT NOT NULL, note TEXT NOT NULL, identity TEXT UNIQUE NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('pending', 'ready'))
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS lead_stages (
        lead_id TEXT PRIMARY KEY, stage TEXT NOT NULL
        CHECK(stage IN ('New','Contacted','Responded','Meeting','Won'))
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS transcripts (
        id TEXT PRIMARY KEY, lead_id TEXT NOT NULL, kind TEXT NOT NULL,
        channel TEXT NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL
    )""")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def list_leads() -> list[dict]:
    with connect() as connection:
        added = connection.execute("SELECT id, name, company, language FROM leads WHERE state='ready' ORDER BY rowid").fetchall()
        stages = {row["lead_id"]: row["stage"] for row in connection.execute("SELECT * FROM lead_stages")}
    result = [dict(lead) for lead in LEADS] + [dict(lead) for lead in added]
    return [{**lead, "stage": stages.get(lead["id"], INITIAL_STAGES.get(lead["id"], "New"))} for lead in result]


def pipeline_counts() -> dict:
    counts = dict.fromkeys(STAGES, 0)
    for lead in list_leads():
        counts[lead["stage"]] += 1
    return counts


def transcripts_for(lead_id: str) -> list[dict]:
    with connect() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM transcripts WHERE lead_id=? ORDER BY rowid", (lead_id,))]


def record_activity(lead_id: str, kind: str, channel: str, text: str, stage: str, activity_id: str) -> dict:
    if stage not in STAGES:
        raise ValueError("Invalid pipeline stage.")
    created_at = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        connection.execute("INSERT INTO transcripts VALUES (?, ?, ?, ?, ?, ?)",
                           (activity_id, lead_id, kind, channel, text, created_at))
        connection.execute("INSERT INTO lead_stages VALUES (?, ?) ON CONFLICT(lead_id) DO UPDATE SET stage=excluded.stage", (lead_id, stage))
    return {"id": activity_id, "lead_id": lead_id, "kind": kind, "channel": channel, "text": text, "created_at": created_at}


def validate_lead(data: dict) -> dict:
    limits = {"name": 120, "company": 160, "language": 40, "note": 4000}
    if not isinstance(data, dict):
        raise ValueError("Provide a name, company, language, and note.")
    result = {}
    for key, limit in limits.items():
        value = data.get(key)
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            raise ValueError(f"Provide {key} (up to {limit} characters).")
        result[key] = value.strip()
    if result["language"] not in LANGUAGES:
        raise ValueError("Choose one of the available languages.")
    return result


def reserve_lead(data: dict) -> dict:
    data = validate_lead(data)
    identity = data["name"].casefold() + "\n" + data["company"].casefold()
    for lead in LEADS:
        if lead["name"].casefold() == data["name"].casefold() and lead["company"].casefold() == data["company"].casefold():
            raise DuplicateLeadError("This lead is already in the list. Select them to continue.")
    ascii_name = unicodedata.normalize("NFKD", data["name"]).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:60] or "new"
    bank_id = f"lead-{slug}-{uuid4().hex[:12]}"
    with connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO leads VALUES (?, ?, ?, ?, ?, ?, 'pending')",
            (bank_id, data["name"], data["company"], data["language"], data["note"], identity),
        )
        row = connection.execute("SELECT * FROM leads WHERE identity=?", (identity,)).fetchone()
        if row["state"] == "ready":
            raise DuplicateLeadError("This lead is already in the list. Select them to continue.")
        # A retry after an upstream failure reuses the reserved bank and document.
        connection.execute("UPDATE leads SET language=?, note=? WHERE id=?", (data["language"], data["note"], row["id"]))
    return {"id": row["id"], **data}


def publish_lead(bank_id: str) -> dict:
    with connect() as connection:
        connection.execute("UPDATE leads SET state='ready' WHERE id=?", (bank_id,))
        row = connection.execute("SELECT id, name, company, language FROM leads WHERE id=?", (bank_id,)).fetchone()
    return {**dict(row), "stage": "New"}


def get_lead(value: str) -> dict:
    for lead in list_leads():
        if value.casefold() in {lead["id"].casefold(), lead["name"].casefold()}:
            return lead
    if value.casefold() == "alex":  # Backward-compatible Python entry point.
        return LEADS[0]
    raise ValueError("Select a lead from the list.")
