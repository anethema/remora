# Project status · 2026-11-25

The WSL2 Ubuntu checkout is `~/src/remora` on the owner's Windows desktop. The project branch is `remora/main`. The [fork](https://github.com/anethema/remora) preserves ArduPilot upstream history. The baseline is the unmodified Rover-4.7.3 source, commit `d9c5097c3d8333435712ffed86bca8ce00c4bb46`. All 21 recursive submodule status entries matched their recorded commits on the verification host.

## Running today

Open **http://127.0.0.1:8765/** in Windows while the WSL dashboard is running. **Boat, motor & wind** opens the design editor while the simulator is idle. The default scenario uses the uncalibrated lancha and an empty boat. The surfaced diver sees the separated point on the simulated handheld and taps Request pickup once. Cancel pickup enters Hold. Station keep here requests Loiter at the current location. The alternative scenario uses a separate surface operator and the native reference boat.

| Milestone | Evidence | Outstanding work |
| --- | --- | --- |
| M0 · verified locally | Built actual Rover with GCC 15.2.0 and Python 3.12.13 on WSL Ubuntu 26.04. Native motorboat heartbeat, GNSS, normal arming, Guided target echo, measured transit, Loiter, Hold and cleanup. | Repeat on fresh supported Linux environments through project CI. |
| M1 · verified locally | Offline browser assets, loopback API and WebSocket, real firmware tracks, drifting virtual diver, seeded two-way impaired link, human authorization, synthetic route checks, results, JSON/CSV and read-only replay. Three native 1 km runs reached verified Loiter. | Add repeated disconnect/restart and scheduled safety-fault regressions. |
| M2 · partial, uncalibrated | Actual JSON SITL actuator loop drives an external planar hull. User selects mass, length, motor thrust/current, steering, battery, wind speed/from-direction, bow and side CdA, and current. Three steering arrangements drove test courses. | Current, wind and battery sensitivity sweeps with distributions. Add current-coupled diver drift alongside explicit ground-relative drift. Measure loaded hull, drag, motor curves and turning response. Add gusts, wave/immersion effects, lead-acid rate dependence and low-reserve policy. |
| M3 · partial | Policy and unit tests, real firmware smoke, seeded native batch, run archives, browser smoke and project-specific CI definition. | Scheduled burst/immersion and GPS/compass outages, corruption, changing no-go polygons, restart handling, independent isolation feedback and full matrix reports. |
| M4 · deferred | The docs record candidate hardware and required calibration. | No hardware control, purchases or deployment. |

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

## Next implementation task

Run controlled paired wind/current sweeps for the reference hull and plot along-track speed, lateral error and energy by steering method. Preserve no-progress and time-out outcomes. Obtain a head-on silhouette with scale at the intended loaded waterline before treating bow windage as a measured input. Any live dive continues to require separate surface supervision and independent recovery.
