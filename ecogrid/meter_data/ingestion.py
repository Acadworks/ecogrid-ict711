"""Validation, de-duplication (MQTT QoS 1 = at-least-once) and freshness."""
from datetime import datetime, timedelta

from ecogrid.meter_data.acl import MeterReading

REPORTING_INTERVAL = timedelta(minutes=1)
FRESHNESS_THRESHOLD = 2 * REPORTING_INTERVAL  # ADR-012


class Ingestor:
    def __init__(self) -> None:
        self._seen: set[str] = set()
        self.accepted: list[MeterReading] = []

    def ingest(self, reading: MeterReading) -> bool:
        """Return True if accepted, False if duplicate or invalid."""
        if reading.event_id in self._seen:
            return False
        if reading.generation_kwh < 0 or reading.consumption_kwh < 0:
            return False
        self._seen.add(reading.event_id)
        self.accepted.append(reading)
        return True


def is_fresh(measured_at: datetime, now: datetime) -> bool:
    return now - measured_at <= FRESHNESS_THRESHOLD
