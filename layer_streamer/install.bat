@echo off
title Installing HyperSpherical Layer Streamer (Zero-CUDA Engine)
cd /d "%~dp0"
echo ======================================================================
echo  Installing HyperSpherical Layer Streamer Module
echo ======================================================================
python -m pip install -e .
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] layer_streamer module installed successfully!
) else (
    echo.
    echo [ERROR] Installation failed. Please ensure Python is on your PATH.
)
pause
