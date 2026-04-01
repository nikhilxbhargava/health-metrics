"""SQLite storage layer for Oura Ring data."""

import json
import sqlite3
import os
from datetime import date

DB_PATH = os.path.join(os.path.dirname(__file__), "oura_data.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS oura_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            day TEXT NOT NULL,
            data JSON NOT NULL,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category, day)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def store_data(category: str, records: list[dict]) -> int:
    """Store fetched records, upserting by (category, day)."""
    conn = get_connection()
    count = 0
    for record in records:
        # Extract the day key — different endpoints use different field names
        day = (
            record.get("day")
            or record.get("bedtime_start", "")[:10]
            or record.get("start_datetime", "")[:10]
            or record.get("timestamp", "")[:10]
            or date.today().isoformat()
        )
        conn.execute(
            """
            INSERT INTO oura_data (category, day, data)
            VALUES (?, ?, ?)
            ON CONFLICT(category, day) DO UPDATE SET
                data = excluded.data,
                fetched_at = CURRENT_TIMESTAMP
            """,
            (category, day, json.dumps(record)),
        )
        count += 1
    conn.commit()
    conn.close()
    return count


def log_sync(start_date: str, end_date: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO sync_log (start_date, end_date) VALUES (?, ?)",
        (start_date, end_date),
    )
    conn.commit()
    conn.close()


def load_data(category: str, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    """Load records for a category, optionally filtered by date range."""
    conn = get_connection()
    query = "SELECT data FROM oura_data WHERE category = ?"
    params: list = [category]

    if start_date:
        query += " AND day >= ?"
        params.append(start_date)
    if end_date:
        query += " AND day <= ?"
        params.append(end_date)

    query += " ORDER BY day"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [json.loads(row["data"]) for row in rows]


def get_last_sync() -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM sync_log ORDER BY synced_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_categories() -> list[str]:
    conn = get_connection()
    rows = conn.execute("SELECT DISTINCT category FROM oura_data").fetchall()
    conn.close()
    return [row["category"] for row in rows]
