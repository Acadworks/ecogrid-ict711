"""Security and evolvability fitness functions."""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ecogrid.contracts.events import TradeConfirmed
from ecogrid.identity.authorization import Forbidden, Principal, require_household


def test_ff08_household_cannot_access_another_household():
    alice = Principal("user-a", frozenset({"household-a"}))
    require_household(alice, "household-a")
    with pytest.raises(Forbidden):
        require_household(alice, "household-b")


BASE = dict(event_id=uuid.uuid4(), schema_version=1, occurred_at=datetime.now(timezone.utc),
            trade_id="T1", seller_id="H1", buyer_id="H2", energy_kwh="3", unit_price="0.20")


def test_ff09_event_contract_rejects_money_and_unversioned_events():
    TradeConfirmed(**BASE)
    with pytest.raises(ValidationError):  # Marketplace must not send money amounts
        TradeConfirmed(**BASE, total_amount="0.60")
    with pytest.raises(ValidationError):  # every event must be versioned
        TradeConfirmed(**{k: v for k, v in BASE.items() if k != "schema_version"})
