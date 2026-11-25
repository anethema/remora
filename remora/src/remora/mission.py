# AP_FLAKE8_CLEAN
"""Simulation-only mission supervisor. Frame is local ENU in metres, time is SITL seconds."""

from __future__ import annotations

import heapq
import math
import random
from collections import deque
from dataclasses import dataclass

Point = tuple[float, float]
ARRIVAL_M = 8.0
OPEN_WATER_HALF_WIDTH_M = 2500.0
NO_PROGRESS_S = 45.0
DEPARTURE_LIMIT_S = 120.0
DEPARTURE_RETREAT_M = 100.0
RECOVERY_GRACE_S = 12.0
MIN_RECOVERY_SPEED_MPS = 0.5
TERMINAL = {"ABORT", "FAULT"}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def heading_error_deg(boat, target):
    if not finite(boat.get("heading_deg")):
        return None
    bearing = math.degrees(math.atan2(target[0] - boat["e"], target[1] - boat["n"]))
    return abs((boat["heading_deg"] - bearing + 180.0) % 360.0 - 180.0)


def point_segment(p, a, b):
    x, y = b[0] - a[0], b[1] - a[1]
    norm = x * x + y * y
    if norm == 0:
        return math.dist(p, a)
    u = max(0.0, min(1.0, ((p[0] - a[0]) * x + (p[1] - a[1]) * y) / norm))
    return math.dist(p, (a[0] + u * x, a[1] + u * y))


