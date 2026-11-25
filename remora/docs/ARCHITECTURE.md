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
| `mission.py` | Integrate the virtual diver's linear drift. Queue virtual radio packets with seeded loss, variable latency, sequence tracking, freshness checks and distinct downlink messages. Review and recheck the active separated rendezvous; apply explicit radio coordinate updates. |
| `engine.py` | Own one firmware child, serialize operator actions, send a Guided target on accepted pickup or coordinate update, verify firmware mode transitions, archive records and clean up on reset or exit. |
| `server.py`, `web/` | Serve an offline situation plot, virtual handheld, operator panel, telemetry histories and read-only replay. Plain browser assets and a loopback HTTP service. |
| `smoke.py`, `batch.py`, `tests/` | Check firmware and motion, repeat the operator sequence across seeds and test policy/failure handling on a virtual clock. |

A fresh run establishes GNSS and confirms the intact pre-arm checks, enters Hold, arms normally, then enters Loiter. The virtual diver can send a request. In the reference workflow a separate surface operator authorizes the rendezvous. In the empty-boat study, the virtual handheld continuously receives a timestamped meeting point. One pickup press sends that exact target and offer time over the impaired radio. The supervisor revalidates freshness and separation on delivery in both workflows. The controller sends a Guided position target and checks the echoed waypoint. Arrival requires both the measured position and a subsequent Loiter heartbeat. A cancellation issues Hold and records the reason. Station keeping resumes only on a separate explicit command and verified firmware Loiter. It uses the boat’s current area as the new station, clears the canceled transit and checks diver separation again. A protective fault stays latched. Reset creates a new run. A failed or disconnected child is closed. The model has no independent propulsion-isolation feedback.

## Timing, space and observability

The firmware's boot milliseconds timestamp position samples. The mission uses elapsed simulation seconds from the initial Loiter fix. Host monotonic time bounds I/O and measures heartbeat and position age. The browser is an observer and has its own rendering cadence. The radio seed reproduces draws for the same event ordering. Firmware scheduling and client action timing can change the trajectory and exact packet sequence.

Initial geography is synthetic, within a square extending 2,500 m from the origin in each axis. Local horizontal positions use metres east and north. GeographicLib converts distances and azimuths to WGS84. Heading and bearing are degrees clockwise from true north for display. MAVLink GPS integers are degrees times 10^7. Diver drift is a ground-relative vector pointing **toward** increasing east/north. It is entered separately from the boat’s water current. Include expected current in the diver drift inputs when modeling a shared water mass. The native reference uses explicitly calm water. In the lancha model, wind direction is the true bearing the wind blows FROM. Wind and current are converted to NED relative velocities in the plant. Wind, current, diver drift and boat ground speed use km/h throughout setup, maps, telemetry and replay. Radio packet loss uses percent across setup and telemetry. Thrust uses lbf for both motor ratings and the modeled total. Internal velocities and archived ground-speed columns use m/s.

The radio simulates a surfaced handheld. Delivered downlink values retain their measurement timestamps. The operator view includes simulated diver truth for scoring and viewing. Approval uses the last accepted diver fix, a projected path and a position uncertainty buffer. The synthetic rectangle represents known open water for the scenario. It contains no bathymetry or real charts.

## Fidelity and expansion

- **L0** runs policy tests with software observations. It covers state transitions, seeded radio, malformed/replayed packet rejection, geometry, loss and fault behavior.
- **L1** runs the actual Rover firmware with its registered `motorboat` model and upstream steering/throttle mapping. Rover's estimator, steering and navigation produce every boat trajectory in the dashboard.
- **L2** is an uncalibrated planar lancha plant in `plant.py`. `fdm.py` and the actual firmware run together in a private namespace using the pinned [SITL JSON protocol](../../libraries/SITL/examples/JSON/readme.md). The plant accepts the 16-channel frame with magic 18458, advances once per frame at the firmware-reported rate and returns timestamped NED position/velocity, yaw, body rates/specific force and battery readings. Duplicate frames resend the same state; skipped frames end the run. A new run starts fresh. No waypoint or diver position enters the plant.

L2 has surge/sway added-mass approximations, quadratic water drag, yaw damping and a rudimentary directional-stability term. It models rate-limited steering, motor lag and deadband, reduced thrust at advancing speed and a per-motor current curve. A steerable propeller at the stern creates side force and moment. The rudder model includes fixed-propeller slipstream. Differential thrust uses independently commanded motors on either side. Voltage, Ah, Wh, chemistry-specific sag and a latched plant cutoff are illustrative. The dashboard reads plant electrical metrics for L2 and retains raw firmware observations in the tlog. Wind force along each body axis is ½ρ × CdA × signed relative wind speed squared. Directions, head-on area, motor ratings and battery settings are scenario inputs. The force model does not include wave-induced immersion, arbitrary wind yaw moment, temperature or lead-acid rate losses.

For the remaining M2 work, measure hull drag, motor response and relative turning performance. Add wave/immersion disturbances and characterize the useful electrical operating range. Compare AGM and LiFePO4 with measured inputs. For M3, extend the scenario schema with scheduled radio/sensor/battery faults, mapped exclusion polygons and independent isolation feedback. Keep fault outcomes and unavailable estimates visible. For M4, identify calibration measurements and supervised test equipment. Physical deployment is outside these simulation milestones.

The supervisor compares true bow heading to the local bearing of the fixed rendezvous during departure. It measures closing speed from position history. The dashboard also shows course over ground, derived from the north and east velocity components of Rover's GLOBAL_POSITION_INT message. Below 0.15 m/s that course is undefined in the display. Ground speed is displayed in km/h. The thrust plot converts total modeled propeller force from newtons to lbf using 4.4482216152605 N/lbf, matching the input unit for per-motor static thrust. Saved samples retain newtons. MAVLink, JSON and CSV retain SI velocity.


## Station keeping and handheld coordinate updates

For a single-motor lancha the plant accepts forward demand and simulates coast at neutral or reverse demand. Steering still deflects to either side. Rover Loiter uses a bow-first return to its stopping point, with reverse braking disabled. GPS position error and onboard heading drive the correction. The environmental forces are computed inside the plant. Wind and current may oppose one another, so the equilibrium heading follows their combined effect on this hull. Guided transit resumes its separate 1.8 m/s cruise command after Rover echoes each waypoint. Acknowledgement comes from the firmware. The comparison model with twin differential thrust retains independent reversible outputs.

In the handheld scenario **Update rendezvous** sends the fresh surfaced position, fix time, request ID and sequence. Subtract the initial diver position from the scenario meeting point to get the original east/north offset; add that offset to the new fix. The supervisor rechecks the route and diver exclusion region before replacing the waypoint. Each accepted point stays fixed until another press. Movement of the target cannot count toward the boat's progress. Retargeting an active transit keeps its timeout. Updating after confirmed rendezvous Loiter starts a new transit. The handheld reports what the radio has acknowledged.
