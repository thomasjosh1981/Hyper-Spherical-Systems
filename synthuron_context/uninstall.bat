@echo off
setlocal enabledelayedexpansion
title HyperSpherical Uninstaller - synthuron_context
cd /d "%~dp0"

echo ======================================================================
echo  HyperSpherical Modular Uninstaller: synthuron_context
echo ======================================================================
echo.

echo [1] Removing Python package:
python -m pip uninstall -y synthuron_context

set "CONFIG_FILE=%LOCALAPPDATA%\HyperSpherical\install_root.txt"
if exist "%CONFIG_FILE%" (
    set /p HYPES_ROOT=<"%CONFIG_FILE%"
    set "TARGET_DIR=!HYPES_ROOT!\modules\synthuron_context"
    if exist "!TARGET_DIR!" (
        echo [2] Removing module files from: !TARGET_DIR!
        rmdir /s /q "!TARGET_DIR!" >nul 2>&1
    )
)

echo.
echo [SUCCESS] synthuron_context uninstalled cleanly.
pause
