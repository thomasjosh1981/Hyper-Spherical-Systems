@echo off
title HyperSpherical ISSI Compression Tool
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python issi_cli.py
pause
