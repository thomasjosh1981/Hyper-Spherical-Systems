@echo off
title Pirate Llama Universal Proxy & Model Aggregator
cd /d "%~dp0"
echo =====================================================================
echo    🏴‍☠️ PIRATE LLAMA — Universal Model Aggregator & Dynamic Router
echo    Built on llama.cpp | Port 8000 | Native GGUF & SFS Container Host
echo =====================================================================
echo.
set "PY313=C:\Users\twist\AppData\Local\Programs\Python\Python313\python.exe"
if exist "%PY313%" (
    "%PY313%" gui\server.py
) else (
    python gui\server.py
)
pause
