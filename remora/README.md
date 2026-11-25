# Project Remora

A local workbench for studying a diver pickup request and a separated rendezvous using ArduPilot Rover. Its initial scenario places a drifting virtual diver 1,000 m east of the boat and a candidate rendezvous 900 m east. A virtual surface operator reviews the request. ArduPilot steers the simulated boat. The handheld receives position and status over a separate impaired radio model.

**Simulation only.** Live diving requires an attentive surface operator, independent recovery and appropriate emergency equipment. This release has no real vehicle endpoint. Hold and zero requested throttle do not establish propulsion isolation or safe boarding.

## Run on the owner's WSL desktop

Open Ubuntu in Windows Terminal.

```bash
cd ~/src/remora
./remora/scripts/run-sim.sh --scenario remora/scenarios/pickup_1km.yaml
```

Open **http://127.0.0.1:8765/** from Windows. Choose **Start**, wait for **Station keeping**, use **Request pickup** on the virtual handheld, then approve the separated rendezvous in the operator panel. Follow the event log to verified Loiter. If packet loss prevents delivery, request again when the control becomes available. Use Scenario setup or click the setup plot to edit positions. A reset ends the firmware process and archives the run. Ctrl+C closes the server and firmware. Each launch uses fresh EEPROM and parameters.

Use the plot, metrics and telemetry selector to inspect a run. Download JSON for replay or CSV for a spreadsheet. **Open replay** loads saved samples into a separate read-only view. Live pause/resume is unavailable. The speed multiplier applies to the next launch. The handheld updates only when simulated packets arrive.

## Fresh installation

Use x86-64 Linux or WSL2 Ubuntu with unprivileged user/network namespaces, Git, a C++ toolchain, gawk, make, iproute2, util-linux and Python 3.11 or 3.12 with venv. Ubuntu 24.04 provides Python 3.12. The owner's Ubuntu 26.04 installation uses a user-installed Python 3.12.13. Bootstrap downloads the pinned submodules and Python packages and builds Rover. Internet is needed during setup. Simulation and replay run offline.

```bash
git clone --branch remora/main https://github.com/anethema/remora.git ~/src/remora
cd ~/src/remora
git remote add upstream https://github.com/ArduPilot/ardupilot.git
./remora/scripts/bootstrap.sh
./remora/scripts/doctor.sh
./remora/scripts/run-tests.sh
./remora/scripts/run-tests.sh --smoke
./remora/scripts/run-batch.sh --suite marine --seeds 1,2,3 --speedup 16
```

Bootstrap uses the checked-in dependency lock and accepts `PYTHON` and `JOBS`. The marine suite currently runs the M1 separated-rendezvous regression. Each run stores logs, data and summaries under `remora/artifacts/`. Smoke runs include a complete MAVLink parameter dump. Runs have unique directories and private firmware transports, so independent runs can overlap.

### WSL troubleshooting

- In Explorer, the owner's checkout is at `\\wsl.localhost\Ubuntu\home\anethema\src\remora`. Compile inside the Linux filesystem.
- If port 8765 is occupied, run `./remora/scripts/run-sim.sh --port 8766` and use the matching port in Windows. The simulator lives inside its own network namespace and uses a private pseudo-terminal. MAVProxy and port forwarding to the boat are unnecessary.
- If the browser cannot connect, run `curl http://127.0.0.1:8765/api/state` inside Ubuntu and check Windows can forward localhost to WSL. The server binds only to loopback.
- If startup fails, read the run's `result.json` and `sitl/firmware/stdout.log`. Doctor checks namespace support. Normal firmware pre-arm checks must pass before a request can execute.
- For a lower-memory build, set `JOBS=2` for bootstrap. A new terminal can run tests or inspect artifacts while the dashboard remains open.

Read [status and next tasks](docs/STATUS.md), [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md) and [licenses](docs/LICENSES.md). The parent project is [ArduPilot](https://github.com/ArduPilot/ardupilot). Remora is an independent, AI-assisted development project.
