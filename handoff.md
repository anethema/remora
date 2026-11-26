# Remora development handoff

**Account transfer · 2026-11-26.** Work in the existing checkout on the owner's Windows PC. All source, decisions and restart instructions are in this repository. The owner's local run archives are still on that PC. Remora's dashboard, share tunnel and Rover firmware were stopped at the owner's request. The transfer check ran without starting them.

The owner dives with their father and wants an offline handheld for a small fiberglass lancha on Mexico's Pacific coast. In the simulation a surfaced diver can request a separated rendezvous, update it while drifting, cancel, or request station keeping. The owner works with electronics, radio, wiring and 3D printing, has a roughly 30 lbf trolling motor, and can do dry bench work this winter. The two-month prototype goal is a real handheld controlling a **simulated** boat over a local radio, plus measured steering on the disconnected motor. The final hull, motor, electronics and pressure rating are open.

**First message to paste into the new local Codex account**

> Open my existing Remora checkout, read `handoff.md` and the Remora section of `AGENTS.md`, and verify the branch, doctor and fast tests. Start the first unimplemented handheld-to-simulator task with a loopback device. Run at most one simulation at a time. Leave sharing off unless I request it, and update STATUS with what you actually ran. Use my Windows PC and its existing WSL checkout.

## Where the work lives

