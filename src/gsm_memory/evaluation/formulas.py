from __future__ import annotations

from fractions import Fraction


def revenue_charge(revenue_vnd: int) -> int:
    if revenue_vnd < 0:
        raise ValueError("revenue cannot be negative")
    return max(280_000 - revenue_vnd, 0) // 5


def auto_accept(program: str, acceptance: Fraction) -> bool:
    return program == "bike_partner" and acceptance < Fraction(1, 2)


def rating_condition(rating: Fraction) -> bool:
    return rating > Fraction(97, 20)


def cancel_rate(cancelled: int, completed: int) -> Fraction | None:
    if cancelled < 0 or completed < 0:
        raise ValueError("counts cannot be negative")
    total = cancelled + completed
    return None if total == 0 else Fraction(cancelled, total)

