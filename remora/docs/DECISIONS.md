# Decisions

| Date | Decision | Rationale and follow-up |
| --- | --- | --- |
| 2026-11-25 | Use the owner's spelling **Remora**, a GitHub fork at `anethema/remora`, branch `remora/main`, on the existing WSL2 Ubuntu machine. | Keep upstream history, GPL licensing and attribution. Leave upstream `master` and pinned submodules intact. |
| 2026-11-25 | Pin `Rover-4.7.3` at `d9c5097c3d8333435712ffed86bca8ce00c4bb46`. | Registry has native powered `motorboat`. Source and official release binary can be checked independently. |
| 2026-11-25 | Run a single steerable native boat with four explicit calm-water simulator parameters. | Check each parameter through MAVLink. Upstream motorboat physics is sailboat-derived, with zero sail area and generic mass/thrust. The native source uses up to 50 N. Verify material effects by measured A/B runs before interpreting sweeps. |
| 2026-11-25 | Use an owned PTY inside a per-child network namespace. | The upstream Linux SITL serial and RC sockets can bind all interfaces. This isolates them while retaining the upstream binary. The browser has no serial, IP address or physical-device selector. |
| 2026-11-25 | Use a targeted headless dependency set with Python 3.12 and Waf. | The upstream full prerequisite script also manages unrelated packages and cross-compilers. WSL already had a suitable native compiler. |
| 2026-11-25 | Use fixed operator-approved waypoints distinct from the diver. | The radio reports simulated surfaced positions. The supervisor checks a swept separation buffer and route validity, then requires actual firmware evidence at the destination. |
| 2026-11-25 | Use file-based run evidence, local canvas plotting and a read-only telemetry WebSocket. | Supports offline use, headless regression and replay without a cloud service. The seed governs the virtual channel. |
| 2026-11-25 | Preserve separate concepts for Hold, Loiter, drift and propulsion isolation. | Firmware-reported throttle and mode are observable. Isolation feedback and a boarding state have no physical implementation in this release. |

No changes to Rover navigation, SITL physics or the pinned submodules are required for M0/M1.


## Design controls and empty-boat simulation

The default interactive scenario now uses a surfaced-diver handheld for human authorization. The downlink supplies a timestamped candidate. A single pickup uplink carries the displayed coordinates and offer time; no second handheld confirmation is required. The supervisor checks the current request, radio freshness and route before commanding actual SITL. The original two-operator L1 scenario remains independently reproducible. Saved empty-boat scenarios using the previous two-step authorization load into one-tap mode. Archived replay events retain the historical sequence.

Use the isolated JSON backend to change actual plant behavior. The native model has fixed mass/thrust assumptions. The new uncalibrated plant accepts selectable single steerable, fixed-motor/rudder and twin differential arrangements. Keep UI wind direction meteorological FROM and current vectors TO. Keep physics units SI. The UI converts wind and ground speed to km/h and motor static thrust from lbf to N.

The original uncalibrated steerable trial reached a no-progress fault. The 120 m fixed-motor/rudder trial also initially failed; the model had very little steering authority at low speed. Subsequent experiments added directional stability and yaw damping, selected lower simulated turn-rate/angle gains for the heavy hull, and included propeller slipstream for the downstream rudder. Preserve those assumptions for sensitivity analysis. All three arrangements then reached a separated short course, and the default steerable lancha reached the 1 km scenario's separated waypoint.

For an empty, low-sided open skiff, a preliminary sensitivity set for **bow CdA** is 0.20, 0.35 and 0.60 m². The middle value illustrates 1.4 m assumed beam × 0.32 m average exposed height × 0.8 assumed drag coefficient. It is not a measured coefficient for a particular hull. The physical quantity is measured head-on above the loaded waterline. [Drag equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/)


After a deliberate cancellation the user can send **Station keep here** over the same radio. The controller verifies fresh position, an armed plant with available propulsion, clear separation and Hold before requesting Loiter. A later position sample and a Loiter heartbeat confirm the state. The boat may move as it brakes. The aborted rendezvous is discarded; protective faults and simulated cutoff cannot trigger an automatic restart.
