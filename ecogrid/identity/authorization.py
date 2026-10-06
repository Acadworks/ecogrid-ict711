"""Household-level authorization (identity provider is Conformist upstream)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    user_id: str
    household_ids: frozenset[str]


class Forbidden(Exception):
    pass


def require_household(principal: Principal, household_id: str) -> None:
    if household_id not in principal.household_ids:
        raise Forbidden(f"{principal.user_id} may not access {household_id}")
