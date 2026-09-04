@echo off
title Hyper-Spherical Systems — Golden Candy Spinner (GCS v6.0)
cd /d "%~dp0"
set PY313="C:\Users\twist\AppData\Local\Programs\Python\Python313\python.exe"
if exist %PY313% (
    %PY313% launch_hypes.py --spinner
) else (
    python launch_hypes.py --spinner
)
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to start Golden Candy Spinner.
    pause
)
