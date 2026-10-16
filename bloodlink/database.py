"""SQLite registries: donors, requests, blood drives, notifications log."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .compatibility import parse_group

SCHEMA = """
CREATE TABLE IF NOT EXISTS donors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    blood_group TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    last_donation TEXT,          -- ISO date YYYY-MM-DD, NULL = never donated
    available INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blood_group TEXT NOT NULL,   -- group needed
    units INTEGER NOT NULL,
    urgency INTEGER NOT NULL,    -- 1 (routine) .. 5 (critical)
    hospital TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS drives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,          -- ISO date YYYY-MM-DD
    location TEXT NOT NULL,
    target_groups TEXT NOT NULL, -- comma-separated groups
    x REAL NOT NULL,
    y REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    donor_id INTEGER,
    request_id INTEGER,
    channel TEXT NOT NULL,
    message TEXT NOT NULL
);
"""

DEFAULT_DB = Path(__file__).resolve().parent.parent / "bloodlink.db"


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    db = Path(db_path) if db_path else DEFAULT_DB
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def add_donor(conn, name, blood_group, x, y, last_donation=None, available=True) -> int:
    abo, rh = parse_group(blood_group)  # validate; raises ValueError on bad input
    cur = conn.execute(
        "INSERT INTO donors (name, blood_group, x, y, last_donation, available)"
        " VALUES (?,?,?,?,?,?)",
        (name, abo + rh, x, y, last_donation, int(available)),
    )
    conn.commit()
    return cur.lastrowid


def add_request(conn, blood_group, units, urgency, hospital, x, y) -> int:
    abo, rh = parse_group(blood_group)  # validate; raises ValueError on bad input
    if not 1 <= urgency <= 5:
        raise ValueError("urgency must be 1..5")
    if units < 1:
        raise ValueError("units must be a positive integer (>= 1)")
    cur = conn.execute(
        "INSERT INTO requests (blood_group, units, urgency, hospital, x, y)"
        " VALUES (?,?,?,?,?,?)",
        (abo + rh, units, urgency, hospital, x, y),
    )
    conn.commit()
    return cur.lastrowid


def schedule_drive(conn, date, location, target_groups, x=0.0, y=0.0) -> int:
    targets = ",".join(g.strip().upper() for g in target_groups)
    cur = conn.execute(
        "INSERT INTO drives (date, location, target_groups, x, y)"
        " VALUES (?,?,?,?,?)",
        (date, location, targets, x, y),
    )
    conn.commit()
    return cur.lastrowid


def list_donors(conn) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM donors ORDER BY id"))


def list_requests(conn, only_open: bool = True) -> list[sqlite3.Row]:
    q = "SELECT * FROM requests" + (" WHERE status='open'" if only_open else "")
    return list(conn.execute(q + " ORDER BY urgency DESC, id"))


def list_drives(conn, upcoming_only: bool = True) -> list[sqlite3.Row]:
    q = "SELECT * FROM drives"
    if upcoming_only:
        q += " WHERE date >= date('now')"
    return list(conn.execute(q + " ORDER BY date, id"))


def log_notification(conn, donor_id, request_id, channel, message) -> int:
    cur = conn.execute(
        "INSERT INTO notifications (donor_id, request_id, channel, message)"
        " VALUES (?,?,?,?)",
        (donor_id, request_id, channel, message),
    )
    conn.commit()
    return cur.lastrowid
