@echo off
setlocal
title PulseMonitor Build

echo.
echo  ============================================================
echo   PulseMonitor portable build
echo  ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

python -B "%~dp0build.py"
if errorlevel 1 (
    echo.
    echo  [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo  Build complete.
pause
