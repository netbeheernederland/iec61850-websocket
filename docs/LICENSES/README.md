<!--
SPDX-FileCopyrightText: 2026 Netbeheer Nederland

SPDX-License-Identifier: Apache-2.0
-->

# Third-party licenses

Full texts of the licenses of the third-party software this project depends on, as SPDX publishes them. Which package
uses which license is listed in [../THIRD_PARTY_LICENSES.txt](../THIRD_PARTY_LICENSES.txt).

| Text | Used by |
|---|---|
| [MIT.txt](MIT.txt) | most Python packages, every package in the HMI's bundle, Font Awesome's code |
| [BSD-3-Clause.txt](BSD-3-Clause.txt) | Python packages (websockets, uvicorn, Flask, starlette, ...), cryptography as one option |
| [Apache-2.0.txt](Apache-2.0.txt) | Python packages (requests, aiohttp, yarl, docker, ...), cryptography and packaging as one option |
| [PSF-2.0.txt](PSF-2.0.txt) | typing-extensions, aiohappyeyeballs, pywin32 (Windows only) |
| [MPL-2.0.txt](MPL-2.0.txt) | certifi; lightningcss (an HMI build tool) |
| [LGPL-2.1-or-later.txt](LGPL-2.1-or-later.txt) | gpiod, in the dr_panel plugin only |
| [BSD-2-Clause.txt](BSD-2-Clause.txt) | packaging as one option; pygments and two HMI build tools |
| [CC-BY-4.0.txt](CC-BY-4.0.txt) | Font Awesome Free's icons, loaded by the HMI |
| [OFL-1.1.txt](OFL-1.1.txt) | Font Awesome Free's fonts, loaded by the HMI |
| [ISC.txt](ISC.txt), [MIT-0.txt](MIT-0.txt), [BlueOak-1.0.0.txt](BlueOak-1.0.0.txt), [CC0-1.0.txt](CC0-1.0.txt) | HMI build and test tools only |

The project's own license is Apache-2.0: [LICENSE](../../LICENSE) in the repository root. The root
[LICENSES/](../../LICENSES) folder holds the texts of the licenses declared by files in this repository (Apache-2.0,
and CC-BY-4.0 for the Code of Conduct), as the [REUSE](https://reuse.software/) specification requires there.
