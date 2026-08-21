@echo off
setlocal enabledelayedexpansion
title HyperSpherical Full Uninstaller
cd /d "%~dp0"

echo ======================================================================
echo  HyperSpherical Full Suite Uninstaller
echo ======================================================================
echo.
echo This will uninstall all HyperSpherical modules from Python and disk.
set /p CONFIRM="Are you sure you want to proceed? (Y/N): "
if /i not "!CONFIRM!"=="Y" (
    echo Uninstallation cancelled.
    pause
    exit /b
)

echo.
echo [1] Uninstalling Python packages...
python -m pip uninstall -y layer_streamer issi_compression tesseract_engine synthuron_context hypermem

set "CONFIG_DIR=%LOCALAPPDATA%\HyperSpherical"
set "CONFIG_FILE=%CONFIG_DIR%\install_root.txt"

if exist "%CONFIG_FILE%" (
    set /p HYPES_ROOT=<"%CONFIG_FILE%"
    if exist "!HYPES_ROOT!\modules" (
        echo [2] Removing HyperSpherical module files from: !HYPES_ROOT!\modules
        rmdir /s /q "!HYPES_ROOT!\modules" >nul 2>&1
    )
    rmdir /s /q "%CONFIG_DIR%" >nul 2>&1
)

echo.
echo ======================================================================
echo  [SUCCESS] All HyperSpherical modules have been uninstalled.
echo ======================================================================
pause
