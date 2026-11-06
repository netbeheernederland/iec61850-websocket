<!--
SPDX-FileCopyrightText: 2026 Netbeheer Nederland

SPDX-License-Identifier: Apache-2.0
-->

# 44. The BFF, SO and FSP change their log level while running, through a shared `/api/log-level`

- Status: proposed
- Date: 2026-11-03

## Context

The BFF, SO and FSP set their log level once, at start, from `--log-level` or `LOG_LEVEL`. Changing it meant
restarting the container, and `LOG_LEVEL` in `docker-compose.yml` is one value for the whole stack. Looking into one
instance's problem meant restarting it with `debug`, losing the state it was in. `resolve_log_level` was copied into
each of the three services. [Spec 0010](../specs/0010-bff-log-level-from-hmi.md) asked to set the BFF's level from the
HMI's Settings page, and [spec 0011](../specs/0011-so-fsp-log-level-from-hmi.md) asked for the same for the SO and
FSPs, from their pages.

## Decision

1. **One route on each service:** `GET /api/log-level` returns the level in use, where it came from (`start` or
   `hmi`), when it was changed, and the start level with its source (`--log-level`, `LOG_LEVEL` or `default`).
   `PUT /api/log-level` with `{"level": ...}` sets it, and `{"level": null}` goes back to the start level. The SO and
   FSP are reached through the BFF's `/api/execute` (decision 0004); the BFF's own route is called directly.
2. **A strict PUT:** it takes the start names in any case (`trace` as `debug`), or a number from 1 to 50. An unknown or
   empty value is a 422 with the names, and nothing changes. At start an unknown value is still quietly `info`, as
   before. A value someone types should be told it's wrong, but a typo in `LOG_LEVEL` shouldn't stop a service.
3. **Which loggers it sets:** the root logger, plus `uvicorn.error`, `uvicorn.access` and `uvicorn.asgi`, which
   `uvicorn.run` sets on their own. The health-check access lines, demoted to `DEBUG` by `HealthCheckAccessFilter`,
   follow it.
4. **`websockets` stays at the start level** when the level is changed, since at debug it logs the `Authorization`
   header: [0046](0046-websockets-logger-pinned-at-start-level.md).
5. **Recorded before it applies:** the BFF records the change as a system event; the SO and FSP write it to their
   actions log (kind `system`) and their container log. Both show on Diagnostics. Because the record is written
   first, a change to `error` is still recorded. The message is "Log level set to DEBUG (was INFO) from the HMI".
6. **Kept in memory only:** a restart goes back to `LOG_LEVEL` / `--log-level`. A raised level is meant for looking
   into a problem, so going back to the configured level is the safer default.
7. **Shared code:** the state and the routes are in the workspace package `rti-common` (`rti_common.log_level`),
   which the BFF, SO and FSP use: [0045](0045-shared-python-package-rti-common.md).
8. **In the HMI:** a `LogLevelSelect` reads and sets the level as soon as a level is chosen, and keeps nothing in the
   browser.
   - On Settings it is the "BFF log level", read from the BFF that the last successful connection check reached.
     The browser's own level is renamed "HMI log level (this browser)".
   - In Monitoring on the ACSI Client and ACSI Server pages it is the selected instance's "Log level". It says that
     it changes the container log and doesn't filter the Activity Log.

## Consequences

- One instance can be put on `debug` without a restart, and without changing the others.
- Anyone who can reach the BFF can change a level, as they can already add or remove connections. Pinning
  `websockets` keeps tokens out of a log that is raised that way (0046).
- Every user and tab sees the same level. The last change wins, and another tab shows it the next time it reads.
- The plugins (`dr_leds`, `dr_panel`) don't have the route. They are services of their own (decision 0029).
- Changing every instance at once isn't possible from the HMI. `LOG_LEVEL` at start still does that.

## In the code

- `modules/common/src/rti_common/log_level.py`, `modules/common/tests/test_log_level.py`
- `modules/bff/src/bff/bff_server.py` (`log_level_router`, the `__main__` block), `modules/bff/tests/test_log_level.py`
- `modules/fsp/src/fsp/bff_endpoint.py`, `modules/so/src/so/bff_endpoint.py` (`add_log_level_routes` in
  `create_bff_router`, the `__main__` block), `modules/{fsp,so}/tests/test_log_level.py`
- `modules/{bff,fsp,so}/docker/Dockerfile`, `.github/workflows/ci.yml`, `.github/workflows/images.yml`
- `modules/hmi/src/components/LogLevelSelect.jsx`, `modules/hmi/src/services/apiService.js` (`getBffLogLevel`,
  `setBffLogLevel`, `getInstanceLogLevel`, `setInstanceLogLevel`), `modules/hmi/src/pages/Settings.jsx`,
  `ACSIServer.jsx`, `ACSIClient.jsx`, `modules/hmi/src/components/ActionLogPanel.jsx` (`toolbar`)
