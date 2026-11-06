<!--
SPDX-FileCopyrightText: 2026 Netbeheer Nederland

SPDX-License-Identifier: Apache-2.0
-->

# 47. `images.yml` pushes the images to ghcr.io, all six for amd64 and arm64

- Status: proposed
- Date: 2026-11-06

## Context

`images.yml` built every image but pushed none (`push: false`). The images on
`ghcr.io/netbeheernederland/iec61850-websocket` were built on a developer's machine and pushed by hand, as
multi-platform images for amd64 and arm64. So what `latest` held depended on who pushed last and from which commit,
and the OCI labels set in CI ([0041](0041-oci-image-labels.md)) never reached the registry.

`images.yml` built `rti-so`, `rti-fsp`, `dr-panel` and `dr-leds` for amd64 and arm64, but `rti-bff` and `rti-hmi`
for amd64 only. Pushed like that, the first build on `main` would replace their multi-platform `latest` with an
amd64-only image, which an arm64 machine, such as a Raspberry Pi running the whole demo, can't pull.

Options considered:

1. **Push from CI, every image for amd64 and arm64** (chosen).
2. **Push from CI, `rti-bff` and `rti-hmi` for amd64 only**: faster builds, but it takes away the arm64 images that
   are published today.
3. **Keep pushing by hand**: no CI change, but `latest` stays tied to someone's machine.

## Decision

1. **`push: ${{ github.event_name != 'pull_request' }}`**: a push to `main`, a `v*` tag or a manual run pushes the
   images it builds; a pull request only checks that they build. The workflow already has `packages: write` and logs
   in to ghcr.io except on pull requests.
2. **`rti-bff` and `rti-hmi` build for `linux/amd64,linux/arm64`**, as the other four do, so every published image
   is multi-platform.
3. **The tags are the ones `docker/metadata-action` already makes**: `main` and `latest` on `main`, `<version>` on a
   tag, and `sha-<full commit>` on every push.
4. **Only the images whose files changed are built and pushed** on `main`; a tag or a manual run builds all six.

## Consequences

- `latest` is the last build of `main`, made from the repository with the OCI labels, and each push can be pinned by
  its `sha-<full commit>` tag.
- An image whose files didn't change keeps its previous `latest`, which may still be one pushed by hand until a tag or a
  manual run rebuilds all six.
- The `rti-bff` and `rti-hmi` builds take longer: the arm64 build runs under QEMU.
- A package first pushed by hand needs this repository to have write access to it, once, under *Package settings →
  Manage Actions access* on GitHub. Without it the push fails with `403 Forbidden`.
- Pushing by hand still works, but a later CI build of the same image replaces its `latest`.

## In the code

- `.github/workflows/images.yml` (the `img` step's platforms, and `push` in the `docker/build-push-action` step)