| Item | Resume point |
| --- | --- |
| Fork and default branch | `anethema/remora`, `remora/main`. Keep project files in the owner's Windows desktop WSL2 Ubuntu checkout at `/home/anethema/src/remora`. |
| Reviewed revisions | Simulator and sharing through `45b5d17c7b`. Steering bench plan through `55a83e9e484757d4f39cc3f99b122d37949e47a2`. Subsequent handoff edits are documentation. |
| Firmware baseline | Upstream tag `Rover-4.7.3`, commit `d9c5097c3d8333435712ffed86bca8ce00c4bb46`. All 21 recursive submodules matched their pins. The fork has no changes to Rover, libraries, Tools or modules at this checkpoint. |
| Project records | [Status and test evidence](remora/docs/STATUS.md) · [Architecture](remora/docs/ARCHITECTURE.md) · [Decisions and tuning](remora/docs/DECISIONS.md) · [Licenses](remora/docs/LICENSES.md) · [Fork contribution guidance](AGENTS.md#project-remora-fork) |

## Working from Windows

Use a Windows editor or Explorer to open `\\wsl.localhost\Ubuntu\home\anethema\src\remora`. This is the same checkout as `/home/anethema/src/remora` in the WSL distro named `Ubuntu`. The folder was verified from Windows PowerShell. Open a local project session there under your own account. You can also open an Ubuntu tab in Windows Terminal and work directly in that folder. The owner can use separate local terminals for the simulator and development work. This workflow needs no SSH tunnel or credentials from the previous Codex account.

| Task | Where it runs today |
| --- | --- |
| Edit source/docs, use GitHub, view the dashboard or replay, prototype handheld firmware and use a serial console for USB hardware | Windows works for these. Open the same source folder. The browser connects to the local dashboard when the backend is running. A future Windows bench gateway can own the device's COM port. |
| Bootstrap/build the pinned Rover, run the project's test scripts and launch the full closed-loop simulation | WSL2 Ubuntu on this PC, or a compatible Linux host. The checked-in runner uses a Linux network namespace, a pseudo-terminal, POSIX process groups and an exclusive `flock`. The optional share helper also uses `flock`. Installing Windows Python or Git Bash alone does not supply these facilities. [SITL runner](remora/src/remora/sitl.py) · [Share helper](remora/src/remora/share.py) |
| Port the whole runner to native Windows | Separate engineering work. Replace transport, process-tree cleanup, locking, build/bootstrap and network isolation, then verify loopback-only access, clean reset and the real firmware regressions. Windows-side handheld development can proceed independently. |

From **PowerShell**, these commands run the existing WSL tools in the correct working directory. Both were exercised from Windows PowerShell during transfer.

```powershell
wsl.exe -d Ubuntu -u anethema --cd /home/anethema/src/remora --exec ./remora/scripts/doctor.sh
wsl.exe -d Ubuntu -u anethema --cd /home/anethema/src/remora --exec ./remora/scripts/run-tests.sh -q
```

For an interactive local shell, run `wsl.exe -d Ubuntu -u anethema --cd /home/anethema/src/remora` once. The remaining shell examples in this document assume that checkout. Keep the Linux build and artifacts there. [Microsoft's WSL command reference](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)

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

On 2026-11-26 at `b43debf5488a5a727680c940a6784cd2e10f951a`, doctor passed and **49 fast tests passed** on WSL2 Ubuntu 26.04 with Python 3.12.13. The shutdown check found zero Rover processes, no dashboard listener on port 8765, and no active share session file. Historical firmware tests are listed below. If recovering onto a fresh WSL installation, follow the [fresh installation instructions](remora/README.md#fresh-installation). Bootstrap initializes pinned submodules, installs locked dependencies and builds Rover. Keep the `upstream` remote pointed at the ArduPilot repository and `origin` at the fork. Read local changes before pulling or switching branches.

## Next development increment

**First deliverable — a handheld command round trip through the existing simulation.** No board purchase is required to start. The browser currently sends an action name to the local engine, which serializes it on the only worker allowed to command its SITL child. The mission generates a synthetic diver position and queues impaired packets. A physical radio protocol, USB gateway, device pairing, external fix source and handheld firmware still need implementation.

1. **Make a loopback handheld fixture.** Start with a button and status display in a small local test process that can later speak USB serial. Exercise pickup, status, update, cancel and station keeping. Use synthetic diver positions for this first slice. Keep start/reset, operator approval and run configuration on the desktop. Preserve existing browser behavior and keep device transport out of the Gradio gateway. Trace one press from local submission through radio receipt to firmware-confirmed execution. HTTP success alone is insufficient.
2. **Define the wire contract before adding radios.** Specify packet version, device and session identifiers, request ID, monotonic command sequence, fix age and acknowledgement state. The in-process session currently uses Python object identity. Pairing/authentication and reboot-safe replay protection require a wire design. Test lost acknowledgements, duplicate presses, delayed pickup after cancel, wrong session and restart. One logical request must execute at most once. Recovery must require a fresh request.
3. **Add real position and hardware in a separate increment.** A button calling the existing action endpoint still uses a synthetic fix. Provide an explicit selectable fix source. Keep device timestamp, host arrival and simulation time distinct, begin at 1×, and map a real outdoor walk onto the run's synthetic east/north origin. In external-fix mode, a dropped device must produce stale/unavailable position. Preserve the surfaced requirement, original offset, exclusion checks, active request ID and in-transit timeout. Use a host USB gateway for the handheld only. Rover's private MAVLink transport stays with the simulator.
4. **Collect acceptance evidence.** L0 tests should show retries execute once and stale fixes/reboots cannot revive a mission. Then use one actual SITL child to demonstrate pickup with an echoed waypoint, a distinct echoed target after a manual update, Cancel to Hold, and Station keep here to verified Loiter. Save run IDs, the event sequence and which parts were physical versus simulated. [Mission/radio](remora/src/remora/mission.py) · [Engine/command queue](remora/src/remora/engine.py) · [Update regressions](remora/tests/test_updates.py)

### Eight-week prototype plan

| Window | Target and evidence |
| --- | --- |
| Weeks 1–2 | Complete the loopback round trip. Show sent, received and executing on the handheld side. Introduce two radio development boards when available. |
| Weeks 3–4 | Implement paired-device commands, trace fresh GNSS fixes, and exercise outages, retries and restarts. Test the magnetic controls with gloves and on the charging dock. |
| Weeks 5–6 | Measure the 30 lbf motor's steering travel, load and sweep with propulsion disconnected. Use those measurements in a distinct simulation profile and compare departures against the baseline. |
| Weeks 7–8 | Walk the handheld outdoors, recording fix age, antenna height, packet delivery, acknowledgements and outcomes while one simulated boat operates. A later on-water trial to a marker needs an operator aboard, independent stop/recovery and clear water away from divers. |

### Hardware candidates and unresolved choices

The owner reported owning the roughly 30 lbf motor. Other items below are candidates. No purchase, pressure rating or completed physical prototype is recorded.

- **Sealed handheld.** The owner proposed a fully cast remote with Qi charging and Hall-effect controls. Prototype a captive magnetic slider usable with gloves and an internal low-power Hall switch such as the TI DRV5032. Test one command per actuation, deliberate release, dock command inhibition, and interference from the dock magnet. Put the Qi receiver behind a flat nonmetallic face and test charging through sample wall thicknesses, including misalignment and cell temperature. A Qi receiver that supplies power needs a compatible battery charger. [Hall switch](https://www.ti.com/product/DRV5032) · [Qi charger reference](https://www.ti.com/product/BQ51050B)
- **Potting and depth.** For the proposed first build, encapsulate the proven electronics and give the protected battery a serviceable, pressure-rated compartment with manufacturer-specified clearance. Record the owner's maximum dive depth before final enclosure selection. Compare GNSS acquisition and radio delivery with the actual shell and resin. Pressure-test a dummy assembly first. Surfaced GPS and radio, readable status and charging on deck are the intended use. [Battery integration guidance](https://www.varta-ag.com/fileadmin/varta_storage/downloads/products/power/cellpac-blox/Technical_Handbook_CellPac_BLOX_Rev.2.0.pdf)
- **Autopilot and radio.** Holybro Pixhawk 6C Mini, PM02 V3 and matching external M10 GNSS/compass are boat bench candidates. A pair of programmable LoRa boards such as the LILYGO T-Echo can prototype the handheld and USB gateway. Verify the chosen radio variant, operating location and Mexican equipment approval before field selection. The local prototype has no internet, cellular or Starlink dependency. [ArduPilot board support](https://ardupilot.org/rover/docs/common-holybro-pixhawk6C.html) · [T-Echo](https://lilygo.cc/products/t-echo) · [Mexican equipment registry](https://portal.crt.gob.mx/equipos-homologados)
- **Steering and propulsion.** Begin with the existing transom clamp, fish scale, tiller arm, pushrod, quick-release pin and a dry mounting board. Choose the positional steering actuator and its separate regulated supply after measuring torque and travel. Identify the motor's nameplate, voltage, current and electrical interface before choosing a motor-side throttle driver. The owner wants one steering actuator and electrical forward thrust. Keep propulsion disconnected on the bench. [Measurement sheet](remora/hardware/steering-bench.md)

### Parallel simulation and calibration backlog

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

Prior runs verified native Guided/Loiter/Hold, manual recovery, three echoed rendezvous coordinates, bow-first station keeping and separated 1 km arrivals. The cross-current study also exposed false no-progress faults during the first turn. The supervisor now allows a bounded interval for a turn that is measurably improving. A 15 lbf negative control in a 2 m/s opposing current still faulted. Refer to the [status evidence](remora/docs/STATUS.md) for historical measurements, timing and limitations. The account-transfer check reran doctor and the fast suite. The reported firmware results come from the archived runs.

Run data are **local to WSL** under `remora/artifacts/<run-id>/`. Start with `result.json` (terminal outcome and reason), `scenario.json` (reusable inputs), `manifest.json` (provenance) and `run.json` (browser replay). Inspect `samples.jsonl`, `trajectory.csv` and `sitl/firmware/` for telemetry, parameters and L2 actuator/plant data. A station test may end with an incomplete pickup result even when its station assertions pass.

## Reopen the last experiment

The last editor state was saved and the simulator was shut down. On a later session, reuse an existing dashboard if one is listening. For a new run, use `./remora/scripts/run-sim.sh` for the checked-in 55 lbf calm-water default. To reopen the owner's last 80 lbf setup on this WSL checkout, use the following command **in place of** the default launch. The archived scenario exactly matched the idle editor at handoff.

```bash
./remora/scripts/run-sim.sh --scenario remora/artifacts/20261125T231616Z-b5b75ae1/scenario.json
```

On a fresh clone, reproduce the same inputs from `remora/scenarios/lancha_cross_current.yaml` by setting maximum draw to **100 A** and simulation speed to **10×**. The tracked scenario uses 80 A and 8×. Use **Boat, motor & wind → Apply scenario → Start run**. **Save JSON** preserves editor settings across restarts. For shared controls, see [sharing instructions](remora/README.md#share-the-controls). The temporary invite grants control and is kept outside Git.

## Finishing a local session

Keep changes under `remora/` where practical and preserve upstream commit history, submodule pins, GPL notices and arming checks. Record exact commands, revisions, run IDs, outcomes, limitations and next steps in [STATUS](remora/docs/STATUS.md). Update [DECISIONS](remora/docs/DECISIONS.md) when choosing an interface or tuning policy and [ARCHITECTURE](remora/docs/ARCHITECTURE.md) when data flow changes. Preserve local run archives. Keep generated logs, builds, keys and temporary share invites outside Git.

When finished with a demo, export any desired result, Reset to archive the run, then Ctrl+C in the dashboard terminal. If an invite was explicitly started, `./remora/scripts/share-sim.sh --stop` closes it. The owner prefers a quiet desktop between sessions.
