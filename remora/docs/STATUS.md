# Project status · 2026-11-26

The WSL2 Ubuntu checkout is `~/src/remora` on the owner's Windows desktop. The project branch is `remora/main`. The [fork](https://github.com/anethema/remora) preserves ArduPilot upstream history. The baseline is the unmodified Rover-4.7.3 source, commit `d9c5097c3d8333435712ffed86bca8ce00c4bb46`. All 21 recursive submodule status entries matched their recorded commits on the verification host.

## Local account transfer · 2026-11-26

The new local developer should start with the [account handoff](../../handoff.md). Windows PowerShell resolved the existing WSL folder and successfully ran doctor through `wsl.exe` against the registered `Ubuntu` distro. At `b43debf548`, the WSL fast suite passed all 49 tests. The saved 80 lbf scenario was present. The dashboard on 8765, share session and Rover firmware were stopped. No firmware run or hardware test was performed for the transfer.

The proposed first increment for the two-month prototype is a local loopback handheld driving the existing simulated mission, followed by radio hardware, fresh GNSS input and failure tests. The Qi-charged, magnetically operated remote is a design proposal. Confirm motor model and intended dive depth before selecting the final drive or enclosure. [Development brief and acceptance checks](../../handoff.md#next-development-increment)

## Previous development checkpoint · 2026-11-25

Start the next engineering session with the [root handoff](../../handoff.md). Simulator and sharing changes end at `45b5d17c7b`. The dry steering plan was added at `55a83e9e48`. On that checkout, `./remora/scripts/doctor.sh` passed, and `./remora/scripts/run-tests.sh -q` reported **49 passed** with Python 3.12.13. No firmware or hardware test was run for this documentation checkpoint.

The WSL dashboard answered on port 8765 and reported IDLE. Its 80 lbf, 20 km/h crosswind, northward current setup matched archived `20261125T231616Z-b5b75ae1/scenario.json` exactly. This run ended in station keeping after 1,729.239 simulated seconds with pickup outcome `incomplete`. An earlier run, `20261125T214844Z-9d308cac`, reached rendezvous, continued holding, then finished with a latched simulated motor cutoff at 52,400.016 simulated seconds. A completed pickup and a successful final run outcome are separate fields. Full results and raw logs stay on WSL.

### Simulation and calibration backlog

1. Run paired calm, wind-only, current-only and combined conditions using the same seeds, hull and pickup timing. Preserve negative controls. Publish the scenario inputs, run IDs, progress, cross-track error, separation and energy outcomes. [Sweep brief](../../handoff.md#parallel-simulation-and-calibration-backlog)
2. Collect the owner's 30 lbf motor identification, mount dimensions and dry steering measurements. Use measured travel and slew rate to improve a motor-specific profile. [Bench worksheet](../hardware/steering-bench.md)
3. Extend environmental and electrical validation, then fault schedules, restart behavior and isolation feedback. The milestone table tracks gaps by subsystem.

## Running today

Open **http://127.0.0.1:8765/** in Windows while the WSL dashboard is running. **Boat, motor & wind** opens the design editor while the simulator is idle. The default scenario uses the uncalibrated lancha and an empty boat. The surfaced diver sees the separated point on the simulated handheld and taps Request pickup once. Cancel pickup enters Hold. Station keep here requests Loiter at the current location directly during pickup or after a cancellation or navigation-only fault. The alternative scenario uses a separate surface operator and the native reference boat.

## Milestones

| Milestone | Evidence | Outstanding work |
| --- | --- | --- |
| M0 · verified | Built real Rover on WSL. Native motorboat heartbeat, GNSS, normal arming, Guided target echo, measured transit, Loiter, Hold and cleanup. A second clean WSL build and an earlier hosted Ubuntu 22.04 job also passed. | Repeat the firmware suite when the integration or source pin changes. |
| M1 · verified locally | Offline browser assets, loopback API and WebSocket, real firmware tracks, drifting virtual diver, seeded two-way impaired link, human authorization, synthetic route checks, results, JSON/CSV and read-only replay. Three native 1 km runs reached verified Loiter. | Add repeated disconnect/restart and scheduled safety-fault regressions. |
| M2 · partial, uncalibrated | Actual JSON SITL actuator loop drives an external planar hull. User selects mass, length, motor thrust/current, steering, battery, wind speed/from-direction, bow and side CdA, and current. Three steering arrangements drove test courses. | Current, wind and battery sensitivity sweeps with distributions. Add current-coupled diver drift alongside explicit ground-relative drift. Measure loaded hull, drag, motor curves and turning response. Add gusts, wave/immersion effects, lead-acid rate dependence and low-reserve policy. |
| M3 · partial | Policy and unit tests, real firmware smoke, seeded native batch, run archives, browser smoke and project-specific CI definition. | Scheduled burst/immersion and GPS/compass outages, corruption, changing no-go polygons, restart handling, independent isolation feedback and full matrix reports. |
| M4 · planning | [Winter steering bench and parts list](../hardware/steering-bench.md) for the existing 30 lbf motor. | Record motor model, mount geometry and dry pivot torque. Select linkage and actuator, then measure shaft angle and slew rate. All physical results are pending. |

## Reproduction and evidence

All commands below run from the fork root. The first checkout was a full-history clone of the release via `git clone --origin upstream --branch Rover-4.7.3 --single-branch https://github.com/ArduPilot/ardupilot.git`, followed by `git switch -c remora/main` and `git submodule update --init --recursive --jobs 8`. Created the GitHub fork under the authenticated owner. `origin` identifies the fork and `upstream` identifies ArduPilot.

| Command executed | Observed result |
| --- | --- |
| `./waf configure --board sitl` and `./waf rover -j12` with the project venv active | Built `build/sitl/bin/ardurover`. Native source build reported 4,256,215 B total flash used. Build log on WSL at `.git/remora-build.log`. |
| `./remora/scripts/doctor.sh` | Checked pin, recursive submodules, binary, imports and private namespace with only loopback. |
| `./remora/scripts/run-tests.sh --smoke --speedup 12` | PASS on source build. 40 m Guided waypoint, residual 3.92 m, maximum excursion 2.16 m in 15 simulated seconds of Loiter. Hold settled to 0% demanded throttle and 0.051 m/s. WSL run `smoke-9c0n7glv`. |
| Earlier validation with official pinned x86-64 binary | PASS before integration. 3.56 m waypoint residual and 2.43 m Loiter excursion. 1,256 parameters enumerated. Separate run `prebuilt-smoke-r7ov3xtb`. |
| `./remora/scripts/run-tests.sh -q` | 31 passed after the one-tap and manual recovery updates. Includes WGS84 conversion, validation, radio ordering/freshness, handover, exclusion checks, no progress, empty-boat confirmation, wind directions, CdA, motor, battery and steering sensitivity. |
| `./remora/scripts/run-batch.sh --suite marine --seeds 1,2,3 --speedup 16` | All three native integrations reached RENDEZVOUS_HOLD. Closest separation 105.41, 105.49, 105.15 m respectively. Confirmed arrivals in 182.50, 182.26, 182.24 sim seconds after approval. Initial diver 1,000 m east, waypoint 900 m east. |
| `./remora/scripts/run-batch.sh --scenario remora/scenarios/lancha_1km.yaml --seeds 7 --speedup 16` | External 200 kg / 55 lbf steerable-motor study reached verified Loiter in 531.50 sim seconds after handheld confirmation. Minimum separation 105.99 m. 12 of 544 virtual packets lost. Run `20261125T205639Z-c5823e03`. |
| Three additional 120 m target tests, virtual diver 260 m east, seed 7 | Steerable motor, fixed propeller + rudder and differential thrust all reached verified Loiter. Earlier steerable and rudder trials produced no-progress faults. Original failures remain in local artifacts. See decisions for model changes. |
| Windows Chrome headless via DevTools against real WSL servers | Drove native request and operator approval. A separate L2 browser test edited thrust, wind 3.6 km/h from north and bow/beam windage, selected differential steering, confirmed via the surfaced handheld and checked verified arrival. Desktop/mobile layouts checked. Zero JS exceptions. Logs/screenshots in `remora/artifacts/browser/`. |

Each launch creates a fresh directory in `remora/artifacts/`. Look in `result.json`, `scenario.json`, `manifest.json`, `samples.jsonl`, `trajectory.csv` and replayable `run.json`. The firmware subdirectory contains its launch arguments, parameter hashes, MAVLink tlog, DataFlash and console output. L2 also records design inputs, shell-free process arguments, a generated simulation parameter file and `plant.csv` with actual actuator channels, thrust and electrical demand. Full local logs are excluded from Git.

## Follow-up verification

- A second clean WSL checkout, new virtual environment and empty build directory passed `JOBS=12 ./remora/scripts/bootstrap.sh`, doctor, 25 then-current tests and the source-built smoke. The 40 m residual was 3.97 m and Loiter excursion was 2.20 m. Build log on the desktop at `.git/remora-clean-install.log`. This used a local Git object reference to reduce network transfer.
- Replayed a real saved L2 run in Windows Chrome. Verified the live controls were disabled, scrubbed to the final passing Loiter metrics and returned to the idle operator view.
- With a 20 km/h headwind on the same 120 m northbound course, bow CdA of 0.20, 0.35 and 0.60 m² consumed 9.96, 10.61 and 11.42 simulated Wh. All three reached Loiter. Inputs and exact data are in the individual run archives. These are model sensitivities, not measured coefficients for the photographed boat.
- The initial GitHub Actions run exposed a host interpreter selection in the DroneCAN generator when bootstrap received an explicit `PYTHON`. Bootstrap now selects its venv interpreter for Waf.
- A user run with 5 km/h easterly wind and 1 m/s northward current stayed in Loiter until handheld confirmation under the original interaction. Once authorized, it reached about 694 m diver separation before the run ended. An immediate-authorization repeat with the same inputs hit the 45 s no-progress limit during the initial turn. Wind-only and current-only runs both reached Loiter. The result depends on starting conditions, vehicle tuning and the selected progress window.
- After the owner changed the interaction, one-tap pickup on the default 1 km lancha scenario reached verified Loiter in 531.26 sim seconds after authorization (106.30 m minimum separation). An actual Windows Chrome run verified a single click, Guided transit and arrival. Human authorization now travels in the pickup packet. A separate surface operator remains selectable in the reference scenario.

- Windows Chrome drove one-tap pickup, canceled during Guided transit, observed Hold, then explicitly requested station keeping. The firmware confirmed Loiter and the handheld received the acknowledgement. Raw results are in `remora/artifacts/browser/station-probe.log`. Run the repeatable headless equivalent with `./remora/scripts/run-tests.sh --recovery -q`.

- A 120 s open-loop full-throttle check on the generic 80 lbf / 200 kg model gave 7.98 km/h in calm air and 7.95 km/h into a 5 km/h wind (bow CdA 0.35 m², no current, flat water). This is an uncalibrated plant result. The available battery model is 12 V. The [Minn Kota Riptide Transom 80](https://minnkota.johnsonoutdoors.com/us/shop/saltwater-trolling-motors/riptide-transom/1363831) is rated 24 V and 56 A, so the electrical model does not represent this particular product.

## Cross-current departure investigation

The 80 lbf steerable lancha runs used identical scenario settings, including a 20 km/h wind from east, 1 m/s current to the north, 200 kg hull and radio seed 7. In WSL archive `20261125T211010Z-e27162e1` pickup began at 76.5 simulated seconds and heading 151°. The bow swung past south. By the time the old best-range timer expired at 203 s the boat was closing again. In `20261125T211228Z-5fe36f2e`, pickup began at 181.3 s and heading 181°. The run reached rendezvous at 725 s. In `20261125T211642Z-43087a07` the bow was still turning from 228° toward the 89° target when the old timer tripped at 191.2 s. With the revised supervisor, replaying the measured inputs from both failed runs kept the boat in Guided transit at their original cutoffs. Subsequent trajectory verification uses independent firmware runs.

Reproduce from the fork root with `./remora/scripts/run-batch.sh --scenario remora/scenarios/lancha_cross_current.yaml --seeds 7 --speedup 16 --request-after 146`. Vary the last value to exercise other departure phases. Each run writes the scenario, actual radio/firmware event times, parameter readbacks, samples, trajectory and result under `remora/artifacts/`.

- `./remora/scripts/run-tests.sh -q` passed 36 tests, including jammed steering, excessive retreat, a slowly improving turn reaching the absolute deadline, regaining ground and explicit recovery.
- `./remora/scripts/run-tests.sh --smoke --speedup 12` verified a 3.81 m waypoint residual, 2.07 m Loiter excursion and 0% Hold demand. `./remora/scripts/run-tests.sh --recovery -q` verified both Cancel–Hold–Loiter and direct Guided–Loiter. Windows Chrome separately exercised the direct handheld button, ground course and target bearing and received the station acknowledgement.
- Hosted Linux CI passed the complete baseline and initial station recovery suite on [the preceding project revision](https://github.com/anethema/remora/actions/runs/45701893947).

The same closed-loop cross-current scenario reached verified Loiter on all four departure timings. All times are simulated.

| Request after (s) | Final state | Time from authorization (s) | Minimum diver separation (m) |
| ---: | --- | ---: | ---: |
| 27 | RENDEZVOUS_HOLD | 534.7 | 107.4 |
| 76 | RENDEZVOUS_HOLD | 527.2 | 107.4 |
| 146 | RENDEZVOUS_HOLD | 521.0 | 107.6 |
| 181 | RENDEZVOUS_HOLD | 521.5 | 106.6 |

A separate 15 lbf negative control with a 2 m/s westward current against an eastbound route faulted for no sustained progress at 74.0 s. The supervisor recorded failure and requested Hold.

## Forward-only station and diver position updates

The single-motor lancha now turns toward its station and offsets drift with forward thrust. The initial selection of forward Loiter alone lost over 400 m in the northward-current test. The tuned profile is confined to the external simulation. Firmware settings are verified by readback. Water speed and wind are never passed directly to the navigation controller.

- `./remora/scripts/run-tests.sh --station -q` passed four real Rover tests, each lasting 420 simulated seconds. During the final 180 s the maximum measured station offsets were 12.3 m for the northward 1 m/s current alone, 6.1 m for the 20 km/h wind from east alone, 11.0 m combined and 10.7 m with both reversed. The combined boat settled near 152° true, the opposite case near 331°. Every sampled thrust was forward or zero. The initial turn can make a considerably larger excursion.
- `./remora/scripts/run-tests.sh --update -q` passed. MAVLink showed three distinct commanded and echoed waypoints, including a manual update from confirmed Loiter. The terminal update in run `20261125T213129Z-5f0ac2c4` put the meeting point at E 130.0, N 62.3 m. Windows Chrome also exercised updates underway and after arrival, maintaining a fixed waypoint between presses, and verified station keeping, replay lockout and the separate-operator scenario. See `remora/artifacts/browser/manual-update-probe.log`.
- `./remora/scripts/run-tests.sh -q` passed 47 tests. `--recovery -q` passed with the forward-drive profile. The reference native `--smoke --speedup 12` passed with a 3.88 m waypoint residual and 2.10 m Loiter excursion. With the new forward profile, the 1 km cross-current scenario reached Loiter for pickup requests at 27 s and 146 s, with minimum diver separations of 106.8 m and 108.2 m.
- The preferred physical interface is electrical throttle control without a throttle servo. For a verified brushed motor, study a forward-only driver on the motor-side leads. The exact make, model, throttle interface and fault behavior remain hardware-planning questions. The simulation's current estimate cannot validate any battery-side controller.

## Desktop dashboard

The current desktop dashboard is **http://127.0.0.1:8765/**. The previous interactive run was archived as `20261125T213150Z-ccadc1f5`. Its replacement reached Loiter with the same user scenario. Verified a single firmware process and a held per-user lock. A second dashboard port has been closed. All 48 unit tests passed, including duplicate startup rejection and lock release after an interrupted launch. The handheld explains when a coordinate update is unavailable. The hosted verification for the preceding change was canceled before simulation to reserve the session for the owner's desktop.

The telemetry picker labels its units. Total motor thrust now displays in lbf, matching the static per-motor rating in setup. On the existing 80 lbf single-motor run `20261125T213747Z-5818f27c`, Windows Chrome showed 33.0 lbf from a roughly 147 N sample. The browser also verified the 80 lbf reference conversion, zero thrust and unavailable thrust, without starting a second simulator.

## Calibration inputs

Obtain a head-on silhouette with scale at the intended loaded waterline before treating bow windage as a measured input. Any live dive continues to require separate surface supervision and independent recovery.

## Consistent dashboard units

All operator speed inputs and readings now use km/h. The setup, plot and replay use lbf for thrust and percent for radio loss. A read-only Windows Chrome test on port 8765 exercised signed current/drift limits, zero, fractional packet loss, JSON save/load roundtrips, map rendering and 80/160 lbf single/twin ratings. The existing scenario was identical before and after the test. Evidence is in `remora/artifacts/browser/dashboard-units-readonly.log`.

## Gradio shared controls

During sharing verification, the temporary Gradio invite rendered the same dashboard in Windows Chrome. Verified three advancing WebSocket samples and HTTP 200 for a handheld status action on the same real run visible on the desktop. An independent HTTPS client received HTTP 403 without an invite and for a write from a different origin. Two browser contexts also passed scenario-edit, startup and reconnect synchronization checks using an in-memory fixture. All 49 unit tests passed. The public control link is private and excluded from this file. Retrieve an active invite privately on WSL with `./remora/scripts/share-sim.sh --url`.

## Hosted verification at the pause

The [last successful hosted run](https://github.com/anethema/remora/actions/runs/45703349561) verified revision `54682da6b9`, including build, doctor, native smoke, rendezvous and recovery. The [subsequent run](https://github.com/anethema/remora/actions/runs/45705484544) was canceled. Current-branch update and station results above are from WSL. The project workflow now requires manual dispatch to run firmware on GitHub. Coordinate this with desktop usage to keep one simulation active.
