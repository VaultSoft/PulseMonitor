@echo off
setlocal enabledelayedexpansion
title PulseMonitor — Build Installer

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║  PulseMonitor v1.1.0 — Build Script                      ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

:: ── Check Python ─────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Install Python 3.10+ from https://python.org
    pause & exit /b 1
)

:: ── Install/upgrade build dependencies ───────────────────────────
echo  [1/4] Installing build dependencies...
pip install --quiet --upgrade pyinstaller PyQt6 pyqtgraph psutil GPUtil wmi
if errorlevel 1 ( echo  [ERROR] pip install failed. & pause & exit /b 1 )

:: ── Build with PyInstaller ────────────────────────────────────────
echo  [2/4] Building with PyInstaller (this takes ~60-90 seconds)...
pyinstaller PulseMonitor.spec --noconfirm --clean
if errorlevel 1 ( echo  [ERROR] PyInstaller build failed. & pause & exit /b 1 )

:: ── Verify output ─────────────────────────────────────────────────
if not exist "dist\PulseMonitor\PulseMonitor.exe" (
    echo  [ERROR] Build output not found at dist\PulseMonitor\PulseMonitor.exe
    pause & exit /b 1
)

:: ── Write README.txt ──────────────────────────────────────────────
echo  [3/4] Creating portable ZIP...
(
echo PulseMonitor v1.1.0
echo ════════════════════
echo.
echo Portable application — no installation required.
echo.
echo To run:
echo   Double-click PulseMonitor.exe
echo.
echo To uninstall:
echo   Delete this folder. No registry entries are written.
echo.
echo Data stored at: %%APPDATA%%\PulseMonitor\
echo   config.json  — settings
echo   history.db   — performance history ^(SQLite^)
echo.
echo VaultSoft — https://ko-fi.com/vaultsoft
) > "dist\PulseMonitor\README.txt"

:: ── Package: only PulseMonitor.exe, _internal\, README.txt ───────
if exist "PulseMonitor_v1.1.0_Portable.zip" del "PulseMonitor_v1.1.0_Portable.zip"

powershell -NoProfile -Command ^
    "$src = 'dist\PulseMonitor'; $zip = 'PulseMonitor_v1.1.0_Portable.zip';" ^
    "Add-Type -AssemblyName System.IO.Compression.FileSystem;" ^
    "$z = [System.IO.Compression.ZipFile]::Open($zip, 'Create');" ^
    "function Add-Entry($arc, $disk, $entry) {" ^
    "  [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($arc, $disk, $entry) | Out-Null };" ^
    "Add-Entry $z \"$src\PulseMonitor.exe\" 'PulseMonitor\PulseMonitor.exe';" ^
    "Add-Entry $z \"$src\README.txt\" 'PulseMonitor\README.txt';" ^
    "Get-ChildItem -Recurse \"$src\_internal\" | Where-Object { -not $_.PSIsContainer } | ForEach-Object {" ^
    "  $rel = $_.FullName.Substring((Resolve-Path $src).Path.Length + 1).Replace('\','/');" ^
    "  Add-Entry $z $_.FullName \"PulseMonitor/$rel\" };" ^
    "$z.Dispose()"
if errorlevel 1 ( echo  [ERROR] ZIP creation failed. & pause & exit /b 1 )

echo  [4/4] Done!
echo.
echo  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo  Portable ZIP: PulseMonitor_v1.1.0_Portable.zip
echo   Contents: PulseMonitor.exe  _internal\  README.txt
echo   (No install.bat or uninstall.bat included)
echo  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
pause
