"""Uncalibrated planar launch dynamics. Inputs are firmware channel PWM only."""

# AP_FLAKE8_CLEAN
import math

HULLS = {"light": (3.0, 150), "lancha": (3.7, 200), "loaded": (4.3, 250)}
DEFAULT_DESIGN = dict(
    model="native",
    length_m=3.7,
    mass_kg=200,
    thrust_lbf=55,
    max_current_a=50,
    steering="steerable",
    battery="LiFePO4",
    capacity_ah=100,
    wind_speed_mps=0,
    wind_from_deg=0,
    wind_cda_bow_m2=0.7,
    wind_cda_beam_m2=2.0,
    current_e_mps=0,
    current_n_mps=0,
)
DESIGN_LIMITS = {
    "length_m": (2, 6),
    "mass_kg": (80, 650),
    "thrust_lbf": (15, 120),
    "max_current_a": (5, 120),
    "capacity_ah": (20, 400),
    "wind_speed_mps": (0, 20),
    "wind_from_deg": (0, 360),
    "wind_cda_bow_m2": (0, 12),
    "wind_cda_beam_m2": (0, 20),
    "current_e_mps": (-2, 2),
    "current_n_mps": (-2, 2),
}
STEERING = ("steerable", "rudder", "differential")


def design(raw):
    if not isinstance(raw, dict) or set(raw) != set(DEFAULT_DESIGN):
        raise ValueError("Incomplete boat design")
    if (
        raw["model"] not in ("native", "lancha")
        or raw["steering"] not in STEERING
        or raw["battery"] not in ("AGM", "LiFePO4")
    ):
        raise ValueError("Unknown boat model, steering arrangement or battery chemistry")
    for key, (lo, hi) in DESIGN_LIMITS.items():
        value = raw[key]
        if type(value) not in (int, float) or not lo <= value <= hi:
            raise ValueError(f"{key} must be between {lo} and {hi}")
    return dict(raw)


def demand(pwm):
    # Invalid/uninitialized outputs represent a neutral actuator.
    if not 900 <= pwm <= 2100:
        return 0.0
    x = max(-1.0, min(1.0, (pwm - 1500) / 500))
    return math.copysign(max(0.0, abs(x) - 0.04) / 0.96, x)


class Plant:
    def __init__(self, config):
        self.c = design(config)
        self.t = self.e = self.n = self.ve = self.vn = self.yaw = self.rate = 0.0
        self.steer = self.a = self.b = self.energy = self.ah = 0.0
        self.volts = 13.2 if self.c["battery"] == "LiFePO4" else 12.75
        self.amps = self.force = 0.0
        self.cutoff = False

    def step(self, ch1, ch3, dt):
        c = self.c
        twin = c["steering"] == "differential"
        left = demand(ch1) if twin else 0.0
        right = demand(ch3)
        target_angle = 0 if twin else math.radians(35) * demand(ch1)
        self.steer += max(-dt, min(dt, target_angle - self.steer))
        self.a += (left - self.a) * min(1, dt / 0.35)
        self.b += (right - self.b) * min(1, dt / 0.35)

        # Per-motor current and static thrust. All coefficients are illustrative.
        self.amps = 0.5 + (0.0 if self.cutoff else c["max_current_a"] * (abs(self.a) ** 1.5 + abs(self.b) ** 1.5))
        self.ah += self.amps * dt / 3600
        soc = max(0.0, 1 - self.ah / c["capacity_ah"])
        lithium = c["battery"] == "LiFePO4"
        ocv = 12.0 + 1.2 * soc if lithium else 11.7 + 1.05 * soc
        self.volts = max(0.0, ocv - self.amps * (0.009 if lithium else 0.017) * 100 / c["capacity_ah"])
        self.cutoff |= self.volts < 10.5 or soc == 0
        self.energy += self.amps * self.volts * dt / 3600

        co, si = math.cos(self.yaw), math.sin(self.yaw)
        rel_n, rel_e = self.vn - c["current_n_mps"], self.ve - c["current_e_mps"]
        u, v = co * rel_n + si * rel_e, -si * rel_n + co * rel_e
        source = math.radians(c["wind_from_deg"])
        wind_n = -c["wind_speed_mps"] * math.cos(source) - self.vn
        wind_e = -c["wind_speed_mps"] * math.sin(source) - self.ve
        wu, wv = co * wind_n + si * wind_e, -si * wind_n + co * wind_e
        length, mass = c["length_m"], c["mass_kg"]
        scale = c["thrust_lbf"] * 4.4482216152605 * min(1.0, self.volts / 12.0)
        if self.cutoff:
            scale = 0.0

        def thrust(cmd):
            advance = max(0.0, math.copysign(1.0, cmd) * u)
            return cmd * scale * max(0.0, 1 - advance / 4.5)

        tl, tr = thrust(self.a), thrust(self.b)
        self.force = tl + tr
        fx = self.force
        fy = moment = 0.0
        if twin:
            moment = (tl - tr) * length * 0.16
        elif c["steering"] == "rudder":
            # Downstream rudder sees hull inflow and the fixed propeller slipstream.
            # Effective area/lift slope and slipstream disk loading are uncalibrated.
            inflow_sq = u * abs(u) + tr / 85.0
            fy = -33.0 * inflow_sq * math.sin(2 * self.steer)
        else:
            fx = tr * math.cos(self.steer)
            fy = -tr * math.sin(self.steer)
        moment -= fy * length * 0.42
        # Dissipative body forces, simple anisotropic added mass and yaw damping.
        drag_scale = (mass / 200.0) ** 0.45 * (length / 3.7) ** 0.4
        fx += -0.5 * drag_scale * (18 * u + 65 * u * abs(u)) + 0.5 * 1.225 * c["wind_cda_bow_m2"] * wu * abs(wu)
        fy += -drag_scale * (48 * v + 135 * v * abs(v)) + 0.5 * 1.225 * c["wind_cda_beam_m2"] * wv * abs(wv)
        moment += 24 * length * v * abs(u) * drag_scale
        moment -= (140 * self.rate + 180 * self.rate * abs(self.rate)) * drag_scale
        ax, ay = fx / (1.08 * mass), fy / (1.45 * mass)
        self.vn += (co * ax - si * ay) * dt
        self.ve += (si * ax + co * ay) * dt
        self.n += self.vn * dt
        self.e += self.ve * dt
        self.rate += moment / (0.10 * mass * length**2) * dt
        self.yaw = math.remainder(self.yaw + self.rate * dt, 2 * math.pi)
        self.t += dt
        return {
            "timestamp": self.t,
            "imu": {"gyro": [0, 0, self.rate], "accel_body": [ax, ay, -9.80665]},
            "position": [self.n, self.e, 0],
            "velocity": [self.vn, self.ve, 0],
            "attitude": [0, 0, self.yaw],
            "battery": {"voltage": self.volts, "current": self.amps},
        }

    def metrics(self):
        return {
            "sim_s": self.t,
            "thrust_n": self.force,
            "steering_deg": math.degrees(self.steer),
            "voltage_v": self.volts,
            "current_a": self.amps,
            "soc_pct": max(0.0, 100 * (1 - self.ah / self.c["capacity_ah"])),
            "energy_wh": self.energy,
            "motor_cutoff": self.cutoff,
        }
