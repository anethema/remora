# Source and dependency licenses

Remora project code follows the repository's [GPL-3.0-or-later license](../../COPYING.txt). Keep the source, notices, build instructions and submodule revisions together when distributing a modified build. Retain upstream copyright and third-party notices. ArduPilot has no affiliation with this fork.

The native firmware and its bundled dependencies retain their upstream licenses at the pinned commits. No third-party map tiles, fonts, plotting libraries or remote scripts are delivered by the dashboard.

| Python components in the locked environment | License or metadata |
| --- | --- |
| pymavlink | LGPLv3 as declared by 2.4.49 |
| GeographicLib, PyYAML, pytest, fastcrc, attrs, iniconfig, pluggy, setuptools, wheel, future, DroneCAN | MIT |
| aiohttp | Apache-2.0 AND MIT |
| aiosignal, frozenlist, multidict, propcache, yarl | Apache-2.0 |
| aiohappyeyeballs, typing_extensions | PSF-2.0 |
| lxml, idna | BSD-3-Clause; the lxml wheel also contains native library notices |
| Pygments | BSD-2-Clause |
| pyserial | BSD |
| packaging | Apache-2.0 OR BSD-2-Clause |
| pexpect, ptyprocess | ISC |
| EmPy 3.3.4 | Its `em` module declares LGPL; wheel metadata's License field is an unresolved placeholder. |

Inventory is based on the installed distributions and module metadata. Wheel-specific bundled dependencies can have additional terms. Inspect the exact artifacts and retain their licenses for a release.
