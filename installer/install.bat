@echo off
setlocal enabledelayedexpansion
title PulseMonitor Setup

echo.
echo  ============================================================
echo   PulseMonitor v1.3.0  --  Setup
echo   Professional PC Health Monitor
echo  ============================================================
echo.

:: ── Resolve paths ──────────────────────────────────────────────────
set "SRC=%~dp0"
:: Strip trailing backslash for robocopy compatibility
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
set "INSTALL_DIR=%LOCALAPPDATA%\PulseMonitor"
set "EXE_SRC=%SRC%\PulseMonitor.exe"

echo  Source folder  : %SRC%
echo  Install target : %INSTALL_DIR%
echo  Exe to verify  : %EXE_SRC%
echo.

:: ── Check source exe exists ────────────────────────────────────────
echo  [1/5] Verifying source files...
if not exist "%EXE_SRC%" (
    echo.
    echo  [ERROR] PulseMonitor.exe was not found at:
    echo          %EXE_SRC%
    echo.
    echo  Make sure you extracted the full ZIP before running install.bat
    echo  and that install.bat is in the same folder as PulseMonitor.exe.
    echo.
    pause
    exit /b 1
)
echo         OK - PulseMonitor.exe found.
echo.

:: ── Create install directory ───────────────────────────────────────
echo  [2/5] Creating install directory...
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
    if errorlevel 1 (
        echo  [ERROR] Could not create directory: %INSTALL_DIR%
        echo  Check that you have write permission to %LOCALAPPDATA%
        echo.
        pause
        exit /b 1
    )
    echo         Created: %INSTALL_DIR%
) else (
    echo         Already exists: %INSTALL_DIR%
)
echo.

:: ── Copy all files ─────────────────────────────────────────────────
echo  [3/5] Copying files (this may take a moment)...
robocopy "%SRC%" "%INSTALL_DIR%" /E /NFL /NDL /NJH /NJS /nc /ns /np ^
    /XF "install.bat" "uninstall.bat"
set "RCE=%errorlevel%"
if %RCE% GEQ 8 (
    echo.
    echo  [ERROR] File copy failed. Robocopy exit code: %RCE%
    echo  Common causes:
    echo    - Destination is read-only or locked
    echo    - PulseMonitor.exe is already running (close it first)
    echo    - Antivirus is blocking the copy
    echo.
    pause
    exit /b 1
)
echo         Files copied successfully (robocopy code %RCE% = OK).
echo.

:: ── Copy uninstaller ───────────────────────────────────────────────
copy /Y "%~dp0uninstall.bat" "%INSTALL_DIR%\uninstall.bat" >nul 2>&1

:: ── Desktop shortcut ───────────────────────────────────────────────
echo  [4/5] Creating shortcuts...
powershell -NoProfile -Command ^
    "$ws = New-Object -COM WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\PulseMonitor.lnk'); $s.TargetPath = '%INSTALL_DIR%\PulseMonitor.exe'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Description = 'PulseMonitor - PC Health Monitor'; $s.Save()"
if errorlevel 1 (
    echo  [WARN] Desktop shortcut creation failed - continuing anyway.
) else (
    echo         Desktop shortcut created.
)

:: ── Start Menu shortcut ────────────────────────────────────────────
set "SM_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\PulseMonitor"
if not exist "%SM_DIR%" mkdir "%SM_DIR%"
powershell -NoProfile -Command ^
    "$ws = New-Object -COM WScript.Shell; $s = $ws.CreateShortcut('%SM_DIR%\PulseMonitor.lnk'); $s.TargetPath = '%INSTALL_DIR%\PulseMonitor.exe'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Description = 'PulseMonitor - PC Health Monitor'; $s.Save()"
powershell -NoProfile -Command ^
    "$ws = New-Object -COM WScript.Shell; $s = $ws.CreateShortcut('%SM_DIR%\Uninstall PulseMonitor.lnk'); $s.TargetPath = '%INSTALL_DIR%\uninstall.bat'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Save()"
echo         Start Menu entry created.
echo.

:: ── Registry (Add/Remove Programs) ────────────────────────────────
echo  [5/5] Registering with Windows (Add/Remove Programs)...
set "REGKEY=HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\PulseMonitor"
reg add "%REGKEY%" /v "DisplayName"     /t REG_SZ    /d "PulseMonitor"                        /f >nul
reg add "%REGKEY%" /v "DisplayVersion"  /t REG_SZ    /d "1.3.0"                               /f >nul
reg add "%REGKEY%" /v "Publisher"       /t REG_SZ    /d "PulseMonitor"                        /f >nul
reg add "%REGKEY%" /v "InstallLocation" /t REG_SZ    /d "%INSTALL_DIR%"                       /f >nul
reg add "%REGKEY%" /v "UninstallString" /t REG_SZ    /d "\"%INSTALL_DIR%\uninstall.bat\""     /f >nul
reg add "%REGKEY%" /v "NoModify"        /t REG_DWORD /d 1                                     /f >nul
reg add "%REGKEY%" /v "NoRepair"        /t REG_DWORD /d 1                                     /f >nul
echo         Registered in Add/Remove Programs.
echo.

:: ── Done ───────────────────────────────────────────────────────────
echo  ============================================================
echo   Installation complete!
echo.
echo    Location : %INSTALL_DIR%
echo    Shortcut : Desktop and Start Menu
echo.
echo   NOTE: CPU temperature monitoring on AMD systems requires
echo   running PulseMonitor as administrator.
echo  ============================================================
echo.

set /p "LAUNCH=  Launch PulseMonitor now? [Y/n]: "
if /i not "!LAUNCH!"=="n" (
    echo  Launching PulseMonitor...
    start "" "%INSTALL_DIR%\PulseMonitor.exe"
)

echo.
echo  Press any key to close this window.
pause >nul
