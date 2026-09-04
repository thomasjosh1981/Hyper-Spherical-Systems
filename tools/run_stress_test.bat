@echo off
title Advanced Brain & Router Stress Test
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python tools\advanced_brain_stress_test.py --endpoint "http://localhost:11434" --model "gemma4:latest"
pause
