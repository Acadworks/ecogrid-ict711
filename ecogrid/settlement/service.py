"""Settlement: idempotent consumer of TradeConfirmed + double-entry ledger.
Settles on min(agreed, delivered) energy."""
import sqlite3
from decimal import Decimal

from ecogrid.contracts.events import DeliveredEnergyMeasured, TradeConfirmed

SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_event (event_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS settlement (
    trade_id TEXT PRIMARY KEY, buyer_id TEXT, seller_id TEXT,
    agreed_kwh TEXT, unit_price TEXT, delivered_kwh TEXT, amount TEXT
);
CREATE TABLE IF NOT EXISTS ledger_entry (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT, account TEXT, debit TEXT, credit TEXT
);
"""


class SettlementService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        conn.executescript(SCHEMA)

    def _first_time(self, event_id: str) -> bool:
        try:
            self.conn.execute("INSERT INTO processed_event VALUES (?)", (event_id,))
            return True
        except sqlite3.IntegrityError:
            return False

    def on_trade_confirmed(self, e: TradeConfirmed) -> None:
        with self.conn:
            if not self._first_time(str(e.event_id)):
                return
            self.conn.execute(
                "INSERT INTO settlement VALUES (?, ?, ?, ?, ?, NULL, NULL)",
                (e.trade_id, e.buyer_id, e.seller_id, str(e.energy_kwh), str(e.unit_price)),
            )

    def on_delivered(self, e: DeliveredEnergyMeasured) -> None:
        with self.conn:
            if not self._first_time(str(e.event_id)):
                return
            agreed, price = self.conn.execute(
                "SELECT agreed_kwh, unit_price FROM settlement WHERE trade_id = ?",
                (e.trade_id,),
            ).fetchone()
            settled_kwh = min(Decimal(agreed), e.delivered_kwh)
            amount = (settled_kwh * Decimal(price)).quantize(Decimal("0.01"))
            self.conn.execute(
                "UPDATE settlement SET delivered_kwh = ?, amount = ? WHERE trade_id = ?",
                (str(e.delivered_kwh), str(amount), e.trade_id),
            )
            buyer, seller = self.conn.execute(
                "SELECT buyer_id, seller_id FROM settlement WHERE trade_id = ?", (e.trade_id,)
            ).fetchone()
            self.conn.execute(
                "INSERT INTO ledger_entry (trade_id, account, debit, credit) VALUES (?, ?, ?, '0')",
                (e.trade_id, f"buyer:{buyer}", str(amount)),
            )
            self.conn.execute(
                "INSERT INTO ledger_entry (trade_id, account, debit, credit) VALUES (?, ?, '0', ?)",
                (e.trade_id, f"seller:{seller}", str(amount)),
            )
