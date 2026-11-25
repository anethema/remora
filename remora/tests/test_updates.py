"""Radio and mission invariants for moving, manually updated rendezvous points."""

# AP_FLAKE8_CLEAN
import math

import pytest

from remora.mission import Mission, Packet
from test_mission import BASE, BOAT

GUIDED = dict(BOAT, mode="GUIDED")


def handheld(heading=90.0, **overrides):
    settings = dict(BASE, authorization="handheld_pickup", drift_n_mps=0.5)
    settings.update(overrides)
    mission = Mission(settings)
    boat = dict(BOAT, heading_deg=heading)
    for t in (0, 1, 2):
        mission.step(t, boat)
    mission.action("request", 2, boat)
    assert mission.step(2, boat) == [("target", settings["target_e_m"], settings["target_n_m"])]
    mission.step(3, dict(boat, mode="GUIDED"))
    return mission


def test_press_captures_fix_and_delivery_does_not_follow_new_fixes():
    m = handheld()
    m.c["latency_s"] = 3
    m.step(5, GUIDED)
    assert m.action("update_rendezvous", 5, GUIDED) == []
    queued = next(item[2] for item in m._queue if item[2].kind == "update_rendezvous")
    assert queued.payload["fix_t"] == 5
    assert m.snapshot(5, GUIDED)["radio"]["update"]["status"] == "sent"
    assert m.target == (900, 0)
    with pytest.raises(ValueError, match="in flight"):
        m.action("update_rendezvous", 6, GUIDED)
    # A newer independent position report can arrive before the control packet.
    m._receive(Packet(m._session, "fix", 999, 6, {"e": 1000, "n": 3}), 6, GUIDED)
    target = None
    statuses = set()
    for tick in range(61, 181):
        t = tick / 10
        commands = m.step(t, GUIDED)
        if commands:
            assert target is None
            target = commands
        statuses.add(m.snapshot(t, GUIDED)["radio"]["update"]["status"])
    assert target == [("target", 900, 2.5)]
    assert m.target == (900, 2.5)
    assert "executing" in statuses
    received = m.snapshot(18, GUIDED)["radio"]["telemetry"]
    assert received["meeting_active"] and (received["target_e"], received["target_n"]) == m.target


def test_stale_invalid_replayed_and_unsafe_updates_do_not_change_target():
    m = handheld()
    original = m.target
    valid = dict(e=1000, n=2, fix_t=4, surfaced=True, request_id=m._request)
    for session, timestamp, payload in [
        (object(), 4, valid),
        (m._session, 16, dict(valid, fix_t=1)),
        (m._session, 4, dict(valid, fix_t=9)),
        (m._session, 4, dict(valid, surfaced=False)),
        (m._session, 4, dict(valid, n=math.nan)),
        (m._session, 4, dict(valid, request_id=999)),
    ]:
        assert m._receive(Packet(session, "update_rendezvous", 5, timestamp, payload), timestamp, GUIDED) == []
        assert m.target == original
    bad = Packet(m._session, "update_rendezvous", 5, 5, dict(valid, e=2900, fix_t=5))
    assert m._receive(bad, 5, GUIDED) == []
    assert m.target == original and "known" in m.snapshot(5, GUIDED)["events"][-1]["message"]
    unsafe = Packet(m._session, "update_rendezvous", 6, 6, dict(valid, e=-5, fix_t=6))
    assert m._receive(unsafe, 6, GUIDED) == []
    assert m.target == original and "exclusion" in m.snapshot(6, GUIDED)["events"][-1]["message"]
    good = Packet(m._session, "update_rendezvous", 7, 7, dict(valid, n=3.5, fix_t=7))
    assert m._receive(good, 7, GUIDED) == [("target", 900, 3.5)]
    assert m._receive(good, 7, GUIDED) == []
    assert m._receive(Packet(m._session, "cancel", 8, 8, {}), 8, GUIDED) == [("hold",)]
    assert m._receive(good, 9, GUIDED) == []
    assert m.state == "ABORT" and m.target == (900, 3.5)


def test_telemetry_outage_and_missing_mode_gate_handheld_update():
    m = handheld()
    for t, boat in [(30, GUIDED), (4, BOAT), (4, dict(GUIDED, armed=False)), (4, dict(GUIDED, heartbeat_age_s=5))]:
        with pytest.raises(ValueError):
            m.action("update_rendezvous", t, boat)
        assert "update_rendezvous" not in m.snapshot(t, boat)["actions"]
    surface = Mission(BASE)
    assert "update_rendezvous" not in surface.snapshot(4, BOAT)["actions"]
    with pytest.raises(ValueError):
        surface.action("update_rendezvous", 4, BOAT)


@pytest.mark.parametrize(
    "drift,heading,timeout", [(0, 90, 1200), (0.01, 90, 1200), (1, 90, 1200), (0.01, 270, 1200), (1, 90, 20)]
)
def test_repeated_updates_cannot_credit_target_motion_or_starve_deadlines(drift, heading, timeout):
    # North drift creates a safe hazard corridor east of the boat. Starting at
    # negative target north means the moving candidate actually closes on this fixed boat.
    m = handheld(heading=heading, target_n_m=-200, drift_n_mps=drift, timeout_s=timeout)
    boat = dict(GUIDED, heading_deg=heading)
    expected_deadline = min(m._began + timeout, m._progress_at + 45)
    updates = 0
    for t in range(4, int(expected_deadline) + 2):
        if "update_rendezvous" in m.snapshot(t, boat)["actions"]:
            m.action("update_rendezvous", t, boat)
            updates += 1
        commands = m.step(t, boat)
        assert m._eta(t) is None
        if m.state == "FAULT":
            assert commands == [("hold",)]
            break
    assert updates > 5 and m.state == "FAULT" and t <= expected_deadline + 1
    assert "timed out" in m.fault if timeout == 20 else "progress" in m.fault


def test_lost_update_does_not_move_target_and_can_be_retried():
    m = handheld()
    m.c["loss"] = 1.0
    m.action("update_rendezvous", 4, GUIDED)
    m.c["loss"] = 0.0
    for t in range(4, 31):
        assert not m.step(t, GUIDED)
    assert m.target == (900, 0)
    assert m.snapshot(30, GUIDED)["radio"]["update"]["status"] == "unconfirmed"
    assert m.action("update_rendezvous", 30, GUIDED) == []
    assert m.step(30, GUIDED) == [("target", 900, 15)]
