"""Headless real-firmware regression, invoked by run-tests.sh --recovery."""

# AP_FLAKE8_CLEAN
import time

from remora.engine import Engine
from remora.scenario import PROJECT, load


def await_sample(engine, condition, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sample = engine.snapshot()
        assert sample["status"] != "FAULT" and sample["state"] != "FAULT", sample.get("fault")
        if condition(sample):
            return sample
        time.sleep(0.04)
    raise AssertionError(f"Timed out in {sample['state']} with actions {sample['actions']}")


def test_cancel_and_station_keep_with_source_built_rover():
    scenario = load(PROJECT / "scenarios/lancha_1km.yaml")
    scenario.update(speedup=12, loss=0, target_e_m=130, diver_e_m=280)
    engine = Engine(scenario)
    engine.start()
    try:
        await_sample(engine, lambda s: "request" in s["actions"])
        engine.action("request")
        await_sample(engine, lambda s: s["state"] == "TRANSIT_TO_RENDEZVOUS" and s["boat"]["e"] > 18)
        engine.action("cancel")
        await_sample(
            engine, lambda s: s["state"] == "ABORT" and s["boat"]["mode"] == "HOLD" and "station_keep" in s["actions"]
        )
        engine.action("station_keep")
        station = await_sample(engine, lambda s: s["state"] == "STATION_KEEPING" and s["boat"]["mode"] == "LOITER")
        assert station["station"]["e"] > 15
        after = await_sample(engine, lambda s: s["sim_s"] > station["sim_s"] + 5 and "request" in s["actions"])
        assert after["state"] == "STATION_KEEPING" and after["boat"]["mode"] == "LOITER"
        assert after["station"] == station["station"]
        engine.action("request")
        await_sample(engine, lambda s: s["boat"]["mode"] == "GUIDED" and s["boat"]["e"] > station["station"]["e"] + 15)
        engine.action("station_keep")
        direct = await_sample(engine, lambda s: s["state"] == "STATION_KEEPING" and s["boat"]["mode"] == "LOITER")
        assert direct["station"]["e"] > station["station"]["e"] + 10
        confirmed = await_sample(engine, lambda s: s["radio"]["ack"] == "Station keeping here")
        assert confirmed["station"] == direct["station"]
        print(f"Verified Cancel/Hold recovery and direct Guided/Loiter at {direct['station']}. Evidence in {engine.run_dir}")
    finally:
        engine.finish()
