from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app_metadata
import build


class ReleaseReliabilityTests(unittest.TestCase):
    def test_version_file_is_authoritative(self) -> None:
        version = build.read_version(ROOT / "VERSION")
        self.assertEqual(version, app_metadata.APP_VERSION)
        self.assertEqual(build.portable_zip_name(version), f"PulseMonitor_v{version}_Portable.zip")

    def test_no_stale_version_in_installer(self) -> None:
        installer = (ROOT / "installer" / "install.bat").read_text(encoding="utf-8")
        self.assertNotIn("1.3.0", installer)
        self.assertIn("APP_VERSION", installer)
        self.assertIn("VERSION", installer)

    def test_spec_is_repo_relative_and_has_no_bytecode_fallback(self) -> None:
        spec = (ROOT / "PulseMonitor.spec").read_text(encoding="utf-8")
        self.assertNotIn(r"C:\Users\Josh", spec)
        self.assertNotIn("_missing_stdlib_pycs", spec)
        self.assertNotIn("stdlib_pyc", spec)
        self.assertNotIn("encodings_pyc", spec)
        self.assertIn('str(ROOT / "pulsemonitor.py")', spec)
        self.assertIn('str(ROOT / "VERSION")', spec)

    def test_build_script_filters_codex_runtime_path_entries(self) -> None:
        original = os.pathsep.join(
            [
                r"C:\Windows\System32",
                r"C:\Users\Josh\.cache\codex-runtimes\poppler\bin",
                r"C:\Tools\Python311",
                r"C:\RandomDlls",
            ]
        )
        filtered = build.sanitized_path_entries(
            original,
            [Path(r"C:\Windows"), Path(r"C:\Tools\Python311")],
        )
        self.assertEqual(filtered, [r"C:\Windows\System32", r"C:\Tools\Python311"])

    def test_build_script_refuses_to_clean_repo_root(self) -> None:
        with self.assertRaises(ValueError):
            build._assert_within_repo(ROOT, ROOT)

    def test_bundle_audit_rejects_root_icu_and_lhm_dlls(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            app_dir = Path(td) / "PulseMonitor"
            internal = app_dir / "_internal"
            internal.mkdir(parents=True)
            (app_dir / "PulseMonitor.exe").write_bytes(b"placeholder")
            (app_dir / "icudt78.dll").write_bytes(b"unexpected")

            with self.assertRaisesRegex(RuntimeError, "Root-level ICU"):
                build.validate_bundle(app_dir)

            (app_dir / "icudt78.dll").unlink()
            (internal / "LibreHardwareMonitorLib.dll").write_bytes(b"unexpected")
            with self.assertRaisesRegex(RuntimeError, "Forbidden bundled"):
                build.validate_bundle(app_dir)

    def test_bundle_audit_accepts_normal_onedir_shape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            app_dir = Path(td) / "PulseMonitor"
            internal = app_dir / "_internal"
            internal.mkdir(parents=True)
            (app_dir / "PulseMonitor.exe").write_bytes(b"placeholder")
            (internal / "icudt78.dll").write_bytes(b"qt dependency")

            build.validate_bundle(app_dir)

    def test_portable_zip_contains_app_folder(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app_dir = root / "dist" / "PulseMonitor"
            internal = app_dir / "_internal"
            internal.mkdir(parents=True)
            (app_dir / "PulseMonitor.exe").write_bytes(b"placeholder")
            (app_dir / "README.txt").write_text("readme", encoding="utf-8")
            (internal / "dependency.dll").write_bytes(b"dll")

            zip_path = root / "dist" / "PulseMonitor_v1.1.0_Portable.zip"
            build.create_portable_zip(app_dir, zip_path)

            with zipfile.ZipFile(zip_path) as archive:
                names = set(archive.namelist())
            self.assertIn("PulseMonitor/PulseMonitor.exe", names)
            self.assertIn("PulseMonitor/README.txt", names)
            self.assertIn("PulseMonitor/_internal/dependency.dll", names)

    def test_lhm_folder_is_not_tracked_or_referenced_for_bundling(self) -> None:
        listed = subprocess.run(
            ["git", "-c", "safe.directory=C:/Users/Josh/PulseMonitor", "ls-files", "lhm", "lhm/*"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        self.assertEqual(listed.stdout.strip(), "")
        spec = (ROOT / "PulseMonitor.spec").read_text(encoding="utf-8")
        self.assertNotIn("lhm", spec.lower())
        self.assertNotIn("HidSharp", spec)

    def test_github_actions_build_verifies_package_without_releasing(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
        self.assertIn("python -B build.py", workflow)
        self.assertIn("actions/upload-artifact", workflow)
        self.assertNotIn("softprops/action-gh-release", workflow)
        self.assertNotIn("gh release", workflow.lower())
        self.assertNotIn("git tag", workflow.lower())

    def test_packaged_smoke_exit_is_environment_only(self) -> None:
        source = (ROOT / "pulsemonitor.py").read_text(encoding="utf-8")
        self.assertIn("PULSEMONITOR_SMOKE_EXIT_MS", source)
        self.assertIn("QTimer.singleShot", source)


if __name__ == "__main__":
    unittest.main()
