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

## Departure turns and handheld station keeping

A single steerable stern motor has ±35° travel in the external plant. Select Rover's corresponding vectored-thrust mixer with `MOT_VEC_ANGLEMAX=35` for that arrangement and verify firmware readback on startup. The fixed-rudder and differential models use 0 for this parameter. All these values apply only inside the isolated JSON simulation.

The supervisor treats a departure at least 45° off bearing as an initial turn. After 45 simulated seconds without range progress it permits the turn to continue only with measured improvement of at least 4° across the recent 6–8 s history. The turn allowance ends at 120 s from authorization or 100 m of retreat. Rebase the progress distance once the bow is within 35° and closing at 0.5 m/s or more, or the boat is already 3 m closer. During established transit, a boat regaining earlier ground at 0.5 m/s or more within 15 m of its prior best can get up to 12 extra seconds. These are experimental simulator thresholds. The existing position, link, propulsion and separation checks run during the maneuver.

Station keep here is a radio command available directly during transit, after cancellation, at rendezvous, or after a confirmed navigation-only no-progress/timeout Hold. On receipt, clear the pickup and capture the current position. If the boat already reports Loiter, cycle through confirmed Hold before requesting Loiter so Rover takes a new station. The handheld reports success after Loiter telemetry. A disarm, propulsion cutoff, unsafe station or stale telemetry blocks the request.

## Single-motor propulsion and holding against the drift

Use forward-only propulsion for the steerable motor and fixed-motor/rudder lancha models. In the Rover-4.7.3 source, Loiter halves its speed request at heading errors of 90° or greater. Simply selecting forward Loiter with the former 1.8 m/s limit let a 1 m/s following current satisfy the resulting 0.9 m/s speed request and take away steering thrust. The first current-only trial drifted over 400 m during 420 simulated seconds. The new isolated profile combines a higher Loiter speed ceiling with gentler position corrections and tuned steering. The motor can coast. A displacement downwind/down-current can provide the steady position error needed to hold forward thrust. Heading and station excursion are observables, with no exact-on-point guarantee. See the [pinned Rover Loiter implementation](../../Rover/mode_loiter.cpp).

The owner prefers electrical motor control and a separate steering actuator. For a confirmed two-wire brushed motor, study a forward-only PWM drive on the leads between the motor and its factory power controller. This replaces the factory power output for that operating mode. The design should ensure a single power stage has control of the motor at a time. If the chosen factory controller has a documented electrical throttle command input, it can alternatively retain its own power stage. Both options avoid a throttle servo. Record the actual motor model, lead functions, supply voltage, controller current limits, loss-of-command behavior and independent stop before choosing hardware. The factory twist grip alone cannot govern a motor disconnected from its original driver.

The battery leads and motor leads serve different functions on an electronically controlled trolling motor. Minn Kota lists the candidate Riptide Transom 80 as 24 V, 56 A maximum draw with variable-speed electronics. Page 12 of its manual specifies setting the speed selector to zero before connecting its 24 V battery supply. For this candidate, leave battery-side switching to isolation and use a proper throttle interface for propulsion. The generic Remora 12 V electrical model remains an uncalibrated stand-in. [Motor specifications](https://minnkota.johnsonoutdoors.com/us/shop/saltwater-trolling-motors/riptide-transom/1363831) · [Manufacturer manual](https://johnsonoutdoors.widen.net/content/bk7u89wlvl/pdf/RT-Transom-80-42-Manual-2094927rd.pdf#page=12)

## Manual relocation of the rendezvous

The diver explicitly authorizes each move using the handheld. Keep the original east/north separation offset from the diver at every fresh fix. Require matching pickup ID, ordered commands, fresh radio telemetry and a permitted route. Log separately the radio receipt, firmware execution and arrival. The surface-operator scenario retains its own approval workflow.


## One simulation at a time

Use the single WSL dashboard on port 8765. The shared SITL adapter acquires an exclusive per-user OS file lock before spawning firmware and releases it after the child exits. Dashboard, batch, smoke and live tests all use the adapter. Unit tests can run without firmware. Schedule hosted firmware verification separately from desktop sim sessions.

## Operator display units

Use one unit per quantity throughout the dashboard. Display boat, wind, current and diver speeds in km/h; distances in m; thrust in lbf; and radio loss in percent. Store scenarios and telemetry with their established field units. Apply conversions at the editor and display boundaries, including reload and replay. Keep an unchanged field at its original precision when saving other edits.

## Sharing one simulated boat

Use Gradio's temporary HTTPS sharing service as an optional transport for the existing dashboard. The owner requested the full simulator controls for invited guests. Each guest uses the normal supervisor and the single-simulation interlock. The generated invite stays in the user's private WSL cache outside Git. The offline desktop workflow has no Gradio dependency.
