"""Shared application metadata for PulseMonitor."""
from __future__ import annotations

import re
import sys
from pathlib import Path

APP_NAME = "PulseMonitor"
GITHUB_OWNER = "VaultSoft"
GITHUB_REPO = "PulseMonitor"

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def app_base_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def read_version(version_file: Path | None = None) -> str:
    path = version_file or app_base_dir() / "VERSION"
    version = path.read_text(encoding="utf-8").strip()
    if not _VERSION_RE.fullmatch(version):
        raise ValueError(f"Invalid PulseMonitor version in {path}: {version!r}")
    return version


APP_VERSION = read_version()
