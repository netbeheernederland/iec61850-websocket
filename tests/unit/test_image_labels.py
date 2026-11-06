# SPDX-FileCopyrightText: 2026 Netbeheer Nederland
# SPDX-License-Identifier: Apache-2.0
"""Every image carries the OCI labels, the same in its Dockerfile and in CI.

The Dockerfiles set what doesn't change between builds; images.yml adds
version, revision and created, and repeats title and description, which
would otherwise be the repository's (decision 0041).
"""

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "images.yml"
DOCKERFILES = sorted((ROOT / "examples").glob("*/**/docker/Dockerfile"))
REPO = "https://github.com/netbeheernederland/iec61850-websocket"
STATIC_KEYS = {
    "source",
    "url",
    "documentation",
    "title",
    "description",
    "licenses",
    "vendor",
}
PER_BUILD_KEYS = {"version", "revision", "created"}


def _stages(text: str) -> list[str]:
    return re.split(r"^FROM ", text, flags=re.MULTILINE)[1:]


def _labels(stage: str) -> dict[str, str]:
    joined = stage.replace("\\\n", " ")
    labels = {}
    for line in re.findall(r"^LABEL (.*)$", joined, flags=re.MULTILINE):
        for key, value in re.findall(
            r'org\.opencontainers\.image\.(\S+?)="([^"]*)"', line
        ):
            labels[key] = value
    return labels


def _workflow_images() -> dict[str, dict[str, str]]:
    # The `case` of the img step: one line per image, `k=v ;` pairs.
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["build"][
        "steps"
    ]
    [script] = [s["run"] for s in steps if s.get("id") == "img"]
    images = {}
    for line in re.findall(r"^\s*\w+\)\s+(.*);;$", script, flags=re.MULTILINE):
        fields = dict(re.findall(r'(\w)=("[^"]*"|\S+)', line))
        images[fields["f"]] = {k: v.strip('"') for k, v in fields.items()}
    return images


@pytest.fixture(params=DOCKERFILES, ids=lambda p: str(p.relative_to(ROOT)))
def dockerfile(request) -> Path:
    return request.param


def test_there_are_six_images():
    assert len(DOCKERFILES) == 6


def test_the_final_stage_has_the_static_labels(dockerfile):
    stages = _stages(dockerfile.read_text(encoding="utf-8"))
    # Labels of a build stage don't reach the image.
    assert all(not _labels(stage) for stage in stages[:-1])
    labels = _labels(stages[-1])
    assert set(labels) == STATIC_KEYS
    assert labels["source"] == REPO
    assert labels["url"] == REPO
    folder = dockerfile.parent.parent.relative_to(ROOT).as_posix()
    assert labels["documentation"] == f"{REPO}/blob/main/{folder}/README.md"
    assert (dockerfile.parent.parent / "README.md").is_file()
    assert labels["vendor"] == "Netbeheer Nederland"
    # ghcr.io shows at most 512 characters of a description.
    assert 0 < len(labels["description"]) <= 512


def test_no_dockerfile_sets_the_per_build_labels(dockerfile):
    text = dockerfile.read_text(encoding="utf-8")
    for key in PER_BUILD_KEYS:
        assert f"org.opencontainers.image.{key}" not in text


def test_licenses_is_the_repository_license(dockerfile):
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    labels = _labels(_stages(dockerfile.read_text(encoding="utf-8"))[-1])
    assert labels["licenses"] == pyproject["project"]["license"]


def test_ci_builds_every_image_with_its_dockerfile_title_and_description():
    images = _workflow_images()
    assert set(images) == {p.relative_to(ROOT).as_posix() for p in DOCKERFILES}
    for file, fields in images.items():
        labels = _labels(_stages((ROOT / file).read_text(encoding="utf-8"))[-1])
        assert fields["n"] == f"iec61850-websocket/{labels['title']}"
        assert fields["d"] == labels["description"]


def test_ci_writes_the_labels_and_annotations_on_manifest_and_index():
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["build"][
        "steps"
    ]
    [meta] = [s for s in steps if s.get("id") == "meta"]
    assert (
        meta["env"]["DOCKER_METADATA_ANNOTATIONS_LEVELS"]
        == "${{ steps.img.outputs.annotation_levels }}"
    )
    for field in ("labels", "annotations"):
        assert "image.title=${{ steps.img.outputs.title }}" in meta["with"][field]
        assert (
            "image.description=${{ steps.img.outputs.description }}"
            in meta["with"][field]
        )
    [build] = [s for s in steps if "docker/build-push-action" in s.get("uses", "")]
    assert build["with"]["labels"] == "${{ steps.meta.outputs.labels }}"
    assert build["with"]["annotations"] == "${{ steps.meta.outputs.annotations }}"


def test_ci_pushes_except_on_a_pull_request():
    # Decision 0047: main, a tag or a manual run pushes; a pull request builds.
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["build"][
        "steps"
    ]
    [build] = [s for s in steps if "docker/build-push-action" in s.get("uses", "")]
    assert build["with"]["push"] == "${{ github.event_name != 'pull_request' }}"
    [login] = [s for s in steps if "docker/login-action" in s.get("uses", "")]
    assert login["if"] == "github.event_name != 'pull_request'"


def _img_outputs(tmp_path: Path, image: str) -> dict[str, str]:
    """Runs the img step's script for one matrix image, as the runner would."""
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["build"][
        "steps"
    ]
    [script] = [s["run"] for s in steps if s.get("id") == "img"]
    output = tmp_path / f"{image}.out"
    subprocess.run(
        ["bash", "-e", "-c", script.replace("${{ matrix.image }}", image)],
        env={"PATH": "/usr/bin:/bin", "GITHUB_OUTPUT": str(output)},
        check=True,
    )
    return dict(
        line.split("=", 1) for line in output.read_text().splitlines() if "=" in line
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
@pytest.mark.parametrize("image", ["so", "fsp", "bff", "io", "leds", "hmi"])
def test_ci_puts_index_annotations_only_on_a_multi_platform_image(tmp_path, image):
    # BuildKit refuses index annotations on a single-platform export.
    outputs = _img_outputs(tmp_path, image)
    multi = "," in outputs["platforms"]
    assert outputs["annotation_levels"] == ("manifest,index" if multi else "manifest")


def test_ci_builds_every_image_for_amd64_and_arm64(tmp_path):
    # Decision 0047: a pushed image replaces latest, so each must keep arm64.
    platforms = {
        image: _img_outputs(tmp_path, image)["platforms"]
        for image in ["so", "fsp", "bff", "io", "leds", "hmi"]
    }
    assert set(platforms.values()) == {"linux/amd64,linux/arm64"}
