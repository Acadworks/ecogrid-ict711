# EcoGrid Energy – Architecture Decision Records

Each record follows the format: context, decision, consequences. ADR-005 was revised and ADR-011/012 were added by the team after validating the AI-assisted design (see the AI-Assisted Design Portfolio).

| ADR | Decision | Status |
|---|---|---|
| ADR-001 | DDD-based modular monolith for Marketplace, Settlement & Payments, Identity and Notifications | Accepted |
| ADR-002 | MQTT for smart-meter communication (Eclipse Mosquitto, QoS 1) | Accepted |
| ADR-003 | PostgreSQL as the transactional system of record | Accepted |
| ADR-004 | TimescaleDB for high-frequency meter readings (~14.4 M rows/day) | Accepted |
| ADR-005 | Cross-context events published through a transactional outbox, versioned and consumed idempotently | Accepted (revised by team) |
| ADR-006 | Kafka deferred until >1,000 msg/s, a replay requirement, or 3+ independent consumers | Accepted |
| ADR-007 | Energy reservation and trade confirmation in one atomic transaction (Reservation inside EnergyOffer) | Accepted |
| ADR-008 | Bounded contexts communicate only through domain events in `ecogrid/contracts` | Accepted |
| ADR-009 | Anti-Corruption Layers for meter vendors (kW x interval -> kWh, Wh -> kWh) and the payment provider | Accepted |
| ADR-010 | Design for microservice extraction, not immediate microservices | Accepted |
| ADR-011 | Meter ingestion runs as a separate, horizontally scalable worker deployable from day one | Accepted (team) |
| ADR-012 | Energy availability is stale after 2 x the 1-minute reporting interval; stale offers freeze | Accepted (team) |

## ADR-005 (revised) – Transactional outbox for cross-context events
- **Context:** In-process events are lost if the application crashes after a trade is committed but before Settlement is notified. Financial integrity is the top architectural driver.
- **Decision:** `TradeConfirmed` and other cross-context events are written to an outbox table in the same database transaction as the business change, then relayed. Every event carries `event_id` and `schema_version`; consumers are idempotent.
- **Consequences:** No lost financial events; duplicates are possible and handled by idempotent consumers (fitness function FF02). Adds an outbox relay to operate.

## ADR-011 – Separate meter-ingestion worker
- **Context:** ~167 readings/s average (10,000 meters every minute) with bursts. Running ingestion inside the API process lets spikes starve Marketplace of CPU and database connections.
- **Decision:** Meter ingestion is a separate deployable (same repository and image, different entrypoint), scaled horizontally with MQTT shared subscriptions.
- **Consequences:** Workloads are isolated; two deployables to operate instead of one.

## ADR-012 – Freshness threshold
- **Context:** Meters report every 60 s; treating a 30 s silence as stale would wrongly freeze healthy offers, while trusting old data risks selling energy that no longer exists.
- **Decision:** Availability is stale after 2 x the reporting interval (2 minutes); stale offers freeze until fresh data arrives.
- **Consequences:** Fail closed for that household's energy, fail open for the rest of the platform (fitness function FF06).
