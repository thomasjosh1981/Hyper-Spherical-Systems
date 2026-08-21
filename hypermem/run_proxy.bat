@echo off
title HyperMem Universal Proxy Server (Port 8765)
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python -m hypermem.cli run
pause
