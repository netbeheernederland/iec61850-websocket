<!--
SPDX-FileCopyrightText: 2026 Netbeheer Nederland

SPDX-License-Identifier: Apache-2.0
-->

# 43. The HMI takes LOG_LEVEL and --log-level, as the FSP, SO and BFF do

- Status: proposed
- Date: 2026-10-29

## Context

The FSP, SO and BFF read `LOG_LEVEL`, and `--log-level` wins over it. The HMI had no log level: its 48 `console.*`
calls always showed, and `LOG_LEVEL` for the stack didn't reach it. Its nginx logged at the image's default level.
[Spec 0008](../specs/0008-hmi-log-level.md) asked for the same setting as the other services, and decided on a URL
parameter and a Settings page choice.

## Decision

1. **`src/utils/log.js` is the HMI's only way to the console**: `log.error`, `log.warn`, `log.info`, `log.debug`, each
   calling the console's method only at or above the level. `critical` shows errors, as `error` does. A test fails on
   any other use of `console` in `src/`: a call, a method passed on (`.catch(console.error)`) or `console` itself as a
   value.
2. **The names and fallback of `resolve_log_level`**: case-insensitive, `trace` as `debug`, a number as it is, and an
   unknown or empty value is `info`. The HMI names a level by what it shows - `trace` is `debug`, `warn` is `warning`,
   `fatal` is `critical`, and a number the name it shows as much as (15 hides debug, so `info`) - with the value as
   given when it differs: `debug ("trace" from LOG_LEVEL)`.
3. **The first source that is set wins**, even with an unknown value, as `--log-level` does over `LOG_LEVEL`:
   `?log=` in the URL (read once at load, so it survives navigation and not a reload without it), the Settings page
   (localStorage `rti-hmi-log-level`, applied without a reload), the container's `LOG_LEVEL` (`window.RTI_CONFIG`),
   the build's `VITE_LOG_LEVEL`, then `info`. The URL is on top, as for decision 0014's BFF address the Settings page
   is: a link turns on debug without changing anything stored.
4. **At build time, `--log-level` wins over `LOG_LEVEL`**, which wins over `VITE_LOG_LEVEL`. Vite's CLI reads
   `--log-level` as its own `--logLevel`, which has no `debug` or `warning`, and then prints none of its errors - not
   even through a `customLogger`, as its CLI logs them with a logger of its own. So `npm run dev`, `build` and
   `preview` run `vite-cli.js`, which takes `--log-level` off the command line, puts it in `LOG_LEVEL` and runs Vite;
   `vite.config.js` puts `LOG_LEVEL` in `VITE_LOG_LEVEL`. `vite --log-level` without it stops in `vite.config.js` with
   a message on stderr.
5. **The container's `LOG_LEVEL` also sets nginx's error log**, the main-level `error_log` in `nginx.conf`, so nginx's
   own messages at start follow it too (`conf.d/` is read inside `http`, which inherits it): `debug` → `info`
   (nginx's `debug` needs a debug build), `info` → `notice`, `warning` → `warn`, `error` and `critical` → `error`.
   Each start begins from the image's `nginx.conf`, kept as `nginx.conf.rti-orig` on the first; unset, that copy is
   put back. The access log stays on.
6. **`docker-compose.yml` passes `LOG_LEVEL=${LOG_LEVEL:-info}` to the BFF, the FSPs, the SO and the HMI**, so one
   variable sets them all. The plugins in the overlays (`dr_leds`, `dr_panel`) don't read `LOG_LEVEL`, and don't get it.
   For the HMI it also sets `NGINX_ENTRYPOINT_QUIET_LOGS=1`: the nginx image's `/docker-entrypoint.sh: ...` lines don't
   follow `LOG_LEVEL`, so they are off; `HMI_NGINX_ENTRYPOINT_QUIET_LOGS=` (empty) turns them back on.
7. The level in use and its source are logged once at start, on `console.info` at every level:
   `HMI log level: debug (from LOG_LEVEL)`. At `warning` or `error` it says why the rest is quiet.

## Consequences

- `LOG_LEVEL=debug docker compose up -d` makes the HMI's debug messages show, and `LOG_LEVEL=error` hides warnings.
- Debug goes to `console.debug`, which Chrome shows only with "Verbose" on.
- The two `console.log` calls are now debug: they no longer show at the default level.
- New HMI code logs through `log`; the test says where otherwise.
- `40-rti-config.sh` takes `RTI_CONFIG_JS` and `RTI_NGINX_CONF` to write elsewhere, for its test.

## In the code

- `examples/rti-demo/modules/hmi/src/utils/log.js`, `src/main.jsx`, `src/pages/Settings.jsx`, every `console.` caller in
  `src/`
- `examples/rti-demo/modules/hmi/vite-cli.js`, `vite.config.js`, `vite.log-level.js`, `package.json` (scripts)
- `examples/rti-demo/modules/hmi/docker/40-rti-config.sh`
- `examples/rti-demo/docker-compose.yml`
- Tests: `src/utils/log.test.js`, `src/noConsole.test.js`, `src/pages/Settings.test.jsx`, `vite.log-level.test.js`,
  `tests/unit/test_hmi_runtime_config.py`
