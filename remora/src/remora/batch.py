# AP_FLAKE8_CLEAN
"""Scripted surface operator for repeatable integration tests."""

import argparse
import json
import time

from .engine import Engine
from .scenario import DEFAULT, load


def exercise(config):
    engine = Engine(config)
    engine.start()
    wall_timeout = 120 + 3 * config["timeout_s"] / config["speedup"]
    deadline = time.monotonic() + wall_timeout
    request_t = -100
    try:
        while time.monotonic() < deadline:
            s = engine.snapshot()
            state, actions = s["state"], s["actions"]
            if s["status"] == "FAULT" or state in ("FAULT", "ABORT"):
                break
            if state == "RENDEZVOUS_HOLD":
                break
            if s.get("approval_block_reason"):
                engine.action("reject")
                break
            if s["sim_s"] >= config["timeout_s"] and "abort" in actions:
                engine.action("abort")
                break
            if "approve" in actions:
                engine.action("approve")
            elif "request" in actions and s["sim_s"] - request_t >= 15:
                engine.action("request")
                request_t = s["sim_s"]
            time.sleep(0.08)
        else:
            if "abort" in engine.snapshot()["actions"]:
                engine.action("abort")
    finally:
        engine.finish()
    report = dict(engine.result or {})
    report.update(seed=config["seed"], path=str(engine.run_dir))
    return report


def main():
    parser = argparse.ArgumentParser(description="Run the native-boat M1 pickup regression across seeds")
    parser.add_argument("--suite", choices=["marine"], default="marine", help="M1 separated rendezvous regression")
    parser.add_argument("--scenario", default=str(DEFAULT))
    parser.add_argument("--seeds", default="7", help="comma-separated integer seeds")
    parser.add_argument("--speedup", type=int, help="override simulation speed")
    opts = parser.parse_args()
    config = load(opts.scenario)
    if opts.speedup is not None:
        config["speedup"] = opts.speedup
    reports = [exercise(dict(config, seed=int(seed))) for seed in opts.seeds.split(",")]
    print(json.dumps(reports, indent=2))
    return int(any(r.get("outcome") != "passed" for r in reports))


if __name__ == "__main__":
    raise SystemExit(main())
