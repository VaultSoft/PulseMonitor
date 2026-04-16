@echo off
setlocal
title PulseMonitor — Uninstall

echo.
echo  ╔═══════════════════════════════════════════════════════════╗
echo  ║        PulseMonitor — Uninstall                           ║
echo  ╚═══════════════════════════════════════════════════════════╝
echo.

set /p CONFIRM="  Remove PulseMonitor? [y/N]: "
if /i not "%CONFIRM%"=="y" ( echo  Cancelled. & pause & exit /b 0 )

set "INSTALL_DIR=%LOCALAPPDATA%\PulseMonitor"

:: ── Kill running instance ─────────────────────────────────────────
taskkill /IM PulseMonitor.exe /F >nul 2>&1

:: ── Remove shortcuts ──────────────────────────────────────────────
del /F /Q "%USERPROFILE%\Desktop\PulseMonitor.lnk" >nul 2>&1
rd /S /Q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\PulseMonitor" >nul 2>&1

:: ── Remove registry key ───────────────────────────────────────────
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\PulseMonitor" /f >nul 2>&1

:: ── Remove install directory (after a brief delay to ensure exe is released) ─
timeout /T 1 /NOBREAK >nul
rd /S /Q "%INSTALL_DIR%" >nul 2>&1
if exist "%INSTALL_DIR%" (
    echo  [WARN] Could not fully remove %INSTALL_DIR%
    echo  You can delete it manually after restarting.
) else (
    echo  PulseMonitor has been removed.
)

echo.
pause
