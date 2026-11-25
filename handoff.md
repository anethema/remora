# Remora development handoff

**Paused 2026-11-25.** Remora runs real ArduPilot Rover firmware in a desktop simulation of a diver and a small powered surface boat. The 1 km pickup scenario works end to end. The largest engineering uncertainty is how closely the simulated lancha turns, holds station and consumes energy under load. The next software increment is a repeatable wind/current comparison. The owner can collect steering measurements indoors in parallel.

## Where the work lives

| Item | Resume point |
| --- | --- |
| Fork and default branch | `anethema/remora`, `remora/main`. Keep project files in the owner's Windows desktop WSL2 Ubuntu checkout at `/home/anethema/src/remora`. |
| Reviewed revisions | Simulator and sharing through `45b5d17c7b`. Steering bench plan through `55a83e9e484757d4f39cc3f99b122d37949e47a2`. Subsequent handoff edits are documentation. |
| Firmware baseline | Upstream tag `Rover-4.7.3`, commit `d9c5097c3d8333435712ffed86bca8ce00c4bb46`. All 21 recursive submodules matched their pins. The fork has no changes to Rover, libraries, Tools or modules at this checkpoint. |
| Project records | [Status and test evidence](remora/docs/STATUS.md) · [Architecture](remora/docs/ARCHITECTURE.md) · [Decisions and tuning](remora/docs/DECISIONS.md) · [Licenses](remora/docs/LICENSES.md) · [Fork contribution guidance](AGENTS.md#project-remora-fork) |

### Resume in the existing checkout

Open Ubuntu in Windows Terminal. These checks inspect the tree, verify the build environment and run the fast tests without starting a boat.

```bash
cd ~/src/remora
git status -sb
git log -1 --oneline --decorate
git remote -v
./remora/scripts/doctor.sh
./remora/scripts/run-tests.sh -q
```

On the reviewed checkout doctor passed and **49 tests passed**. If recovering onto a fresh WSL installation, follow the [fresh installation instructions](remora/README.md#fresh-installation). Bootstrap initializes pinned submodules, installs locked dependencies and builds Rover. Keep the `upstream` remote pointed at the ArduPilot repository and `origin` at the fork. Read local changes before pulling or switching branches.

## Next development increment

1. **Reproduce the reference run.** Start with the committed [cross-current scenario](remora/scenarios/lancha_cross_current.yaml). It specifies a 3.7 m, 200 kg boat, 80 lbf steerable motor, 20 km/h wind from east and 3.6 km/h current toward north. Use the delayed pickup command below to control the departure phase. Record the commit, scenario, seed, request time and outcome.
2. **Add paired sensitivity runs.** Use the same reference hull, request time and seeds across calm, wind-only, current-only and combined runs. Start with one steerable motor. Report time to rendezvous, along-track speed, lateral error, minimum diver separation and Wh. Keep failures, timeouts and incomplete runs in the table. Then compare steering arrangements, recording per-motor and total installed thrust so a twin setup does not silently double the comparison rating. Extend [the batch runner](remora/src/remora/batch.py) as needed. The existing `marine` suite exercises the native pickup regression.
3. **Completion evidence.** Commit reproducible scenario inputs or batch arguments and a compact results table with run IDs. Include a deliberately underpowered case. Explain any failure using heading, course, actual actuator effort and range history. Preserve the raw artifacts on WSL. Update [STATUS](remora/docs/STATUS.md) with commands and outcomes, and record new model assumptions in [DECISIONS](remora/docs/DECISIONS.md).
4. **Owner's parallel task.** Identify the existing ~30 lbf motor and measure its dry pivot torque, steering travel and sweep time with propulsion disconnected. The linkage concept is one positional steering actuator with a tiller arm, pushrod and manual release. The sheet specifies photos, measurements and parts to choose after measuring. The simulator currently assumes ±35° and 1 rad/s. Use measurements to calibrate a profile for that motor. Hardware selection, water loads and testing are pending. [Steering bench worksheet](remora/hardware/steering-bench.md)

After the sweep, the main open work is optional current-coupled diver drift, waves and intermittent propeller immersion, motor/battery and hull calibration, scheduled radio and sensor faults, restart handling, mapped exclusion areas and independent simulated isolation feedback. [Milestone backlog](remora/docs/STATUS.md#milestones)

## Where to change the code

| Question | Start here |
| --- | --- |
| Where are model parameters and units defined? | [Scenario validation and geographic conversion](remora/src/remora/scenario.py), [versioned scenarios](remora/scenarios/), [design editor](remora/web/design.js). |
| What moves the boat? | [L2 plant](remora/src/remora/plant.py) and [JSON dynamics adapter](remora/src/remora/fdm.py). Actual firmware actuator outputs drive the hull. The plant returns simulated sensor state. L1 uses the upstream native motorboat. |
| Who sets the waypoint or orders Hold? | [Mission and virtual radio](remora/src/remora/mission.py) validate the request. [Engine](remora/src/remora/engine.py) owns the run and [SITL adapter](remora/src/remora/sitl.py) issues commands and checks MAVLink telemetry. [Parameter profiles](remora/configs/) are simulation-specific. |
| Where do desktop and guest controls meet? | [Local HTTP/WebSocket API](remora/src/remora/server.py), [browser controls](remora/web/app.js), [optional Gradio gateway](remora/src/remora/share.py). Both browsers operate the same engine. |
| Where should a regression go? | [Tests](remora/tests/) for policy, scenarios, concurrency and real firmware regressions. [Project CI](.github/workflows/remora-simulation.yml) builds and runs fast checks on matching pushes and PRs. Firmware integration steps run on manual dispatch. |

### Behavior to preserve

- The default virtual empty-boat scenario uses **one pickup press** to authorize a separated waypoint. The native reference uses a separate surface operator. The handheld **Update rendezvous** command applies the original offset to a fresh surfaced diver fix and rechecks the route. Targets stay fixed between accepted updates.
- **Cancel pickup** requests Hold, which permits drift. **Station keep here** explicitly requests verified Loiter at the boat's current area. Protective faults stay latched. Propulsion isolation and safe boarding require independent evidence. The project has no vehicle control endpoint. Live diving retains an attentive surface operator and independent recovery.
- The single-motor model turns bow-first and uses forward thrust. The autopilot observes motion and heading. Wind and water current act in the plant. Diver drift is presently a separately entered ground-relative vector. For single-motor electrical throttle, the preference is a motor-side drive compatible with the identified motor, with no second throttle servo. The generic 12 V battery and current estimates have no hardware calibration.
- Display speeds in km/h, thrust in lbf, distances in metres and radio loss in percent. Wind direction is **from**, current and drift vectors point **toward**. Internal and archived fields retain their documented units. Keep simulation and read-only replay distinct.

## Reproduce firmware evidence

Only one simulation may run at a time. Check [the desktop dashboard](http://127.0.0.1:8765/) first. If a run is active, finish and archive it before starting a firmware test. Run the commands individually and sequentially. Coordinate hosted firmware tests with the desktop as well.

```bash
./remora/scripts/run-tests.sh --smoke --speedup 12
./remora/scripts/run-tests.sh --recovery -q
./remora/scripts/run-tests.sh --update -q
./remora/scripts/run-tests.sh --station -q
./remora/scripts/run-batch.sh --scenario remora/scenarios/lancha_cross_current.yaml --seeds 7 --speedup 16 --request-after 146
```

Prior runs verified native Guided/Loiter/Hold, manual recovery, three echoed rendezvous coordinates, bow-first station keeping and separated 1 km arrivals. The cross-current study also exposed false no-progress faults during the first turn. The supervisor now allows a bounded interval for a turn that is measurably improving. A 15 lbf negative control in a 2 m/s opposing current still faulted. Refer to the [status evidence](remora/docs/STATUS.md) for historical measurements, timing and limitations. The handoff check reran doctor and the fast suite only.

Run data are **local to WSL** under `remora/artifacts/<run-id>/`. Start with `result.json` (terminal outcome and reason), `scenario.json` (reusable inputs), `manifest.json` (provenance) and `run.json` (browser replay). Inspect `samples.jsonl`, `trajectory.csv` and `sitl/firmware/` for telemetry, parameters and L2 actuator/plant data. A station test may end with an incomplete pickup result even when its station assertions pass.

## Reopen the last experiment

At handoff the local dashboard responded **IDLE**. If it is still listening, reuse it. Otherwise run `./remora/scripts/run-sim.sh` for the checked-in 55 lbf calm-water default. To reopen the owner's last 80 lbf setup on this WSL checkout, use the following command **in place of** the default launch. The archived scenario exactly matched the idle editor at handoff.

```bash
./remora/scripts/run-sim.sh --scenario remora/artifacts/20261125T231616Z-b5b75ae1/scenario.json
```

On a fresh clone, reproduce the same inputs from `remora/scenarios/lancha_cross_current.yaml` by setting maximum draw to **100 A** and simulation speed to **10×**. The tracked scenario uses 80 A and 8×. Use **Boat, motor & wind → Apply scenario → Start run**. **Save JSON** preserves editor settings across restarts. For shared controls, see [sharing instructions](remora/README.md#share-the-controls). The temporary invite grants control and is kept outside Git.
