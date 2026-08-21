@echo off
:: ============================================================================
:: HyperMem Windows System Service Installer (Requires Administrator Privileges)
:: ============================================================================
NET SESSION >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [!] Requesting Administrator Privileges...
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

echo ============================================================================
echo   HYPERMEM UNIVERSAL SYSTEM SERVICE INSTALLER
echo   [Installing HyperMem as an Autonomous Background Windows Service]
echo ============================================================================

cd /d "%~dp0"

echo [*] Checking Python environment...
where python >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found on system PATH. Please ensure Python is installed.
    pause
    exit /b
)

echo [*] Installing HyperMem package in standalone mode...
python -m pip install -e . >nul 2>&1

echo [*] Registering HyperMem Windows Background Scheduled Daemon...
schtasks /create /tn "HyperMemUniversalProxy" /tr "python \"%~dp0hypermem\cli.py\" --serve --port 8765" /sc onstart /ru SYSTEM /f >nul 2>&1

echo [*] Starting HyperMem Universal Proxy Service immediately on Port 8765...
start "" /b python "%~dp0hypermem\cli.py" --serve --port 8765

echo.
echo ============================================================================
echo [SUCCESS] HyperMem is now installed and running as a Windows System Service!
echo   ? Local Proxy Gateway: http://127.0.0.1:8765
echo   ? Live Control Center: http://127.0.0.1:8765/dashboard
echo ============================================================================
echo.
pause
