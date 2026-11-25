"""Real Rover regression for explicit handheld updates while travelling and after arrival."""

# AP_FLAKE8_CLEAN
import math
import time

from pymavlink import mavutil

from remora.engine import Engine
from remora.scenario import PROJECT, load


def wait_for(engine, condition, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sample = engine.snapshot()
        assert sample["status"] != "FAULT" and sample["state"] != "FAULT", sample.get("fault")
        if condition(sample):
            return sample
        time.sleep(0.04)
    raise AssertionError(f"Timed out in {sample['state']}, target {sample['target']}, boat {sample['boat']}")


def changed_target(engine, old):
    engine.action("update_rendezvous")
    state = wait_for(engine, lambda s: s["radio"]["update"]["status"] == "executing" and s["target"] != old)
    update = state["radio"]["update"]
    assert state["target"] == {"e": update["target_e"], "n": update["target_n"]}
    assert state["boat"]["mode"] == "GUIDED"
    return state["target"]


def test_update_during_transit_and_from_rendezvous_hold():
    scenario = load(PROJECT / "scenarios/lancha_1km.yaml")
    scenario.update(speedup=12, loss=0, latency_s=1, target_e_m=130, diver_e_m=280, drift_n_mps=0.6)
    engine = Engine(scenario)
    engine.start()
    try:
        wait_for(engine, lambda s: "request" in s["actions"])
        engine.action("request")
        transit = wait_for(engine, lambda s: "update_rendezvous" in s["actions"] and s["boat"]["e"] > 35)
        first = changed_target(engine, transit["target"])
        assert first["n"] > 5
        held = wait_for(engine, lambda s: s["state"] == "RENDEZVOUS_HOLD")
        assert held["target"] == first and held["boat"]["mode"] == "LOITER"
        assert math.hypot(held["boat"]["e"] - first["e"], held["boat"]["n"] - first["n"]) < 8
        later = wait_for(engine, lambda s: s["sim_s"] > held["sim_s"] + 16)
        assert later["target"] == first and later["diver"]["n"] > held["diver"]["n"] + 8
        second = changed_target(engine, first)
        assert second["n"] - first["n"] > 12
        arrival = wait_for(engine, lambda s: s["state"] == "RENDEZVOUS_HOLD" and s["boat"]["mode"] == "LOITER")
        assert arrival["target"] == second
        assert math.hypot(arrival["boat"]["e"] - second["e"], arrival["boat"]["n"] - second["n"]) < 8
        assert arrival["metrics"]["minimum_separation_m"] > 53
    finally:
        engine.finish()

    # Match the three emitted WGS84 targets to actual position-target reports from the vehicle.
    messages = mavutil.mavlink_connection(str(engine.run_dir / "sitl/firmware/telemetry.tlog"))
    commanded, echoed = set(), set()
    try:
        while msg := messages.recv_match():
            if msg.get_type() == "SET_POSITION_TARGET_GLOBAL_INT" and msg.get_srcSystem() == 255:
                commanded.add((msg.lat_int, msg.lon_int))
            if msg.get_type() == "POSITION_TARGET_GLOBAL_INT" and msg.get_srcSystem() == 1:
                echoed.add((msg.lat_int, msg.lon_int))
    finally:
        messages.close()
    assert len(commanded) == 3
    for lat, lon in commanded:
        assert any(abs(a - lat) <= 2 and abs(b - lon) <= 2 for a, b in echoed)
    print(f"Verified {len(commanded)} actual Guided targets, final {second}, in {engine.run_dir}")
