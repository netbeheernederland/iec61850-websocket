# SPDX-FileCopyrightText: 2026 Netbeheer Nederland
# SPDX-License-Identifier: Apache-2.0
"""The HMI container's 40-rti-config.sh: /config.js and nginx's error log.

It runs at container start and writes window.RTI_CONFIG from BFF_HOST,
BFF_PORT and LOG_LEVEL, and nginx's error log level from LOG_LEVEL
(decision 0014, spec 0008). The error log is set at main level in
nginx.conf, from the image's copy kept on the first start.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "examples" / "rti-demo" / "modules" / "hmi" / "docker" / "40-rti-config.sh"
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh"),
]


# The nginx image's nginx.conf, cut down; the error_log inside http is ours,
# to show that only the main-level one changes.
NGINX_CONF = """user  nginx;
worker_processes  auto;

error_log  /var/log/nginx/error.log notice;
pid        /run/nginx.pid;

http {
    error_log /var/log/nginx/http.log warn;
    include /etc/nginx/conf.d/*.conf;
}
"""


def _main_error_log(nginx_conf: str) -> str:
    return next(
        line for line in nginx_conf.splitlines() if line.startswith("error_log")
    )


def _run(tmp_path: Path, **env: str) -> tuple[str, str]:
    config_js = tmp_path / "config.js"
    nginx_conf = tmp_path / "nginx.conf"
    if not nginx_conf.exists():
        nginx_conf.write_text(NGINX_CONF)
    subprocess.run(
        ["sh", str(SCRIPT)],
        env={
            "PATH": os.environ["PATH"],
            "RTI_CONFIG_JS": str(config_js),
            "RTI_NGINX_CONF": str(nginx_conf),
            **env,
        },
        check=True,
        capture_output=True,
    )
    return config_js.read_text(), nginx_conf.read_text()


def test_nothing_set_writes_an_empty_config_and_leaves_nginx_as_it_is(tmp_path):
    config_js, nginx_conf = _run(tmp_path)
    assert config_js == "window.RTI_CONFIG = {  };\n"
    assert nginx_conf == NGINX_CONF


def test_bff_address_and_log_level(tmp_path):
    config_js, _ = _run(
        tmp_path, BFF_HOST="192.168.100.10", BFF_PORT="3000", LOG_LEVEL="debug"
    )
    assert config_js == (
        'window.RTI_CONFIG = { bffHost: "192.168.100.10", bffPort: "3000", logLevel: "debug" };\n'
    )


def test_empty_log_level_is_left_out(tmp_path):
    config_js, nginx_conf = _run(tmp_path, BFF_HOST="bff", LOG_LEVEL="")
    assert config_js == 'window.RTI_CONFIG = { bffHost: "bff" };\n'
    assert nginx_conf == NGINX_CONF


def test_log_level_is_escaped_as_bff_host_is(tmp_path):
    config_js, _ = _run(tmp_path, LOG_LEVEL='de"bug\\')
    assert config_js == 'window.RTI_CONFIG = { logLevel: "de\\"bug\\\\" };\n'


@pytest.mark.parametrize(
    ("log_level", "nginx"),
    [
        ("debug", "info"),
        ("TRACE", "info"),
        ("info", "notice"),
        ("warning", "warn"),
        ("error", "error"),
        ("critical", "error"),
        ("10", "info"),
        ("30", "warn"),
        ("50", "error"),
        ("loud", "notice"),
    ],
)
def test_nginx_error_log_follows_log_level(tmp_path, log_level, nginx):
    _, nginx_conf = _run(tmp_path, LOG_LEVEL=log_level)
    assert _main_error_log(nginx_conf) == f"error_log /var/log/nginx/error.log {nginx};"
    assert (
        NGINX_CONF.replace(
            "error_log  /var/log/nginx/error.log notice;",
            f"error_log /var/log/nginx/error.log {nginx};",
        )
        == nginx_conf
    )


def test_each_start_begins_from_the_image_nginx_conf(tmp_path):
    _run(tmp_path, LOG_LEVEL="debug")
    _, nginx_conf = _run(tmp_path, LOG_LEVEL="error")
    assert _main_error_log(nginx_conf) == "error_log /var/log/nginx/error.log error;"
    assert nginx_conf.count("error_log /var/log/nginx/error.log") == 1


def test_unsetting_log_level_restores_the_image_nginx_conf(tmp_path):
    _run(tmp_path, LOG_LEVEL="debug")
    _, nginx_conf = _run(tmp_path)
    assert nginx_conf == NGINX_CONF


def test_a_nginx_conf_without_a_main_error_log_gets_one(tmp_path):
    (tmp_path / "nginx.conf").write_text("worker_processes  auto;\nhttp {\n}\n")
    _, nginx_conf = _run(tmp_path, LOG_LEVEL="warning")
    assert nginx_conf == (
        "worker_processes  auto;\nhttp {\n}\nerror_log /var/log/nginx/error.log warn;\n"
    )
