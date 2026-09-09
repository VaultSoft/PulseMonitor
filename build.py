#!/usr/bin/env python3
"""Build and package the PulseMonitor portable Windows bundle."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from app_metadata import APP_NAME, read_version

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
SPEC_FILE = ROOT / "PulseMonitor.spec"

BLOCKED_PATH_MARKERS = (
    "\\.cache\\codex-runtimes\\",
    "\\codex-runtimes\\",
    "\\poppler",
    "\\libheif",
)


def portable_zip_name(version: str | None = None) -> str:
    return f"{APP_NAME}_v{version or read_version()}_Portable.zip"


def portable_zip_path(root: Path = ROOT, version: str | None = None) -> Path:
    return root / "dist" / portable_zip_name(version)


def _normalized_path(path: Path | str) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _default_allowed_path_roots(environ: dict[str, str] | None = None) -> list[Path]:
    env = environ or os.environ
    python_dir = Path(sys.executable).resolve().parent
    system_root = Path(env.get("SystemRoot", r"C:\Windows"))
    return [
        python_dir,
        python_dir / "Scripts",
        system_root,
        system_root / "System32",
        system_root / "System32" / "Wbem",
        system_root / "System32" / "WindowsPowerShell" / "v1.0",
    ]


def _is_under_allowed_root(entry: str, allowed_roots: list[Path]) -> bool:
    normalized = _normalized_path(entry)
    for root in allowed_roots:
        root_normalized = _normalized_path(root)
        if normalized == root_normalized or normalized.startswith(root_normalized + os.sep):
            return True
    return False


def sanitized_path_entries(
    path_value: str,
    allowed_roots: list[Path] | None = None,
) -> list[str]:
    roots = allowed_roots or _default_allowed_path_roots()
    entries: list[str] = []
    for entry in path_value.split(os.pathsep):
        if not entry:
            continue
        normalized = entry.replace("/", "\\").lower()
        if any(marker in normalized for marker in BLOCKED_PATH_MARKERS):
            continue
        if _is_under_allowed_root(entry, roots):
            entries.append(entry)
    return entries


def build_environment(environ: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(environ or os.environ)
    env["PYTHONNOUSERSITE"] = "1"
    env["PATH"] = os.pathsep.join(
        sanitized_path_entries(env.get("PATH", ""), _default_allowed_path_roots(env))
    )
    return env


def _assert_within_repo(path: Path, root: Path = ROOT) -> Path:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
        raise ValueError(f"Refusing to remove path outside build output scope: {path}")
    return resolved_path


def clean_build_outputs(root: Path = ROOT) -> None:
    for path in (root / "build", root / "dist"):
        if path.exists():
            shutil.rmtree(_assert_within_repo(path, root))


def run_pyinstaller(root: Path = ROOT) -> None:
    cmd = [
        sys.executable,
        "-B",
        "-m",
        "PyInstaller",
        str(root / "PulseMonitor.spec"),
        "--noconfirm",
        "--clean",
    ]
    subprocess.run(cmd, cwd=root, env=build_environment(), check=True)


def write_readme(app_dir: Path, version: str) -> None:
    readme = app_dir / "README.txt"
    readme.write_text(
        "\n".join(
            [
                f"{APP_NAME} v{version}",
                "=" * (len(APP_NAME) + len(version) + 2),
                "",
                "Portable application - no installation required.",
                "",
                "To run:",
                f"  Double-click {APP_NAME}.exe",
                "",
                "To uninstall:",
                "  Delete this folder. No registry entries are written.",
                "",
                "Data stored at: %APPDATA%\\PulseMonitor\\",
                "  config.json  - settings",
                "  history.db   - performance history (SQLite)",
                "",
                "VaultSoft - https://ko-fi.com/vaultsoft",
                "",
            ]
        ),
        encoding="utf-8",
    )


def copy_version_file(app_dir: Path, root: Path = ROOT) -> None:
    shutil.copy2(root / "VERSION", app_dir / "VERSION")


def create_portable_zip(app_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(app_dir.rglob("*")):
            if path.is_file():
                archive.write(path, Path(APP_NAME) / path.relative_to(app_dir))


def find_root_level_icu_dlls(app_dir: Path) -> list[Path]:
    return sorted(path for path in app_dir.glob("icu*.dll") if path.is_file())


def find_forbidden_bundle_entries(app_dir: Path) -> list[Path]:
    forbidden_names = {
        "hidsharp.dll",
        "librehardwaremonitorlib.dll",
        "stdlib_pyc",
        "encodings_pyc",
    }
    return sorted(path for path in app_dir.rglob("*") if path.name.lower() in forbidden_names)


def validate_bundle(app_dir: Path) -> None:
    exe = app_dir / f"{APP_NAME}.exe"
    if not exe.exists():
        raise FileNotFoundError(f"Missing packaged executable: {exe}")
    if not (app_dir / "_internal").is_dir():
        raise FileNotFoundError(f"Missing PyInstaller dependency directory: {app_dir / '_internal'}")

    root_icu = find_root_level_icu_dlls(app_dir)
    if root_icu:
        found = ", ".join(path.name for path in root_icu)
        raise RuntimeError(f"Root-level ICU DLL leakage detected: {found}")

    forbidden = find_forbidden_bundle_entries(app_dir)
    if forbidden:
        found = ", ".join(str(path.relative_to(app_dir)) for path in forbidden)
        raise RuntimeError(f"Forbidden bundled entries detected: {found}")


def build(root: Path = ROOT) -> Path:
    version = read_version(root / "VERSION")
    clean_build_outputs(root)
    run_pyinstaller(root)

    app_dir = root / "dist" / APP_NAME
    write_readme(app_dir, version)
    copy_version_file(app_dir, root)
    validate_bundle(app_dir)

    zip_path = portable_zip_path(root, version)
    create_portable_zip(app_dir, zip_path)
    return zip_path


def main() -> int:
    try:
        zip_path = build()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    print(f"Portable ZIP: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
