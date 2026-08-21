@echo off
title Installing HyperSpherical Synthuron Context Engine
cd /d "%~dp0"
echo ======================================================================
echo  Installing HyperSpherical Synthuron Context Engine Module
echo ======================================================================
python -m pip install -e .
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] synthuron_context module installed successfully!
) else (
    echo.
    echo [ERROR] Installation failed. Please ensure Python is on your PATH.
)
pause
