# AP_FLAKE8_CLEAN
"""Versioned, bounded inputs for the synthetic open-water M1 scenario."""

import math
from pathlib import Path

import yaml
from geographiclib.geodesic import Geodesic

from .plant import DEFAULT_DESIGN, design

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "remora"
DEFAULT = PROJECT / "scenarios/pickup_1km.yaml"
LIMITS = {
    "seed": (0, 2**31 - 1),
    "speedup": (1, 32),
    "diver_e_m": (-5000, 5000),
    "diver_n_m": (-5000, 5000),
    "target_e_m": (-5000, 5000),
    "target_n_m": (-5000, 5000),
    "drift_e_mps": (-3, 3),
    "drift_n_mps": (-3, 3),
    "exclusion_m": (5, 1000),
    "uncertainty_m": (0, 200),
    "latency_s": (0, 30),
    "loss": (0, 1),
    "freshness_s": (1, 120),
    "timeout_s": (10, 7200),
}


def validate(raw):
    if not isinstance(raw, dict) or set(raw) - {"boat_design", "authorization"} != set(LIMITS) | {
        "name",
        "schema_version",
    }:
        raise ValueError("Expected all version 1 scenario fields and no extra fields")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ValueError("Unsupported scenario schema version")
    if not isinstance(raw["name"], str) or not raw["name"].strip() or len(raw["name"]) > 100:
        raise ValueError("Provide a scenario name of 1–100 characters")
    for field, (lo, hi) in LIMITS.items():
        val = raw[field]
        if type(val) not in (int, float) or not lo <= val <= hi:
            raise ValueError(f"{field} must be a finite number from {lo} to {hi}")
        if field in ("seed", "speedup") and type(val) is not int:
            raise ValueError(f"{field} must be an integer")
    role = raw.get("authorization", "surface_operator")
    if role not in ("surface_operator", "diver_handheld"):
        raise ValueError("Unknown rendezvous authorization")
    return dict(raw, boat_design=design(raw.get("boat_design", DEFAULT_DESIGN)), authorization=role)


def load(path=DEFAULT):
    return validate(yaml.safe_load(Path(path).read_text()))


class LocalFrame:
    """WGS84 azimuthal equidistant coordinates centered on the first boat fix."""

    def __init__(self, lat, lon):
        self.lat, self.lon = lat, lon

    def en(self, lat, lon):
        line = Geodesic.WGS84.Inverse(self.lat, self.lon, lat, lon)
        az = math.radians(line["azi1"])
        return line["s12"] * math.sin(az), line["s12"] * math.cos(az)

    def gps(self, east, north):
        line = Geodesic.WGS84.Direct(self.lat, self.lon, math.degrees(math.atan2(east, north)), math.hypot(east, north))
        return line["lat2"], line["lon2"]
