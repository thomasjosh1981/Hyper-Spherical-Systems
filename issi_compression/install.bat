@echo off
title Installing HyperSpherical ISSI Compression Module
cd /d "%~dp0"
echo ======================================================================
echo  Installing HyperSpherical ISSI Compression Module
echo ======================================================================
python -m pip install -e .
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] issi_compression module installed successfully!
) else (
    echo.
    echo [ERROR] Installation failed. Please ensure Python is on your PATH.
)
pause
