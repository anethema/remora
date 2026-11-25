"""One isolated, owned ArduRover SITL child and its private MAVLink channel."""
# AP_FLAKE8_CLEAN
import hashlib
import json
import math
import os
import select
import signal
import subprocess
import time
import tty
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Event

from pymavlink.dialects.v20 import ardupilotmega as mav

ROOT = Path(__file__).resolve().parents[3]
PIN = "d9c5097c3d8333435712ffed86bca8ce00c4bb46"
MODES = {0: "MANUAL", 4: "HOLD", 5: "LOITER", 15: "GUIDED", 16: "INITIALISING"}


@dataclass
class Telemetry:
    sim_s: float = 0
    lat: float | None = None
    lon: float | None = None
    heading_deg: float | None = None
    speed_mps: float | None = None
    mode: str = "STARTING"
    armed: bool = False
    throttle_pct: float | None = None
    voltage_v: float | None = None
    current_a: float | None = None
    soc_pct: float | None = None
    age_s: float = math.inf
    heartbeat_age_s: float = math.inf


class Sitl:
    """Single-threaded. Every command goes to a newly allocated kernel PTY."""

    def __init__(self, run_dir: Path, speedup: int = 8, cancel: Event | None = None):
        if not 1 <= speedup <= 32:
            raise ValueError("speedup must be between 1 and 32")
        self.run_dir = Path(run_dir).resolve()
        self.speedup = speedup
        self.cancel = cancel
        self.work = self.run_dir / "firmware"
        self.process = self.file = self.log = self.raw = None
        self.data = Telemetry()
        self.heartbeat_at = self.position_at = -math.inf
        self.last_gcs = -math.inf
        self.last = {}
        self.params = {}
        self.param_indices = set()
        self.param_count = 0
        self.status = []
        self.identity = {}

    def __enter__(self):
        binary = ROOT / "build/sitl/bin/ardurover"
        if not binary.is_file():
            raise FileNotFoundError(f"Build Rover with ./remora/scripts/bootstrap.sh first: {binary}")
        # A per-run directory keeps DataFlash, EEPROM and parameters private.
        self.work.mkdir(parents=True, exist_ok=False)
        try:
            self.log = (self.work / "stdout.log").open("wb")
            self.raw = (self.work / "telemetry.tlog").open("wb")
            master, slave = os.openpty()
            try:
                tty.setraw(slave)
                self.file = os.fdopen(master, "r+b", buffering=0)
                self.mav = mav.MAVLink(self.file, srcSystem=255, srcComponent=190)
                self.mav.robust_parsing = True
                self.mav.set_send_callback(self._log_packet)
                native = ROOT / "Tools/autotest/default_params"
                defaults = [native / "rover.parm", native / "motorboat.parm", ROOT / "remora/configs/calm.parm"]
                # Each namespace has only loopback. The firmware RC socket also stays inside it.
                args = ["setpriv", "--pdeathsig", "KILL", "unshare", "--user", "--map-root-user", "--net", "sh", "-ec",
                        'ip link set lo up; exec "$@"', "remora-sitl", str(binary),
                        "--model", "motorboat", "--home", "20.0,-110.0,0,0", "--wipe",
                        "--speedup", str(self.speedup), "--serial0", f"uart:{os.ttyname(slave)}:115200",
                        "--defaults", ",".join(map(str, defaults))]
                for port in (1, 2, 5, 6, 7, 8):
                    args.extend([f"--serial{port}", "none"])
                self.identity = {
                    "argv": args, "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                    "upstream": PIN, "speedup": self.speedup,
                    "profiles": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in defaults},
                }
                self.process = subprocess.Popen(args, cwd=self.work, stdin=subprocess.DEVNULL,
                                                stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
            finally:
                # Keep a slave FD until firmware has opened it, avoiding a transient EIO on the master.
                self.slave = slave
            self._save_identity()
            return self
        except BaseException:
            self.close()
            raise

    def _save_identity(self):
        (self.work / "launch.json").write_text(json.dumps(self.identity, indent=2) + "\n")

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()
        for stream in (self.file, self.raw, self.log):
            if stream:
                stream.close()
        if getattr(self, "slave", None) is not None:
            os.close(self.slave)
            self.slave = None

    def poll(self, timeout: float = 0.1) -> Telemetry:
        if self.cancel is not None and self.cancel.is_set():
            raise InterruptedError("Simulation stopped")
        if self.process.poll() is not None:
            raise RuntimeError(f"SITL exited {self.process.returncode}. See {self.work / 'stdout.log'}")
        if time.monotonic() - self.last_gcs >= 0.8 / self.speedup:
            self.mav.heartbeat_send(mav.MAV_TYPE_GCS, mav.MAV_AUTOPILOT_INVALID, 0, 0, mav.MAV_STATE_ACTIVE)
            self.last_gcs = time.monotonic()
        # Drain what's already queued; wait at most once. Cap work per poll to preserve operator responsiveness.
        for _ in range(32):
            if not select.select([self.file], [], [], timeout)[0]:
                break
            timeout = 0
            chunk = os.read(self.file.fileno(), 65536)
            if not chunk:
                raise RuntimeError("SITL telemetry transport closed")
            for msg in self.mav.parse_buffer(chunk) or ():
                if msg.get_type() != "BAD_DATA" and msg.get_srcSystem() == 1 and msg.get_srcComponent() == 1:
                    self._log_packet(msg)
                    self._ingest(msg)
        now = time.monotonic()
        self.data.age_s = now - self.position_at
        self.data.heartbeat_age_s = now - self.heartbeat_at
        return replace(self.data)

    def _log_packet(self, msg):
        timestamp = (time.time_ns() // 1000).to_bytes(8, "big")
        self.raw.write(timestamp + msg.get_msgbuf())

    def _ingest(self, msg):
        kind = msg.get_type()
        self.last[kind] = msg
        if kind == "HEARTBEAT":
            self.heartbeat_at = time.monotonic()
            self.data.mode = MODES.get(msg.custom_mode, f"MODE_{msg.custom_mode}")
            self.data.armed = bool(msg.base_mode & mav.MAV_MODE_FLAG_SAFETY_ARMED)
        elif kind == "GLOBAL_POSITION_INT":
            self.position_at = time.monotonic()
            self.data.sim_s = msg.time_boot_ms / 1000
            self.data.lat, self.data.lon = msg.lat / 1e7, msg.lon / 1e7
            self.data.speed_mps = math.hypot(msg.vx, msg.vy) / 100
            self.data.heading_deg = msg.hdg / 100 if msg.hdg != 65535 else None
        elif kind == "VFR_HUD":
            self.data.throttle_pct = msg.throttle
        elif kind == "SYS_STATUS":
            self.data.voltage_v = msg.voltage_battery / 1000 if msg.voltage_battery != 65535 else None
            self.data.current_a = msg.current_battery / 100 if msg.current_battery != -1 else None
            self.data.soc_pct = msg.battery_remaining if msg.battery_remaining >= 0 else None
        elif kind == "PARAM_VALUE":
            self.params[msg.param_id] = msg.param_value
            if msg.param_index < msg.param_count:
                self.param_count = msg.param_count
                self.param_indices.add(msg.param_index)
        elif kind == "STATUSTEXT":
            self.status = (self.status + [msg.text])[-12:]

    def _wait(self, predicate, reason, timeout=15, send=None):
        deadline = time.monotonic() + timeout
        retry = 0
        while time.monotonic() < deadline:
            self.poll(0.05)
            if predicate():
                return
            if send and time.monotonic() >= retry:
                send()
                retry = time.monotonic() + 1
        raise TimeoutError(f"{reason}. Last firmware messages: {self.status}")

    def _cmd(self, command, *values):
        self.mav.command_long_send(1, 1, command, 0, *values, *([0] * (7 - len(values))))

    def ready(self):
        self._wait(lambda: "HEARTBEAT" in self.last, "No firmware heartbeat")
        heartbeat = self.last["HEARTBEAT"]
        if heartbeat.type != mav.MAV_TYPE_SURFACE_BOAT or heartbeat.autopilot != mav.MAV_AUTOPILOT_ARDUPILOTMEGA:
            raise RuntimeError("Expected ArduPilot surface boat")
        self._wait(lambda: "AUTOPILOT_VERSION" in self.last, "No firmware version",
                   send=lambda: self._cmd(mav.MAV_CMD_REQUEST_MESSAGE, mav.MAVLINK_MSG_ID_AUTOPILOT_VERSION))
        version = self.last["AUTOPILOT_VERSION"]
        revision = bytes(version.flight_custom_version).decode("ascii").rstrip("\x00")
        self.identity.update(firmware_revision=revision, flight_sw_version=hex(version.flight_sw_version),
                             vehicle_type=heartbeat.type)
        self._save_identity()
        if version.flight_sw_version >> 8 != 0x040703 or not revision:
            raise RuntimeError(f"Unexpected Rover firmware version {self.identity}")
        if not PIN.startswith(revision):
            if subprocess.run(["git", "merge-base", "--is-ancestor", PIN, revision], cwd=ROOT).returncode:
                raise RuntimeError(f"Firmware revision {revision} is outside the pinned Rover lineage")
        self.mav.request_data_stream_send(1, 1, mav.MAV_DATA_STREAM_ALL, 4, 1)

        def navigation_ready():
            gps = self.last.get("GPS_RAW_INT")
            state = self.last.get("SYS_STATUS")
            return (gps and gps.fix_type >= 3 and self.data.lat is not None and self.data.lat != 0 and state and
                    state.onboard_control_sensors_health & mav.MAV_SYS_STATUS_PREARM_CHECK)
        self._wait(navigation_ready, "Waiting for GNSS and all normal pre-arm checks", timeout=110)
        expected = {"FRAME_CLASS": 2, "ARMING_SKIPCHK": 0, "ARMING_REQUIRE": 1, "SIM_TIDE_SPEED": 0,
                    "SIM_WIND_SPD": 0, "SIM_WIND_T": 0, "SIM_WAVE_ENABLE": 0, "SERVO1_FUNCTION": 26,
                    "SERVO3_FUNCTION": 70}
        for name, value in expected.items():
            self._wait(lambda: name in self.params, f"Missing parameter {name}",
                       send=lambda: self.mav.param_request_read_send(1, 1, name.encode(), -1))
            if self.params[name] != value:
                raise RuntimeError(f"Unexpected {name}={self.params[name]}, expected {value}")
        self.mode("HOLD")
        self.identity["verified_parameters"] = expected
        self._save_identity()
        return replace(self.data)

    def mode(self, name: str):
        if name not in {"HOLD", "LOITER", "GUIDED"}:
            raise ValueError(f"Unsupported mode {name}")
        number = next(k for k, v in MODES.items() if v == name)
        self._wait(lambda: self.data.mode == name, f"Mode {name} was not confirmed",
                   send=lambda: self.mav.set_mode_send(1, mav.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, number))

    def arm(self):
        self._wait(lambda: self.data.armed, "Firmware did not arm",
                   send=lambda: self._cmd(mav.MAV_CMD_COMPONENT_ARM_DISARM, 1))

    def target(self, lat: float, lon: float):
        if self.data.mode != "GUIDED" or not self.data.armed:
            raise RuntimeError("Target requires confirmed GUIDED and armed telemetry")
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("Invalid WGS84 target")
        self.last.pop("POSITION_TARGET_GLOBAL_INT", None)
        self.mav.set_position_target_global_int_send(
            0, 1, 1, mav.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, 0x0DF8,
            round(lat * 1e7), round(lon * 1e7), 0, 0, 0, 0, 0, 0, 0, 0, 0)

        def echoed_target():
            echo = self.last.get("POSITION_TARGET_GLOBAL_INT")
            return echo and abs(echo.lat_int - round(lat * 1e7)) <= 2 and abs(echo.lon_int - round(lon * 1e7)) <= 2

        self._wait(echoed_target, "Firmware did not echo the requested waypoint", timeout=6,
                   send=lambda: self._cmd(mav.MAV_CMD_REQUEST_MESSAGE, mav.MAVLINK_MSG_ID_POSITION_TARGET_GLOBAL_INT))

    def dump_params(self):
        self.param_indices.clear()
        self.params.clear()
        self.mav.param_request_list_send(1, 1)
        deadline = time.monotonic() + 70
        next_repair = time.monotonic() + 3
        while not self.param_count or len(self.param_indices) != self.param_count:
            self.poll(0.05)
            now = time.monotonic()
            if now > deadline:
                raise TimeoutError(f"Incomplete parameter table: {len(self.param_indices)}/{self.param_count}")
            if now > next_repair:
                if not self.param_count:
                    self.mav.param_request_list_send(1, 1)
                for i in sorted(set(range(self.param_count)) - self.param_indices)[:10]:
                    self.mav.param_request_read_send(1, 1, b"", i)
                next_repair = now + 0.25
        dump = json.dumps(self.params, indent=2, sort_keys=True) + "\n"
        (self.work / "parameters.json").write_text(dump)
        self.identity["parameter_count"] = self.param_count
        self.identity["parameter_sha256"] = hashlib.sha256(dump.encode()).hexdigest()
        self._save_identity()
