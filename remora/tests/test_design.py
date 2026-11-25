"""Regression checks for what the design controls actually change."""

# AP_FLAKE8_CLEAN
import math

import pytest
from remora.mission import Mission
from remora.plant import DEFAULT_DESIGN, Plant, demand
from remora.scenario import load, validate


def simulate(ch1=1500, ch3=1500, duration=8, **changes):
    p = Plant(dict(DEFAULT_DESIGN, model="lancha", **changes))
    for _ in range(round(duration * 100)):
        p.step(ch1, ch3, 0.01)
    return p


def test_north_wind_pushes_south_and_windage_controls_force():
    calm = simulate()
    north = simulate(wind_speed_mps=5, wind_from_deg=0)
    south = simulate(wind_speed_mps=5, wind_from_deg=180)
    bare = simulate(wind_speed_mps=5, wind_from_deg=0, wind_cda_bow_m2=0)
    assert calm.n == bare.n == 0
    assert north.n < 0 < south.n
    assert abs(north.e) < 1e-6
    assert abs(north.n) == pytest.approx(south.n, abs=0.001)
    beam = simulate(wind_speed_mps=5, wind_from_deg=90)
    larger = simulate(wind_speed_mps=5, wind_from_deg=90, wind_cda_beam_m2=4)
    assert larger.e < beam.e < 0


def test_motor_hull_and_battery_sensitivity():
    base = simulate(ch3=1900)
    strong = simulate(ch3=1900, thrust_lbf=80)
    heavy = simulate(ch3=1900, mass_kg=300)
    agm = simulate(ch3=1900, battery="AGM")
    big = simulate(ch3=1900, capacity_ah=200)
    assert heavy.n < base.n < strong.n
    assert 0 < base.energy < 12
    assert agm.volts < base.volts < big.volts
    assert base.metrics()["soc_pct"] < big.metrics()["soc_pct"] < 100


def test_steering_signs_and_neutral():
    assert demand(0) == demand(1500) == demand(1490) == 0
    for method in ("steerable", "rudder"):
        right = simulate(1780, 1850, duration=1.5, steering=method)
        left = simulate(1220, 1850, duration=1.5, steering=method)
        assert right.yaw > 0 > left.yaw
        assert right.yaw == pytest.approx(-left.yaw)
    twin = simulate(1850, 1150, duration=1.5, steering="differential")
    assert twin.yaw > 0 and math.hypot(twin.e, twin.n) < 0.001


def test_v1_scenarios_and_validation():
    legacy = load()
    del legacy["authorization"], legacy["boat_design"]
    assert validate(legacy)["boat_design"]["model"] == "native"
    c = load()
    for patch in ({"wind_from_deg": -1}, {"wind_cda_beam_m2": float("nan")}, {"steering": "real"}):
        with pytest.raises(ValueError):
            validate(dict(c, boat_design={**DEFAULT_DESIGN, **patch}))


def test_handheld_requires_a_delivered_offer_and_matching_confirmation():
    c = dict(load(), authorization="diver_handheld", latency_s=1, loss=0)
    m = Mission(c)
    boat = dict(e=0, n=0, mode="LOITER", armed=True, age_s=0, heartbeat_age_s=0)
    m.step(0, boat)
    m.action("request", 0, boat)
    m.step(2, boat)
    with pytest.raises(ValueError):
        m.action("approve", 2, boat)
    assert "confirm" not in m.snapshot(2, boat)["actions"]
    for t in (3, 4, 5, 6):
        m.step(t, boat)
    snap = m.snapshot(6, boat)
    assert "confirm" in snap["actions"]
    assert snap["radio"]["telemetry"]["meeting_range_m"] == pytest.approx(100, abs=0.1)
    assert m.action("confirm", 6, boat) == []
    assert m.state == "PICKUP_REQUESTED"
    assert m.step(8, boat) == [("target", 900, 0)]
    assert m.state == "TRANSIT_TO_RENDEZVOUS"
