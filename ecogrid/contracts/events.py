"""Published Language: versioned integration events shared by all bounded contexts.

Only this package may be imported across context boundaries (see .importlinter).
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IntegrationEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    event_id: UUID
    schema_version: int = Field(ge=1)
    occurred_at: datetime


class EnergyAvailabilityUpdated(IntegrationEvent):
    household_id: str
    available_kwh: Decimal = Field(ge=0)
    measured_at: datetime
    valid_until: datetime


class DeliveredEnergyMeasured(IntegrationEvent):
    trade_id: str
    delivered_kwh: Decimal = Field(ge=0)


class TradeConfirmed(IntegrationEvent):
    """Carries quantity and unit price only. Money is calculated by Settlement."""
    trade_id: str
    seller_id: str
    buyer_id: str
    energy_kwh: Decimal = Field(gt=0)
    unit_price: Decimal = Field(gt=0)
