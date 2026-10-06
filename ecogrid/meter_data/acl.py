"""Anti-Corruption Layer: translates vendor payloads into the canonical MeterReading.

Power (kW) is NOT energy (kWh): energy = average power x interval length.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class MeterReading:
    meter_id: str
    event_id: str
    measured_at: datetime
    generation_kwh: Decimal
    consumption_kwh: Decimal


def from_vendor_a(payload: dict, interval: timedelta) -> MeterReading:
    """Vendor A reports average power in kW over the reporting interval."""
    hours = Decimal(str(interval.total_seconds())) / Decimal(3600)
    return MeterReading(
        meter_id=payload["deviceNo"],
        event_id=payload["msgId"],
        measured_at=datetime.fromisoformat(payload["readingTs"]),
        generation_kwh=Decimal(str(payload["kwGenerated"])) * hours,
        consumption_kwh=Decimal(str(payload["kwConsumed"])) * hours,
    )


def from_vendor_b(payload: dict) -> MeterReading:
    """Vendor B reports interval energy in Wh."""
    return MeterReading(
        meter_id=payload["meter_id"],
        event_id=payload["event_id"],
        measured_at=datetime.fromisoformat(payload["timestamp"]),
        generation_kwh=Decimal(str(payload["generation_wh"])) / Decimal(1000),
        consumption_kwh=Decimal(str(payload["consumption_wh"])) / Decimal(1000),
    )
