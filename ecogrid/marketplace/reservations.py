"""EnergyOffer aggregate with Reservation inside it: the oversell check and the
reservation happen in ONE database transaction (one aggregate per transaction)."""
import sqlite3
from decimal import Decimal

SCHEMA = """
CREATE TABLE IF NOT EXISTS energy_offer (
    offer_id TEXT PRIMARY KEY,
    available_wh INTEGER NOT NULL CHECK (available_wh >= 0)
);
CREATE TABLE IF NOT EXISTS reservation (
    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id TEXT NOT NULL REFERENCES energy_offer(offer_id),
    buyer_id TEXT NOT NULL,
    reserved_wh INTEGER NOT NULL CHECK (reserved_wh > 0)
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    conn.executescript(SCHEMA)
    return conn


def create_offer(conn: sqlite3.Connection, offer_id: str, kwh: Decimal) -> None:
    conn.execute("INSERT INTO energy_offer VALUES (?, ?)", (offer_id, int(kwh * 1000)))


def reserve(conn: sqlite3.Connection, offer_id: str, buyer_id: str, kwh: Decimal) -> bool:
    wh = int(kwh * 1000)
    conn.execute("BEGIN IMMEDIATE")  # write lock: serialises competing buyers
    try:
        cur = conn.execute(
            "UPDATE energy_offer SET available_wh = available_wh - ? "
            "WHERE offer_id = ? AND available_wh >= ?",
            (wh, offer_id, wh),
        )
        if cur.rowcount != 1:
            conn.execute("ROLLBACK")
            return False
        conn.execute(
            "INSERT INTO reservation (offer_id, buyer_id, reserved_wh) VALUES (?, ?, ?)",
            (offer_id, buyer_id, wh),
        )
        conn.execute("COMMIT")
        return True
    except Exception:
        conn.execute("ROLLBACK")
        raise
