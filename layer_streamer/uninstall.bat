@echo off
setlocal enabledelayedexpansion
title HyperSpherical Uninstaller - layer_streamer
cd /d "%~dp0"

echo ======================================================================
echo  HyperSpherical Modular Uninstaller: layer_streamer
echo ======================================================================
echo.

echo [1] Removing Python package:
python -m pip uninstall -y layer_streamer

set "CONFIG_FILE=%LOCALAPPDATA%\HyperSpherical\install_root.txt"
if exist "%CONFIG_FILE%" (
    set /p HYPES_ROOT=<"%CONFIG_FILE%"
    set "TARGET_DIR=!HYPES_ROOT!\modules\layer_streamer"
    if exist "!TARGET_DIR!" (
        echo [2] Removing module files from: !TARGET_DIR!
        rmdir /s /q "!TARGET_DIR!" >nul 2>&1
    )
)

echo.
echo [SUCCESS] layer_streamer uninstalled cleanly.
pause
