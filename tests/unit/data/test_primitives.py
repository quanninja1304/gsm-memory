from datetime import datetime
from fractions import Fraction

import pytest

from gsm_memory.data.contracts import ScenarioManifest
from gsm_memory.data.primitives import as_fraction, component_seed, rational, stable_id, utc
from gsm_memory.evaluation.formulas import auto_accept, cancel_rate, rating_condition, revenue_charge


def test_ids_and_seed_are_stable():
    assert stable_id("driver", "D_A") == stable_id("driver", "D_A")
    assert stable_id("driver", "D_A") != stable_id("driver", "D_B")
    assert component_seed("events", "W0") == 18431874524840890038


def test_exact_arithmetic_boundaries():
    assert rational(2, 10) == {"n": 1, "d": 5}
    assert as_fraction(rational(49, 100)) == Fraction(49, 100)
    assert [revenue_charge(x) for x in (200_000, 280_000, 300_000)] == [16_000, 0, 0]
    assert auto_accept("bike_partner", Fraction(49,100))
    assert not auto_accept("bike_partner", Fraction(1,2))
    assert not rating_condition(Fraction(97,20)) and rating_condition(Fraction(49,10))
    assert cancel_rate(2,8)==Fraction(1,5) and cancel_rate(0,0) is None


def test_timezone_required():
    with pytest.raises(ValueError): utc(datetime(2026, 1, 1))


def test_closed_scenario_rejects_unknown_key():
    with pytest.raises(Exception): ScenarioManifest.model_validate({"unexpected": True})
