@echo off
title Installing HyperSpherical Tesseract 5-File Stripe Vault
cd /d "%~dp0"
echo ======================================================================
echo  Installing HyperSpherical Tesseract Engine Module
echo ======================================================================
python -m pip install -e .
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] tesseract_engine module installed successfully!
) else (
    echo.
    echo [ERROR] Installation failed. Please ensure Python is on your PATH.
)
pause
