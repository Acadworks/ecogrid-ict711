"""Fitness functions for driver #1 - financial integrity (dynamic, triggered on every PR)."""
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from ecogrid.contracts.events import DeliveredEnergyMeasured, TradeConfirmed
from ecogrid.marketplace.reservations import connect, create_offer, reserve
from ecogrid.settlement.service import SettlementService

NOW = datetime.now(timezone.utc)


def test_ff01_no_oversell_under_concurrent_buyers(tmp_path):
    """50 buyers race for 1 kWh each from a 5 kWh offer: exactly 5 may succeed."""
    db = str(tmp_path / "market.db")
    create_offer(connect(db), "offer-1", Decimal("5"))
    results: list[bool] = []
    lock = threading.Lock()
    start = threading.Barrier(50)

    def buyer(i: int) -> None:
        conn = connect(db)
        start.wait()
        ok = reserve(conn, "offer-1", f"buyer-{i}", Decimal("1"))
        with lock:
            results.append(ok)

    threads = [threading.Thread(target=buyer, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    conn = connect(db)
    reserved_wh = conn.execute("SELECT SUM(reserved_wh) FROM reservation").fetchone()[0]
    remaining_wh = conn.execute("SELECT available_wh FROM energy_offer").fetchone()[0]
    assert results.count(True) == 5
    assert reserved_wh == 5000 and remaining_wh == 0  # zero oversold energy


def _trade() -> TradeConfirmed:
    return TradeConfirmed(
        event_id=uuid.uuid4(), schema_version=1, occurred_at=NOW, trade_id="T1001",
        seller_id="H001", buyer_id="H025", energy_kwh=Decimal("3"), unit_price=Decimal("0.20"),
    )


def test_ff02_duplicate_events_create_one_settlement_and_balanced_ledger():
    svc = SettlementService(sqlite3.connect(":memory:"))
    trade = _trade()
    delivered = DeliveredEnergyMeasured(
        event_id=uuid.uuid4(), schema_version=1, occurred_at=NOW,
        trade_id="T1001", delivered_kwh=Decimal("3"),
    )
    for _ in range(3):  # MQTT/outbox delivery is at-least-once
        svc.on_trade_confirmed(trade)
        svc.on_delivered(delivered)

    c = svc.conn
    assert c.execute("SELECT COUNT(*) FROM settlement").fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM ledger_entry").fetchone()[0] == 2
    debits, credits = c.execute(
        "SELECT SUM(CAST(debit AS REAL)), SUM(CAST(credit AS REAL)) FROM ledger_entry"
    ).fetchone()
    assert debits == credits  # double-entry balances


def test_ff03_settlement_uses_delivered_energy_when_short():
    """Agreed 3 kWh @ 0.20, meter shows only 2.5 kWh delivered -> buyer pays 0.50, not 0.60."""
    svc = SettlementService(sqlite3.connect(":memory:"))
    svc.on_trade_confirmed(_trade())
    svc.on_delivered(DeliveredEnergyMeasured(
        event_id=uuid.uuid4(), schema_version=1, occurred_at=NOW,
        trade_id="T1001", delivered_kwh=Decimal("2.5"),
    ))
    amount = svc.conn.execute("SELECT amount FROM settlement").fetchone()[0]
    assert Decimal(amount) == Decimal("0.50")
