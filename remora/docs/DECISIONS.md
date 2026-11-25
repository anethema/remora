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
