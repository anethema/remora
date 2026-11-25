# AP_FLAKE8_CLEAN
"""One thread owns the child process, MAVLink and simulated mission clock."""

import copy
import csv
import hashlib
import io
import json
import math
import queue
import subprocess
import threading
import uuid
from concurrent.futures import Future
from datetime import datetime, timezone

from .mission import Mission
from .scenario import PROJECT, ROOT, LocalFrame, validate
from .sitl import Sitl


def idle():
    return dict(
        status="IDLE",
        state="IDLE",
        fidelity="L1",
        run_id=None,
        sim_s=0,
        boat=None,
        diver=None,
        target=None,
        radio={},
        isolation=None,
        separation_m=None,
        eta_s=None,
        events=[],
        actions=["start"],
        metrics={},
    )


def revision(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


class Engine:
    def __init__(self, config):
        self.config = validate(config)
        self.lock = threading.RLock()
        self.lifecycle = threading.Lock()
        self.worker = None
        self.stop = threading.Event()
        self.commands = queue.Queue()
        self.state = idle()
        self.history = []
        self.result = None
        self.run_dir = None

    @property
    def fidelity(self):
        return "L2" if self.config["boat_design"]["model"] == "lancha" else "L1"

    def snapshot(self):
        with self.lock:
            return dict(copy.deepcopy(self.state), fidelity=self.fidelity)

    def configure(self, config):
        with self.lock:
            if self.state["status"] != "IDLE":
                raise ValueError("Reset the current run before editing the scenario")
            self.config = validate(config)
            return self.config.copy()

    def start(self):
        with self.lifecycle, self.lock:
            if self.state["status"] != "IDLE":
                raise ValueError("Reset before starting another run")
            spacing = math.hypot(self.config["diver_e_m"], self.config["diver_n_m"])
            if spacing <= self.config["exclusion_m"] + self.config["uncertainty_m"] + 8:
                raise ValueError("Move the initial diver clear of the boat before starting SITL")
            self.stop.clear()
            self.commands = queue.Queue()
            self.history = []
            self.result = None
            ident = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
            self.run_dir = PROJECT / "artifacts" / ident
            self.run_dir.mkdir(parents=True)
            self.state.update(status="STARTING", run_id=ident, actions=["reset"])
            self.worker = threading.Thread(target=self._run, name="remora-sitl")
            self.worker.start()
            return self.snapshot()

    def action(self, name):
        if name == "start":
            return self.start()
        if name == "reset":
            self.finish(reset=True)
            return self.snapshot()
        with self.lock:
            if self.state["status"] != "RUNNING" or self.stop.is_set():
                raise ValueError("A running simulation is required")
            reply = Future()
            self.commands.put((name, reply))
        try:
            reply.result(timeout=30)
        except TimeoutError as exc:
            reply.cancel()
            raise ValueError("Command response timed out; inspect the event log") from exc
        return self.snapshot()

    def finish(self, reset=False):
        with self.lifecycle:
            with self.lock:
                self.stop.set()
                worker = self.worker
            if worker:
                worker.join()
            with self.lock:
                self.worker = None
                if reset:
                    self.state = idle()
                    self.history = []
                    self.result = None
                    self.run_dir = None

    def export(self):
        with self.lock:
            return dict(
                schema_version=1,
                run_id=self.state["run_id"],
                fidelity=self.fidelity,
                scenario=dict(self.config),
                result=copy.deepcopy(self.result),
                events=copy.deepcopy(self.state["events"]),
                samples=list(self.history),
            )

    def csv(self):
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(
            (
                "sim_s",
                "state",
                "boat_e_m",
                "boat_n_m",
                "diver_e_m",
                "diver_n_m",
                "separation_m",
                "heading_deg",
                "speed_mps",
                "voltage_v",
                "current_a",
                "throttle_pct",
                "course_deg",
            )
        )
        for row in self.export()["samples"]:
            boat, diver = row.get("boat") or {}, row.get("diver") or {}
            writer.writerow(
                (
                    row["sim_s"],
                    row["state"],
                    boat.get("e"),
                    boat.get("n"),
                    diver.get("e"),
                    diver.get("n"),
                    row["separation_m"],
                    boat.get("heading_deg"),
                    boat.get("speed_mps"),
                    boat.get("voltage_v"),
                    boat.get("current_a"),
                    boat.get("throttle_pct"),
                    boat.get("course_deg"),
                )
            )
        return out.getvalue()

    def _run(self):
        path = self.run_dir
        terminal_status = "STOPPED"
        try:
            write_json(path / "scenario.json", self.config)
            binary = ROOT / "build/sitl/bin/ardurover"
            write_json(
                path / "manifest.json",
                {
                    "project_revision": revision("rev-parse", "HEAD"),
                    "upstream": "d9c5097c3d8333435712ffed86bca8ce00c4bb46",
                    "tracked_changes": revision("status", "--short", "--untracked-files=no"),
                    "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                    "config_sha256": hashlib.sha256((path / "scenario.json").read_bytes()).hexdigest(),
                    "frame": "JSON" if self.fidelity == "L2" else "motorboat",
                    "fidelity": self.fidelity,
                    "seed": self.config["seed"],
                },
            )
            with Sitl(
                path / "sitl", speedup=self.config["speedup"], cancel=self.stop, boat_design=self.config["boat_design"]
            ) as sim:
                sim.ready()
                if self.stop.is_set():
                    return
                sim.arm()
                sim.mode("LOITER")
                self._drive(sim, path)
        except InterruptedError:
            if not self.stop.is_set():
                terminal_status = "FAULT"
                with self.lock:
                    self.state.update(state="FAULT", fault="Simulator I/O interrupted")
        except Exception as exc:
            terminal_status = "FAULT"
            with self.lock:
                reason = f"{type(exc).__name__}: {exc}"
                self.state.update(fault=reason, state="FAULT", eta_s=None)
                self.state["events"] = [*self.state["events"], dict(t=self.state["sim_s"], message=reason)]
        finally:
            with self.lock:
                self.state.update(status=terminal_status, actions=["reset"])
                self.result = self._result(self.state)
                self.state["result"] = self.result
                while not self.commands.empty():
                    _, reply = self.commands.get_nowait()
                    if not reply.done():
                        reply.set_exception(ValueError("Simulation ended"))
            write_json(path / "run.json", self.export())
            (path / "trajectory.csv").write_text(self.csv())
            write_json(path / "result.json", self.result)

    def _result(self, state):
        name = state["state"]
        outcome = {"FAULT": "failed", "ABORT": "aborted"}.get(name, "incomplete")
        if name == "RENDEZVOUS_HOLD":
            minimum = state["metrics"]["minimum_separation_m"]
            verified = state["boat"]["mode"] == "LOITER" and state["boat"]["armed"]
            within_timeout = state["metrics"]["time_to_rendezvous_s"] <= self.config["timeout_s"]
            cleared = minimum > self.config["exclusion_m"] + self.config["uncertainty_m"]
            outcome = "passed" if verified and within_timeout and cleared else "failed"
        return dict(
            outcome=outcome, state=name, sim_s=state["sim_s"], fault=state.get("fault"), metrics=dict(state["metrics"])
        )

    @staticmethod
    def _execute(sim, frame, commands):
        for command, *args in commands:
            if command == "target":
                sim.mode("GUIDED")
                sim.target(*frame.gps(*args))
            elif command in ("hold", "loiter"):
                sim.mode(command.upper())
            else:
                raise ValueError(f"Unknown simulation command {command}")

    def _drive(self, sim, path):
        first = sim.poll()
        frame = LocalFrame(first.lat, first.lon)
        mission = Mission(self.config)
        start = first.sim_s
        initial_energy = None
        last_record = -1
        event_count = 0
        run_id = self.state["run_id"]
        with (path / "samples.jsonl").open("w", buffering=1) as journal:
            while not self.stop.is_set():
                sample = sim.poll(timeout=0.1)
                t = max(0.0, sample.sim_s - start)
                east, north = frame.en(sample.lat, sample.lon)
                boat = {
                    k: getattr(sample, k)
                    for k in (
                        "speed_mps",
                        "heading_deg",
                        "course_deg",
                        "mode",
                        "armed",
                        "age_s",
                        "heartbeat_age_s",
                        "voltage_v",
                        "current_a",
                        "soc_pct",
                        "throttle_pct",
                    )
                }
                boat.update(e=east, n=north, lat=sample.lat, lon=sample.lon)
                if sim.plant:
                    plant = json.loads((sim.work / "plant.json").read_text())
                    boat["plant"] = plant
                    boat.update({key: plant[key] for key in ("voltage_v", "current_a", "soc_pct")})
                reply, error = None, None
                pending = mission.step(t, boat)
                if not self.commands.empty():
                    action, reply = self.commands.get_nowait()
                    if reply.set_running_or_notify_cancel():
                        try:
                            pending.extend(mission.action(action, t, boat))
                        except ValueError as exc:
                            error = exc
                    else:
                        reply = None
                try:
                    self._execute(sim, frame, pending)
                    public = mission.snapshot(t, boat)
                    state = dict(**public, status="RUNNING", sim_s=t, run_id=run_id, fidelity=self.fidelity, boat=boat)
                    state["actions"] = list(state["actions"]) + ["reset"]
                    if sim.plant:
                        if initial_energy is None:
                            initial_energy = plant["energy_wh"]
                        state["metrics"]["energy_used_wh"] = plant["energy_wh"] - initial_energy
                    if state["state"] in ("RENDEZVOUS_HOLD", "FAULT", "ABORT"):
                        state["result"] = self._result(state)
                    with self.lock:
                        self.state = copy.deepcopy(state)
                        self.result = state.get("result")
                        if t - last_record >= 1 or reply or len(state["events"]) != event_count:
                            record = copy.deepcopy(state)
                            record["events"] = record["events"][event_count:]
                            self.history.append(record)
                            journal.write(json.dumps(record, allow_nan=False) + "\n")
                            last_record, event_count = t, len(state["events"])
                except Exception as exc:
                    if reply and not reply.done():
                        reply.set_exception(ValueError(str(exc)))
                    raise
                if reply:
                    if error:
                        reply.set_exception(error)
                    else:
                        reply.set_result(True)
