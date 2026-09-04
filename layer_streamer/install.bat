@echo off
setlocal enabledelayedexpansion
title HyperSpherical Installer - layer_streamer
cd /d "%~dp0"

echo ======================================================================
echo  HyperSpherical Modular Installer: layer_streamer
echo ======================================================================
echo.

set "CONFIG_DIR=%LOCALAPPDATA%\HyperSpherical"
set "CONFIG_FILE=%CONFIG_DIR%\install_root.txt"
set "DEFAULT_ROOT=%LOCALAPPDATA%\HyperSpherical"

if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"

if exist "%CONFIG_FILE%" (
    set /p HYPES_ROOT=<"%CONFIG_FILE%"
    echo [1] Found existing HyperSpherical installation at:
    echo     !HYPES_ROOT!
    echo.
) else (
    echo [1] Initial HyperSpherical Setup
    echo     Default installation folder: %DEFAULT_ROOT%
    set /p USER_CHOICE="    Press ENTER to accept default, or type custom folder path: "
    if "!USER_CHOICE!"=="" (
        set "HYPES_ROOT=%DEFAULT_ROOT%"
    ) else (
        set "HYPES_ROOT=!USER_CHOICE!"
    )
    echo !HYPES_ROOT!>"%CONFIG_FILE%"
    echo.
)

set "TARGET_DIR=!HYPES_ROOT!\modules\layer_streamer"
echo [2] Installing module to: !TARGET_DIR!
if not exist "!TARGET_DIR!" mkdir "!TARGET_DIR!"
xcopy /E /I /Y /Q "%~dp0*" "!TARGET_DIR!" >nul 2>&1

echo [3] Registering with Python environment...
python -m pip install -e "!TARGET_DIR!"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ======================================================================
    echo  [SUCCESS] layer_streamer installed into:
    echo  !TARGET_DIR!
    echo ======================================================================
) else (
    echo.
    echo  [ERROR] pip install failed. Please verify Python is installed.
)
pause
