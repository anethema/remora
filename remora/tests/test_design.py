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


def test_one_tap_delivers_one_guided_target():
    c = validate(dict(load(), authorization="diver_handheld", latency_s=1, loss=0))
    assert c["authorization"] == "handheld_pickup"
    m = Mission(c)
    boat = dict(e=0, n=0, mode="LOITER", armed=True, age_s=0, heartbeat_age_s=0)
    m.step(0, boat)
    with pytest.raises(ValueError):
        m.action("request", 0, boat)
    for t in range(1, 7):
        assert m.step(t, boat) == []
    snap = m.snapshot(6, boat)
    assert "request" in snap["actions"]
    assert snap["radio"]["telemetry"]["meeting_range_m"] == pytest.approx(100, abs=0.1)
    assert m.action("request", 6, boat) == []
    assert m.state == "STATION_KEEPING"
    assert m.step(8, boat) == [("target", 900, 0)]
    assert m.state == "TRANSIT_TO_RENDEZVOUS"
    assert m.step(9, dict(boat, mode="GUIDED")) == []


def test_single_press_rechecks_route_and_rejects_stale_or_substituted_offer():
    from remora.mission import Packet

    m = Mission(dict(load(), authorization="handheld_pickup", latency_s=0, loss=0))
    boat = dict(e=0, n=0, mode="LOITER", armed=True, age_s=0, heartbeat_age_s=0)
    for t in range(5):
        m.step(t, boat)
    payload = dict(e=1000.0, n=0.0, target_e=900.0, target_n=0.0, offer_t=4.0)
    for fields in [dict(target_e=1000.0), dict(offer_t=-30.0)]:
        assert m._receive(Packet(m._session, "request", 1, 4.0, dict(payload, **fields)), 4.0, boat) == []
        assert m.state == "STATION_KEEPING"
    m.action("request", 4.0, boat)
    commands = m.step(4.0, dict(boat, e=999))
    assert all(cmd[0] != "target" for cmd in commands)
    assert "confirm" not in m.snapshot(4.0, boat)["actions"]


def test_cancel_then_manually_station_keep_at_current_position():
    m = Mission(dict(load(), latency_s=0, loss=0))
    boat = dict(e=0, n=0, mode="LOITER", armed=True, age_s=0, heartbeat_age_s=0)
    m.step(0, boat)
    m.action("request", 0, boat)
    m.step(0, boat)
    assert m.action("approve", 1, boat) == [("target", 900, 0)]
    guided = dict(boat, mode="GUIDED", e=220.0)
    m.step(2, guided)
    assert m.action("cancel", 3, guided) == []
    assert m.step(3, guided) == [("hold",)]
    hold = dict(guided, mode="HOLD", e=222.0)
    assert m.step(4, hold) == []
    assert m.state == "ABORT"
    assert "station_keep" in m.snapshot(4, hold)["actions"]
    m.action("station_keep", 4, hold)
    assert m.step(4, hold) == [("loiter",)]
    assert m.state == "SETTING_STATION"
    m.step(5, dict(hold, mode="LOITER"))
    s = m.snapshot(5, boat)
    assert s["state"] == "STATION_KEEPING"
    assert s["station"] == {"e": 222.0, "n": 0}
    assert "request" in s["actions"]
    assert m.step(6, dict(hold, mode="LOITER")) == []


@pytest.mark.parametrize(
    "update", [dict(armed=False), dict(e=995.0), dict(heartbeat_age_s=20.0), dict(plant={"motor_cutoff": True})]
)
def test_unsafe_manual_station_keep_is_refused(update):
    m = Mission(dict(load(), latency_s=0, loss=0))
    boat = dict(e=0, n=0, mode="LOITER", armed=True, age_s=0, heartbeat_age_s=0)
    m.step(0, boat)
    m.action("abort", 1, boat)
    hold = dict(boat, mode="HOLD")
    hold.update(update)
    assert "station_keep" not in m.snapshot(2, hold)["actions"]
    with pytest.raises(ValueError):
        m.action("station_keep", 2, hold)
    assert m.state == "ABORT"
