@echo off
title HyperMem Zero-Config Auto-Interceptor (Port Displacer & MITM Hook)
cd /d "%~dp0"
echo ======================================================================
echo  HYPERMEM ZERO-CONFIG UNIVERSAL AI AUTO-INTERCEPTOR
echo ======================================================================
echo  [+] Scanning local AI ports (11434 Ollama, 1234 LM Studio, 8080 Llama.cpp, etc.)
echo  [+] Auto-detecting AI app traffic (Cursor, VS Code, LangChain, Copilot, etc.)
echo  [+] Prompting 1-Click Consent on new app detection
echo  [+] Applying transparent M2M / ISSI 10x Token Compression
echo ======================================================================

set PYTHONIOENCODING=utf-8
python -m hypermem.auto_interceptor
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Auto-interceptor exited with error code %ERRORLEVEL%.
    pause
)
