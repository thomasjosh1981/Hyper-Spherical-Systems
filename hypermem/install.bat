@echo off
title Installing HyperMem Universal Proxy & Memory Orchestrator
cd /d "%~dp0"
echo ======================================================================
echo  Installing HyperMem Module
echo ======================================================================
python -m pip install -e .
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] hypermem module installed successfully!
) else (
    echo.
    echo [ERROR] Installation failed. Please ensure Python is on your PATH.
)
pause
