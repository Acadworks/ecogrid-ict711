"""Fitness functions for meter ingestion: units, de-duplication, freshness, throughput."""
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from ecogrid.meter_data.acl import from_vendor_a, from_vendor_b
from ecogrid.meter_data.ingestion import FRESHNESS_THRESHOLD, Ingestor, is_fresh

T0 = datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc)
METERS = 10_000
REPORTING_SECONDS = 60
AVG_RATE = METERS / REPORTING_SECONDS          # ~166.7 readings/s
SUSTAINED_TEST_RATE = 250                      # readings/s (1.5x average)


def _vendor_a(i: int, kw: float = 4.82) -> dict:
    return {"deviceNo": f"SM-{i % METERS}", "msgId": f"a-{i}",
            "readingTs": T0.isoformat(), "kwGenerated": kw, "kwConsumed": 1.2}


def test_ff04_acl_converts_power_to_energy():
    """Corrects the AI error: 4.82 kW for one minute is 0.0803 kWh, not 4.82 kWh."""
    r = from_vendor_a(_vendor_a(1), interval=timedelta(minutes=1))
    assert r.generation_kwh.quantize(Decimal("0.0001")) == Decimal("0.0803")
    b = from_vendor_b({"meter_id": "B-778", "event_id": "b-1", "timestamp": T0.isoformat(),
                       "generation_wh": 4800, "consumption_wh": 1300})
    assert b.generation_kwh == Decimal("4.8")


def test_ff05_duplicate_readings_are_counted_once():
    ing = Ingestor()
    r = from_vendor_a(_vendor_a(7), interval=timedelta(minutes=1))
    assert ing.ingest(r) is True
    assert ing.ingest(r) is False  # QoS 1 redelivery
    assert len(ing.accepted) == 1


@pytest.mark.parametrize("age_s, fresh", [(60, True), (120, True), (121, False)])
def test_ff06_freshness_threshold_is_two_reporting_intervals(age_s, fresh):
    assert FRESHNESS_THRESHOLD == timedelta(minutes=2)
    assert is_fresh(T0, T0 + timedelta(seconds=age_s)) is fresh


@pytest.mark.performance
def test_ff07_ingestion_throughput_exceeds_sustained_target():
    """Holistic in production; here an in-process regression benchmark of ACL + validation.
    The full MQTT -> worker -> TimescaleDB load test (250/s sustained, 500/s burst) runs nightly."""
    assert round(AVG_RATE) == 167
    n = SUSTAINED_TEST_RATE * 60  # one minute of sustained-test traffic
    ing = Ingestor()
    start = time.perf_counter()
    accepted = sum(ing.ingest(from_vendor_a(_vendor_a(i), timedelta(minutes=1))) for i in range(n))
    rate = n / (time.perf_counter() - start)
    assert rate >= SUSTAINED_TEST_RATE, f"{rate:.0f} readings/s"
    assert accepted / n >= 0.999
