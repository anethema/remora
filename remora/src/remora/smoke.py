"""Run the calm-water L1 baseline against the built motorboat firmware."""

# AP_FLAKE8_CLEAN
import argparse
import json
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from geographiclib.geodesic import Geodesic

from .sitl import ROOT, Sitl


def smoke(run_dir: Path, speedup: int):
    report = {"fidelity": "L1", "result": "FAIL", "events": [], "thresholds_m": {"arrival": 4, "loiter_excursion": 12}}
    track = run_dir / "trajectory.jsonl"
    print(f"Baseline artifacts: {run_dir}", flush=True)
    try:
        with Sitl(run_dir, speedup) as sim, track.open("w") as points:
            start = sim.ready()
            report["events"].append([start.sim_s, "GNSS, pre-arm checks and HOLD confirmed"])
            sim.dump_params()
            sim.arm()
            sim.mode("GUIDED")
            waypoint = Geodesic.WGS84.Direct(start.lat, start.lon, 0, 40)
            lat, lon = waypoint["lat2"], waypoint["lon2"]
            sim.target(lat, lon)
            report["waypoint"] = {"lat": lat, "lon": lon}
            report["events"].append([sim.data.sim_s, "Armed, GUIDED, 40 m waypoint echoed"])

            def sample():
                previous = sim.data.sim_s
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    data = sim.poll(0.06)
                    if data.age_s > 2 or data.heartbeat_age_s > 3:
                        raise RuntimeError("Stale boat telemetry during smoke")
                    if data.sim_s > previous:
                        points.write(json.dumps(asdict(data), allow_nan=False) + "\n")
                        return data
                raise TimeoutError("Firmware clock did not advance")

            navigation_begin = sim.data.sim_s
            while True:
                data = sample()
                error = Geodesic.WGS84.Inverse(data.lat, data.lon, lat, lon)["s12"]
                if not data.armed or data.mode != "GUIDED":
                    raise RuntimeError(f"Unexpected state during transit: {data}")
                if error <= report["thresholds_m"]["arrival"]:
                    break
                if data.sim_s - navigation_begin > 100:
                    raise TimeoutError(f"40 m waypoint took over 100 sim s, remaining {error:.2f} m")
            report["waypoint_residual_m"] = error
            report["transit_s"] = data.sim_s - navigation_begin
            sim.mode("LOITER")
            anchor = sample()
            excursion = 0
            while data.sim_s < anchor.sim_s + 15:
                data = sample()
                if data.mode != "LOITER" or not data.armed:
                    raise RuntimeError("Lost LOITER or arming during station-keeping interval")
                excursion = max(excursion, Geodesic.WGS84.Inverse(anchor.lat, anchor.lon, data.lat, data.lon)["s12"])
            report["loiter_max_excursion_m"] = excursion
            if excursion > report["thresholds_m"]["loiter_excursion"]:
                raise RuntimeError(f"Loiter exceeded excursion threshold at {excursion:.2f} m")
            report["events"].append([data.sim_s, "15 s LOITER observed"])
            sim.mode("HOLD")
            hold_start = sim.data.sim_s
            while data.sim_s < hold_start + 7:
                data = sample()
                if data.mode != "HOLD":
                    raise RuntimeError("Lost HOLD")
            report["hold_speed_mps"] = data.speed_mps
            report["hold_throttle_pct"] = data.throttle_pct
            if data.throttle_pct != 0:
                raise RuntimeError("Nonzero throttle demand at end of HOLD")
            report["events"].append([data.sim_s, "HOLD and zero throttle demand confirmed"])
            report["firmware"] = sim.identity
        report["result"] = "PASS"
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        (run_dir / "smoke.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speedup", type=int, default=8, help="simulator speed factor, 1 to 32")
    parser.add_argument("--out", type=Path, help="new run directory (default remora/artifacts/smoke-*)")
    args = parser.parse_args()
    if args.out:
        args.out.mkdir(parents=True, exist_ok=False)
        path = args.out
    else:
        artifacts = ROOT / "remora/artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        path = Path(tempfile.mkdtemp(prefix="smoke-", dir=artifacts))
    result = smoke(path, args.speedup)
    print(
        f"PASS: waypoint residual {result['waypoint_residual_m']:.2f} m, "
        f"LOITER excursion {result['loiter_max_excursion_m']:.2f} m, HOLD throttle {result['hold_throttle_pct']}%"
    )


if __name__ == "__main__":
    main()
