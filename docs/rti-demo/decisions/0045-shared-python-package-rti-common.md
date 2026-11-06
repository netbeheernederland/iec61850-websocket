<!--
SPDX-FileCopyrightText: 2026 Netbeheer Nederland

SPDX-License-Identifier: Apache-2.0
-->

# 45. Code the BFF, SO and FSP share goes in a workspace package, `rti-common`

- Status: proposed
- Date: 2026-11-03

## Context

The BFF, SO and FSP are separate services ([0002](0002-five-separate-services.md)), each its own uv workspace member
with its own image. Code they all need was copied into each: `resolve_log_level` three times (2026-11-03), and
`HealthCheckAccessFilter` three times with different quiet paths. [Spec 0010](../specs/0010-bff-log-level-from-hmi.md)
and [spec 0011](../specs/0011-so-fsp-log-level-from-hmi.md) add a log-level state and two routes to all three
([0044](0044-log-level-while-running.md)), about 200 lines, which would make a third copy of something larger.

Options considered:

1. **A new workspace package, `modules/common`** (chosen): `rti-common`, imported as `rti_common`. The three services
   depend on it as a workspace source.
2. **Three copies**, as before: no new member, but three places to fix, and three sets of tests for the same code.
3. **Put it in `acsi-plugins`**, which the SO and FSP already depend on: no new member for them. The BFF doesn't depend
   on it, though, and would pull in the plugin host for a log-level route. The code has nothing to do with plugins.
4. **A package published to a registry**: versioned on its own, but the demo is built and released as one repository,
   and a release step for a few hundred lines is more than it needs.

## Decision

1. **`examples/rti-demo/modules/common`** is a uv workspace member, `rti-common`, with the import package `rti_common`.
   It depends on FastAPI only, and has its own tests (`pytest -m unit`), which CI runs as for the other members.
2. **What goes in:** code that the BFF, SO and FSP each need in the same form. Now that is `rti_common.log_level`:
   `resolve_log_level`, the start level, the state and the `/api/log-level` routes. Code that differs per service
   stays in the service: `HealthCheckAccessFilter`, whose quiet paths differ, stays in each.
3. **What stays out:** the plugin host and the plugin contract (in `acsi-plugins`), and anything only one service uses.
   The HMI is JavaScript and shares nothing with it.
4. **The routes are offered two ways**, since the services build their API differently: `log_level_router()` returns
   an `APIRouter` for the BFF's app, and `add_log_level_routes(router)` adds them to an existing router, which the SO
   and FSP use so their `/api/apis` listing (which reads each route's `path`) includes them.
5. **Each Python Dockerfile copies `modules/common`** before `uv sync --frozen`, as it copies its own member, and CI's
   image filters rebuild the BFF, SO and FSP images when it changes.

## Consequences

- One place to fix and test the log-level code. The services' tests check only how each one records a change.
- The next shared piece has a home, and doesn't need a decision of its own unless it needs more than FastAPI.
- One more workspace member: `uv.lock`, the root `pyproject.toml`, three Dockerfiles and `images.yml` name it. A
  service image built without the `COPY` fails at `uv sync`, not at run time.
- A change to `rti-common` rebuilds three images, even when only one service uses the changed part.
- The package is not versioned on its own: the three services always use the copy in the same commit.

## In the code

- `examples/rti-demo/modules/common/` (`pyproject.toml`, `src/rti_common/log_level.py`, `tests/`)
- `pyproject.toml` (workspace members), `examples/rti-demo/modules/{bff,fsp,so}/pyproject.toml` (`rti-common`
  dependency and workspace source)
- `examples/rti-demo/modules/{bff,fsp,so}/docker/Dockerfile` (`COPY examples/rti-demo/modules/common/`)
- `.github/workflows/ci.yml` (the package's tests), `.github/workflows/images.yml` (the so, fsp and bff filters)
