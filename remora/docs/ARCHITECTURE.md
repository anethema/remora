# Program architecture

## Implemented data flow

```text
Windows browser — localhost HTTP + read-only WebSocket — aiohttp server
                                                           |
                                               single engine worker
                                             /                    \
                              seeded handheld radio             MAVLink 2
                               and mission supervisor          private PTY
                                                                    |
                                                    Rover SITL + native motorboat
                                                          private net namespace
```

| Component | Responsibility |
| --- | --- |
| `scenario.py` and `scenarios/` | Validate versioned inputs, map between WGS84 and a local east/north frame using GeographicLib. |
| `sitl.py` | Create a new PTY, process group and isolated network namespace. Verify vehicle type, version, frame, environment, arming checks and servo functions. Send commands only to this child. |
| `mission.py` | Integrate the virtual diver's linear drift. Queue virtual radio packets with seeded loss, variable latency, sequence tracking, freshness checks and distinct downlink messages. Review and continuously recheck a fixed separated rendezvous. |
| `engine.py` | Own one firmware child, serialize operator actions, send one Guided target on acceptance, verify firmware mode transitions, archive records and clean up on reset or exit. |
| `server.py`, `web/` | Serve an offline situation plot, virtual handheld, operator panel, telemetry histories and read-only replay. Plain browser assets and a loopback HTTP service. |
| `smoke.py`, `batch.py`, `tests/` | Check firmware and motion, repeat the operator sequence across seeds and test policy/failure handling on a virtual clock. |

A fresh run establishes GNSS and confirms the intact pre-arm checks, enters Hold, arms normally, then enters Loiter. The virtual diver can send a request. Only the operator can authorize a separated rendezvous. The controller sends a Guided position target and checks the echoed waypoint. Arrival requires both the measured position and a subsequent Loiter heartbeat. An abort issues Hold, records the reason and latches the supervisor. Reset creates a new run. A failed or disconnected child is closed. The model has no independent propulsion-isolation feedback.

## Timing, space and observability

The firmware's boot milliseconds timestamp position samples. The mission uses elapsed simulation seconds from the initial Loiter fix. Host monotonic time bounds I/O and measures heartbeat and position age. The browser is an observer and has its own rendering cadence. The radio seed reproduces draws for the same event ordering. Firmware scheduling and client action timing can change the trajectory and exact packet sequence.

Initial geography is synthetic, within a square extending 2,500 m from the origin in each axis. Local horizontal positions use metres east and north. GeographicLib converts distances and azimuths to WGS84. Heading and bearing are degrees clockwise from true north for display. MAVLink GPS integers are degrees times 10^7. Diver drift is a ground-relative vector pointing **toward** increasing east/north. The active model uses explicitly calm water. Wind direction conventions must be verified end to end before adding controls.

The radio simulates a surfaced handheld. Delivered downlink values retain their measurement timestamps. The operator view includes simulated diver truth for scoring and viewing. Approval uses the last accepted diver fix, a projected path and a position uncertainty buffer. The synthetic rectangle represents known open water for the scenario. It contains no bathymetry or real charts.

## Fidelity and expansion

- **L0** runs policy tests with software observations. It covers state transitions, seeded radio, malformed/replayed packet rejection, geometry, loss and fault behavior.
- **L1** runs the actual Rover firmware with its registered `motorboat` model and upstream steering/throttle mapping. Rover's estimator, steering and navigation produce every boat trajectory in the dashboard.
- **L2** is planned. The pinned native model uses a 2 kg mass, generic motor and sailboat-derived dynamics. The initial 245 N, 12 V trolling motor and 150–250 kg lancha belong in a distinct, explicitly uncalibrated plant. A candidate external JSON FDM should consume real actuator outputs and return sensor truth at firmware timing. Validate coordinates, units and reset before sweeps.

For M2, specify surge/sway/yaw and water-relative drag, motor immersion and steering limits, wind/current/waves, electrical sag, usable capacity and charge state. Compare AGM and LiFePO4 with measured inputs. For M3, extend the scenario schema with scheduled radio/sensor/battery faults, mapped exclusion polygons and independent isolation feedback. Keep fault outcomes and unavailable estimates visible. For M4, identify calibration measurements and supervised test equipment. Physical deployment is outside these simulation milestones.
