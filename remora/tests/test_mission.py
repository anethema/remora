# AP_FLAKE8_CLEAN
"""Run with PYTHONPATH=remora/src python -m unittest discover -s remora/tests."""

import math
import unittest

from remora.mission import Mission, Packet, segments_distance

BASE = dict(
    schema_version=1,
    name="pickup",
    seed=5,
    speedup=10.0,
    diver_e_m=1000.0,
    diver_n_m=0.0,
    drift_e_mps=0.0,
    drift_n_mps=0.025,
    target_e_m=900.0,
    target_n_m=0.0,
    exclusion_m=45.0,
    uncertainty_m=8.0,
    latency_s=0.0,
    loss=0.0,
    freshness_s=12.0,
    timeout_s=1200.0,
)
BOAT = dict(
    e=0.0,
    n=0.0,
    mode="LOITER",
    armed=True,
    age_s=0.0,
    heartbeat_age_s=0.0,
    heading_deg=90.0,
    speed_mps=0.0,
    voltage_v=12.4,
)


def requested(**settings):
    mission = Mission(dict(BASE, **settings))
    mission.step(0.0, BOAT)
    mission.action("request", 0.0, BOAT)
    mission.step(0.0, BOAT)
    return mission


def transit(**settings):
    mission = requested(**settings)
    mission.action("approve", 1.0, BOAT)
    return mission


