@echo off
setlocal enabledelayedexpansion
title HyperSpherical Uninstaller - tesseract_engine
cd /d "%~dp0"

echo ======================================================================
echo  HyperSpherical Modular Uninstaller: tesseract_engine
echo ======================================================================
echo.

echo [1] Removing Python package:
python -m pip uninstall -y tesseract_engine

set "CONFIG_FILE=%LOCALAPPDATA%\HyperSpherical\install_root.txt"
if exist "%CONFIG_FILE%" (
    set /p HYPES_ROOT=<"%CONFIG_FILE%"
    set "TARGET_DIR=!HYPES_ROOT!\modules\tesseract_engine"
    if exist "!TARGET_DIR!" (
        echo [2] Removing module files from: !TARGET_DIR!
        rmdir /s /q "!TARGET_DIR!" >nul 2>&1
    )
)

echo.
echo [SUCCESS] tesseract_engine uninstalled cleanly.
pause