def side(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def segments_distance(a, b, c, d):
    if side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0:
        return 0.0
    return min(point_segment(a, c, d), point_segment(b, c, d), point_segment(c, a, b), point_segment(d, a, b))


@dataclass(frozen=True)
class Packet:
    session: object
    kind: str
    sequence: int
    sent: float
    payload: dict


def channel(kind):
    # A late request cannot revive a newer cancellation.
    return "control" if kind in ("request", "cancel", "station_keep") else kind


def can_request_station(state, recoverable_fault):
    return state in ("ABORT", "TRANSIT_TO_RENDEZVOUS", "PICKUP_REQUESTED", "RENDEZVOUS_HOLD") or (
        state == "FAULT" and recoverable_fault
    )


class Mission:
    """Owns the virtual channel, operator approvals and safety policy for one synthetic run."""

    def __init__(self, config: dict):
        numbers = (
            "speedup",
            "diver_e_m",
            "diver_n_m",
            "drift_e_mps",
            "drift_n_mps",
            "target_e_m",
            "target_n_m",
            "exclusion_m",
            "uncertainty_m",
            "latency_s",
            "loss",
            "freshness_s",
            "timeout_s",
        )
        if type(config.get("schema_version")) is not int or config["schema_version"] != 1:
            raise ValueError("Expected scenario schema version 1")
        if type(config.get("seed")) is not int or not isinstance(config.get("name"), str):
            raise ValueError("Expected integer seed and scenario name")
        if any(not finite(config.get(key)) for key in numbers):
            raise ValueError("All scenario numeric fields must be present and finite")
        if (
            not 0 <= config["loss"] <= 1
            or min(config["latency_s"], config["uncertainty_m"]) < 0
            or min(config["speedup"], config["freshness_s"], config["timeout_s"], config["exclusion_m"]) <= 0
        ):
            raise ValueError("Invalid radio, separation or timing limits")
        self.c = dict(config)
        self.target = config["target_e_m"], config["target_n_m"]
        self.velocity = config["drift_e_mps"], config["drift_n_mps"]
        self.state = "STATION_KEEPING"
        self.fault = None
        self._manual_station_recovery = False
        self.single_press = config.get("authorization") == "handheld_pickup"
        self._session = object()
        self._rng = random.Random(config["seed"])
        self._queue = []
        self._sent = self._lost = self._rejected = 0
        self._seq, self._seen = {}, {}
        self._events = []
        self._start = self._fix = self._telemetry = self._latency = None
        self._next_period = self._request_sent_at = -math.inf
        self._ack = "none"
        self._station_sent = -math.inf
        self._station_requested = None
        self._request = self._began = self._arrived = self._loiter_requested = None
        self._min_sep = self._station = None
        self._max_station_error = 0.0
        self._best_distance = math.inf
        self._progress_at = 0.0
        self._progress = deque()
        self._departure_turn = False

    def _clock(self, t):
        if not finite(t) or t < 0:
            raise ValueError("Invalid simulation clock")
        if self._start is None:
            self._start = t
            self._event(t, "Simulation station keeping")

    def _event(self, t, message):
        self._events.append({"t": t, "message": message})

    def _diver(self, t) -> Point:
        dt = 0.0 if self._start is None else t - self._start
        return (self.c["diver_e_m"] + self.velocity[0] * dt, self.c["diver_n_m"] + self.velocity[1] * dt)

    def _send(self, kind, t, payload):
        key = channel(kind)
        seq = self._seq.get(key, 0) + 1
        self._seq[key] = seq
        self._sent += 1
        if self._rng.random() < self.c["loss"]:
            self._lost += 1
        else:
            latency = self.c["latency_s"] * self._rng.uniform(0.5, 1.5)
            heapq.heappush(self._queue, (t + latency, self._sent, Packet(self._session, kind, seq, t, payload)))
        return seq

    def _valid(self, packet, t):
        if not isinstance(packet, Packet) or packet.session is not self._session:
            return False
        k, p = packet.kind, packet.payload
        if (
            k not in ("request", "cancel", "status", "fix", "telemetry", "ack", "station_keep")
            or type(packet.sequence) is not int
            or packet.sequence <= self._seen.get(channel(k), 0)
            or not finite(packet.sent)
            or not 0 <= t - packet.sent <= self.c["freshness_s"]
            or not isinstance(p, dict)
        ):
            return False
        if k == "request" and self.single_press:
            if (
                not finite(p.get("offer_t"))
                or not 0 <= t - p["offer_t"] <= self.c["freshness_s"]
                or (p.get("target_e"), p.get("target_n")) != self.target
            ):
                return False
        if k in ("fix", "request"):
            return all(finite(p.get(key)) for key in ("e", "n"))
        if k == "ack":
            return isinstance(p.get("text"), str)
        if k == "telemetry":
            return (
                all(finite(p.get(key)) for key in ("t", "range_m", "bearing_deg"))
                and p["t"] == packet.sent
                and all(p.get(key) is None or finite(p[key]) for key in ("voltage_v", "eta_s"))
            )
        return True

    def _receive(self, packet, t, boat=None):
        if not self._valid(packet, t):
            self._rejected += 1
            return []
        k, p = packet.kind, packet.payload
        self._seen[channel(k)] = packet.sequence
        if k in ("fix", "request") and (self._fix is None or packet.sent >= self._fix[0]):
            self._fix = packet.sent, (p["e"], p["n"])
        if k == "request" and self.state == "STATION_KEEPING":
            self._request = packet.sequence
            if self.single_press:
                if boat is None:
                    return []
                self._event(t, f"Pickup request {self._request} received with the displayed meeting point")
                self._send("ack", t, {"text": f"Pickup {self._request} received"})
                try:
                    return self._authorize(t, boat, "Surfaced diver")
                except ValueError as exc:
                    self._send("ack", t, {"text": f"Pickup refused: {exc}"})
                    return []
            self.state = "PICKUP_REQUESTED"
            self._event(t, f"Request {self._request} received; awaiting surface operator approval")
            self._send("ack", t, {"text": f"Request {self._request} received"})
        elif (
            k == "station_keep" and can_request_station(self.state, self._manual_station_recovery) and boat is not None
        ):
            reason = self._station_block(t, boat)
            if reason:
                self._event(t, f"Station keeping refused: {reason}")
                self._send("ack", t, {"text": reason})
                return []
            self.state, self.fault = "SETTING_STATION", None
            self._station = (boat["e"], boat["n"])
            self._station_requested = t
            self._request = self._began = self._arrived = self._loiter_requested = None
            self._progress.clear()
            self._event(t, "Station keep received; requested LOITER at the boat")
            self._send("ack", t, {"text": "Station keep received"})
            return [("hold",), ("loiter",)] if boat["mode"] == "LOITER" else [("loiter",)]
        elif k == "cancel":
            if self.state in ("PICKUP_REQUESTED", "TRANSIT_TO_RENDEZVOUS", "RENDEZVOUS_HOLD", "SETTING_STATION"):
                return self._abort("Diver cancellation received", t, "ABORT")
            self._send("ack", t, {"text": "Cancellation received"})
        elif k == "status":
            self._send("ack", t, {"text": self.state})
        elif k == "ack":
            self._ack = p["text"]
            self._latency = t - packet.sent
        elif k == "telemetry":
            self._telemetry = dict(p)
            self._latency = t - packet.sent
        return []

    def _abort(self, reason, t, state, *, manual_station=False):
        if self.state in TERMINAL:
            return []
        self.state, self.fault = state, reason
        self._manual_station_recovery = manual_station
        self._event(t, reason)
        self._send("ack", t, {"text": f"{state}: {reason}"})
        return [("hold",)]

    def failed(self, reason: str, t: float) -> list[tuple]:
        if self.state in TERMINAL:
            self._event(t, str(reason))
            return []
        return self._abort(str(reason), t, "FAULT")

    def _fix_age(self, t):
        return None if self._fix is None else t - self._fix[0]

    def _boat_error(self, boat):
        if not all(finite(boat.get(k)) for k in ("e", "n", "age_s", "heartbeat_age_s")):
            return "Missing boat position or heartbeat"
        if min(boat["age_s"], boat["heartbeat_age_s"]) < 0 or boat["age_s"] > 2 or boat["heartbeat_age_s"] > 3:
            return "Stale boat position or heartbeat"
        if (boat.get("plant") or {}).get("motor_cutoff"):
            return "Simulated motor cutoff is latched"
        if not boat.get("armed"):
            return "Firmware reports disarmed"
        return None

    def _unsafe(self, t, boat, *, station=False):
        error = self._boat_error(boat)
        if error:
            return error
        age = self._fix_age(t)
        if age is None or age > self.c["freshness_s"]:
            return "Diver fix stale or unavailable"
        start = boat["e"], boat["n"]
        destination = start if station else self.target
        if any(abs(coord) > OPEN_WATER_HALF_WIDTH_M for point in (start, destination) for coord in point):
            return "Route leaves the known synthetic open-water area"
        _, fix = self._fix
        now = fix[0] + self.velocity[0] * age, fix[1] + self.velocity[1] * age
        horizon = self.c["freshness_s"] if station else self.c["timeout_s"]
        if not station and self._began is not None:
            horizon = max(0.0, horizon - (t - self._began))
        # A sweep over the bounded transit conservatively includes every predicted hazard position.
        future = now[0] + self.velocity[0] * horizon, now[1] + self.velocity[1] * horizon
        if (
            segments_distance(start, destination, now, future)
            <= self.c["exclusion_m"] + self.c["uncertainty_m"] + ARRIVAL_M
        ):
            return "Route intersects the buffered diver exclusion region"
        return None

    def _station_block(self, t, boat):
        if self.state in TERMINAL and boat.get("mode") != "HOLD":
            return "Waiting for confirmed HOLD"
        if self.state not in TERMINAL and boat.get("mode") not in ("GUIDED", "LOITER"):
            return "Waiting for a verified navigation mode"
        return self._unsafe(t, boat, station=True)

    def _eta(self, t):
        if self.state != "TRANSIT_TO_RENDEZVOUS" or len(self._progress) < 2:
            return None
        first_t, first_d, _ = self._progress[0]
        last_t, last_d, _ = self._progress[-1]
        if last_t - first_t < 3 or t - last_t > self.c["freshness_s"]:
            return None
        closing = (first_d - last_d) / (last_t - first_t)
        return last_d / closing if closing > 0.2 else None

    def action(self, action: str, t: float, boat: dict) -> list[tuple]:
        self._clock(t)
        if action == "station_keep" and can_request_station(self.state, self._manual_station_recovery):
            reason = self._station_block(t, boat)
            if reason:
                raise ValueError(reason)
            if t - self._station_sent < max(2.0, 3 * self.c["latency_s"]):
                raise ValueError("Station keep request is in flight")
            self._station_sent = t
            self._send("station_keep", t, {})
            self._event(t, "Handheld requested station keeping at current position")
            self._ack = "Station keep sent"
            return []
        if action == "status":
            self._send("status", t, {})
            return []
        if action == "abort" and self.state not in TERMINAL:
            return self._abort("Operator aborted simulated navigation", t, "ABORT")
        if action == "request" and self.state == "STATION_KEEPING":
            if t - self._request_sent_at < self.c["freshness_s"]:
                raise ValueError("A handheld request is already in flight")
            e, n = self._diver(t)
            payload = {"e": e, "n": n}
            if self.single_press:
                if not self._visible_offer(t):
                    raise ValueError("Waiting for a fresh separated meeting point on the handheld")
                payload.update(
                    offer_t=self._telemetry["t"],
                    target_e=self._telemetry["target_e"],
                    target_n=self._telemetry["target_n"],
                )
            self._request_sent_at = t
            seq = self._send("request", t, payload)
            self._event(t, f"Handheld transmitted request {seq}")
            self._ack = f"Request {seq} sent"
            return []
        if action == "cancel" and self.state not in TERMINAL:
            self._send("cancel", t, {})
            self._event(t, "Handheld transmitted cancellation")
            return []
        if self.state == "PICKUP_REQUESTED":
            if action == "reject":
                return self._abort("Operator rejected rendezvous", t, "ABORT")
            if action == "approve" and not self.single_press:
                return self._authorize(t, boat, "Surface operator")
        raise ValueError(f"{action} unavailable in {self.state}")

    def _visible_offer(self, t):
        packet = self._telemetry or {}
        return (packet.get("target_e"), packet.get("target_n")) == self.target and 0 <= t - packet["t"] <= self.c[
            "freshness_s"
        ]

    def _authorize(self, t, boat, actor):
        reason = self._unsafe(t, boat)
        if reason:
            self._event(t, f"Approval refused: {reason}")
            raise ValueError(reason)
        if boat.get("mode") != "LOITER":
            raise ValueError("LOITER telemetry is required for approval")
        self._began = self._progress_at = t
        self._best_distance = math.dist((boat["e"], boat["n"]), self.target)
        error = heading_error_deg(boat, self.target)
        self._departure_turn = error is not None and error >= 45.0
        self._progress.clear()
        self.state = "TRANSIT_TO_RENDEZVOUS"
        self._event(t, f"{actor} approved the separated rendezvous")
        self._send("ack", t, {"text": f"Request {self._request} approved"})
        return [("target", *self.target)]

    def step(self, t: float, boat: dict) -> list[tuple]:
        self._clock(t)
        commands = []
        diver = self._diver(t)
        has_position = all(finite(boat.get(k)) for k in ("e", "n"))
        if t >= self._next_period:
            self._next_period = t + 2.0
            self._send("fix", t, {"e": diver[0], "n": diver[1]})
            if self._boat_error(boat) is None:
                e, n = boat["e"] - diver[0], boat["n"] - diver[1]
                voltage = boat.get("voltage_v")
                offer = {}
                if self.single_press and self.state == "STATION_KEEPING" and not self._unsafe(t, boat):
                    de, dn = self.target[0] - diver[0], self.target[1] - diver[1]
                    offer = {
                        "target_e": self.target[0],
                        "target_n": self.target[1],
                        "meeting_range_m": math.hypot(de, dn),
                        "meeting_bearing_deg": math.degrees(math.atan2(de, dn)) % 360,
                    }
                self._send(
                    "telemetry",
                    t,
                    {
                        **offer,
                        "t": t,
                        "range_m": math.hypot(e, n),
                        "bearing_deg": math.degrees(math.atan2(e, n)) % 360,
                        "voltage_v": voltage if finite(voltage) else None,
                        "eta_s": self._eta(t),
                    },
                )
        while self._queue and self._queue[0][0] <= t:
            _, _, packet = heapq.heappop(self._queue)
            delivered = self._receive(packet, t, boat)
            if delivered:
                # Only the latest accepted radio navigation command in this tick can drive Rover.
                commands = delivered
        if self.state == "SETTING_STATION":
            error = self._unsafe(t, boat, station=True)
            if error:
                return commands + self._abort(error, t, "FAULT")
            if boat.get("mode") == "LOITER" and t > self._station_requested:
                self.state = "STATION_KEEPING"
                self._manual_station_recovery = False
                self._request_sent_at = -math.inf
                self._event(t, "LOITER confirmed at the new station")
                self._send("ack", t, {"text": "Station keeping here"})
            elif t - self._station_requested > self.c["freshness_s"]:
                return commands + self._abort("Station LOITER unconfirmed", t, "FAULT")
            else:
                return commands
        if has_position:
            here = boat["e"], boat["n"]
            separation = math.dist(here, diver)
            self._min_sep = separation if self._min_sep is None else min(self._min_sep, separation)
            if self.state in ("STATION_KEEPING", "PICKUP_REQUESTED"):
                if self._station is None:
                    self._station = here
                self._max_station_error = max(self._max_station_error, math.dist(self._station, here))
        if self.state in ("STATION_KEEPING", "PICKUP_REQUESTED"):
            error = self._boat_error(boat)
            if error:
                return commands + self._abort(error, t, "FAULT")
            if boat.get("mode") != "LOITER":
                return commands + self._abort("Station keeping lost LOITER", t, "FAULT")
            if self._fix is not None:
                age = self._fix_age(t)
                fix = self._fix[1]
                now = (fix[0] + self.velocity[0] * age, fix[1] + self.velocity[1] * age)
                future = (
                    now[0] + self.velocity[0] * self.c["freshness_s"],
                    now[1] + self.velocity[1] * self.c["freshness_s"],
                )
                if point_segment(here, now, future) <= self.c["exclusion_m"] + self.c["uncertainty_m"] + ARRIVAL_M:
                    return commands + self._abort("Drifting exclusion region reaches station", t, "FAULT")
        if self.state not in ("TRANSIT_TO_RENDEZVOUS", "RENDEZVOUS_HOLD"):
            return commands
        if any(command[0] == "target" for command in commands):
            return commands
        error = self._unsafe(t, boat)
        if error:
            return commands + self._abort(error, t, "FAULT")
        if self.state == "RENDEZVOUS_HOLD":
            if boat.get("mode") != "LOITER":
                return commands + self._abort("Firmware left rendezvous LOITER", t, "FAULT")
            return commands
        if t - self._began >= self.c["timeout_s"]:
            return commands + self._abort("Transit timed out", t, "FAULT", manual_station=True)
        distance = math.dist((boat["e"], boat["n"]), self.target)
        if self._loiter_requested is not None:
            if boat.get("mode") == "LOITER" and t > self._loiter_requested and distance <= ARRIVAL_M:
                self.state = "RENDEZVOUS_HOLD"
                self._arrived = t
                self._event(t, "Rendezvous confirmed by boat position and LOITER telemetry")
                self._send("ack", t, {"text": "Rendezvous LOITER confirmed"})
            elif t - self._loiter_requested > self.c["freshness_s"]:
                return commands + self._abort("Rendezvous LOITER unconfirmed", t, "FAULT")
            return commands
        if boat.get("mode") != "GUIDED":
            return commands + self._abort("Firmware left approved GUIDED transit", t, "FAULT")
        if not self._progress:
            self._event(t, "GUIDED transit confirmed by firmware telemetry")
            self._send("ack", t, {"text": f"Request {self._request} executing"})
        error = heading_error_deg(boat, self.target)
        if not self._progress or self._progress[-1][0] < t:
            self._progress.append((t, distance, error))
        while len(self._progress) > 1 and self._progress[0][0] < t - 8:
            self._progress.popleft()
        oldest_t, oldest_range, oldest_error = self._progress[0]
        span = t - oldest_t
        closing = span >= 6.0 and (oldest_range - distance) / span >= MIN_RECOVERY_SPEED_MPS
        if self._departure_turn:
            # Rebase range once a wrong-way departure has actually turned and gained ground.
            if distance <= self._best_distance - 3.0 or (closing and error is not None and error <= 35.0):
                self._departure_turn = False
                self._best_distance, self._progress_at = distance, t
                self._event(t, "Departure turn complete; tracking progress toward rendezvous")
            elif t - self._progress_at >= NO_PROGRESS_S:
                turning = span >= 6.0 and error is not None and oldest_error is not None and oldest_error - error >= 4.0
                if turning and t - self._began < DEPARTURE_LIMIT_S and distance <= self._best_distance + DEPARTURE_RETREAT_M:
                    return commands
                if distance > ARRIVAL_M:
                    return commands + self._abort("No sustained progress during departure turn", t, "FAULT", manual_station=True)
        if distance <= ARRIVAL_M:
            self._loiter_requested = t
            self._event(t, "Arrival radius reached; requested LOITER")
            commands.append(("loiter",))
        elif distance <= self._best_distance - 3.0:
            self._best_distance, self._progress_at = distance, t
        elif t - self._progress_at >= NO_PROGRESS_S:
            # A turn can temporarily lose ground. Give a boat already closing on its
            # best range time to regain it, with a deadline anchored to that same best.
            recovering = closing and distance - self._best_distance <= 15.0
            if not recovering or t - self._progress_at >= NO_PROGRESS_S + RECOVERY_GRACE_S:
                return commands + self._abort("No sustained progress toward rendezvous", t, "FAULT", manual_station=True)
        return commands

    def snapshot(self, t: float, boat: dict) -> dict:
        diver = self._diver(t)
        sep = math.dist((boat["e"], boat["n"]), diver) if all(finite(boat.get(k)) for k in ("e", "n")) else None
        age = None if self._telemetry is None else max(0.0, t - self._telemetry["t"])
        actions = ["status"]
        if self.state not in TERMINAL:
            actions.extend(["abort", "cancel"])
        if (
            self.state == "STATION_KEEPING"
            and t - self._request_sent_at >= self.c["freshness_s"]
            and (not self.single_press or self._visible_offer(t))
        ):
            actions.append("request")
        station_block = None
        if can_request_station(self.state, self._manual_station_recovery):
            station_block = self._station_block(t, boat)
            if not station_block and t - self._station_sent >= max(2.0, 3 * self.c["latency_s"]):
                actions.append("station_keep")
        block_reason = None
        if self.state == "PICKUP_REQUESTED":
            block_reason = self._unsafe(t, boat)
            actions.append("reject")
            if block_reason is None:
                actions.append("approve")
        return {
            "state": self.state,
            "fault": self.fault,
            "approval_block_reason": block_reason,
            "station_block_reason": station_block,
            "departure_turn": self.state == "TRANSIT_TO_RENDEZVOUS" and self._departure_turn,
            "station": {"e": self._station[0], "n": self._station[1]}
            if self._station and self.state in ("STATION_KEEPING", "SETTING_STATION")
            else None,
            "offer_block_reason": self._unsafe(t, boat)
            if self.single_press and self.state == "STATION_KEEPING"
            else None,
            "diver": {"e": diver[0], "n": diver[1]},
            "target": {"e": self.target[0], "n": self.target[1]},
            "radio": {
                "status": "waiting" if age is None else ("stale" if age > self.c["freshness_s"] else "connected"),
                "age_s": age,
                "fix_age_s": self._fix_age(t),
                "ack": self._ack,
                "latency_s": self._latency,
                "loss": self._lost / self._sent if self._sent else None,
                "telemetry": dict(self._telemetry) if self._telemetry else None,
            },
            "separation_m": sep,
            "eta_s": self._eta(t),
            "isolation": None,
            "events": list(self._events),
            "actions": actions,
            "metrics": {
                "minimum_separation_m": self._min_sep,
                "time_to_rendezvous_s": self._arrived - self._began if self._arrived is not None else None,
                "maximum_station_error_m": self._max_station_error,
                "radio_sent": self._sent,
                "radio_lost": self._lost,
                "radio_rejected": self._rejected,
            },
        }