class MissionTests(unittest.TestCase):
    def test_firmware_confirmed_rendezvous(self):
        m = Mission(BASE)
        with self.assertRaises(ValueError):
            m.action("approve", 0.0, BOAT)
        self.assertEqual(m.action("request", 0.0, BOAT), [])
        self.assertEqual(m.state, "STATION_KEEPING")
        self.assertEqual(m.step(0.0, BOAT), [])
        self.assertEqual(m.state, "PICKUP_REQUESTED")
        self.assertEqual(m.action("approve", 1.0, BOAT), [("target", 900.0, 0.0)])
        guided = dict(BOAT, mode="GUIDED")
        m.step(2.0, guided)
        self.assertEqual(m.step(7.0, dict(guided, e=50.0)), [])
        self.assertGreater(m.snapshot(7.0, guided)["eta_s"], 0)
        self.assertEqual(m.step(100.0, dict(guided, e=895.0)), [("loiter",)])
        self.assertEqual(m.step(101.0, dict(guided, e=897.0)), [])
        self.assertEqual(m.state, "TRANSIT_TO_RENDEZVOUS")
        m.step(102.0, dict(BOAT, e=899.0))
        result = m.snapshot(102.0, BOAT)
        self.assertEqual(result["state"], "RENDEZVOUS_HOLD")
        self.assertIsNone(result["isolation"])
        self.assertGreater(result["metrics"]["minimum_separation_m"], BASE["exclusion_m"])
        self.assertEqual(result["metrics"]["time_to_rendezvous_s"], 101.0)

    def test_delayed_and_lost_both_directions(self):
        m = Mission(dict(BASE, latency_s=2.0))
        m.action("request", 0.0, BOAT)
        m.step(0.0, BOAT)
        self.assertIsNone(m.snapshot(0.0, BOAT)["radio"]["telemetry"])
        self.assertEqual(m.state, "STATION_KEEPING")
        m.step(3.0, BOAT)
        self.assertEqual(m.state, "PICKUP_REQUESTED")
        radio = m.snapshot(3.0, BOAT)["radio"]
        self.assertIn("sent", radio["ack"])
        self.assertEqual(radio["telemetry"]["range_m"], 1000)
        self.assertEqual(radio["telemetry"]["bearing_deg"], 270)
        m.step(6.0, BOAT)
        self.assertIn("received", m.snapshot(6.0, BOAT)["radio"]["ack"])
        lost = Mission(dict(BASE, loss=1.0))
        lost.action("request", 0.0, BOAT)
        for t in range(20):
            self.assertEqual(lost.step(t, BOAT), [])
        r = lost.snapshot(19.0, BOAT)["radio"]
        self.assertEqual(r["loss"], 1.0)
        self.assertIsNone(r["telemetry"])
        self.assertIn("request", lost.snapshot(19.0, BOAT)["actions"])
        self.assertEqual(lost.state, "STATION_KEEPING")

    def test_replay_stale_future_malformed_foreign_requests_rejected(self):
        m = Mission(BASE)
        req = Packet(m._session, "request", 2, 20.0, {"e": 1000.0, "n": 0.0})
        for bad in (
            None,
            Packet(object(), "request", 2, 20.0, req.payload),
            Packet(m._session, "request", 2, 21.0, req.payload),
            Packet(m._session, "request", 2, 1.0, req.payload),
            Packet(m._session, "request", 2, 20.0, {"e": math.nan}),
            Packet(m._session, "evil", 2, 20.0, {}),
        ):
            self.assertEqual(m._receive(bad, 20.0), [])
        self.assertEqual(m.state, "STATION_KEEPING")
        m._receive(req, 20.0)
        m._receive(req, 21.0)
        self.assertEqual(m.state, "PICKUP_REQUESTED")
        self.assertEqual(m.snapshot(21.0, BOAT)["metrics"]["radio_rejected"], 7)

    def test_reordered_cancel_suppresses_older_request(self):
        m = Mission(BASE)
        m._receive(Packet(m._session, "cancel", 2, 1.0, {}), 2.0)
        m._receive(Packet(m._session, "request", 1, 0.0, {"e": 1000.0, "n": 0.0}), 2.0)
        self.assertEqual(m.state, "STATION_KEEPING")

    def test_static_and_projected_hazard_and_unknown_route(self):
        for case, reason in (
            ({"diver_e_m": 500.0, "diver_n_m": 40.0}, "exclusion"),
            ({"diver_e_m": 300.0, "diver_n_m": -80.0, "drift_n_mps": 1.0}, "exclusion"),
            ({"target_e_m": 3000.0}, "known"),
        ):
            with self.subTest(case=case):
                m = requested(**case)
                with self.assertRaisesRegex(ValueError, reason):
                    m.action("approve", 1.0, BOAT)
                self.assertEqual(m.state, "PICKUP_REQUESTED")
        self.assertEqual(segments_distance((0.0, 0.0), (10.0, 0.0), (5.0, -10.0), (5.0, 10.0)), 0.0)
        self.assertEqual(segments_distance((0.0, 0.0), (10.0, 0.0), (5.0, 0.0), (5.0, 0.0)), 0.0)
        self.assertEqual(segments_distance((0.0, 0.0), (10.0, 0.0), (15.0, 0.0), (19.0, 0.0)), 5.0)

    def test_stale_fix_and_firmware_loss_abort(self):
        m = requested()
        with self.assertRaisesRegex(ValueError, "fix stale"):
            m.action("approve", 15.0, BOAT)
        for updates, reason in (
            (dict(age_s=15.0), "Stale"),
            (dict(heartbeat_age_s=15.0), "heartbeat"),
            (dict(armed=False), "disarmed"),
            (dict(mode="MANUAL"), "GUIDED"),
        ):
            with self.subTest(updates=updates):
                m = transit()
                b = dict(BOAT, mode="GUIDED")
                b.update(updates)
                self.assertEqual(m.step(2.0, b), [("hold",)])
                self.assertIn(reason, m.fault)
                self.assertIsNone(m.snapshot(2.0, b)["isolation"])
        m = transit()
        m.c["loss"] = 1.0
        self.assertEqual(m.step(15.0, dict(BOAT, mode="GUIDED")), [("hold",)])
        self.assertIn("fix stale", m.fault)

    def test_no_progress_and_timeout(self):
        guided = dict(BOAT, mode="GUIDED")
        for settings, reason in (({}, "progress"), ({"timeout_s": 8.0}, "timed out")):
            m = transit(**settings)
            m.step(2.0, guided)
            m.step(7.0, guided)
            self.assertIsNone(m.snapshot(7.0, guided)["eta_s"])
            self.assertEqual(m.step(50.0, guided), [("hold",)])
            self.assertIn(reason, m.fault)
            self.assertEqual(m.step(51.0, guided), [])
            with self.assertRaises(ValueError):
                m.action("request", 52.0, guided)

    def test_route_rechecked_during_navigation(self):
        m = transit()
        self.assertEqual(m.step(2.0, dict(BOAT, e=990.0, mode="GUIDED")), [("hold",)])
        self.assertIn("exclusion", m.fault)

    def test_abort_reject_cancel_and_failed_do_not_restart(self):
        for action in ("abort", "reject", "cancel", "failed"):
            with self.subTest(action=action):
                m = requested()
                if action == "failed":
                    commands = m.failed("SITL stopped", 1.0)
                else:
                    commands = m.action(action, 1.0, BOAT)
                    commands += m.step(1.0, BOAT)
                self.assertEqual(commands, [("hold",)])
                self.assertIn(m.state, ("FAULT", "ABORT"))
                self.assertEqual(m.snapshot(1.0, BOAT)["actions"], ["status"])
                self.assertIsNone(m.snapshot(1.0, BOAT)["isolation"])
                with self.assertRaises(ValueError):
                    m.action("approve", 2.0, BOAT)

    def test_seed_is_repeatable(self):
        def run():
            m = Mission(dict(BASE, latency_s=2.0, loss=0.3))
            m.action("request", 0.0, BOAT)
            for t in range(100):
                m.step(t, BOAT)
            return m.snapshot(99.0, BOAT)

        self.assertEqual(run(), run())

    def test_invalid_configuration(self):
        for bad in (
            dict(loss=1.01),
            dict(seed=True),
            dict(target_n_m=math.nan),
            dict(freshness_s=0),
            dict(schema_version=9),
            dict(latency_s=-1),
        ):
            with self.assertRaises(ValueError):
                Mission(dict(BASE, **bad))
