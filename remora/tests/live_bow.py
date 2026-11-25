"""Measure forward-only station keeping with the source-built Rover and uncalibrated lancha."""
# AP_FLAKE8_CLEAN
import json
import math
import statistics
import time

import pytest

from remora.engine import Engine
from remora.scenario import PROJECT, load


@pytest.mark.parametrize(
    "wind_from,wind_speed,current_n,expected_bow",
    [(90, 0, 1, 180), (90, 20 / 3.6, 0, 90), (90, 20 / 3.6, 1, 150), (270, 20 / 3.6, -1, 330)],
    ids=["current", "wind", "combined", "reversed"],
)
def test_forward_hold(wind_from, wind_speed, current_n, expected_bow):
    c = load(PROJECT / "scenarios/lancha_cross_current.yaml")
    c.update(speedup=24, loss=0)
    c["boat_design"].update(wind_from_deg=wind_from, wind_speed_mps=wind_speed, current_n_mps=current_n)
    engine = Engine(c)
    engine.start()
    try:
        deadline = time.monotonic() + 110
        while time.monotonic() < deadline:
            sample = engine.snapshot()
            assert sample["state"] != "FAULT", sample.get("fault")
            if sample["sim_s"] >= 420:
                break
            time.sleep(0.06)
        else:
            pytest.fail(f"Station study timed out in {sample['state']}")
    finally:
        engine.finish()

    path = engine.run_dir
    with (path / "samples.jsonl").open() as stream:
        samples = [json.loads(row) for row in stream]
    assert all(s["state"] == "STATION_KEEPING" and s["boat"]["mode"] == "LOITER" for s in samples)
    assert all(s["boat"]["plant"]["thrust_n"] >= 0 for s in samples)
    station = samples[0]["station"]
    settled = [s["boat"] for s in samples if s["sim_s"] >= 240]
    assert len(settled) >= 100
    errors = [math.hypot(b["e"] - station["e"], b["n"] - station["n"]) for b in settled]
    bow_errors = [abs((b["heading_deg"] - expected_bow + 180) % 360 - 180) for b in settled]
    assert max(errors) < 20, (max(errors), path)
    assert statistics.mean(bow_errors) < 20, (statistics.mean(bow_errors), path)
    assert statistics.median(b["plant"]["thrust_n"] for b in settled) > 0
    print(f"{path.name} · mean heading error {statistics.mean(bow_errors):.1f} deg, "
          f"max settled station error {max(errors):.1f} m")
